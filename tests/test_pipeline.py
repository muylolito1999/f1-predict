"""Tests for storage and data pipeline components."""

import pytest
import pandas as pd

from src.data.storage import Storage


@pytest.fixture
def storage(tmp_path):
    """Create a temporary storage instance."""
    return Storage(db_path=str(tmp_path / "test.db"))


class TestStorage:
    def test_create_schema(self, storage):
        """Schema should be created on init."""
        with storage._connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}

        expected = {"races", "results", "fp_sessions", "weather",
                    "standings", "constructor_standings", "upgrades",
                    "elo_ratings", "pit_stops", "circuits"}
        assert expected.issubset(table_names)

    def test_save_and_get_race(self, storage):
        race_id = storage.save_race(
            year=2024, round_num=1, name="Bahrain GP",
            circuit_id="bahrain", date="2024-03-02",
        )

        race = storage.get_race(2024, 1)
        assert race is not None
        assert race["name"] == "Bahrain GP"
        assert race["id"] == race_id

    def test_save_and_get_results(self, storage):
        race_id = storage.save_race(
            year=2024, round_num=1, name="Bahrain GP",
            circuit_id="bahrain", date="2024-03-02",
        )

        storage.save_result(race_id, "VER", "Max Verstappen", "Red Bull",
                            1, 1, "Finished", 25.0)
        storage.save_result(race_id, "LEC", "Charles Leclerc", "Ferrari",
                            2, 2, "Finished", 18.0)

        results = storage.get_results(race_id)
        assert len(results) == 2
        assert results.iloc[0]["driver_id"] == "VER"

    def test_upsert_race(self, storage):
        """Save race twice should update, not duplicate."""
        storage.save_race(year=2024, round_num=1, name="Bahrain GP",
                          circuit_id="bahrain", date="2024-03-02")
        storage.save_race(year=2024, round_num=1, name="Bahrain Grand Prix",
                          circuit_id="bahrain", date="2024-03-02")

        races = storage.get_races_for_season(2024)
        assert len(races) == 1
        assert races[0]["name"] == "Bahrain Grand Prix"

    def test_fp_session_data(self, storage):
        race_id = storage.save_race(
            year=2024, round_num=1, name="Test GP",
            circuit_id="test", date="2024-01-01",
        )

        storage.save_fp_session(race_id, "FP1", "VER", "Max Verstappen",
                                "Red Bull", {"best_lap_time": 90.5, "lap_count": 25})

        fp_data = storage.get_fp_data(race_id, "FP1")
        assert len(fp_data) == 1
        assert fp_data.iloc[0]["best_lap_time"] == 90.5

    def test_elo_ratings(self, storage):
        storage.save_elo("driver", "VER", 2024, 1, 1550.0)
        storage.save_elo("driver", "VER", 2024, 2, 1560.0)

        latest = storage.get_latest_elo("driver", "VER")
        assert latest == 1560.0

    def test_default_elo(self, storage):
        elo = storage.get_latest_elo("driver", "UNKNOWN")
        assert elo == 1500.0

    def test_driver_results_at_circuit(self, storage):
        race_id = storage.save_race(
            year=2024, round_num=1, name="Test GP",
            circuit_id="test_circuit", date="2024-01-01",
        )
        storage.save_result(race_id, "VER", "Max Verstappen", "Red Bull",
                            1, 1, "Finished", 25.0)

        results = storage.get_driver_results_at_circuit("VER", "test_circuit")
        assert len(results) == 1

    def test_standings(self, storage):
        storage.save_standings(2024, 5, "VER", "Max Verstappen", "Red Bull",
                               125.0, 1, 4)

        standings = storage.get_standings_before_race(2024, 6)
        assert len(standings) == 1
        assert standings.iloc[0]["points"] == 125.0

    def test_upgrades(self, storage):
        storage.save_upgrade(
            team="Red Bull", date="2024-05-01", component="floor",
            impact_score=0.15, confidence="confirmed", sentiment=0.7,
            summary="New floor", source_url="http://test.com",
            source_name="Test",
        )

        upgrades = storage.get_team_upgrades("Red Bull", "2024-05-10", 14)
        assert len(upgrades) == 1
        assert upgrades.iloc[0]["impact_score"] == 0.15

    def test_circuit_storage(self, storage):
        storage.save_circuit("monza", "Autodromo Nazionale Monza", "Italy",
                             45.6, 9.3, 5.793, 11, 2, 162, "high_speed",
                             "low", 0.9)

        circuit = storage.get_circuit("monza")
        assert circuit is not None
        assert circuit["corners"] == 11
        assert circuit["power_sensitivity"] == 0.9

    def test_get_all_drivers_for_season(self, storage):
        race_id = storage.save_race(
            year=2024, round_num=1, name="Test",
            circuit_id="test", date="2024-01-01",
        )
        storage.save_result(race_id, "VER", "Max Verstappen", "Red Bull",
                            1, 1, "Finished", 25.0)
        storage.save_result(race_id, "LEC", "Charles Leclerc", "Ferrari",
                            2, 2, "Finished", 18.0)

        drivers = storage.get_all_drivers_for_season(2024)
        assert len(drivers) == 2
        driver_ids = {d["driver_id"] for d in drivers}
        assert "VER" in driver_ids
        assert "LEC" in driver_ids
