"""One-shot feature-group ablation.

Zero out each feature group in turn and measure the top-3 accuracy delta
on a held-out season. Surfaces which groups are actually earning their
complexity.

Usage:
    python scripts/ablate_features.py -s 2025 -ts 2022 2023 2024
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from src.data.storage import Storage
from src.features.builder import FeatureBuilder, FEATURE_COLUMNS
from src.models.trainer import Trainer

logger = logging.getLogger(__name__)


GROUPS = {
    "practice": [c for c in FEATURE_COLUMNS if c.startswith("fp_")],
    "driver": [c for c in FEATURE_COLUMNS if c.startswith("driver_")],
    "team": [c for c in FEATURE_COLUMNS if c.startswith("team_")],
    "circuit": [c for c in FEATURE_COLUMNS if c.startswith("circuit_")],
    "weather": [c for c in FEATURE_COLUMNS if c.startswith("race_")],
    "strategy": [
        "tyre_deg_relative", "expected_pit_stops", "optimal_compound_advantage",
        "undercut_potential", "starting_tyre_compound",
    ],
    "news": [c for c in FEATURE_COLUMNS if c.startswith("upgrade_")
             or c in ("team_media_confidence", "regulation_compliance_flag")],
    "telemetry": [c for c in FEATURE_COLUMNS if c.startswith("telemetry_")],
    "grid": ["predicted_grid_position"],
    "teammate": ["teammate_fp_pace_delta"],
}


def _eval_top3(scores: np.ndarray, y: pd.Series, groups: list[int]) -> float:
    correct = 0
    n = 0
    offset = 0
    for g in groups:
        if offset + g > len(scores):
            break
        race_scores = scores[offset:offset + g]
        race_positions = y.iloc[offset:offset + g].values
        actual_winner = int(np.argmin(race_positions))
        pred_top3 = set(np.argsort(race_scores)[-3:])
        if actual_winner in pred_top3:
            correct += 1
        n += 1
        offset += g
    return correct / max(n, 1)


def run_ablation(storage: Storage, train_seasons: list[int], test_season: int,
                  out_path: str) -> dict:
    trainer = Trainer(storage)
    builder = FeatureBuilder(storage)

    X_tr, y_tr = builder.build_training_data(train_seasons)
    X_vl, y_vl = builder.build_training_data([test_season])
    groups_tr = trainer._compute_groups(X_tr, y_tr, train_seasons)
    groups_vl = trainer._compute_groups(X_vl, y_vl, [test_season])

    baseline_model = type(trainer.lgb_model)(params=trainer.lgb_model.params)
    baseline_model.train(X_tr, y_tr, groups_tr)
    baseline_scores = baseline_model.predict(X_vl)
    baseline_top3 = _eval_top3(baseline_scores, y_vl, groups_vl)
    logger.info(f"Baseline top-3: {baseline_top3:.4f}")

    deltas: dict[str, float] = {"baseline": baseline_top3}

    for name, cols in GROUPS.items():
        cols = [c for c in cols if c in X_tr.columns]
        if not cols:
            continue
        X_tr_ab = X_tr.copy()
        X_vl_ab = X_vl.copy()
        X_tr_ab[cols] = 0.0
        X_vl_ab[cols] = 0.0
        m = type(trainer.lgb_model)(params=trainer.lgb_model.params)
        m.train(X_tr_ab, y_tr, groups_tr)
        scores = m.predict(X_vl_ab)
        top3 = _eval_top3(scores, y_vl, groups_vl)
        deltas[name] = top3
        logger.info(f"  drop {name}: top-3={top3:.4f} (delta {top3 - baseline_top3:+.4f})")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(deltas, indent=2))
    logger.info(f"Ablation results saved to {out_path}")
    return deltas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Feature-group ablation study")
    parser.add_argument("--season", "-s", type=int, required=True)
    parser.add_argument("--train-seasons", "-ts", nargs="+", type=int, required=True)
    parser.add_argument("--db-path", default="data/f1_predict.db")
    parser.add_argument("--out", default="reports/ablation.json")
    args = parser.parse_args()

    storage = Storage(db_path=args.db_path)
    run_ablation(storage, args.train_seasons, args.season, args.out)
