"""Optuna TPE hyperparameter search over time-series CV folds.

Scored by mean top-3 accuracy — matches the business metric the user
cares about. Falls back gracefully if Optuna isn't installed.
"""

import logging
from typing import Callable

import numpy as np
import pandas as pd

try:
    import optuna
    _OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None
    _OPTUNA_AVAILABLE = False

from src.models.lightgbm_model import LightGBMRanker, _podium_label_gain
from src.models.xgboost_model import XGBoostRanker

logger = logging.getLogger(__name__)


def _cv_score(model_factory: Callable, X_by_season: dict, y_by_season: dict,
              groups_by_season: dict, seasons: list[int]) -> float:
    """Mean top-3 accuracy across expanding-window folds."""
    seasons = sorted(seasons)
    top3s: list[float] = []

    for k in range(1, len(seasons)):
        train_seasons = seasons[:k]
        val_season = seasons[k]
        X_tr = pd.concat([X_by_season[s] for s in train_seasons], ignore_index=True)
        y_tr = pd.concat([y_by_season[s] for s in train_seasons], ignore_index=True)
        groups_tr: list[int] = []
        for s in train_seasons:
            groups_tr.extend(groups_by_season[s])

        X_vl = X_by_season[val_season]
        y_vl = y_by_season[val_season]
        groups_vl = groups_by_season[val_season]

        model = model_factory()
        model.train(X_tr, y_tr, groups_tr)
        scores = model.predict(X_vl)

        correct = 0
        n = 0
        offset = 0
        for g in groups_vl:
            if offset + g > len(scores):
                break
            race_scores = scores[offset:offset + g]
            race_positions = y_vl.iloc[offset:offset + g].values
            actual_winner = int(np.argmin(race_positions))
            pred_top3 = set(np.argsort(race_scores)[-3:])
            if actual_winner in pred_top3:
                correct += 1
            n += 1
            offset += g
        if n:
            top3s.append(correct / n)

    return float(np.mean(top3s)) if top3s else 0.0


def tune_lightgbm(X_by_season: dict, y_by_season: dict,
                   groups_by_season: dict, seasons: list[int],
                   n_trials: int = 40) -> dict:
    if not _OPTUNA_AVAILABLE:
        logger.warning("Optuna not installed — returning default LightGBM params")
        return LightGBMRanker()._default_params()

    def objective(trial):
        params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [3, 5, 10],
            "lambdarank_truncation_level": 5,
            "label_gain": _podium_label_gain(max_drivers=22),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 31, 255),
            "min_child_samples": trial.suggest_int("min_child_samples", 4, 20),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 1.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 200, 800),
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        }
        return _cv_score(
            lambda: LightGBMRanker(params=params),
            X_by_season, y_by_season, groups_by_season, seasons,
        )

    study = optuna.create_study(direction="maximize",
                                 sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = {**LightGBMRanker()._default_params(), **study.best_params}
    logger.info(f"Best LightGBM top-3 acc: {study.best_value:.4f}")
    return best


def tune_xgboost(X_by_season: dict, y_by_season: dict,
                  groups_by_season: dict, seasons: list[int],
                  n_trials: int = 40) -> dict:
    if not _OPTUNA_AVAILABLE:
        logger.warning("Optuna not installed — returning default XGBoost params")
        return XGBoostRanker()._default_params()

    def objective(trial):
        params = {
            "objective": "rank:pairwise",
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "n_estimators": trial.suggest_int("n_estimators", 200, 800),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 15),
            "gamma": trial.suggest_float("gamma", 0.0, 0.5),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 1.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
            "random_state": 42,
            "n_jobs": -1,
        }
        return _cv_score(
            lambda: XGBoostRanker(params=params),
            X_by_season, y_by_season, groups_by_season, seasons,
        )

    study = optuna.create_study(direction="maximize",
                                 sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = {**XGBoostRanker()._default_params(), **study.best_params}
    logger.info(f"Best XGBoost top-3 acc: {study.best_value:.4f}")
    return best
