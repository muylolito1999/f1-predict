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

logger = logging.getLogger(__name__)


class Trainer:
    """Handles model training, validation, and retraining."""

    def __init__(self, storage: Storage, model_dir: str = "models"):
        self.storage = storage
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.xgb_model = XGBoostRanker()
        self.lgb_model = LightGBMRanker()
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

        X_train, y_train = self.feature_builder.build_training_data(train_seasons)

        if X_train.empty:
            logger.error("No training data available")
            return {"error": "No training data"}

        logger.info(f"Training data: {len(X_train)} samples, {len(FEATURE_COLUMNS)} features")

        # Compute groups (number of drivers per race)
        groups_train = self._compute_groups(X_train, y_train, train_seasons)

        # Compute recency weights
        weights = self._compute_recency_weights(X_train, train_seasons)

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

    def load_models(self):
        """Load pre-trained models from disk."""
        xgb_path = self.model_dir / "xgboost_ranker.joblib"
        lgb_path = self.model_dir / "lightgbm_ranker.joblib"

        if xgb_path.exists():
            self.xgb_model.load(str(xgb_path))
            self.ensemble.add_model("xgboost", self.xgb_model)

        if lgb_path.exists():
            self.lgb_model.load(str(lgb_path))
            self.ensemble.add_model("lightgbm", self.lgb_model)

        if not self.ensemble.models:
            raise FileNotFoundError(
                f"No trained models found in {self.model_dir}. "
                "Run 'f1predict train' first."
            )

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
