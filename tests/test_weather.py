"""Weather provider tests."""

from __future__ import annotations

import asyncio

from app.schemas import WeatherAlert
from app.services.weather import (
    ScenarioWeatherProvider,
    clear_scenario_weather,
    set_scenario_weather,
)


def test_scenario_weather_default():
    clear_scenario_weather()
    w = asyncio.get_event_loop().run_until_complete(ScenarioWeatherProvider().get_current())
    assert w.is_raining is False
    assert w.city == "Pune"


def test_scenario_weather_override():
    set_scenario_weather(
        WeatherAlert(temp_c=18, rain_mm=40, is_raining=True, is_heavy_rain=True, condition="Rain")
    )
    w = asyncio.get_event_loop().run_until_complete(ScenarioWeatherProvider().get_current())
    assert w.is_heavy_rain is True
    assert w.temp_c == 18
    clear_scenario_weather()
