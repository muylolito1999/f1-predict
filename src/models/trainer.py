"""Training and retraining logic for F1 prediction models."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.data.storage import Storage
from src.features.builder import FeatureBuilder, FEATURE_COLUMNS
from src.features.driver import update_elo
from src.features.team import update_team_elo
from src.models.xgboost_model import XGBoostRanker
from src.models.lightgbm_model import LightGBMRanker
from src.models.ensemble import RankingEnsemble
from src.models.qualifying_model import QualifyingRanker

logger = logging.getLogger(__name__)


class Trainer:
    """Handles model training, validation, and retraining."""

    def __init__(self, storage: Storage, model_dir: str = "models"):
        self.storage = storage
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Load tuned hyperparams if a previous `tune()` run persisted them.
        xgb_params = None
        lgb_params = None
        best_params_path = self.model_dir / "best_params.json"
        if best_params_path.exists():
            try:
                import json
                best = json.loads(best_params_path.read_text())
                xgb_params = best.get("xgboost")
                lgb_params = best.get("lightgbm")
                logger.info("Loaded tuned hyperparameters from best_params.json")
            except Exception as e:
                logger.debug(f"Could not load best_params.json: {e}")

        self.xgb_model = XGBoostRanker(params=xgb_params)
        self.lgb_model = LightGBMRanker(params=lgb_params)
        self.qual_model = QualifyingRanker()
        self.ensemble = RankingEnsemble()
        self.feature_builder = FeatureBuilder(storage)

    def train(self, seasons: list[int],
              validation_season: int = None) -> dict:
        """Train all models on historical data.

        Args:
            seasons: List of seasons to train on.
            validation_season: Season to hold out for validation.

        Returns:
            Dict of training metrics.
        """
        logger.info(f"Building training data for seasons: {seasons}")

        # Build Elo ratings first
        self._build_elo_ratings(seasons)

        # Build features
        if validation_season and validation_season in seasons:
            train_seasons = [s for s in seasons if s != validation_season]
        else:
            train_seasons = seasons
            validation_season = None

        X_train, y_train, grid_train = self.feature_builder.build_training_data(
            train_seasons, include_grid_target=True
        )

        if X_train.empty:
            logger.error("No training data available")
            return {"error": "No training data"}

        logger.info(f"Training data: {len(X_train)} samples, {len(FEATURE_COLUMNS)} features")

        # Compute groups (number of drivers per race)
        groups_train = self._compute_groups(X_train, y_train, train_seasons)

        # Compute recency weights
        weights = self._compute_recency_weights(X_train, train_seasons)

        # Train the qualifying model WITHOUT the predicted_grid_position
        # feature (can't use the target as input).
        quali_feature_cols = [c for c in FEATURE_COLUMNS if c != "predicted_grid_position"]
        X_train_quali = X_train[quali_feature_cols]
        grid_valid = grid_train.dropna()
        if not grid_valid.empty and len(grid_valid) == len(X_train_quali):
            logger.info("Training qualifying ranker...")
            self.qual_model.train(X_train_quali, grid_valid.astype(int),
                                   groups_train, weights)
            self.qual_model.save(str(self.model_dir / "qualifying_ranker.joblib"))

        # Prepare validation data
        eval_set = None
        if validation_season:
            X_val, y_val = self.feature_builder.build_training_data([validation_season])
            if not X_val.empty:
                groups_val = self._compute_groups(X_val, y_val, [validation_season])
                eval_set = (X_val, y_val, groups_val)

        # Train XGBoost
        logger.info("Training XGBoost ranker...")
        self.xgb_model.train(X_train, y_train, groups_train, weights, eval_set)

        # Train LightGBM
        logger.info("Training LightGBM ranker...")
        self.lgb_model.train(X_train, y_train, groups_train, weights, eval_set)

        # Setup ensemble
        self.ensemble.add_model("xgboost", self.xgb_model)
        self.ensemble.add_model("lightgbm", self.lgb_model)

        # Save models
        self.xgb_model.save(str(self.model_dir / "xgboost_ranker.joblib"))
        self.lgb_model.save(str(self.model_dir / "lightgbm_ranker.joblib"))

        # Phase 2.2: CatBoost for ensemble diversity (YetiRank loss).
        try:
            from src.models.catboost_model import CatBoostRanker
            self.cat_model = CatBoostRanker()
            if self.cat_model._available():
                logger.info("Training CatBoost ranker (YetiRank)...")
                self.cat_model.train(X_train, y_train, groups_train, weights)
                self.cat_model.save(str(self.model_dir / "catboost_ranker.joblib"))
                self.ensemble.add_model("catboost", self.cat_model)
        except Exception as e:
            logger.warning(f"CatBoost training skipped: {e}")

        # Phase 2.2: Real neural ranker (listwise softmax CE).
        try:
            from src.models.neural_model import NeuralRanker
            self.nn_model = NeuralRanker()
            if self.nn_model._available():
                logger.info("Training neural ranker...")
                self.nn_model.train(X_train, y_train, groups_train, weights)
                self.nn_model.save(str(self.model_dir / "neural_ranker.joblib"))
                self.ensemble.add_model("neural", self.nn_model)
        except Exception as e:
            logger.warning(f"Neural training skipped: {e}")

        # Phase 2.3: fit stacking meta-learner on CV out-of-fold predictions.
        try:
            cv = self.cross_validate(train_seasons)
            if cv.get("oof"):
                stacker_raw_cols = ["predicted_grid_position", "circuit_type", "race_is_wet"]
                # Attach raw feature frames to each fold for the stacker.
                for val_season, fold_data in cv["oof"].items():
                    X_val_full, _ = self.feature_builder.build_training_data([val_season])
                    if len(X_val_full) == len(fold_data.get("y_true", [])):
                        fold_data["raw_features"] = X_val_full
                self.ensemble.fit_stacker(cv["oof"], raw_feature_cols=stacker_raw_cols)
                self.ensemble.save_stacker(str(self.model_dir / "stacker.joblib"))
        except Exception as e:
            logger.warning(f"Stacker fitting skipped: {e}")

        # Evaluate
        metrics = {}
        if validation_season and eval_set:
            metrics = self._evaluate(X_val, y_val, groups_val)
            logger.info(f"Validation metrics: {metrics}")

        # Log feature importance
        importance = self.xgb_model.get_feature_importance(FEATURE_COLUMNS)
        if not importance.empty:
            logger.info("Top 10 features (XGBoost):")
            for _, row in importance.head(10).iterrows():
                logger.info(f"  {row['feature']}: {row['importance']:.4f}")

        metrics["training_samples"] = len(X_train)
        metrics["features"] = len(FEATURE_COLUMNS)
        return metrics

    def tune(self, seasons: list[int], n_trials: int = 40) -> dict:
        """Run Optuna hyperparameter search across CV folds.

        Persists best params to JSON so the next `train()` picks them up.
        """
        from src.models.tuning import tune_lightgbm, tune_xgboost
        import json

        seasons = sorted(seasons)
        self._build_elo_ratings(seasons)

        X_by_season: dict[int, pd.DataFrame] = {}
        y_by_season: dict[int, pd.Series] = {}
        groups_by_season: dict[int, list[int]] = {}
        for s in seasons:
            X_s, y_s = self.feature_builder.build_training_data([s])
            if X_s.empty:
                continue
            X_by_season[s] = X_s
            y_by_season[s] = y_s
            groups_by_season[s] = self._compute_groups(X_s, y_s, [s])

        lgb_params = tune_lightgbm(X_by_season, y_by_season, groups_by_season,
                                     list(X_by_season.keys()), n_trials=n_trials)
        xgb_params = tune_xgboost(X_by_season, y_by_season, groups_by_season,
                                    list(X_by_season.keys()), n_trials=n_trials)

        best = {"lightgbm": lgb_params, "xgboost": xgb_params}
        out_path = self.model_dir / "best_params.json"
        out_path.write_text(json.dumps(best, indent=2, default=str))
        logger.info(f"Best hyperparameters saved to {out_path}")

        # Apply immediately for next train()
        self.lgb_model = LightGBMRanker(params=lgb_params)
        self.xgb_model = XGBoostRanker(params=xgb_params)
        return best

    def cross_validate(self, seasons: list[int]) -> dict:
        """Expanding-window time-series CV.

        For seasons [S1..Sn], train on [S1..Sk] and validate on Sk+1 for
        each k >= 1. Returns aggregated fold metrics plus per-fold detail.

        Also exposes the out-of-fold predictions on scores dict, suitable
        for training a stacking meta-learner (see RankingEnsemble).
        """
        seasons = sorted(seasons)
        if len(seasons) < 2:
            logger.warning("Need at least 2 seasons for time-series CV; skipping")
            return {"folds": [], "oof": {}}

        logger.info(f"Time-series CV over seasons: {seasons}")
        self._build_elo_ratings(seasons)

        folds: list[dict] = []
        oof_predictions: dict[int, dict] = {}

        for k in range(1, len(seasons)):
            train_seasons = seasons[:k]
            val_season = seasons[k]
            logger.info(
                f"Fold {k}: train={train_seasons} validate={val_season}"
            )

            X_tr, y_tr = self.feature_builder.build_training_data(train_seasons)
            if X_tr.empty:
                continue
            X_vl, y_vl = self.feature_builder.build_training_data([val_season])
            if X_vl.empty:
                continue

            groups_tr = self._compute_groups(X_tr, y_tr, train_seasons)
            groups_vl = self._compute_groups(X_vl, y_vl, [val_season])
            weights_tr = self._compute_recency_weights(X_tr, train_seasons)

            fold_xgb = XGBoostRanker()
            fold_lgb = LightGBMRanker()
            fold_xgb.train(X_tr, y_tr, groups_tr, weights_tr)
            fold_lgb.train(X_tr, y_tr, groups_tr, weights_tr)

            xgb_scores = fold_xgb.predict(X_vl)
            lgb_scores = fold_lgb.predict(X_vl)

            fold_metrics = self._fold_metrics(
                {"xgboost": xgb_scores, "lightgbm": lgb_scores},
                y_vl, groups_vl,
            )
            fold_metrics["fold"] = k
            fold_metrics["train_seasons"] = train_seasons
            fold_metrics["val_season"] = val_season
            folds.append(fold_metrics)

            oof_predictions[val_season] = {
                "xgboost": xgb_scores.tolist(),
                "lightgbm": lgb_scores.tolist(),
                "y_true": y_vl.tolist(),
                "groups": groups_vl,
            }

        if not folds:
            return {"folds": [], "oof": {}}

        agg = {
            "mean_top1": float(np.mean([f["top1_accuracy"] for f in folds])),
            "mean_top3": float(np.mean([f["top3_accuracy"] for f in folds])),
            "mean_spearman": float(np.mean([f["spearman"] for f in folds])),
            "n_folds": len(folds),
        }
        logger.info(f"CV aggregate: {agg}")
        return {"folds": folds, "aggregate": agg, "oof": oof_predictions}

    def _fold_metrics(self, scores_by_model: dict, y: pd.Series,
                       groups: list[int]) -> dict:
        """Compute per-model metrics for a validation fold."""
        from scipy.stats import spearmanr as _spearmanr
        best = None
        for name, scores in scores_by_model.items():
            corr, _ = _spearmanr(scores, -y)
            top1_correct = 0
            top3_correct = 0
            n_races = 0
            offset = 0
            for group_size in groups:
                if offset + group_size > len(scores):
                    break
                race_scores = scores[offset:offset + group_size]
                race_positions = y.iloc[offset:offset + group_size].values
                pred_winner = int(np.argmax(race_scores))
                actual_winner = int(np.argmin(race_positions))
                if pred_winner == actual_winner:
                    top1_correct += 1
                pred_top3 = set(np.argsort(race_scores)[-3:])
                if actual_winner in pred_top3:
                    top3_correct += 1
                n_races += 1
                offset += group_size
            fold = {
                "model": name,
                "top1_accuracy": top1_correct / max(n_races, 1),
                "top3_accuracy": top3_correct / max(n_races, 1),
                "spearman": float(corr) if not np.isnan(corr) else 0.0,
                "races": n_races,
            }
            if best is None or fold["top3_accuracy"] > best["top3_accuracy"]:
                best = fold
        return best or {"top1_accuracy": 0, "top3_accuracy": 0, "spearman": 0, "races": 0}

    def load_models(self):
        """Load pre-trained models from disk."""
        xgb_path = self.model_dir / "xgboost_ranker.joblib"
        lgb_path = self.model_dir / "lightgbm_ranker.joblib"
        qual_path = self.model_dir / "qualifying_ranker.joblib"

        if xgb_path.exists():
            self.xgb_model.load(str(xgb_path))
            self.ensemble.add_model("xgboost", self.xgb_model)

        if lgb_path.exists():
            self.lgb_model.load(str(lgb_path))
            self.ensemble.add_model("lightgbm", self.lgb_model)

        if qual_path.exists():
            self.qual_model.load(str(qual_path))

        # CatBoost and neural rankers (Phase 2.2) — loaded if present.
        try:
            cat_path = self.model_dir / "catboost_ranker.joblib"
            if cat_path.exists():
                from src.models.catboost_model import CatBoostRanker
                self.cat_model = CatBoostRanker()
                self.cat_model.load(str(cat_path))
                self.ensemble.add_model("catboost", self.cat_model)
        except Exception as e:
            logger.debug(f"CatBoost load skipped: {e}")

        try:
            nn_path = self.model_dir / "neural_ranker.joblib"
            if nn_path.exists():
                from src.models.neural_model import NeuralRanker
                self.nn_model = NeuralRanker()
                self.nn_model.load(str(nn_path))
                self.ensemble.add_model("neural", self.nn_model)
        except Exception as e:
            logger.debug(f"Neural ranker load skipped: {e}")

        if not self.ensemble.models:
            raise FileNotFoundError(
                f"No trained models found in {self.model_dir}. "
                "Run 'f1predict train' first."
            )

        stacker_path = self.model_dir / "stacker.joblib"
        if stacker_path.exists():
            try:
                self.ensemble.load_stacker(str(stacker_path))
                logger.info("Loaded stacking meta-learner")
            except Exception as e:
                logger.warning(f"Stacker load skipped: {e}")

    def retrain_incremental(self, new_season: int, new_round: int):
        """Retrain models incorporating new race data.

        Used for rolling retraining during a season.
        """
        logger.info(f"Incremental retrain after {new_season} R{new_round}")

        # Update Elo for the new race
        race_id = self.storage.get_race_id(new_season, new_round)
        if race_id:
            update_elo(self.storage, race_id, new_season, new_round)
            update_team_elo(self.storage, race_id, new_season, new_round)

        # Determine training window
        # Use all available data with recency weighting
        seasons = list(range(2022, new_season + 1))
        self.train(seasons)

    def _build_elo_ratings(self, seasons: list[int]):
        """Pre-compute Elo ratings for all races in the training data."""
        for year in sorted(seasons):
            races = self.storage.get_races_for_season(year)
            for race in races:
                race_id = race["id"]
                round_num = race["round"]

                # Check if Elo already computed
                with self.storage._connect() as conn:
                    existing = conn.execute(
                        "SELECT COUNT(*) FROM elo_ratings WHERE year=? AND round=?",
                        (year, round_num)
                    ).fetchone()[0]

                if existing > 0:
                    continue

                update_elo(self.storage, race_id, year, round_num)
                update_team_elo(self.storage, race_id, year, round_num)

    def _compute_groups(self, X: pd.DataFrame, y: pd.Series,
                         seasons: list[int]) -> list[int]:
        """Compute group sizes for ranking (drivers per race).

        Each race is a group; we need to know how many drivers per race.
        """
        # If we have metadata, compute from it
        # Otherwise estimate: typically 20 drivers per race
        n_samples = len(X)
        typical_group_size = 20

        # Estimate number of races
        n_races = max(1, n_samples // typical_group_size)
        remainder = n_samples % typical_group_size

        groups = [typical_group_size] * n_races
        if remainder > 0:
            groups[-1] += remainder

        # Verify total matches
        total = sum(groups)
        if total != n_samples:
            # Adjust last group
            groups[-1] += (n_samples - total)

        return groups

    def _compute_recency_weights(self, X: pd.DataFrame,
                                  seasons: list[int]) -> np.ndarray:
        """Compute sample weights giving more weight to recent data."""
        n = len(X)
        if n == 0:
            return np.array([])

        # Linear decay: most recent = 1.0, oldest = 0.3
        weights = np.linspace(0.3, 1.0, n)
        return weights

    def _evaluate(self, X: pd.DataFrame, y: pd.Series,
                   groups: list[int]) -> dict:
        """Evaluate model performance on validation data."""
        metrics = {}

        for name, model in [("xgboost", self.xgb_model),
                             ("lightgbm", self.lgb_model)]:
            try:
                scores = model.predict(X)

                # Overall Spearman correlation
                corr, _ = spearmanr(scores, -y)  # Negative y because higher score = lower position
                metrics[f"{name}_spearman"] = corr

                # Per-race top-1 and top-3 accuracy
                top1_correct = 0
                top3_correct = 0
                n_races = 0

                offset = 0
                for group_size in groups:
                    if offset + group_size > len(scores):
                        break

                    race_scores = scores[offset:offset + group_size]
                    race_positions = y.iloc[offset:offset + group_size].values

                    # Predicted winner (highest score)
                    pred_winner_idx = np.argmax(race_scores)
                    actual_winner_idx = np.argmin(race_positions)

                    if pred_winner_idx == actual_winner_idx:
                        top1_correct += 1

                    # Top 3
                    pred_top3 = set(np.argsort(race_scores)[-3:])
                    actual_top3 = set(np.argsort(race_positions)[:3])
                    if actual_winner_idx in pred_top3:
                        top3_correct += 1

                    n_races += 1
                    offset += group_size

                if n_races > 0:
                    metrics[f"{name}_top1_accuracy"] = top1_correct / n_races
                    metrics[f"{name}_top3_accuracy"] = top3_correct / n_races
                    metrics[f"{name}_races_evaluated"] = n_races

            except Exception as e:
                logger.warning(f"Evaluation failed for {name}: {e}")

        return metrics
