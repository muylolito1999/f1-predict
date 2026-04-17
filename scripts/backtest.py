"""Backtesting script for model evaluation.

Walk-forward backtesting: for each race in the test season,
train on all prior data and predict.
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, ".")

from src.data.storage import Storage
from src.features.builder import FeatureBuilder, FEATURE_COLUMNS
from src.models.trainer import Trainer
from src.prediction.output import display_comparison, display_metrics

logger = logging.getLogger(__name__)


def run_backtest(storage: Storage, config: dict,
                  train_seasons: list[int], test_season: int,
                  output_json: str | None = None,
                  stratify: bool = False,
                  fit_calibrator: str | None = None,
                  calibration_plot: str | None = None):
    """Run walk-forward backtest on a season.

    Args:
        storage: Database storage.
        config: Configuration dict.
        train_seasons: Seasons to use for initial training.
        test_season: Season to evaluate on.
    """
    model_dir = config.get("model", {}).get("save_dir", "models")
    trainer = Trainer(storage, model_dir=model_dir)
    feature_builder = FeatureBuilder(storage)

    # Train initial model
    logger.info(f"Training initial model on seasons: {train_seasons}")
    trainer.train(train_seasons)

    # Get test season races
    test_races = storage.get_races_for_season(test_season)
    if not test_races:
        logger.error(f"No races found for {test_season}")
        return

    logger.info(f"Backtesting on {test_season}: {len(test_races)} races")

    # Metrics accumulators
    all_metrics = {
        "top1_correct": 0,
        "top3_correct": 0,
        "top5_correct": 0,
        "spearman_correlations": [],
        "position_errors": [],
        "races_evaluated": 0,
    }
    per_race_records: list[dict] = []
    per_driver_records: list[dict] = []

    for race in test_races:
        race_id = race["id"]
        round_num = race["round"]
        race_name = race["name"]

        # Get actual results
        actual = storage.get_results(race_id)
        if actual.empty:
            continue

        # Get drivers from results
        drivers = [
            {
                "driver_id": row["driver_id"],
                "driver_name": row["driver_name"],
                "team": row["team"],
            }
            for _, row in actual.iterrows()
            if pd.notna(row["finish_position"])
        ]

        if not drivers:
            continue

        # Build features
        try:
            features_df = feature_builder.build_race_features(
                test_season, round_num, drivers
            )
        except Exception as e:
            logger.warning(f"Feature building failed for R{round_num}: {e}")
            continue

        if features_df.empty:
            continue

        # Predict
        try:
            X = features_df[FEATURE_COLUMNS].fillna(0.0)
            predictions = trainer.ensemble.predict(
                X,
                driver_ids=features_df["driver_id"].tolist(),
                driver_names=features_df.get("driver_name", pd.Series()).tolist(),
                teams=features_df.get("team", pd.Series()).tolist(),
            )
        except Exception as e:
            logger.warning(f"Prediction failed for R{round_num}: {e}")
            continue

        # Evaluate
        actual_order = actual.sort_values("finish_position")
        actual_winner = actual_order.iloc[0]["driver_id"]
        actual_top3 = set(actual_order.head(3)["driver_id"])
        actual_top5 = set(actual_order.head(5)["driver_id"])

        pred_winner = predictions.iloc[0]["driver_id"]
        pred_top3 = set(predictions.head(3)["driver_id"])
        pred_top5 = set(predictions.head(5)["driver_id"])

        if pred_winner == actual_winner:
            all_metrics["top1_correct"] += 1
        if actual_winner in pred_top3:
            all_metrics["top3_correct"] += 1
        if actual_winner in pred_top5:
            all_metrics["top5_correct"] += 1

        # Spearman correlation
        pred_order = predictions.set_index("driver_id")["predicted_position"]
        actual_pos = actual.set_index("driver_id")["finish_position"]
        common = pred_order.index.intersection(actual_pos.index)

        if len(common) > 2:
            corr, _ = spearmanr(
                pred_order.loc[common].values,
                actual_pos.loc[common].values,
            )
            all_metrics["spearman_correlations"].append(corr)

        # Mean position error
        for driver_id in common:
            pred_pos = pred_order.loc[driver_id]
            actual_p = actual_pos.loc[driver_id]
            all_metrics["position_errors"].append(abs(pred_pos - actual_p))

        # Capture per-driver probabilities + actual position for calibration.
        for _, pred_row in predictions.iterrows():
            did = pred_row["driver_id"]
            actual_row = actual[actual["driver_id"] == did]
            if actual_row.empty or pd.isna(actual_row.iloc[0].get("finish_position")):
                continue
            per_driver_records.append({
                "year": test_season,
                "round": round_num,
                "driver_id": did,
                "win_probability": float(pred_row.get("win_probability", 0.0)),
                "podium_probability": float(pred_row.get("podium_probability", 0.0)),
                "points_probability": float(pred_row.get("points_probability", 0.0)),
                "actual_position": int(actual_row.iloc[0]["finish_position"]),
            })

        all_metrics["races_evaluated"] += 1

        # Per-race record for stratified analysis
        race_row = storage.get_race(test_season, round_num) or {}
        circuit_id = race_row.get("circuit_id", "")
        weather_row = storage.get_weather(race_id, "R") or {}
        per_race_records.append({
            "year": test_season,
            "round": round_num,
            "race_name": race_name,
            "circuit_id": circuit_id,
            "is_wet": int(bool(weather_row.get("is_wet"))),
            "pred_winner": pred_winner,
            "actual_winner": actual_winner,
            "top1_correct": int(pred_winner == actual_winner),
            "top3_correct": int(actual_winner in pred_top3),
            "top5_correct": int(actual_winner in pred_top5),
            "spearman": float(corr) if len(common) > 2 else None,
            "mean_position_error": (
                float(np.mean([abs(pred_order.loc[d] - actual_pos.loc[d]) for d in common]))
                if len(common) > 0 else None
            ),
        })

        # Display individual race comparison
        logger.info(f"\nR{round_num} {race_name}:")
        logger.info(f"  Predicted winner: {pred_winner} | Actual: {actual_winner} | {'✓' if pred_winner == actual_winner else '✗'}")
        if len(common) > 2:
            logger.info(f"  Spearman correlation: {corr:.3f}")

    # Final summary
    n_races = all_metrics["races_evaluated"]
    if n_races == 0:
        logger.error("No races could be evaluated")
        return

    summary = {
        "races_evaluated": n_races,
        "top1_accuracy": all_metrics["top1_correct"] / n_races,
        "top3_accuracy": all_metrics["top3_correct"] / n_races,
        "top5_accuracy": all_metrics["top5_correct"] / n_races,
        "avg_spearman_correlation": (
            np.mean(all_metrics["spearman_correlations"])
            if all_metrics["spearman_correlations"] else 0.0
        ),
        "mean_position_error": (
            np.mean(all_metrics["position_errors"])
            if all_metrics["position_errors"] else 0.0
        ),
        "median_position_error": (
            np.median(all_metrics["position_errors"])
            if all_metrics["position_errors"] else 0.0
        ),
    }

    logger.info(f"\n{'='*50}")
    logger.info(f"BACKTEST RESULTS: {test_season}")
    logger.info(f"{'='*50}")
    display_metrics(summary)

    if calibration_plot:
        _write_calibration_plot(per_driver_records, calibration_plot, test_season)

    if fit_calibrator:
        from src.models.calibration import ProbabilityCalibrator
        cal = ProbabilityCalibrator()
        cal.fit(per_driver_records)
        cal.save(fit_calibrator)
        logger.info(f"Calibrator saved to {fit_calibrator}")
        summary["calibrator_path"] = fit_calibrator

    if stratify:
        stratified = _stratify_metrics(per_race_records, storage)
        logger.info("\nStratified metrics:")
        for bucket_name, bucket_metrics in stratified.items():
            logger.info(f"  {bucket_name}: {bucket_metrics}")
        summary["stratified"] = stratified

    if output_json:
        out_path = Path(output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "summary": summary,
            "per_race": per_race_records,
            "train_seasons": train_seasons,
            "test_season": test_season,
        }
        out_path.write_text(json.dumps(payload, indent=2, default=_json_default))
        logger.info(f"Metrics written to {out_path}")

    return summary


def _json_default(obj):
    """JSON encoder for numpy types."""
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not JSON serializable: {type(obj)}")


def _write_calibration_plot(records: list[dict], path: str, season: int):
    """Reliability diagram for win/podium/points probabilities."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — skipping calibration plot")
        return

    if not records:
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, (key, cutoff) in zip(axes, [
        ("win_probability", 1),
        ("podium_probability", 3),
        ("points_probability", 10),
    ]):
        probs = np.array([r[key] for r in records])
        outcomes = np.array([int(r["actual_position"] <= cutoff) for r in records])
        # Bin predictions into deciles and plot mean predicted vs observed.
        bins = np.linspace(0, 1, 11)
        idx = np.digitize(probs, bins) - 1
        xs, ys = [], []
        for b in range(10):
            mask = idx == b
            if mask.sum() < 3:
                continue
            xs.append(probs[mask].mean())
            ys.append(outcomes[mask].mean())
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="perfect")
        ax.plot(xs, ys, "o-", label=f"n={len(probs)}")
        ax.set_title(f"{key} (top {cutoff}) — {season}")
        ax.set_xlabel("predicted")
        ax.set_ylabel("observed")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.legend()
    fig.tight_layout()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100)
    plt.close(fig)
    logger.info(f"Calibration plot written to {out}")


def _stratify_metrics(records: list[dict], storage: Storage) -> dict:
    """Bucket per-race metrics by circuit type, weather, season position, sprint."""
    from src.features.circuit import _find_circuit_metadata

    def _agg(rows: list[dict]) -> dict:
        if not rows:
            return {"n": 0}
        n = len(rows)
        return {
            "n": n,
            "top1": sum(r["top1_correct"] for r in rows) / n,
            "top3": sum(r["top3_correct"] for r in rows) / n,
            "top5": sum(r["top5_correct"] for r in rows) / n,
            "spearman": float(np.mean([r["spearman"] for r in rows if r["spearman"] is not None])) if any(r["spearman"] is not None for r in rows) else None,
        }

    buckets: dict[str, list[dict]] = {}

    for r in records:
        meta = _find_circuit_metadata(r["circuit_id"])
        ctype = meta.get("type", "unknown") if meta else "unknown"
        buckets.setdefault(f"circuit_type:{ctype}", []).append(r)
        buckets.setdefault(f"wet:{bool(r['is_wet'])}", []).append(r)
        buckets.setdefault(
            "season_phase:early" if r["round"] <= 5 else "season_phase:rest", []
        ).append(r)

    return {k: _agg(v) for k, v in buckets.items()}


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Backtest F1 prediction model")
    parser.add_argument("--season", "-s", type=int, required=True,
                        help="Season to backtest on")
    parser.add_argument("--train-seasons", "-ts", nargs="+", type=int,
                        help="Seasons for training (default: all before test)")
    parser.add_argument("--db-path", default="data/f1_predict.db")
    parser.add_argument("--output-json", default=None,
                        help="Write metrics JSON to this path (e.g. reports/baseline.json)")
    parser.add_argument("--stratify", action="store_true",
                        help="Break out metrics by circuit type, weather, season phase")
    parser.add_argument("--fit-calibrator", default=None,
                        help="Fit isotonic calibrator on this run and save to path")
    parser.add_argument("--calibration-plot", default=None,
                        help="Write reliability diagrams PNG to this path")
    args = parser.parse_args()

    storage = Storage(db_path=args.db_path)
    train_seasons = args.train_seasons or list(range(2022, args.season))

    run_backtest(
        storage, {}, train_seasons, args.season,
        output_json=args.output_json, stratify=args.stratify,
        fit_calibrator=args.fit_calibrator,
        calibration_plot=args.calibration_plot,
    )
