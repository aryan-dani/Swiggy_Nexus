"""Weather providers — OpenWeather + scenario simulation for demos/judges."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

import httpx

from app.config import settings
from app.schemas import WeatherAlert

log = logging.getLogger(__name__)

_scenario: WeatherAlert | None = None


class WeatherProvider(Protocol):
    async def get_current(self) -> WeatherAlert: ...


class ScenarioWeatherProvider:
    """In-memory / simulate-endpoint controlled weather for demos."""

    async def get_current(self) -> WeatherAlert:
        global _scenario
        if _scenario is None:
            return WeatherAlert(
                source="scenario",
                city=settings.HOME_CITY,
                lat=settings.HOME_LAT,
                lng=settings.HOME_LNG,
                temp_c=28.0,
                rain_mm=0.0,
                is_raining=False,
                is_heavy_rain=False,
                condition="Clear",
            )
        return _scenario


class OpenWeatherProvider:
    async def get_current(self) -> WeatherAlert:
        if not settings.OPENWEATHER_API_KEY:
            return await ScenarioWeatherProvider().get_current()
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": settings.HOME_LAT,
            "lon": settings.HOME_LNG,
            "appid": settings.OPENWEATHER_API_KEY,
            "units": "metric",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            rain_mm = float((data.get("rain") or {}).get("1h") or 0.0)
            temp = float((data.get("main") or {}).get("temp") or 28.0)
            condition = ((data.get("weather") or [{}])[0].get("main") or "Clear")
            is_raining = rain_mm > 0.2 or condition.lower() in ("rain", "drizzle", "thunderstorm")
            return WeatherAlert(
                source="openweather",
                city=settings.HOME_CITY,
                lat=settings.HOME_LAT,
                lng=settings.HOME_LNG,
                temp_c=temp,
                humidity=int((data.get("main") or {}).get("humidity") or 60),
                rain_mm=rain_mm,
                is_raining=is_raining,
                is_heavy_rain=rain_mm >= 8.0 or condition.lower() == "thunderstorm",
                condition=condition,
                observed_at=datetime.now(timezone.utc),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("OpenWeather failed (%s); scenario fallback", e)
            return await ScenarioWeatherProvider().get_current()


def set_scenario_weather(alert: WeatherAlert) -> WeatherAlert:
    global _scenario
    _scenario = alert
    return alert


def clear_scenario_weather() -> None:
    global _scenario
    _scenario = None


def get_weather_provider() -> WeatherProvider:
    if settings.OPENWEATHER_API_KEY and not settings.FORCE_SCENARIO_WEATHER:
        return OpenWeatherProvider()
    return ScenarioWeatherProvider()
