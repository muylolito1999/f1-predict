"""Feature builder — combines all feature modules into model input."""

import logging

import numpy as np
import pandas as pd

from src.data.storage import Storage
from src.features.practice import extract_practice_features
from src.features.driver import extract_driver_features
from src.features.team import extract_team_features
from src.features.circuit import extract_circuit_features
from src.features.weather_features import extract_weather_features
from src.features.strategy import extract_strategy_features
from src.features.news_features import extract_news_features

logger = logging.getLogger(__name__)

# Ordered list of all features the model expects
FEATURE_COLUMNS = [
    # Practice features (aggregated)
    "fp_best_lap_delta", "fp_long_run_pace", "fp_short_run_pace",
    "fp_consistency", "fp_long_run_degradation", "fp_speed_trap_max",
    "fp_improvement_fp1_to_fp3", "fp_total_laps",
    # Driver features
    "driver_elo", "driver_circuit_history", "driver_circuit_best",
    "driver_recent_form", "driver_wet_ability", "driver_overtake_rate",
    "driver_dnf_rate", "driver_championship_pos", "driver_championship_points",
    "driver_teammate_delta", "driver_starts", "driver_wins_rate",
    "driver_podium_rate", "driver_podium_streak",
    # Team features
    "team_elo", "team_constructor_pos", "team_constructor_points",
    "team_recent_form", "team_development_trajectory",
    "team_pit_stop_avg", "team_pit_stop_consistency",
    "team_reliability_score",
    # Circuit features
    "circuit_type", "circuit_length", "circuit_corners", "circuit_drs_zones",
    "circuit_altitude", "circuit_power_sensitivity", "circuit_tyre_stress",
    "circuit_overtaking_difficulty", "circuit_safety_car_prob",
    # Weather features
    "race_temp_air", "race_temp_track", "race_humidity", "race_wind_speed",
    "race_rain_prob", "race_is_wet", "race_temp_delta_fp",
    "race_conditions_change", "race_is_night",
    # Strategy features
    "tyre_deg_relative", "expected_pit_stops", "optimal_compound_advantage",
    "undercut_potential", "starting_tyre_compound",
    # News/upgrade features
    "upgrade_impact_score", "upgrade_component_type", "upgrade_sentiment",
    "team_media_confidence", "regulation_compliance_flag",
    "upgrade_recency_days", "upgrade_cumulative",
]


class FeatureBuilder:
    """Assembles feature vectors for all drivers at a race."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def build_race_features(self, year: int, round_num: int,
                             drivers: list[dict] = None,
                             fp_sessions: list[str] = None,
                             race_weather: dict = None) -> pd.DataFrame:
        """Build feature matrix for all drivers at a race.

        Args:
            year: Season year.
            round_num: Race round number.
            drivers: List of {"driver_id", "driver_name", "team"} dicts.
                     If None, fetched from database.
            fp_sessions: FP sessions to use. Defaults to all available.
            race_weather: Pre-fetched weather dict.

        Returns:
            DataFrame with one row per driver and all features as columns.
        """
        race = self.storage.get_race(year, round_num)
        if not race:
            raise ValueError(f"Race not found: {year} Round {round_num}")

        race_id = race["id"]
        circuit_id = race["circuit_id"]
        race_date = race.get("date", "")

        # Get drivers
        if drivers is None:
            drivers = self.storage.get_all_drivers_for_season(year)
            if not drivers:
                # Try to get from FP data
                fp_data = self.storage.get_fp_data(race_id)
                if not fp_data.empty:
                    drivers = fp_data[["driver_id", "driver_name", "team"]].drop_duplicates().to_dict("records")

        if not drivers:
            raise ValueError(f"No drivers found for {year} Round {round_num}")

        # Circuit features (same for all drivers)
        circuit_feats = extract_circuit_features(self.storage, circuit_id, race_id)

        # Weather features (same for all drivers)
        weather_feats = extract_weather_features(
            self.storage, race_id, race_weather
        )

        rows = []
        for driver_info in drivers:
            driver_id = driver_info["driver_id"]
            team = driver_info["team"]

            try:
                # Per-driver features
                practice_feats = extract_practice_features(
                    self.storage, race_id, driver_id, fp_sessions
                )

                driver_feats = extract_driver_features(
                    self.storage, driver_id, team, year, round_num, circuit_id
                )

                team_feats = extract_team_features(
                    self.storage, team, year, round_num
                )

                strategy_feats = extract_strategy_features(
                    self.storage, race_id, driver_id, fp_sessions
                )

                news_feats = extract_news_features(
                    self.storage, team, race_date
                )

                # Combine all features
                all_feats = {
                    **practice_feats,
                    **driver_feats,
                    **team_feats,
                    **circuit_feats,
                    **weather_feats,
                    **strategy_feats,
                    **news_feats,
                }

                # Add metadata
                all_feats["driver_id"] = driver_id
                all_feats["driver_name"] = driver_info.get("driver_name", "")
                all_feats["team"] = team
                all_feats["year"] = year
                all_feats["round"] = round_num

                rows.append(all_feats)

            except Exception as e:
                logger.warning(f"Error building features for {driver_id}: {e}")
                continue

        if not rows:
            return pd.DataFrame(columns=["driver_id"] + FEATURE_COLUMNS)

        df = pd.DataFrame(rows)

        # Ensure all expected columns exist
        for col in FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0

        return df

    def build_training_data(self, seasons: list[int],
                             fp_sessions: list[str] = None) -> tuple[pd.DataFrame, pd.Series]:
        """Build training dataset from historical seasons.

        Returns:
            Tuple of (feature_matrix, target_positions).
        """
        all_features = []
        all_targets = []

        for year in seasons:
            races = self.storage.get_races_for_season(year)
            logger.info(f"Building features for {year}: {len(races)} races")

            for race in races:
                round_num = race["round"]
                race_id = race["id"]

                try:
                    # Get actual results for targets
                    results = self.storage.get_results(race_id)
                    if results.empty:
                        continue

                    # Build features
                    drivers = [
                        {
                            "driver_id": row["driver_id"],
                            "driver_name": row["driver_name"],
                            "team": row["team"],
                        }
                        for _, row in results.iterrows()
                    ]

                    features_df = self.build_race_features(
                        year, round_num, drivers, fp_sessions
                    )

                    if features_df.empty:
                        continue

                    # Merge with actual finish positions
                    result_map = dict(zip(
                        results["driver_id"],
                        results["finish_position"]
                    ))

                    features_df["target_position"] = features_df["driver_id"].map(result_map)

                    # Drop rows without target
                    valid = features_df.dropna(subset=["target_position"])
                    if valid.empty:
                        continue

                    all_features.append(valid)

                except Exception as e:
                    logger.warning(
                        f"Error building features for {year} R{round_num}: {e}"
                    )
                    continue

        if not all_features:
            return pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=float)

        combined = pd.concat(all_features, ignore_index=True)

        targets = combined["target_position"].astype(float)
        feature_matrix = combined[FEATURE_COLUMNS].fillna(0.0)

        return feature_matrix, targets

    def get_feature_columns(self) -> list[str]:
        """Return ordered list of feature column names."""
        return FEATURE_COLUMNS.copy()
