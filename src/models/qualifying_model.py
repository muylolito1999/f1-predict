"""Qualifying (grid-position) ranker.

Two-stage pipeline: predict qualifying first, then feed the predicted grid
into the race model as a feature. When actual qualifying has happened,
real grid positions override the predicted ones.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb

logger = logging.getLogger(__name__)


class QualifyingRanker:
    """LightGBM ranker targeting qualifying/grid position.

    Uses the same feature schema as the race model but trained on
    grid_position instead of finish_position.
    """

    def __init__(self, params: dict | None = None):
        self.params = params or self._default_params()
        self.model: lgb.LGBMRanker | None = None

    def _default_params(self) -> dict:
        # Grid position rewards single-lap pace more heavily — encourage
        # the model to weight practice and quali-pace features.
        return {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [3, 5, 10],
            "learning_rate": 0.04,
            "num_leaves": 63,
            "n_estimators": 400,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "min_child_samples": 8,
            "reg_alpha": 0.05,
            "reg_lambda": 0.5,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        }

    def train(self, X: pd.DataFrame, grid_positions: pd.Series,
              groups: list[int],
              sample_weights: np.ndarray | None = None):
        """Train on grid-position targets.

        Args:
            X: feature matrix (same schema as race model).
            grid_positions: integer grid positions per row.
            groups: drivers per race.
            sample_weights: optional recency weights.
        """
        relevance = grid_positions.max() - grid_positions + 1

        self.model = lgb.LGBMRanker(**self.params)
        fit_params = {"X": X, "y": relevance, "group": groups}
        if sample_weights is not None:
            fit_params["sample_weight"] = sample_weights
        self.model.fit(**fit_params)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return ranking scores (higher = better grid position)."""
        if self.model is None:
            raise RuntimeError("QualifyingRanker not trained")
        return self.model.predict(X)

    def predict_grid(self, X: pd.DataFrame,
                      driver_ids: list[str]) -> pd.DataFrame:
        """Return DataFrame with driver_id and predicted grid position 1..N."""
        scores = self.predict(X)
        result = pd.DataFrame({"driver_id": driver_ids, "score": scores})
        result = result.sort_values("score", ascending=False).reset_index(drop=True)
        result["predicted_grid_position"] = range(1, len(result) + 1)
        return result

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "params": self.params}, path)
        logger.info(f"Qualifying model saved to {path}")

    def load(self, path: str):
        data = joblib.load(path)
        self.model = data["model"]
        self.params = data["params"]
        logger.info(f"Qualifying model loaded from {path}")
