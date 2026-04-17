"""LightGBM Learning-to-Rank model for F1 race prediction."""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb

logger = logging.getLogger(__name__)


def _podium_label_gain(max_drivers: int = 22) -> list[float]:
    """Exponential gain over top-5 positions, near-zero elsewhere.

    LightGBM's label_gain is indexed by relevance. Our relevance
    mapping is relevance = max_y - y + 1, so higher relevance = better
    finish. We want the loss to prioritize getting P1..P5 right.

    Example for 20 drivers (relevance range 1..20):
    - Relevance 20 (P1) → gain 31
    - Relevance 19 (P2) → gain 15
    - Relevance 18 (P3) → gain 7
    - Relevance 17 (P4) → gain 3
    - Relevance 16 (P5) → gain 1
    - Relevance 1..15 (P20..P6) → small linear gain so ordering outside
      the points doesn't get NaN gradients.
    """
    gain = [0.0] * (max_drivers + 1)
    for rel in range(1, max_drivers + 1):
        pos = max_drivers - rel + 1
        if pos <= 5:
            gain[rel] = float(2 ** (6 - pos) - 1)  # P1=31, P2=15, ..., P5=1
        else:
            # Tiny linear penalty so positions 6..22 are still ordered.
            gain[rel] = 0.01 * (max_drivers - pos + 1)
    return gain


class LightGBMRanker:
    """LightGBM-based LambdaRank model."""

    def __init__(self, params: dict = None):
        self.params = params or self._default_params()
        self.model: lgb.LGBMRanker | None = None
        self.feature_importances_ = None

    def _default_params(self) -> dict:
        # Deeper + narrower vs XGBoost to reduce ensemble correlation,
        # and a podium-weighted label_gain (Phase 2.4) so the loss cares
        # strongly about top-5 positions and is nearly indifferent about
        # P11-vs-P12 ordering.
        return {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [3, 5, 10],
            "lambdarank_truncation_level": 5,
            "label_gain": _podium_label_gain(max_drivers=22),
            "learning_rate": 0.04,
            "num_leaves": 127,
            "max_depth": -1,
            "n_estimators": 600,
            "subsample": 0.85,
            "colsample_bytree": 0.9,
            "min_child_samples": 6,
            "reg_alpha": 0.05,
            "reg_lambda": 0.8,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        }

    def train(self, X: pd.DataFrame, y: pd.Series,
              groups: list[int],
              sample_weights: np.ndarray = None,
              eval_set: tuple = None):
        """Train the ranking model.

        Args:
            X: Feature matrix.
            y: Target relevance scores (inverted position).
            groups: Group sizes (number of drivers per race).
            sample_weights: Optional sample weights.
            eval_set: Optional (X_val, y_val, groups_val) for validation.
        """
        # Convert positions to relevance (higher = better)
        relevance = y.max() - y + 1

        self.model = lgb.LGBMRanker(**self.params)

        fit_params = {
            "X": X,
            "y": relevance,
            "group": groups,
        }

        if sample_weights is not None:
            fit_params["sample_weight"] = sample_weights

        if eval_set:
            X_val, y_val, groups_val = eval_set
            rel_val = y_val.max() - y_val + 1
            fit_params["eval_set"] = [(X_val, rel_val)]
            fit_params["eval_group"] = [groups_val]

        self.model.fit(**fit_params)
        self.feature_importances_ = self.model.feature_importances_

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict ranking scores. Higher = better position."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        return self.model.predict(X)

    def predict_race(self, X: pd.DataFrame,
                      driver_ids: list[str]) -> pd.DataFrame:
        """Predict full race ranking."""
        scores = self.predict(X)

        result = pd.DataFrame({
            "driver_id": driver_ids,
            "score": scores,
        })

        result = result.sort_values("score", ascending=False).reset_index(drop=True)
        result["predicted_position"] = range(1, len(result) + 1)

        return result

    def get_feature_importance(self, feature_names: list[str]) -> pd.DataFrame:
        """Get feature importance ranking."""
        if self.feature_importances_ is None:
            return pd.DataFrame()

        importance = pd.DataFrame({
            "feature": feature_names,
            "importance": self.feature_importances_,
        })
        return importance.sort_values("importance", ascending=False)

    def save(self, path: str):
        """Save model to disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model": self.model,
            "params": self.params,
            "feature_importances": self.feature_importances_,
        }, path)
        logger.info(f"LightGBM model saved to {path}")

    def load(self, path: str):
        """Load model from disk."""
        data = joblib.load(path)
        self.model = data["model"]
        self.params = data["params"]
        self.feature_importances_ = data["feature_importances"]
        logger.info(f"LightGBM model loaded from {path}")
