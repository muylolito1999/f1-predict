"""Ensemble combiner for ranking models."""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.special import softmax
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


class RankingEnsemble:
    """Combines predictions from multiple ranking models."""

    def __init__(self, weights: dict[str, float] = None):
        # Default: roughly equal weight across 4 genuinely different
        # ranking formulations. Stacking meta-learner (Phase 2.3) can
        # override these per fold.
        self.weights = weights or {
            "xgboost": 0.30,
            "lightgbm": 0.30,
            "catboost": 0.25,
            "neural": 0.15,
        }
        self.models = {}
        self.stacker = None  # Set by fit_stacker (Phase 2.3)
        self._stacker_feature_order: list[str] = []
        self._stacker_raw_cols: list[str] = []

    def add_model(self, name: str, model):
        """Register a model for the ensemble."""
        self.models[name] = model

    def predict(self, X: pd.DataFrame,
                driver_ids: list[str],
                driver_names: list[str] = None,
                teams: list[str] = None,
                simulator=None,
                dnf_rates: np.ndarray | None = None,
                sc_probability: float = 0.35) -> pd.DataFrame:
        """Generate ensemble prediction for a race.

        Returns DataFrame with predicted positions and win probabilities.

        If `simulator` is provided (a RaceSimulator), win/podium/points
        probabilities and p10/p90 finish ranges come from Monte Carlo;
        otherwise the old softmax/gap heuristics are used.
        """
        if not self.models:
            raise RuntimeError("No models registered. Call add_model() first.")

        raw_scores = {}  # name -> raw np array
        for name, model in self.models.items():
            try:
                s = model.predict(X)
                if s is None or len(s) != len(driver_ids):
                    continue
                raw_scores[name] = np.asarray(s, dtype=np.float64)
            except Exception as e:
                logger.warning(f"Model {name} prediction failed: {e}")
                continue

        if not raw_scores:
            raise RuntimeError("All model predictions failed")

        # Phase 2.3: stacking meta-learner if fitted, else weighted average.
        if self.stacker is not None:
            combined = self._stacker_predict(raw_scores, X)
        else:
            combined = np.zeros(len(driver_ids), dtype=np.float64)
            total_weight = 0.0
            for name, scores in raw_scores.items():
                w = self.weights.get(name, 0.0)
                if w <= 0:
                    continue
                denom = scores.max() - scores.min() + 1e-10
                scores_norm = (scores - scores.min()) / denom
                combined += scores_norm * w
                total_weight += w
            if total_weight > 0:
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

        if simulator is not None:
            sim = simulator.simulate(
                scores=combined, driver_ids=driver_ids,
                dnf_rates=dnf_rates, sc_probability=sc_probability,
            )
            sim_map = {
                did: (
                    float(sim["win_probability"][i]),
                    float(sim["podium_probability"][i]),
                    float(sim["points_probability"][i]),
                    float(sim["expected_position"][i]),
                    float(sim["position_p10"][i]),
                    float(sim["position_p90"][i]),
                )
                for i, did in enumerate(driver_ids)
            }
            result["win_probability"] = result["driver_id"].map(lambda d: sim_map[d][0])
            result["podium_probability"] = result["driver_id"].map(lambda d: sim_map[d][1])
            result["points_probability"] = result["driver_id"].map(lambda d: sim_map[d][2])
            result["expected_position"] = result["driver_id"].map(lambda d: sim_map[d][3])
            result["position_p10"] = result["driver_id"].map(lambda d: sim_map[d][4])
            result["position_p90"] = result["driver_id"].map(lambda d: sim_map[d][5])
            result.attrs["simulated_positions"] = sim["simulated_positions"]
        else:
            # Legacy heuristic path retained for back-compat.
            probs = softmax(combined * 5)
            prob_map = dict(zip(driver_ids, probs))
            result["win_probability"] = result["driver_id"].map(prob_map)
            result["podium_probability"] = self._compute_position_probability(
                combined, driver_ids, result, top_n=3
            )
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

    # ------------------------------------------------------------------
    # Phase 2.3: stacking meta-learner
    # ------------------------------------------------------------------

    def fit_stacker(self, oof_predictions: dict, raw_feature_cols: list[str] | None = None):
        """Fit a stacking meta-learner on out-of-fold predictions.

        Args:
            oof_predictions: dict mapping val_season -> {
                "xgboost": [...], "lightgbm": [...], "y_true": [...],
                "groups": [...],
                "raw_features": optional DataFrame with raw feature columns.
            }
            raw_feature_cols: optional list of raw feature names to blend
                with base-model scores at the meta stage.

        The meta-learner is a logistic regression predicting P(win) per
        driver within a race. Meta-features are per-model z-scored base
        scores plus a small set of raw features (grid, circuit_type, etc.).
        """
        X_meta: list[np.ndarray] = []
        y_meta: list[int] = []
        model_names = [n for n in ("xgboost", "lightgbm", "catboost", "neural")
                       if any(n in s for s in oof_predictions.values())]

        if not model_names:
            logger.warning("No base-model scores in oof_predictions; skipping stacker fit")
            return

        self._stacker_feature_order = list(model_names)
        self._stacker_raw_cols = list(raw_feature_cols) if raw_feature_cols else []

        for season, data in oof_predictions.items():
            groups = data.get("groups") or []
            y_true = np.asarray(data.get("y_true", []), dtype=np.float64)
            if not groups or not len(y_true):
                continue

            raw_df = data.get("raw_features")
            raw_arr = None
            if raw_df is not None and self._stacker_raw_cols:
                raw_arr = raw_df[self._stacker_raw_cols].fillna(0.0).values

            offset = 0
            for g in groups:
                if offset + g > len(y_true):
                    break
                # Per-race normalization of each base-model's scores.
                features = []
                for name in model_names:
                    s = np.asarray(data[name][offset:offset + g], dtype=np.float64)
                    s = (s - s.mean()) / (s.std() + 1e-9)
                    features.append(s)

                meta = np.vstack(features).T  # (g, n_models)
                if raw_arr is not None:
                    meta = np.hstack([meta, raw_arr[offset:offset + g]])

                # Label: P1 driver = 1, others = 0.
                positions = y_true[offset:offset + g]
                labels = (positions == positions.min()).astype(int)

                X_meta.append(meta)
                y_meta.extend(labels.tolist())
                offset += g

        if not X_meta:
            logger.warning("No stacker training rows; skipping")
            return

        X_meta_arr = np.vstack(X_meta)
        y_meta_arr = np.asarray(y_meta)
        if y_meta_arr.sum() == 0 or y_meta_arr.sum() == len(y_meta_arr):
            logger.warning("Degenerate labels for stacker; skipping")
            return

        self.stacker = LogisticRegression(max_iter=200, C=1.0)
        self.stacker.fit(X_meta_arr, y_meta_arr)
        logger.info(
            f"Stacker fit on {len(X_meta_arr)} rows across "
            f"{len(model_names)} base models"
        )

    def _stacker_predict(self, raw_scores: dict, X: pd.DataFrame) -> np.ndarray:
        """Produce stacked ranking scores for a single race."""
        feat_cols: list[np.ndarray] = []
        for name in self._stacker_feature_order:
            s = raw_scores.get(name)
            if s is None:
                s = np.zeros(len(X))
            s = (s - s.mean()) / (s.std() + 1e-9)
            feat_cols.append(s)
        meta = np.vstack(feat_cols).T
        if self._stacker_raw_cols:
            raw = X[self._stacker_raw_cols].fillna(0.0).values
            meta = np.hstack([meta, raw])
        # Probability of being P1; acts as the ranking score.
        return self.stacker.predict_proba(meta)[:, 1]

    def save_stacker(self, path: str):
        if self.stacker is None:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "stacker": self.stacker,
            "feature_order": self._stacker_feature_order,
            "raw_cols": self._stacker_raw_cols,
        }, path)

    def load_stacker(self, path: str):
        data = joblib.load(path)
        self.stacker = data["stacker"]
        self._stacker_feature_order = data["feature_order"]
        self._stacker_raw_cols = data["raw_cols"]
