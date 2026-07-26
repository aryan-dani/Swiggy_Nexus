"""QoL trigger unit tests."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.db.store import init_durable_tables, list_qol_events
from app.main import app
from app.schemas import WeatherAlert
from app.services import qol_triggers
from app.services.match import match_provider
from app.services.weather import set_scenario_weather

client = TestClient(app)


def setup_function():
    init_durable_tables()
    match_provider.reset()
    qol_triggers._cooldowns.clear()


def test_rooftop_rescue_on_heavy_rain():
    alert = set_scenario_weather(
        WeatherAlert(
            source="scenario",
            temp_c=20,
            rain_mm=30,
            is_raining=True,
            is_heavy_rain=True,
            condition="Thunderstorm",
        )
    )
    ev = asyncio.get_event_loop().run_until_complete(qol_triggers.check_rooftop_rescue(alert))
    assert ev is not None
    assert ev["kind"] == "rooftop_rescue"


def test_guest_sos():
    result = asyncio.get_event_loop().run_until_complete(qol_triggers.guest_sos(6))
    assert result["status"] == "pending_approval"
    assert result["approval"]["trigger_type"] == "guest_sos"


def test_ipl_timeout():
    match_provider.simulate(required_run_rate=14, is_timeout=True, is_tense_chase=True)
    ev = asyncio.get_event_loop().run_until_complete(qol_triggers.check_ipl_timeout())
    assert ev is not None
    assert ev["kind"] == "ipl_timeout"


def test_simulate_weather_endpoint():
    r = client.post(
        "/api/concierge/simulate/weather",
        json={
            "rain_mm": 25,
            "temp_c": 21,
            "is_raining": True,
            "is_heavy_rain": True,
            "condition": "Heavy rain",
        },
    )
    assert r.status_code == 200
    assert r.json()["weather"]["is_heavy_rain"] is True
    assert list_qol_events(limit=5)


def test_timeline_endpoint():
    client.post("/api/concierge/simulate/guests", json={"count": 4})
    r = client.get("/api/concierge/timeline")
    assert r.status_code == 200
    assert "items" in r.json()
