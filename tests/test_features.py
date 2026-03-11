"""Tests for feature extraction modules."""

import pytest
import pandas as pd

from src.data.storage import Storage
from src.features.practice import extract_practice_features
from src.features.driver import extract_driver_features, update_elo
from src.features.team import extract_team_features
from src.features.circuit import extract_circuit_features, CIRCUIT_METADATA
from src.features.weather_features import extract_weather_features
from src.features.strategy import extract_strategy_features
from src.features.news_features import extract_news_features
from src.features.builder import FeatureBuilder, FEATURE_COLUMNS


@pytest.fixture
def storage(tmp_path):
    """Create a temporary storage instance with test data."""
    db_path = str(tmp_path / "test.db")
    s = Storage(db_path=db_path)

    # Insert test race
    race_id = s.save_race(
        year=2024, round_num=1, name="Bahrain Grand Prix",
        circuit_id="bahrain", date="2024-03-02",
        circuit_name="Bahrain International Circuit",
        country="Bahrain", latitude=26.0325, longitude=50.5106,
    )

    # Insert test results
    s.save_result(race_id, "VER", "Max Verstappen", "Red Bull",
                  grid_position=1, finish_position=1, status="Finished", points=25)
    s.save_result(race_id, "LEC", "Charles Leclerc", "Ferrari",
                  grid_position=2, finish_position=2, status="Finished", points=18)
    s.save_result(race_id, "NOR", "Lando Norris", "McLaren",
                  grid_position=4, finish_position=3, status="Finished", points=15)
    s.save_result(race_id, "PER", "Sergio Perez", "Red Bull",
                  grid_position=3, finish_position=5, status="Finished", points=10)

    # Insert test FP data
    s.save_fp_session(race_id, "FP1", "VER", "Max Verstappen", "Red Bull", {
        "best_lap_time": 90.5, "median_lap_time": 91.2, "lap_count": 25,
        "consistency_stddev": 0.3, "long_run_pace": 92.0,
        "long_run_degradation": 0.05, "short_run_pace": 90.5,
        "sector1_best": 28.5, "sector2_best": 35.0, "sector3_best": 27.0,
        "speed_trap_max": 320.0, "compound_soft_pace": 90.5,
        "compound_medium_pace": 91.5, "compound_hard_pace": 92.5,
    })
    s.save_fp_session(race_id, "FP1", "LEC", "Charles Leclerc", "Ferrari", {
        "best_lap_time": 90.8, "median_lap_time": 91.5, "lap_count": 22,
        "consistency_stddev": 0.4, "long_run_pace": 92.3,
        "long_run_degradation": 0.06, "short_run_pace": 90.8,
        "sector1_best": 28.7, "sector2_best": 35.1, "sector3_best": 27.0,
        "speed_trap_max": 318.0, "compound_soft_pace": 90.8,
        "compound_medium_pace": 91.8, "compound_hard_pace": None,
    })

    # Insert weather
    s.save_weather(race_id, "FP1", {
        "air_temp": 28.0, "track_temp": 42.0, "humidity": 45.0,
        "wind_speed": 8.0, "wind_direction": 180.0,
        "rain_probability": 0.0, "is_wet": 0,
    })
    s.save_weather(race_id, "R", {
        "air_temp": 30.0, "track_temp": 45.0, "humidity": 40.0,
        "wind_speed": 6.0, "wind_direction": 200.0,
        "rain_probability": 0.0, "is_wet": 0,
    })

    # Insert standings
    s.save_standings(2024, 0, "VER", "Max Verstappen", "Red Bull", 0, 1, 0)
    s.save_standings(2024, 0, "LEC", "Charles Leclerc", "Ferrari", 0, 2, 0)

    # Insert circuit
    s.save_circuit("bahrain", "Bahrain International Circuit", "Bahrain",
                   26.0325, 50.5106, 5.412, 15, 3, 7, "technical", "high", 0.5)

    return s


class TestPracticeFeatures:
    def test_extract_basic_features(self, storage):
        race_id = storage.get_race_id(2024, 1)
        features = extract_practice_features(storage, race_id, "VER", ["FP1"])

        assert "fp1_best_lap_delta" in features
        assert features["fp1_best_lap_delta"] == 0.0  # VER is the leader
        assert features["fp1_lap_count"] == 25

    def test_leader_has_zero_delta(self, storage):
        race_id = storage.get_race_id(2024, 1)
        features = extract_practice_features(storage, race_id, "VER", ["FP1"])
        assert features["fp1_best_lap_delta"] == 0.0

    def test_non_leader_has_positive_delta(self, storage):
        race_id = storage.get_race_id(2024, 1)
        features = extract_practice_features(storage, race_id, "LEC", ["FP1"])
        assert features["fp1_best_lap_delta"] > 0

    def test_missing_session_returns_empty(self, storage):
        race_id = storage.get_race_id(2024, 1)
        features = extract_practice_features(storage, race_id, "VER", ["FP3"])
        # Should still return dict but may be sparse
        assert isinstance(features, dict)


class TestDriverFeatures:
    def test_extract_basic_features(self, storage):
        features = extract_driver_features(
            storage, "VER", "Red Bull", 2024, 1, "bahrain"
        )
        assert "driver_elo" in features
        assert "driver_recent_form" in features
        assert "driver_circuit_history" in features

    def test_default_values(self, storage):
        # Unknown driver should get defaults
        features = extract_driver_features(
            storage, "UNKNOWN", "Unknown Team", 2024, 1, "bahrain"
        )
        assert features["driver_elo"] == 1500.0
        assert features["driver_recent_form"] == 10.0

    def test_elo_update(self, storage):
        race_id = storage.get_race_id(2024, 1)
        update_elo(storage, race_id, 2024, 1)

        ver_elo = storage.get_latest_elo("driver", "VER")
        lec_elo = storage.get_latest_elo("driver", "LEC")

        # Winner should have higher Elo than P2
        assert ver_elo > lec_elo


class TestTeamFeatures:
    def test_extract_basic_features(self, storage):
        features = extract_team_features(storage, "Red Bull", 2024, 1)

        assert "team_elo" in features
        assert "team_constructor_pos" in features
        assert "team_pit_stop_avg" in features
        assert "team_reliability_score" in features


class TestCircuitFeatures:
    def test_extract_known_circuit(self, storage):
        features = extract_circuit_features(storage, "bahrain")

        assert features["circuit_corners"] == 15
        assert features["circuit_drs_zones"] == 3
        assert features["circuit_type"] == 1  # technical

    def test_circuit_metadata_coverage(self):
        # Ensure we have metadata for major circuits
        assert "monza" in CIRCUIT_METADATA
        assert "silverstone" in CIRCUIT_METADATA
        assert "monaco" in CIRCUIT_METADATA
        assert "spa" in CIRCUIT_METADATA

    def test_unknown_circuit_defaults(self, storage):
        features = extract_circuit_features(storage, "unknown_circuit_xyz")
        assert "circuit_type" in features
        assert "circuit_corners" in features


class TestWeatherFeatures:
    def test_extract_features(self, storage):
        race_id = storage.get_race_id(2024, 1)
        features = extract_weather_features(storage, race_id)

        assert features["race_temp_air"] == 30.0
        assert features["race_is_wet"] == 0
        assert "race_temp_delta_fp" in features
        assert "race_is_night" in features

    def test_night_race_detection(self, storage):
        race_id = storage.get_race_id(2024, 1)
        features = extract_weather_features(storage, race_id)
        assert features["race_is_night"] == 1  # Bahrain is a night race


class TestStrategyFeatures:
    def test_extract_features(self, storage):
        race_id = storage.get_race_id(2024, 1)
        features = extract_strategy_features(storage, race_id, "VER", ["FP1"])

        assert "tyre_deg_relative" in features
        assert "expected_pit_stops" in features
        assert "optimal_compound_advantage" in features


class TestNewsFeatures:
    def test_no_upgrades_defaults(self, storage):
        features = extract_news_features(storage, "Red Bull", "2024-03-02")

        assert features["upgrade_impact_score"] == 0.0
        assert features["upgrade_sentiment"] == 0.0

    def test_with_upgrade_data(self, storage):
        storage.save_upgrade(
            team="Red Bull", date="2024-02-28", component="floor",
            impact_score=0.15, confidence="confirmed", sentiment=0.7,
            summary="New floor edge design", source_url="", source_name="test",
        )

        features = extract_news_features(storage, "Red Bull", "2024-03-02")
        assert features["upgrade_impact_score"] == 0.15
        assert features["upgrade_sentiment"] == 0.7


class TestFeatureBuilder:
    def test_build_race_features(self, storage):
        builder = FeatureBuilder(storage)

        drivers = [
            {"driver_id": "VER", "driver_name": "Max Verstappen", "team": "Red Bull"},
            {"driver_id": "LEC", "driver_name": "Charles Leclerc", "team": "Ferrari"},
        ]

        df = builder.build_race_features(2024, 1, drivers, ["FP1"])

        assert len(df) == 2
        assert "driver_id" in df.columns

        # Check all feature columns exist
        for col in FEATURE_COLUMNS:
            assert col in df.columns, f"Missing feature column: {col}"

    def test_feature_columns_count(self):
        # Verify we have the expected number of features
        assert len(FEATURE_COLUMNS) > 50, "Should have 50+ features"
