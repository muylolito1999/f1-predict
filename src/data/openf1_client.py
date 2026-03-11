"""OpenF1 API client for real-time and supplementary telemetry data."""

import logging
from datetime import datetime

import requests
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openf1.org/v1"


class OpenF1Client:
    """Fetches data from the OpenF1 API (free, no auth required)."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "f1-predict/0.1"})

    def _get(self, endpoint: str, params: dict = None) -> list[dict]:
        """Make API request."""
        url = f"{BASE_URL}/{endpoint}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_sessions(self, year: int = None,
                     session_type: str = None) -> list[dict]:
        """Get available sessions."""
        params = {}
        if year:
            params["year"] = year
        if session_type:
            params["session_type"] = session_type
        return self._get("sessions", params)

    def get_session_key(self, year: int, race_name: str,
                        session_type: str) -> int | None:
        """Find session key for a specific session."""
        # Map session types
        type_map = {
            "FP1": "Practice 1", "FP2": "Practice 2", "FP3": "Practice 3",
            "Q": "Qualifying", "R": "Race",
        }
        target = type_map.get(session_type, session_type)

        sessions = self.get_sessions(year=year)
        for s in sessions:
            if (target.lower() in s.get("session_name", "").lower() and
                    race_name.lower() in s.get("meeting_name", "").lower()):
                return s.get("session_key")
        return None

    def get_laps(self, session_key: int,
                 driver_number: int = None) -> list[dict]:
        """Get lap data for a session."""
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        return self._get("laps", params)

    def get_drivers(self, session_key: int) -> list[dict]:
        """Get driver information for a session."""
        return self._get("drivers", {"session_key": session_key})

    def get_car_data(self, session_key: int, driver_number: int,
                     speed_gt: int = None) -> list[dict]:
        """Get car telemetry data (speed, RPM, gear, throttle, brake).

        Warning: This can return very large datasets. Use filters.
        """
        params = {
            "session_key": session_key,
            "driver_number": driver_number,
        }
        if speed_gt:
            params["speed>"] = speed_gt
        return self._get("car_data", params)

    def get_stints(self, session_key: int,
                   driver_number: int = None) -> list[dict]:
        """Get stint data (tyre compound, stint length)."""
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        return self._get("stints", params)

    def get_weather(self, session_key: int) -> list[dict]:
        """Get weather data for a session."""
        return self._get("weather", {"session_key": session_key})

    def get_speed_traps(self, session_key: int) -> pd.DataFrame:
        """Get speed trap data aggregated by driver."""
        laps = self.get_laps(session_key)
        if not laps:
            return pd.DataFrame()

        df = pd.DataFrame(laps)
        if "st_speed" not in df.columns:
            return pd.DataFrame()

        speed_data = df.groupby("driver_number").agg(
            max_speed=("st_speed", "max"),
            avg_speed=("st_speed", "mean"),
        ).reset_index()

        return speed_data

    def get_session_summary(self, session_key: int) -> dict:
        """Get aggregated session summary for quick analysis."""
        laps = self.get_laps(session_key)
        drivers = self.get_drivers(session_key)

        if not laps or not drivers:
            return {}

        driver_map = {
            d["driver_number"]: d for d in drivers
        }

        df = pd.DataFrame(laps)

        summary = {}
        for driver_num, group in df.groupby("driver_number"):
            driver_info = driver_map.get(driver_num, {})
            valid = group[group["lap_duration"].notna()]

            if valid.empty:
                continue

            summary[driver_num] = {
                "driver_number": driver_num,
                "name_acronym": driver_info.get("name_acronym", ""),
                "team_name": driver_info.get("team_name", ""),
                "best_lap": valid["lap_duration"].min(),
                "median_lap": valid["lap_duration"].median(),
                "lap_count": len(group),
                "sectors": {
                    f"s{i}": valid[f"duration_sector_{i}"].min()
                    for i in range(1, 4)
                    if f"duration_sector_{i}" in valid.columns
                    and valid[f"duration_sector_{i}"].notna().any()
                },
            }

        return summary
