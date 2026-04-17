"""Historical data collection via Jolpica-F1 (Ergast replacement) API."""

import logging
import time

import requests
import pandas as pd

from src.data.storage import Storage

logger = logging.getLogger(__name__)

BASE_URL = "https://api.jolpi.ca/ergast/f1"


class HistoricalClient:
    """Fetches historical F1 data from Jolpica-F1 API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "f1-predict/0.1"})

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make API request with rate limiting and 429 back-off."""
        url = f"{BASE_URL}/{endpoint}.json"
        for attempt in range(6):
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                # Exponential back-off: 2s, 4s, 8s, 16s, 32s, 64s.
                wait = 2 ** (attempt + 1)
                logger.warning(f"429 rate-limited on {endpoint}; sleeping {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            time.sleep(0.8)  # Base rate limit
            return resp.json()
        resp.raise_for_status()
        return {}

    def get_season_races(self, year: int) -> list[dict]:
        """Get all races in a season."""
        data = self._get(f"{year}")
        races = data["MRData"]["RaceTable"]["Races"]
        return races

    def get_race_results(self, year: int, round_num: int) -> list[dict]:
        """Get results for a specific race."""
        data = self._get(f"{year}/{round_num}/results")
        races = data["MRData"]["RaceTable"]["Races"]
        if not races:
            return []
        return races[0].get("Results", [])

    def get_qualifying(self, year: int, round_num: int) -> list[dict]:
        """Get qualifying results for a specific race."""
        data = self._get(f"{year}/{round_num}/qualifying")
        races = data["MRData"]["RaceTable"]["Races"]
        if not races:
            return []
        return races[0].get("QualifyingResults", [])

    def get_driver_standings(self, year: int, round_num: int = None) -> list[dict]:
        """Get driver standings after a specific round or end of season."""
        if round_num:
            endpoint = f"{year}/{round_num}/driverStandings"
        else:
            endpoint = f"{year}/driverStandings"
        data = self._get(endpoint)
        tables = data["MRData"]["StandingsTable"]["StandingsLists"]
        if not tables:
            return []
        return tables[0].get("DriverStandings", [])

    def get_constructor_standings(self, year: int,
                                  round_num: int = None) -> list[dict]:
        """Get constructor standings after a specific round or end of season."""
        if round_num:
            endpoint = f"{year}/{round_num}/constructorStandings"
        else:
            endpoint = f"{year}/constructorStandings"
        data = self._get(endpoint)
        tables = data["MRData"]["StandingsTable"]["StandingsLists"]
        if not tables:
            return []
        return tables[0].get("ConstructorStandings", [])

    def get_pit_stops(self, year: int, round_num: int) -> list[dict]:
        """Get pit stop data for a race."""
        data = self._get(f"{year}/{round_num}/pitstops")
        races = data["MRData"]["RaceTable"]["Races"]
        if not races:
            return []
        return races[0].get("PitStops", [])

    def collect_season(self, year: int, storage: Storage):
        """Collect full season historical data and save to storage."""
        races = self.get_season_races(year)
        logger.info(f"Collecting {year} season: {len(races)} races")

        for race in races:
            round_num = int(race["round"])
            race_name = race["raceName"]
            circuit = race["Circuit"]

            # Skip if race already has results (idempotent restart).
            existing_race_id = storage.get_race_id(year, round_num)
            if existing_race_id is not None:
                existing_results = storage.get_results(existing_race_id)
                if not existing_results.empty:
                    logger.info(f"  Round {round_num}: {race_name} — already collected, skipping")
                    continue

            logger.info(f"  Round {round_num}: {race_name}")

            # Save race
            race_id = storage.save_race(
                year=year,
                round_num=round_num,
                name=race_name,
                circuit_id=circuit["circuitId"],
                date=race["date"],
                circuit_name=circuit["circuitName"],
                country=circuit["Location"].get("country", ""),
                latitude=float(circuit["Location"].get("lat", 0)),
                longitude=float(circuit["Location"].get("long", 0)),
            )

            # Save circuit info
            storage.save_circuit(
                circuit_id=circuit["circuitId"],
                name=circuit["circuitName"],
                country=circuit["Location"].get("country", ""),
                latitude=float(circuit["Location"].get("lat", 0)),
                longitude=float(circuit["Location"].get("long", 0)),
            )

            # Save results
            results = self.get_race_results(year, round_num)
            for result in results:
                driver = result["Driver"]
                constructor = result["Constructor"]
                pos = result.get("position")
                grid = result.get("grid")

                storage.save_result(
                    race_id=race_id,
                    driver_id=driver["code"] if "code" in driver else driver["driverId"],
                    driver_name=f"{driver['givenName']} {driver['familyName']}",
                    team=constructor["name"],
                    grid_position=int(grid) if grid else None,
                    finish_position=int(pos) if pos else None,
                    status=result.get("status", ""),
                    points=float(result.get("points", 0)),
                    laps_completed=int(result.get("laps", 0)),
                    fastest_lap_time=result.get("FastestLap", {}).get("Time", {}).get("time"),
                    fastest_lap_rank=int(result["FastestLap"]["rank"]) if "FastestLap" in result and "rank" in result["FastestLap"] else None,
                )

            # Save pit stops
            try:
                pit_stops = self.get_pit_stops(year, round_num)
                for ps in pit_stops:
                    storage.save_pit_stop(
                        race_id=race_id,
                        driver_id=ps["driverId"],
                        stop_number=int(ps["stop"]),
                        lap=int(ps["lap"]),
                        duration=self._parse_pit_duration(ps.get("duration", "0")),
                    )
            except Exception as e:
                logger.debug(f"No pit stop data for round {round_num}: {e}")

            # Save standings after this round
            try:
                standings = self.get_driver_standings(year, round_num)
                for s in standings:
                    driver = s["Driver"]
                    constructors = s.get("Constructors", [{}])
                    team = constructors[0].get("name", "") if constructors else ""
                    storage.save_standings(
                        year=year,
                        round_num=round_num,
                        driver_id=driver.get("code", driver["driverId"]),
                        driver_name=f"{driver['givenName']} {driver['familyName']}",
                        team=team,
                        points=float(s.get("points", 0)),
                        position=int(s.get("position", 0)),
                        wins=int(s.get("wins", 0)),
                    )
            except Exception as e:
                logger.debug(f"No standings for round {round_num}: {e}")

            try:
                c_standings = self.get_constructor_standings(year, round_num)
                for cs in c_standings:
                    constructor = cs["Constructor"]
                    storage.save_constructor_standing(
                        year=year,
                        round_num=round_num,
                        team=constructor["name"],
                        points=float(cs.get("points", 0)),
                        position=int(cs.get("position", 0)),
                        wins=int(cs.get("wins", 0)),
                    )
            except Exception as e:
                logger.debug(f"No constructor standings for round {round_num}: {e}")

        logger.info(f"Completed {year} season collection")

    def _parse_pit_duration(self, duration_str: str) -> float:
        """Parse pit stop duration string to seconds."""
        try:
            if ":" in duration_str:
                parts = duration_str.split(":")
                return float(parts[0]) * 60 + float(parts[1])
            return float(duration_str)
        except (ValueError, IndexError):
            return 0.0
