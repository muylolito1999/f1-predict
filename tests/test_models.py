"""Tests for ML model components."""

import pytest
import numpy as np
import pandas as pd

from src.models.xgboost_model import XGBoostRanker
from src.models.lightgbm_model import LightGBMRanker
from src.models.ensemble import RankingEnsemble
from src.models.bayesian_updater import BayesianUpdater, TeamPrior
from src.data.storage import Storage


def _make_synthetic_data(n_races: int = 10, n_drivers: int = 20,
                          n_features: int = 10):
    """Create synthetic training data for testing."""
    np.random.seed(42)
    total = n_races * n_drivers

    X = pd.DataFrame(
        np.random.randn(total, n_features),
        columns=[f"feature_{i}" for i in range(n_features)],
    )

    # Target: positions 1 to n_drivers, repeated per race
    y = pd.Series(np.tile(np.arange(1, n_drivers + 1), n_races), dtype=float)

    # Groups: n_drivers per race
    groups = [n_drivers] * n_races

    return X, y, groups


class TestXGBoostRanker:
    def test_train_and_predict(self):
        model = XGBoostRanker({"objective": "rank:pairwise",
                                "n_estimators": 10,
                                "max_depth": 3})
        X, y, groups = _make_synthetic_data()

        model.train(X, y, groups)
        scores = model.predict(X[:20])

        assert len(scores) == 20
        assert not np.any(np.isnan(scores))

    def test_predict_race(self):
        model = XGBoostRanker({"objective": "rank:pairwise",
                                "n_estimators": 10,
                                "max_depth": 3})
        X, y, groups = _make_synthetic_data()
        model.train(X, y, groups)

        driver_ids = [f"DRV{i}" for i in range(20)]
        result = model.predict_race(X[:20], driver_ids)

        assert len(result) == 20
        assert "predicted_position" in result.columns
        assert list(result["predicted_position"]) == list(range(1, 21))

    def test_feature_importance(self):
        model = XGBoostRanker({"objective": "rank:pairwise",
                                "n_estimators": 10})
        X, y, groups = _make_synthetic_data()
        model.train(X, y, groups)

        importance = model.get_feature_importance(list(X.columns))
        assert not importance.empty
        assert len(importance) == X.shape[1]

    def test_save_load(self, tmp_path):
        model = XGBoostRanker({"objective": "rank:pairwise",
                                "n_estimators": 10})
        X, y, groups = _make_synthetic_data()
        model.train(X, y, groups)

        path = str(tmp_path / "model.joblib")
        model.save(path)

        model2 = XGBoostRanker()
        model2.load(path)

        scores1 = model.predict(X[:5])
        scores2 = model2.predict(X[:5])
        np.testing.assert_array_almost_equal(scores1, scores2)


class TestLightGBMRanker:
    def test_train_and_predict(self):
        model = LightGBMRanker({"objective": "lambdarank",
                                 "n_estimators": 10,
                                 "num_leaves": 15,
                                 "verbose": -1})
        X, y, groups = _make_synthetic_data()

        model.train(X, y, groups)
        scores = model.predict(X[:20])

        assert len(scores) == 20
        assert not np.any(np.isnan(scores))


class TestRankingEnsemble:
    def test_predict(self):
        X, y, groups = _make_synthetic_data()

        xgb = XGBoostRanker({"objective": "rank:pairwise", "n_estimators": 10})
        xgb.train(X, y, groups)

        lgb = LightGBMRanker({"objective": "lambdarank", "n_estimators": 10,
                                "verbose": -1, "num_leaves": 15})
        lgb.train(X, y, groups)

        ensemble = RankingEnsemble(weights={"xgboost": 0.5, "lightgbm": 0.5})
        ensemble.add_model("xgboost", xgb)
        ensemble.add_model("lightgbm", lgb)

        driver_ids = [f"DRV{i}" for i in range(20)]
        result = ensemble.predict(X[:20], driver_ids)

        assert len(result) == 20
        assert "predicted_position" in result.columns
        assert "win_probability" in result.columns
        assert result["win_probability"].sum() > 0

    def test_probabilities_sum_to_one(self):
        X, y, groups = _make_synthetic_data()

        xgb = XGBoostRanker({"objective": "rank:pairwise", "n_estimators": 10})
        xgb.train(X, y, groups)

        ensemble = RankingEnsemble()
        ensemble.add_model("xgboost", xgb)

        driver_ids = [f"DRV{i}" for i in range(20)]
        result = ensemble.predict(X[:20], driver_ids)

        total_prob = result["win_probability"].sum()
        assert abs(total_prob - 1.0) < 0.01


class TestBayesianUpdater:
    def test_initialize_regulation_year(self, tmp_path):
        storage = Storage(db_path=str(tmp_path / "test.db"))
        updater = BayesianUpdater(storage)

        teams = ["Red Bull", "Ferrari", "McLaren"]
        updater.initialize_season(2026, teams)

        assert updater.state.regulation_year is True
        assert updater.state.fp_weight_boost > 1.0

        for team in teams:
            assert updater.get_team_uncertainty(team) > 100

    def test_initialize_normal_year(self, tmp_path):
        storage = Storage(db_path=str(tmp_path / "test.db"))
        updater = BayesianUpdater(storage)

        teams = ["Red Bull", "Ferrari"]
        updater.initialize_season(2024, teams)

        assert updater.state.regulation_year is False

    def test_update_reduces_uncertainty(self, tmp_path):
        storage = Storage(db_path=str(tmp_path / "test.db"))
        updater = BayesianUpdater(storage)

        updater.initialize_season(2026, ["Red Bull", "Ferrari"])
        initial_var = updater.get_team_uncertainty("Red Bull")

        updater.update_after_race({"Red Bull": 1, "Ferrari": 3})
        after_var = updater.get_team_uncertainty("Red Bull")

        assert after_var < initial_var

    def test_fp_weight_decreases_over_season(self, tmp_path):
        storage = Storage(db_path=str(tmp_path / "test.db"))
        updater = BayesianUpdater(storage, cold_start_races=5)

        updater.initialize_season(2026, ["Red Bull"])
        initial_boost = updater.get_fp_weight_boost()

        for i in range(5):
            updater.update_after_race({"Red Bull": 1})

        final_boost = updater.get_fp_weight_boost()
        assert final_boost < initial_boost
        assert final_boost == pytest.approx(1.0, abs=0.1)

    def test_confidence_levels(self, tmp_path):
        storage = Storage(db_path=str(tmp_path / "test.db"))
        updater = BayesianUpdater(storage, cold_start_races=5)

        updater.initialize_season(2026, ["Red Bull"])
        assert updater.get_confidence_level() == "VERY LOW"

        updater.update_after_race({"Red Bull": 1})
        assert updater.get_confidence_level() == "LOW"

        for _ in range(4):
            updater.update_after_race({"Red Bull": 1})
        assert updater.get_confidence_level() == "HIGH"
