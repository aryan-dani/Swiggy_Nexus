"""Night-out wizard + plain-text Calendar write-back."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.models import ensure_night_out_guests
from app.db.store import init_durable_tables
from app.graph.nodes import _rule_based_sommelier, calendar_mutate_node
from app.main import app
from app.services import google_calendar as gcal
from app.services import night_out_wizard as wiz

client = TestClient(app)


def setup_function():
    init_durable_tables()
    ensure_night_out_guests()
    wiz._DRAFTS.clear()
    wiz._CHAT_WIZARDS.clear()


def test_sommelier_is_plain_text_not_markdown_table():
    text = _rule_based_sommelier(
        {
            "group_profile": {
                "must_be_vegan": False,
                "must_be_vegetarian": True,
                "max_spice_tolerance": 3,
                "all_allergies": [],
                "individual_profiles": [
                    {
                        "email": "swayam@nexus.ai",
                        "full_name": "Swayam",
                        "profile": {"is_vegetarian": True, "spice_tolerance": 2},
                    }
                ],
            }
        }
    )
    assert "|---|" not in text
    assert "###" not in text
    assert "• Swayam" in text
    assert "AI Sommelier" in text


def test_calendar_mutate_plain_text(monkeypatch: pytest.MonkeyPatch):
    import asyncio

    captured: dict[str, str] = {}

    def fake_patch(event_id: str, description: str) -> bool:
        captured["id"] = event_id
        captured["text"] = description
        return True

    monkeypatch.setattr(
        "app.graph.nodes.update_calendar_event_description",
        fake_patch,
    )
    monkeypatch.setattr("app.graph.nodes.save_execution", lambda *a, **k: None)
    monkeypatch.setattr("app.graph.nodes.record_qol_event", lambda *a, **k: None)

    state = {
        "calendar_event_id": "evt_test",
        "event_id": "evt_test",
        "event_description": "Night out with friends. #dineout #swiggy",
        "mode": "DINEOUT",
        "approval_status": "APPROVED",
        "dineout_restaurant_name": "6 Digs · Kothrud",
        "dineout_slot": "20:00",
        "dineout_booking_id": "DO_BK_TEST",
        "sommelier_recommendations_markdown": "AI Sommelier · Menu picks\n• Aryan — Margherita (Veg)",
        "execution_logs": [],
    }
    asyncio.get_event_loop().run_until_complete(calendar_mutate_node(state))
    assert "###" not in captured["text"]
    assert "|---|" not in captured["text"]
    assert "Autonomous Swiggy Social Concierge" in captured["text"]
    assert "Mode: DINEOUT · Status: APPROVED" in captured["text"]
    assert "Booking ID: DO_BK_TEST" in captured["text"]
    assert "• Aryan — Margherita" in captured["text"]


def test_wizard_happy_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        gcal,
        "create_calendar_event",
        lambda **kwargs: {
            "id": "mock_cal_wiz",
            "event_id": "mock_cal_wiz",
            "htmlLink": "https://calendar.google.com/calendar/render?action=TEMPLATE&text=Test",
            "summary": kwargs.get("summary"),
            "description": kwargs.get("description"),
            "location": kwargs.get("location"),
            "start": {"dateTime": kwargs.get("start_iso") or "2026-08-02T20:00:00+05:30"},
            "end": {"dateTime": "2026-08-02T22:00:00+05:30"},
            "attendees": [{"email": e} for e in kwargs.get("attendee_emails", [])],
            "mock": True,
            "auth_error": "test_stub",
        },
    )

    start = client.post("/api/concierge/night-out/wizard/start")
    assert start.status_code == 200
    wid = start.json()["wizard_id"]
    assert start.json()["step"] == "guests"

    guests = client.post(
        f"/api/concierge/night-out/wizard/{wid}/guests",
        json={"guests": ["aryan", "himali", "siya", "swayam"]},
    )
    assert guests.status_code == 200
    assert guests.json()["step"] == "venue"

    venues = client.get(f"/api/concierge/night-out/wizard/{wid}/venues?q=6%20Digs")
    assert venues.status_code == 200
    assert venues.json()["venues"]
    pick = venues.json()["venues"][0]

    venue = client.post(
        f"/api/concierge/night-out/wizard/{wid}/venue",
        json={"restaurant_id": pick["restaurant_id"], "name": pick["name"]},
    )
    assert venue.status_code == 200
    assert venue.json()["step"] == "slot"
    assert venue.json()["slots"]
    slot = venue.json()["slots"][0]

    slotted = client.post(
        f"/api/concierge/night-out/wizard/{wid}/slot",
        json={"slot": slot["label"], "slot_id": slot.get("slot_id")},
    )
    assert slotted.status_code == 200
    assert slotted.json()["step"] == "confirm"

    confirmed = client.post(f"/api/concierge/night-out/wizard/{wid}/confirm")
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "awaiting_approval"
    assert body.get("approval_request_id")
    assert body.get("venue")
    assert body.get("slot") == slot["label"]


def test_telegram_guest_toggle_step():
    draft = wiz.start_wizard(chat_id="999")
    wid = draft["wizard_id"]
    assert "aryan" in draft["guests"]
    toggled = wiz.toggle_guest(wid, "kabir")
    assert "kabir" in toggled["guests"]
    assert "aryan" in toggled["guests"]
