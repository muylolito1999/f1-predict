"""Neural network ranker for F1 race prediction.

Listwise softmax cross-entropy over per-race groups. Uses PyTorch for the
MLP and falls back to a no-op if torch is unavailable so the rest of the
pipeline keeps working.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    _TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class _RankerMLP:
    """Small MLP defined lazily so importing this module doesn't require torch."""

    @staticmethod
    def build(n_features: int, hidden: tuple = (128, 64), dropout: float = 0.2):
        if not _TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        layers = []
        in_dim = n_features
        for h in hidden:
            layers.append(nn.Linear(in_dim, h))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))
            in_dim = h
        layers.append(nn.Linear(in_dim, 1))
        return nn.Sequential(*layers)


class NeuralRanker:
    """Listwise neural ranker.

    Training objective: listwise softmax cross-entropy.
    For each race-group of drivers, the target distribution puts mass on
    the actual finish positions (higher mass to P1). The model outputs one
    score per driver; we softmax across the group and match the target.
    """

    def __init__(self, epochs: int = 30, batch_size: int = 8,
                 lr: float = 1e-3, hidden: tuple = (128, 64),
                 dropout: float = 0.2, device: str | None = None):
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.hidden = hidden
        self.dropout = dropout
        self.device = device or ("cuda" if _TORCH_AVAILABLE and torch.cuda.is_available() else "cpu")
        self.model = None
        self.feature_mean: np.ndarray | None = None
        self.feature_std: np.ndarray | None = None

    def _available(self) -> bool:
        return _TORCH_AVAILABLE

    def train(self, X: pd.DataFrame, y: pd.Series,
              groups: list[int],
              sample_weights: np.ndarray | None = None,
              eval_set: tuple | None = None):
        if not self._available():
            logger.warning("PyTorch not installed — NeuralRanker disabled")
            return

        X_vals = X.values.astype(np.float32)
        self.feature_mean = X_vals.mean(axis=0)
        self.feature_std = X_vals.std(axis=0) + 1e-6
        X_norm = (X_vals - self.feature_mean) / self.feature_std

        # Race-level relevance: softmax target over negative positions.
        y_vals = y.values.astype(np.float32)

        self.model = _RankerMLP.build(
            n_features=X_vals.shape[1], hidden=self.hidden, dropout=self.dropout
        ).to(self.device)
        opt = torch.optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=1e-4)

        # Build per-race slices up front.
        slices = []
        offset = 0
        for g in groups:
            slices.append((offset, offset + g))
            offset += g

        for epoch in range(self.epochs):
            self.model.train()
            total_loss = 0.0
            np.random.shuffle(slices)

            for a, b in slices:
                x = torch.from_numpy(X_norm[a:b]).to(self.device)
                positions = torch.from_numpy(y_vals[a:b]).to(self.device)
                # Target = softmax of (-position) so P1 gets most mass.
                target = torch.softmax(-positions, dim=0)

                scores = self.model(x).squeeze(-1)
                log_probs = torch.log_softmax(scores, dim=0)
                loss = -(target * log_probs).sum()

                opt.zero_grad()
                loss.backward()
                opt.step()
                total_loss += float(loss.item())

            if (epoch + 1) % 10 == 0:
                logger.debug(f"Neural epoch {epoch+1}: loss={total_loss/len(slices):.4f}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self._available() or self.model is None:
            return np.zeros(len(X), dtype=np.float32)
        X_norm = (X.values.astype(np.float32) - self.feature_mean) / self.feature_std
        self.model.eval()
        with torch.no_grad():
            x = torch.from_numpy(X_norm).to(self.device)
            scores = self.model(x).squeeze(-1).cpu().numpy()
        return scores

    def save(self, path: str):
        if not self._available() or self.model is None:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "state_dict": {k: v.cpu() for k, v in self.model.state_dict().items()},
            "feature_mean": self.feature_mean,
            "feature_std": self.feature_std,
            "hidden": self.hidden,
            "dropout": self.dropout,
            "n_features": self.feature_mean.shape[0],
        }, path)

    def load(self, path: str):
        if not self._available():
            return
        data = joblib.load(path)
        self.feature_mean = data["feature_mean"]
        self.feature_std = data["feature_std"]
        self.hidden = data["hidden"]
        self.dropout = data["dropout"]
        self.model = _RankerMLP.build(
            n_features=data["n_features"], hidden=self.hidden, dropout=self.dropout
        ).to(self.device)
        self.model.load_state_dict(data["state_dict"])
