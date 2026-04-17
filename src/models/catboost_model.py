"""CatBoost YetiRank ranker for ensemble diversity.

YetiRank is a genuinely different ranking formulation from pairwise/
lambdarank, which is why it earns its slot in the ensemble — XGB and LGB
are highly correlated; CatBoost adds decorrelation.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    from catboost import CatBoostRanker as _CBRanker, Pool
    _CATBOOST_AVAILABLE = True
except ImportError:
    _CBRanker = None
    Pool = None
    _CATBOOST_AVAILABLE = False

logger = logging.getLogger(__name__)


class CatBoostRanker:
    """Thin wrapper around catboost.CatBoostRanker with YetiRank loss."""

    def __init__(self, params: dict | None = None):
        self.params = params or self._default_params()
        self.model = None
        self.feature_importances_: np.ndarray | None = None

    def _default_params(self) -> dict:
        return {
            "loss_function": "YetiRank",
            "iterations": 500,
            "learning_rate": 0.04,
            "depth": 7,
            "l2_leaf_reg": 3.0,
            "random_seed": 42,
            "verbose": 0,
        }

    def _available(self) -> bool:
        return _CATBOOST_AVAILABLE

    def _groups_to_ids(self, groups: list[int]) -> np.ndarray:
        """Convert group-size list to a per-row group id array."""
        ids = np.empty(sum(groups), dtype=np.int64)
        offset = 0
        for gid, size in enumerate(groups):
            ids[offset:offset + size] = gid
            offset += size
        return ids

    def train(self, X: pd.DataFrame, y: pd.Series,
              groups: list[int],
              sample_weights: np.ndarray | None = None,
              eval_set: tuple | None = None):
        if not self._available():
            logger.warning("CatBoost not installed — CatBoostRanker disabled")
            return

        relevance = y.max() - y + 1
        group_ids = self._groups_to_ids(groups)

        pool = Pool(
            data=X.values, label=relevance.values,
            group_id=group_ids,
            weight=sample_weights if sample_weights is not None else None,
        )

        self.model = _CBRanker(**self.params)
        self.model.fit(pool)
        self.feature_importances_ = np.asarray(self.model.get_feature_importance())

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self._available() or self.model is None:
            return np.zeros(len(X), dtype=np.float32)
        return self.model.predict(X.values)

    def save(self, path: str):
        if not self._available() or self.model is None:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cbm_path = str(Path(path).with_suffix(".cbm"))
        self.model.save_model(cbm_path)
        joblib.dump({
            "params": self.params,
            "cbm_path": cbm_path,
            "feature_importances": self.feature_importances_,
        }, path)

    def load(self, path: str):
        if not self._available():
            return
        data = joblib.load(path)
        self.params = data["params"]
        self.feature_importances_ = data["feature_importances"]
        self.model = _CBRanker(**self.params)
        self.model.load_model(data["cbm_path"])
