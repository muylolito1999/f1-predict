"""Ensemble combiner for ranking models."""

import logging

import numpy as np
import pandas as pd
from scipy.special import softmax

logger = logging.getLogger(__name__)


class RankingEnsemble:
    """Combines predictions from multiple ranking models."""

    def __init__(self, weights: dict[str, float] = None):
        self.weights = weights or {
            "xgboost": 0.45,
            "lightgbm": 0.45,
            "neural": 0.10,
        }
        self.models = {}

    def add_model(self, name: str, model):
        """Register a model for the ensemble."""
        self.models[name] = model

    def predict(self, X: pd.DataFrame,
                driver_ids: list[str],
                driver_names: list[str] = None,
                teams: list[str] = None) -> pd.DataFrame:
        """Generate ensemble prediction for a race.

        Returns DataFrame with predicted positions and win probabilities.
        """
        if not self.models:
            raise RuntimeError("No models registered. Call add_model() first.")

        all_scores = {}
        total_weight = 0

        for name, model in self.models.items():
            weight = self.weights.get(name, 0.0)
            if weight <= 0:
                continue

            try:
                scores = model.predict(X)
                # Normalize scores to [0, 1] range
                scores_norm = (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)
                all_scores[name] = scores_norm * weight
                total_weight += weight
            except Exception as e:
                logger.warning(f"Model {name} prediction failed: {e}")
                continue

        if not all_scores:
            raise RuntimeError("All model predictions failed")

        # Weighted average of normalized scores
        combined = np.zeros(len(driver_ids))
        for scores in all_scores.values():
            combined += scores
        combined /= total_weight

        # Build result DataFrame
        result = pd.DataFrame({
            "driver_id": driver_ids,
            "ensemble_score": combined,
        })

        if driver_names:
            result["driver_name"] = driver_names
        if teams:
            result["team"] = teams

        # Sort by score (higher = better position)
        result = result.sort_values("ensemble_score", ascending=False).reset_index(drop=True)
        result["predicted_position"] = range(1, len(result) + 1)

        # Win probabilities from softmax of scores
        probs = softmax(combined * 5)  # Temperature scaling
        # Re-sort probabilities to match result order
        prob_map = dict(zip(driver_ids, probs))
        result["win_probability"] = result["driver_id"].map(prob_map)

        # Podium probability (top 3)
        result["podium_probability"] = self._compute_position_probability(
            combined, driver_ids, result, top_n=3
        )

        # Points probability (top 10)
        result["points_probability"] = self._compute_position_probability(
            combined, driver_ids, result, top_n=10
        )

        return result

    def _compute_position_probability(self, scores: np.ndarray,
                                       driver_ids: list[str],
                                       result: pd.DataFrame,
                                       top_n: int) -> list[float]:
        """Estimate probability of finishing in top N.

        Uses a simple approach based on score gaps.
        """
        sorted_scores = result["ensemble_score"].values
        probs = []

        for i in range(len(sorted_scores)):
            if i < top_n:
                # Above the cutoff: probability decreases further from boundary
                gap = sorted_scores[i] - (sorted_scores[top_n] if top_n < len(sorted_scores) else 0)
                prob = min(0.95, 0.5 + gap * 2)
            else:
                # Below the cutoff: probability increases closer to boundary
                gap = (sorted_scores[top_n - 1] if top_n > 0 else 1.0) - sorted_scores[i]
                prob = max(0.05, 0.5 - gap * 2)
            probs.append(prob)

        return probs

    def optimize_weights(self, predictions: list[dict],
                          actual_positions: list[dict]):
        """Optimize ensemble weights based on recent prediction accuracy.

        Args:
            predictions: List of per-model prediction dicts.
            actual_positions: List of actual race results.
        """
        from scipy.stats import spearmanr

        best_weights = self.weights.copy()
        best_corr = -1

        # Grid search over weight combinations
        for w1 in np.arange(0.1, 0.9, 0.1):
            for w2 in np.arange(0.1, 0.9 - w1, 0.1):
                w3 = 1.0 - w1 - w2
                if w3 < 0:
                    continue

                weights = {"xgboost": w1, "lightgbm": w2, "neural": w3}

                # Evaluate with these weights
                corrs = []
                for pred, actual in zip(predictions, actual_positions):
                    combined = np.zeros(len(pred.get("xgboost", [])))
                    for name, w in weights.items():
                        if name in pred:
                            combined += np.array(pred[name]) * w

                    actual_arr = np.array(actual)
                    if len(combined) == len(actual_arr) and len(combined) > 2:
                        corr, _ = spearmanr(combined, actual_arr)
                        corrs.append(corr)

                if corrs:
                    avg_corr = np.mean(corrs)
                    if avg_corr > best_corr:
                        best_corr = avg_corr
                        best_weights = weights

        self.weights = best_weights
        logger.info(f"Optimized ensemble weights: {best_weights} (corr={best_corr:.3f})")

    def get_model_contributions(self, X: pd.DataFrame) -> dict[str, np.ndarray]:
        """Get individual model predictions for analysis."""
        contributions = {}
        for name, model in self.models.items():
            try:
                contributions[name] = model.predict(X)
            except Exception:
                continue
        return contributions
