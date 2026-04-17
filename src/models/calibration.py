"""Isotonic calibration for win/podium/points probabilities.

Monotonic isotonic regression fit on backtest predictions vs realized
outcomes. Wraps simulator outputs so that when the simulator says "35%
win probability", the driver actually wins roughly 35% of the time.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression

logger = logging.getLogger(__name__)


class ProbabilityCalibrator:
    """Fits one isotonic regression per probability type."""

    def __init__(self):
        self.calibrators: dict[str, IsotonicRegression] = {}

    def fit(self, backtest_records: list[dict]):
        """Fit calibrators from per-driver, per-race backtest predictions.

        Each record should be a dict:
          {
            "win_probability": float,
            "podium_probability": float,
            "points_probability": float,
            "actual_position": int,
          }
        """
        if not backtest_records:
            logger.warning("Empty backtest records — skipping calibration")
            return

        arr = {
            "win_probability": [],
            "podium_probability": [],
            "points_probability": [],
        }
        targets = {
            "win_probability": [],
            "podium_probability": [],
            "points_probability": [],
        }
        for r in backtest_records:
            pos = r.get("actual_position")
            if pos is None:
                continue
            for key, cutoff in (
                ("win_probability", 1),
                ("podium_probability", 3),
                ("points_probability", 10),
            ):
                if key in r:
                    arr[key].append(float(r[key]))
                    targets[key].append(int(pos <= cutoff))

        for key in arr:
            if not arr[key]:
                continue
            ir = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            ir.fit(arr[key], targets[key])
            self.calibrators[key] = ir
            logger.info(f"Calibrator fit for {key}: n={len(arr[key])}")

    def transform(self, probabilities: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Apply fitted calibrators; pass-through for keys we can't calibrate."""
        out = {}
        for key, vals in probabilities.items():
            if key in self.calibrators:
                out[key] = self.calibrators[key].transform(np.asarray(vals))
            else:
                out[key] = np.asarray(vals)
        return out

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.calibrators, path)

    def load(self, path: str):
        self.calibrators = joblib.load(path)
