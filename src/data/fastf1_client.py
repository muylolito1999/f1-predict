"""FastF1 wrapper for F1 session data (FP, Qualifying, Race)."""

import logging
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd

from src.data.storage import Storage

logger = logging.getLogger(__name__)


class FastF1Client:
    """Fetches and processes F1 session data using FastF1."""

    def __init__(self, cache_dir: str = "data/cache"):
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(cache_path))

    def get_event_schedule(self, year: int) -> pd.DataFrame:
        """Get the event schedule for a season."""
        return fastf1.get_event_schedule(year)

    def load_session(self, year: int, race: str | int,
                     session_type: str) -> fastf1.core.Session:
        """Load a specific session. session_type: FP1, FP2, FP3, Q, R."""
        session = fastf1.get_session(year, race, session_type)
        session.load()
        return session

    def extract_fp_features(self, year: int, race: str | int,
                            session_type: str) -> list[dict]:
        """Extract practice session features for all drivers.

        Returns list of dicts with per-driver FP metrics.
        """
        try:
            session = self.load_session(year, race, session_type)
        except Exception as e:
            logger.warning(f"Failed to load {session_type} for {race} {year}: {e}")
            return []

        drivers = session.drivers
        results = []

        for driver_num in drivers:
            try:
                driver_laps = session.laps.pick_drivers(driver_num)
                if driver_laps.empty:
                    continue

                driver_info = session.get_driver(driver_num)
                driver_id = driver_info.Abbreviation
                driver_name = f"{driver_info.FirstName} {driver_info.LastName}"
                team = driver_info.TeamName

                features = self._compute_driver_fp_features(driver_laps, session)
                features["driver_id"] = driver_id
                features["driver_name"] = driver_name
                features["team"] = team

                results.append(features)
            except Exception as e:
                logger.debug(f"Error processing driver {driver_num}: {e}")
                continue

        return results

    def _compute_driver_fp_features(self, laps: pd.DataFrame,
                                     session) -> dict:
        """Compute all FP features for a single driver."""
        features = {}

        # Filter out pit in/out laps and invalid laps
        valid_laps = laps[
            ~laps["PitInTime"].notna() &
            ~laps["PitOutTime"].notna()
        ].copy()

        if valid_laps.empty:
            valid_laps = laps.copy()

        # Convert lap times to seconds
        lap_times = valid_laps["LapTime"].dt.total_seconds().dropna()

        if lap_times.empty:
            return features

        # Remove extreme outliers (> 150% of median)
        median_time = lap_times.median()
        representative = lap_times[lap_times < median_time * 1.5]

        if representative.empty:
            representative = lap_times

        # Basic pace metrics
        features["best_lap_time"] = representative.min()
        features["median_lap_time"] = representative.median()
        features["lap_count"] = len(laps)
        features["consistency_stddev"] = representative.std() if len(representative) > 1 else 0.0

        # Sector times
        for sector in [1, 2, 3]:
            col = f"Sector{sector}Time"
            if col in valid_laps.columns:
                sector_times = valid_laps[col].dt.total_seconds().dropna()
                if not sector_times.empty:
                    features[f"sector{sector}_best"] = sector_times.min()

        # Speed trap
        if "SpeedI2" in valid_laps.columns:
            speeds = valid_laps["SpeedI2"].dropna()
            if not speeds.empty:
                features["speed_trap_max"] = speeds.max()
        elif "SpeedFL" in valid_laps.columns:
            speeds = valid_laps["SpeedFL"].dropna()
            if not speeds.empty:
                features["speed_trap_max"] = speeds.max()

        # Long run analysis (stints > 5 laps)
        stints = self._identify_stints(valid_laps)
        long_runs = [s for s in stints if len(s) > 5]

        if long_runs:
            long_run_times = []
            degradation_slopes = []

            for stint in long_runs:
                stint_times = stint["LapTime"].dt.total_seconds().dropna()
                if len(stint_times) < 3:
                    continue

                # Remove first lap of stint (out-lap effect)
                clean_times = stint_times.iloc[1:]
                long_run_times.extend(clean_times.tolist())

                # Calculate degradation (slope of lap times)
                if len(clean_times) >= 3:
                    x = np.arange(len(clean_times))
                    slope = np.polyfit(x, clean_times.values, 1)[0]
                    degradation_slopes.append(slope)

            if long_run_times:
                features["long_run_pace"] = np.mean(long_run_times)
            if degradation_slopes:
                features["long_run_degradation"] = np.mean(degradation_slopes)

        # Short run (single lap) pace
        features["short_run_pace"] = representative.min()

        # Per-compound analysis
        if "Compound" in valid_laps.columns:
            for compound in ["SOFT", "MEDIUM", "HARD"]:
                compound_laps = valid_laps[
                    valid_laps["Compound"] == compound
                ]
                if not compound_laps.empty:
                    times = compound_laps["LapTime"].dt.total_seconds().dropna()
                    if not times.empty:
                        clean = times[times < median_time * 1.5]
                        if not clean.empty:
                            key = f"compound_{compound.lower()}_pace"
                            features[key] = clean.min()

        return features

    def _identify_stints(self, laps: pd.DataFrame) -> list[pd.DataFrame]:
        """Split laps into stints based on pit stops or compound changes."""
        if laps.empty:
            return []

        stints = []
        current_stint = []
        prev_compound = None

        for _, lap in laps.iterrows():
            compound = lap.get("Compound")
            is_pit = pd.notna(lap.get("PitInTime")) or pd.notna(lap.get("PitOutTime"))

            if is_pit or (compound != prev_compound and prev_compound is not None):
                if current_stint:
                    stints.append(pd.DataFrame(current_stint))
                current_stint = [lap]
            else:
                current_stint.append(lap)

            prev_compound = compound

        if current_stint:
            stints.append(pd.DataFrame(current_stint))

        return stints

    def collect_race_results(self, year: int, race: str | int) -> list[dict]:
        """Collect race results for storing."""
        try:
            session = self.load_session(year, race, "R")
        except Exception as e:
            logger.warning(f"Failed to load race {race} {year}: {e}")
            return []

        results = []
        race_results = session.results

        if race_results is None or race_results.empty:
            return []

        for _, row in race_results.iterrows():
            result = {
                "driver_id": row.get("Abbreviation", ""),
                "driver_name": f"{row.get('FirstName', '')} {row.get('LastName', '')}",
                "team": row.get("TeamName", ""),
                "grid_position": int(row["GridPosition"]) if pd.notna(row.get("GridPosition")) else None,
                "finish_position": int(row["Position"]) if pd.notna(row.get("Position")) else None,
                "status": row.get("Status", ""),
                "points": float(row["Points"]) if pd.notna(row.get("Points")) else 0.0,
            }
            results.append(result)

        return results

    def collect_weather(self, year: int, race: str | int,
                        session_type: str) -> dict | None:
        """Extract weather data from a session."""
        try:
            session = self.load_session(year, race, session_type)
        except Exception:
            return None

        weather = session.weather_data
        if weather is None or weather.empty:
            return None

        return {
            "air_temp": weather["AirTemp"].mean(),
            "track_temp": weather["TrackTemp"].mean(),
            "humidity": weather["Humidity"].mean(),
            "wind_speed": weather["WindSpeed"].mean(),
            "wind_direction": weather["WindDirection"].mean(),
            "rain_probability": float(weather["Rainfall"].any()) if "Rainfall" in weather.columns else 0.0,
            "is_wet": int(weather["Rainfall"].any()) if "Rainfall" in weather.columns else 0,
        }

    def collect_season(self, year: int, storage: Storage):
        """Collect all data for a full season and save to storage."""
        schedule = self.get_event_schedule(year)

        for _, event in schedule.iterrows():
            if event.get("EventFormat", "") in ("conventional", "sprint_shootout",
                                                  "sprint_qualifying", "sprint"):
                round_num = event["RoundNumber"]
                race_name = event["EventName"]
                logger.info(f"Collecting {year} Round {round_num}: {race_name}")

                # Save race info
                race_id = storage.save_race(
                    year=year,
                    round_num=round_num,
                    name=race_name,
                    circuit_id=event.get("Location", "").lower().replace(" ", "_"),
                    date=str(event.get("EventDate", "")),
                    circuit_name=event.get("OfficialEventName", race_name),
                    country=event.get("Country", ""),
                    latitude=event.get("Latitude"),
                    longitude=event.get("Longitude"),
                )

                # Collect FP sessions
                for fp in ["FP1", "FP2", "FP3"]:
                    fp_data = self.extract_fp_features(year, round_num, fp)
                    for driver_data in fp_data:
                        storage.save_fp_session(
                            race_id=race_id,
                            session_type=fp,
                            driver_id=driver_data["driver_id"],
                            driver_name=driver_data["driver_name"],
                            team=driver_data["team"],
                            data=driver_data,
                        )

                    # Weather for FP
                    weather = self.collect_weather(year, round_num, fp)
                    if weather:
                        storage.save_weather(race_id, fp, weather)

                # Collect race results
                race_results = self.collect_race_results(year, round_num)
                for result in race_results:
                    storage.save_result(
                        race_id=race_id,
                        driver_id=result["driver_id"],
                        driver_name=result["driver_name"],
                        team=result["team"],
                        grid_position=result["grid_position"],
                        finish_position=result["finish_position"],
                        status=result["status"],
                        points=result["points"],
                    )

                # Race weather
                race_weather = self.collect_weather(year, round_num, "R")
                if race_weather:
                    storage.save_weather(race_id, "R", race_weather)

                logger.info(f"  Completed {race_name}")
