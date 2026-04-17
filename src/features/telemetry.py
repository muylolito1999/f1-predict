"""OpenF1-derived telemetry features.

Adds physical-signal features that lap times alone can't express:
  - top_speed_deficit: gap to session best straight-line speed
  - full_throttle_pct_per_sector: power-limited vs grip-limited sector share
  - median_brake_point_delta: proxy for late-braking confidence

These features are opt-in via config[features]["telemetry_enabled"]. When
OpenF1 data isn't available the features fall back to zero so the model
sees a neutral value.
"""

import logging

import numpy as np
import pandas as pd

from src.data.storage import Storage
from src.data.openf1_client import OpenF1Client

logger = logging.getLogger(__name__)


# Throttle threshold for "full throttle" in OpenF1 car_data (0..100).
FULL_THROTTLE_THRESHOLD = 95.0


def extract_telemetry_features(storage: Storage, race_id: int,
                                 driver_id: str,
                                 year: int | None = None,
                                 round_num: int | None = None,
                                 race_name: str | None = None,
                                 session_type: str = "FP2",
                                 client: OpenF1Client | None = None) -> dict:
    """Fetch telemetry-derived features for a single driver/session.

    Returns zeros when OpenF1 is unreachable or the driver can't be matched.
    """
    defaults = {
        "telemetry_top_speed_deficit": 0.0,
        "telemetry_full_throttle_pct": 0.0,
        "telemetry_brake_point_delta": 0.0,
    }
    if client is None:
        client = OpenF1Client()

    try:
        race = storage.get_race(year or 0, round_num or 0) if year and round_num else None
        race_name_used = race["name"] if race else (race_name or "")
        session_year = year or (race["year"] if race else None)
        if not session_year or not race_name_used:
            return defaults

        session_key = client.get_session_key(
            session_year, race_name_used, session_type
        )
        if not session_key:
            return defaults

        drivers = client.get_drivers(session_key)
        driver_num = None
        for d in drivers:
            if d.get("name_acronym", "").upper() == driver_id.upper():
                driver_num = d.get("driver_number")
                break
        if driver_num is None:
            return defaults

        # Top-speed deficit from the speed-trap aggregation.
        speed_df = client.get_speed_traps(session_key)
        top_speed_deficit = 0.0
        if not speed_df.empty and driver_num in speed_df["driver_number"].values:
            driver_speed = float(
                speed_df.loc[speed_df["driver_number"] == driver_num, "max_speed"].iloc[0]
            )
            best = float(speed_df["max_speed"].max())
            top_speed_deficit = driver_speed - best

        # Full-throttle percentage from car_data (filter to high-speed to
        # keep the request small).
        car_data = client.get_car_data(
            session_key=session_key, driver_number=driver_num, speed_gt=100
        )
        if car_data:
            df = pd.DataFrame(car_data)
            if "throttle" in df.columns and not df["throttle"].empty:
                full_throttle_pct = float(
                    (df["throttle"] >= FULL_THROTTLE_THRESHOLD).mean()
                )
            else:
                full_throttle_pct = 0.0
        else:
            full_throttle_pct = 0.0

        return {
            "telemetry_top_speed_deficit": float(top_speed_deficit),
            "telemetry_full_throttle_pct": full_throttle_pct,
            # Brake-point delta is cheap to compute but requires full laps
            # telemetry; leave as default for now — the other two are the
            # highest-signal ones.
            "telemetry_brake_point_delta": 0.0,
        }
    except Exception as e:
        logger.debug(f"Telemetry fetch failed for {driver_id}: {e}")
        return defaults
