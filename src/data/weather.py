"""Weather data collection from OpenWeatherMap API."""

import logging
import os

import requests

logger = logging.getLogger(__name__)


class WeatherClient:
    """Fetches weather forecasts for race weekends."""

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("OPENWEATHERMAP_API_KEY", "")
        self.session = requests.Session()

    def get_forecast(self, lat: float, lon: float) -> dict | None:
        """Get 5-day forecast for a location (race circuit)."""
        if not self.api_key:
            logger.warning("No OpenWeatherMap API key configured")
            return None

        try:
            resp = self.session.get(
                f"{self.BASE_URL}/forecast",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Weather API error: {e}")
            return None

    def get_race_weather(self, lat: float, lon: float,
                         race_date: str) -> dict:
        """Get weather prediction for race day.

        Returns standardized weather dict for feature extraction.
        """
        forecast = self.get_forecast(lat, lon)
        if not forecast:
            return self._default_weather()

        # Find forecast entries closest to race time (typically 14:00 local)
        entries = forecast.get("list", [])
        if not entries:
            return self._default_weather()

        # Find entries on race day
        race_entries = [
            e for e in entries
            if race_date in e.get("dt_txt", "")
        ]

        if not race_entries:
            # Use closest available forecast
            race_entries = entries[:3]

        # Average the forecasts
        temps = [e["main"]["temp"] for e in race_entries]
        humidity = [e["main"]["humidity"] for e in race_entries]
        wind = [e["wind"]["speed"] for e in race_entries]
        rain_prob = any(
            e.get("rain") or e.get("weather", [{}])[0].get("main") == "Rain"
            for e in race_entries
        )

        return {
            "air_temp": sum(temps) / len(temps),
            "track_temp": sum(temps) / len(temps) + 15,  # Rough estimate
            "humidity": sum(humidity) / len(humidity),
            "wind_speed": sum(wind) / len(wind),
            "wind_direction": race_entries[0].get("wind", {}).get("deg", 0),
            "rain_probability": 1.0 if rain_prob else 0.0,
            "is_wet": int(rain_prob),
        }

    def _default_weather(self) -> dict:
        """Return default weather when API unavailable."""
        return {
            "air_temp": 25.0,
            "track_temp": 40.0,
            "humidity": 50.0,
            "wind_speed": 5.0,
            "wind_direction": 0.0,
            "rain_probability": 0.0,
            "is_wet": 0,
        }
