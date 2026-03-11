"""Weather-based feature extraction."""

from src.data.storage import Storage


def extract_weather_features(storage: Storage, race_id: int,
                              race_weather: dict = None) -> dict:
    """Extract weather features for a race.

    Args:
        storage: Database storage instance.
        race_id: Race ID.
        race_weather: Optional pre-fetched weather dict. If None, reads from DB.

    Returns:
        Dict of feature name -> value.
    """
    features = {}

    # Get race weather
    if race_weather is None:
        race_weather = storage.get_weather(race_id, "R")

    if race_weather:
        features["race_temp_air"] = race_weather.get("air_temp", 25.0)
        features["race_temp_track"] = race_weather.get("track_temp", 40.0)
        features["race_humidity"] = race_weather.get("humidity", 50.0)
        features["race_wind_speed"] = race_weather.get("wind_speed", 5.0)
        features["race_rain_prob"] = race_weather.get("rain_probability", 0.0)
        features["race_is_wet"] = race_weather.get("is_wet", 0)
    else:
        features["race_temp_air"] = 25.0
        features["race_temp_track"] = 40.0
        features["race_humidity"] = 50.0
        features["race_wind_speed"] = 5.0
        features["race_rain_prob"] = 0.0
        features["race_is_wet"] = 0

    # Temperature delta between FP sessions and race
    fp_weather = storage.get_weather(race_id, "FP3")
    if fp_weather is None:
        fp_weather = storage.get_weather(race_id, "FP2")
    if fp_weather is None:
        fp_weather = storage.get_weather(race_id, "FP1")

    if fp_weather and race_weather:
        fp_temp = fp_weather.get("air_temp", 25.0)
        race_temp = features["race_temp_air"]
        features["race_temp_delta_fp"] = abs(race_temp - fp_temp)

        # Significant conditions change flag
        fp_wet = fp_weather.get("is_wet", 0)
        race_wet = features["race_is_wet"]
        temp_change = abs(race_temp - fp_temp) > 10
        wetness_change = fp_wet != race_wet
        features["race_conditions_change"] = int(temp_change or wetness_change)
    else:
        features["race_temp_delta_fp"] = 0.0
        features["race_conditions_change"] = 0

    # Night race flag (approximate from race time or location)
    features["race_is_night"] = _is_night_race(storage, race_id)

    return features


def _is_night_race(storage: Storage, race_id: int) -> int:
    """Determine if a race is a night race."""
    race = None
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT name, circuit_id FROM races WHERE id=?", (race_id,)
        ).fetchone()
        if row:
            race = dict(row)

    if not race:
        return 0

    name = (race.get("name", "") + " " + race.get("circuit_id", "")).lower()

    # Known night races
    night_circuits = ["bahrain", "jeddah", "singapore", "marina_bay",
                      "las_vegas", "losail", "qatar"]
    return int(any(nc in name for nc in night_circuits))
