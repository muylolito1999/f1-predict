"""Backtesting script for model evaluation.

Walk-forward backtesting: for each race in the test season,
train on all prior data and predict.
"""

import logging
import sys

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
                  train_seasons: list[int], test_season: int):
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

        all_metrics["races_evaluated"] += 1

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

    return summary


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
    args = parser.parse_args()

    storage = Storage(db_path=args.db_path)
    train_seasons = args.train_seasons or list(range(2022, args.season))

    run_backtest(storage, {}, train_seasons, args.season)
