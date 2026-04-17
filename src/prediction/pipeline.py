"""End-to-end prediction pipeline orchestration."""

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.storage import Storage
from src.data.fastf1_client import FastF1Client
from src.data.news_scraper import NewsScraper
from src.data.weather import WeatherClient
from src.nlp.upgrade_analyzer import UpgradeAnalyzer
from src.features.builder import FeatureBuilder, FEATURE_COLUMNS
from src.models.trainer import Trainer
from src.models.bayesian_updater import BayesianUpdater
from src.prediction.simulator import RaceSimulator, estimate_dnf_rates

logger = logging.getLogger(__name__)


class PredictionPipeline:
    """Orchestrates the full prediction flow for a race."""

    def __init__(self, storage: Storage, config: dict = None):
        self.storage = storage
        self.config = config or {}
        self.fastf1 = FastF1Client(
            cache_dir=self.config.get("data", {}).get("cache_dir", "data/cache")
        )
        telemetry_enabled = bool(
            (self.config.get("features") or {}).get("telemetry_enabled", False)
        )
        self.feature_builder = FeatureBuilder(
            storage, telemetry_enabled=telemetry_enabled
        )
        self.trainer = Trainer(
            storage,
            model_dir=self.config.get("model", {}).get("save_dir", "models")
        )
        self.bayesian = BayesianUpdater(storage)

        # Optional components
        self.news_scraper = NewsScraper(
            sources=self.config.get("news_sources")
        )
        self.weather_client = WeatherClient(
            api_key=self.config.get("openweathermap", {}).get("api_key")
        )
        self.upgrade_analyzer = UpgradeAnalyzer(
            endpoint=self.config.get("azure_openai", {}).get("endpoint"),
            api_key=self.config.get("azure_openai", {}).get("api_key"),
            deployment=self.config.get("azure_openai", {}).get("deployment", "gpt-4o"),
        )

    def predict_race(self, year: int, race: str | int,
                      fp_sessions: list[str] = None,
                      skip_news: bool = False,
                      skip_weather: bool = False) -> pd.DataFrame:
        """Generate predictions for a specific race.

        Args:
            year: Season year.
            race: Race name or round number.
            fp_sessions: Specific FP sessions to use (default: all available).
            skip_news: Skip news scraping/analysis.
            skip_weather: Skip weather forecast fetching.

        Returns:
            DataFrame with predicted finishing order and probabilities.
        """
        # Step 1: Resolve race info
        round_num = self._resolve_race(year, race)
        race_info = self.storage.get_race(year, round_num)

        if not race_info:
            # Try to collect race info from FastF1
            logger.info(f"Collecting race info for {year} R{round_num}...")
            self._collect_race_info(year, round_num, race)
            race_info = self.storage.get_race(year, round_num)

        if not race_info:
            raise ValueError(f"Could not find race: {year} '{race}'")

        race_id = race_info["id"]
        race_name = race_info["name"]
        circuit_id = race_info["circuit_id"]
        race_date = race_info.get("date", "")

        logger.info(f"Predicting: {year} {race_name} (Round {round_num})")

        # Step 2: Collect FP data
        if fp_sessions is None:
            fp_sessions = ["FP1", "FP2", "FP3"]

        available_sessions = []
        for sess in fp_sessions:
            existing = self.storage.get_fp_data(race_id, sess)
            if existing.empty:
                logger.info(f"Collecting {sess} data...")
                try:
                    fp_data = self.fastf1.extract_fp_features(year, round_num, sess)
                    for driver_data in fp_data:
                        self.storage.save_fp_session(
                            race_id=race_id,
                            session_type=sess,
                            driver_id=driver_data["driver_id"],
                            driver_name=driver_data["driver_name"],
                            team=driver_data["team"],
                            data=driver_data,
                        )
                    if fp_data:
                        available_sessions.append(sess)
                        logger.info(f"  {sess}: {len(fp_data)} drivers")

                    # Also collect weather
                    weather = self.fastf1.collect_weather(year, round_num, sess)
                    if weather:
                        self.storage.save_weather(race_id, sess, weather)
                except Exception as e:
                    logger.warning(f"Could not collect {sess}: {e}")
            else:
                available_sessions.append(sess)

        if not available_sessions:
            logger.warning("No FP data available — predictions based on historical data only")

        # Step 3: Weather forecast
        race_weather = None
        if not skip_weather and race_info.get("latitude"):
            logger.info("Fetching weather forecast...")
            race_weather = self.weather_client.get_race_weather(
                lat=race_info["latitude"],
                lon=race_info["longitude"],
                race_date=race_date,
            )
            if race_weather:
                self.storage.save_weather(race_id, "R", race_weather)

        # Step 4: News & upgrade analysis
        if not skip_news:
            self._analyze_upgrades(race_id, race_date)

        # Step 5: Get drivers
        drivers = self._get_race_drivers(race_id, year, round_num)
        if not drivers:
            raise ValueError("No driver data available for prediction")

        # Step 6a: Determine grid — use actual if we have it, otherwise
        # predict with the qualifying model so the race model sees a grid
        # feature.
        grid_map = self._resolve_grid(year, round_num, race_id, drivers,
                                        available_sessions, race_weather)

        # Step 6b: Build features with grid injected.
        logger.info("Building feature matrix...")
        features_df = self.feature_builder.build_race_features(
            year, round_num, drivers, available_sessions or None,
            race_weather, grid_map=grid_map,
        )

        if features_df.empty:
            raise ValueError("Failed to build feature matrix")

        # Step 7: Apply Bayesian adjustments for cold-start
        if self.bayesian.state.regulation_year:
            X = features_df[FEATURE_COLUMNS].values
            for i, (_, row) in enumerate(features_df.iterrows()):
                X[i] = self.bayesian.adjust_features(
                    X[i], FEATURE_COLUMNS, row.get("team", "")
                )
            features_df[FEATURE_COLUMNS] = X

        # Step 8: Load models and predict
        self.trainer.load_models()
        X = features_df[FEATURE_COLUMNS].fillna(0.0)

        # Monte Carlo simulator (Phase 3.1)
        sim_cfg = (self.config.get("model") or {}).get("simulator", {}) or {}
        simulator = RaceSimulator(
            n_sims=int(sim_cfg.get("n_sims", 5000)),
            score_noise_sigma=float(sim_cfg.get("score_noise_sigma", 0.25)),
            safety_car_position_shake=float(sim_cfg.get("sc_shake", 0.4)),
        )
        is_wet = int(bool(race_weather and race_weather.get("is_wet")))
        dnf_rates = estimate_dnf_rates(
            self.storage,
            driver_ids=features_df["driver_id"].tolist(),
            circuit_id=circuit_id,
            is_wet=is_wet,
            as_of_date=race_date or None,
        )
        sc_prob = float(features_df["circuit_safety_car_prob"].mean()) \
            if "circuit_safety_car_prob" in features_df.columns else 0.35

        predictions = self.trainer.ensemble.predict(
            X,
            driver_ids=features_df["driver_id"].tolist(),
            driver_names=features_df.get("driver_name", pd.Series()).tolist(),
            teams=features_df.get("team", pd.Series()).tolist(),
            simulator=simulator,
            dnf_rates=dnf_rates,
            sc_probability=sc_prob,
        )

        # Phase 3.2: isotonic calibration of probabilities.
        try:
            from src.models.calibration import ProbabilityCalibrator
            cal_path = Path(self.trainer.model_dir) / "calibrator.joblib"
            if cal_path.exists():
                calibrator = ProbabilityCalibrator()
                calibrator.load(str(cal_path))
                calibrated = calibrator.transform({
                    "win_probability": predictions["win_probability"].values,
                    "podium_probability": predictions["podium_probability"].values,
                    "points_probability": predictions["points_probability"].values,
                })
                for k, v in calibrated.items():
                    predictions[k] = v
        except Exception as e:
            logger.debug(f"Calibration skipped: {e}")

        # Add metadata
        predictions["race_name"] = race_name
        predictions["year"] = year
        predictions["round"] = round_num
        predictions["sessions_used"] = ", ".join(available_sessions)
        predictions["confidence"] = self.bayesian.get_confidence_level()

        # Feature importance (global) for back-compat.
        importance = self.trainer.xgb_model.get_feature_importance(FEATURE_COLUMNS)
        if not importance.empty:
            predictions.attrs["feature_importance"] = importance

        # Phase 5.4: per-driver SHAP explanations.
        try:
            import shap  # noqa: F401
            self._attach_shap(predictions, features_df, X)
        except ImportError:
            logger.debug("shap not installed — skipping per-driver explanations")
        except Exception as e:
            logger.debug(f"SHAP computation skipped: {e}")

        # Raw feature matrix (for per-driver explainability in dashboards)
        predictions.attrs["features_df"] = features_df

        return predictions

    def _resolve_race(self, year: int, race: str | int) -> int:
        """Resolve race name/identifier to round number."""
        if isinstance(race, int):
            return race

        # Try to match by name
        races = self.storage.get_races_for_season(year)
        for r in races:
            if race.lower() in r["name"].lower():
                return r["round"]

        # Try FastF1 schedule
        try:
            schedule = self.fastf1.get_event_schedule(year)
            for _, event in schedule.iterrows():
                if race.lower() in str(event.get("EventName", "")).lower():
                    return int(event["RoundNumber"])
                if race.lower() in str(event.get("Country", "")).lower():
                    return int(event["RoundNumber"])
        except Exception:
            pass

        # Try as integer
        try:
            return int(race)
        except ValueError:
            raise ValueError(f"Could not resolve race: '{race}' for {year}")

    def _collect_race_info(self, year: int, round_num: int,
                            race_name: str | int):
        """Collect and store race info from FastF1."""
        try:
            schedule = self.fastf1.get_event_schedule(year)
            for _, event in schedule.iterrows():
                if int(event["RoundNumber"]) == round_num:
                    self.storage.save_race(
                        year=year,
                        round_num=round_num,
                        name=event.get("EventName", str(race_name)),
                        circuit_id=str(event.get("Location", "")).lower().replace(" ", "_"),
                        date=str(event.get("EventDate", "")),
                        circuit_name=event.get("OfficialEventName", ""),
                        country=event.get("Country", ""),
                        latitude=event.get("Latitude"),
                        longitude=event.get("Longitude"),
                    )
                    return
        except Exception as e:
            logger.warning(f"Could not collect race info: {e}")

    def _get_race_drivers(self, race_id: int, year: int,
                           round_num: int) -> list[dict]:
        """Get list of drivers for a race."""
        # Try FP data first
        fp_data = self.storage.get_fp_data(race_id)
        if not fp_data.empty:
            return fp_data[["driver_id", "driver_name", "team"]].drop_duplicates().to_dict("records")

        # Try season data
        drivers = self.storage.get_all_drivers_for_season(year)
        if drivers:
            return drivers

        # Try previous season
        prev_drivers = self.storage.get_all_drivers_for_season(year - 1)
        return prev_drivers

    def _attach_shap(self, predictions: pd.DataFrame,
                      features_df: pd.DataFrame, X: pd.DataFrame) -> None:
        """Attach a top-3 SHAP attribution dict per driver.

        Stored on predictions.attrs['shap_by_driver'] as
            { driver_id: [(feature_name, shap_value), ...] }
        Uses the XGBoost model because TreeExplainer is fast and stable.
        """
        import shap
        xgb_raw = getattr(self.trainer.xgb_model, "model", None)
        if xgb_raw is None:
            return
        explainer = shap.TreeExplainer(xgb_raw)
        shap_vals = explainer.shap_values(X)

        by_driver: dict[str, list[tuple[str, float]]] = {}
        for idx, driver_id in enumerate(features_df["driver_id"].tolist()):
            row_sv = shap_vals[idx]
            # Sort by absolute magnitude, take top 4.
            order = np.argsort(-np.abs(row_sv))[:4]
            by_driver[driver_id] = [
                (FEATURE_COLUMNS[i], float(row_sv[i])) for i in order
            ]
        predictions.attrs["shap_by_driver"] = by_driver

    def _resolve_grid(self, year: int, round_num: int, race_id: int,
                       drivers: list[dict],
                       available_sessions: list[str] | None,
                       race_weather: dict | None) -> dict[str, int]:
        """Return driver_id -> grid_position map.

        Prefers actual grid from results if quali has already happened,
        falls back to the qualifying model's prediction.
        """
        # Actual grid from stored race results.
        actual = self.storage.get_results(race_id)
        if not actual.empty and "grid_position" in actual.columns:
            real_grid = {
                str(row["driver_id"]): int(row["grid_position"])
                for _, row in actual.iterrows()
                if pd.notna(row["grid_position"]) and int(row["grid_position"]) > 0
            }
            if real_grid:
                logger.info(f"Using actual grid positions for {len(real_grid)} drivers")
                return real_grid

        # Predict grid with the qualifying model.
        try:
            self.trainer.load_models()
            if self.trainer.qual_model.model is None:
                return {}
        except Exception:
            return {}

        features_df = self.feature_builder.build_race_features(
            year, round_num, drivers, available_sessions or None, race_weather,
            grid_map=None,
        )
        if features_df.empty:
            return {}

        quali_feature_cols = [c for c in FEATURE_COLUMNS if c != "predicted_grid_position"]
        X_q = features_df[quali_feature_cols].fillna(0.0)
        try:
            grid_df = self.trainer.qual_model.predict_grid(
                X_q, features_df["driver_id"].tolist()
            )
        except Exception as e:
            logger.warning(f"Qualifying prediction failed, using default grid: {e}")
            return {}

        pred_grid = dict(zip(grid_df["driver_id"], grid_df["predicted_grid_position"]))
        logger.info(f"Predicted grid for {len(pred_grid)} drivers via quali model")
        return pred_grid

    def _analyze_upgrades(self, race_id: int, race_date: str):
        """Scrape and analyze upgrade news for all teams."""
        try:
            logger.info("Scraping upgrade news...")
            all_news = self.news_scraper.collect_all_teams(max_articles_per_team=3)

            for team, articles in all_news.items():
                if not articles:
                    continue

                logger.info(f"  Analyzing {len(articles)} articles for {team}...")
                try:
                    summary = self.upgrade_analyzer.get_team_upgrade_summary(
                        team, articles
                    )

                    # Store upgrade data
                    if summary.get("upgrade_impact_score", 0) != 0:
                        self.storage.save_upgrade(
                            team=team,
                            date=race_date or datetime.now().strftime("%Y-%m-%d"),
                            component=summary.get("upgrade_component", "none"),
                            impact_score=summary.get("upgrade_impact_score", 0),
                            confidence=summary.get("upgrade_confidence", "rumor"),
                            sentiment=summary.get("upgrade_sentiment", 0),
                            summary=str(summary.get("details", "")),
                            source_url="",
                            source_name="aggregated",
                            race_id=race_id,
                        )
                except Exception as e:
                    logger.warning(f"  NLP analysis failed for {team}: {e}")

        except Exception as e:
            logger.warning(f"News scraping failed: {e}")
