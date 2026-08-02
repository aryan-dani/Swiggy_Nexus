"""Night-out workflow — Calendar create, 6 Digs prefer, receipt after approve."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.models import ensure_night_out_guests
from app.db.store import init_durable_tables, list_qol_events
from app.main import app
from app.services import google_calendar as gcal
from app.services.night_out import resolve_guest_emails

client = TestClient(app)


def setup_function():
    init_durable_tables()
    ensure_night_out_guests()


def test_create_calendar_event_mock_returns_html_link(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gcal, "get_calendar_service", lambda: None)
    event = gcal.create_calendar_event(
        summary="Dinner at 6 Digs #dineout #swiggy",
        location="6 Digs · Kothrud",
        description="With Swayam and Sobaan #dineout #swiggy",
        attendee_emails=["aryan@nexus.ai", "himali@nexus.ai", "siya@nexus.ai"],
        allow_mock=True,
    )
    assert event["mock"] is True
    assert "action=TEMPLATE" in event["htmlLink"]
    assert event["event_id"].startswith("mock_cal_")
    assert len(event["attendees"]) == 3


def test_create_calendar_event_requires_auth_when_mock_disallowed(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(gcal, "get_calendar_service", lambda: None)
    with pytest.raises(gcal.CalendarAuthError):
        gcal.create_calendar_event(
            summary="Dinner",
            location="6 Digs",
            description="x",
            attendee_emails=["aryan@nexus.ai"],
            allow_mock=False,
        )


def test_resolve_guests_maps_himali_siya_swayam():
    emails = resolve_guest_emails(["Himali", "Siya", "Swayam"])
    assert emails[0] == "aryan@nexus.ai"
    assert "himali@nexus.ai" in emails
    assert "siya@nexus.ai" in emails
    assert "swayam@nexus.ai" in emails
    assert len(emails) == 4


def test_dineout_search_finds_six_digs():
    from mcp_server.dineout import dispatcher as dineout

    ok, data, err = dineout.handle_search_restaurants({"query": "6 Digs", "area": "Kothrud"})
    assert ok is True and err is None
    names = [r["name"] for r in data["restaurants"]]
    assert any("6 Digs" in n for n in names)


def test_night_out_endpoint_stages_approval_and_prefers_six_digs(monkeypatch: pytest.MonkeyPatch):
    # Offline CI: don't require live Google OAuth for graph/HITL assertions.
    monkeypatch.setattr(
        gcal,
        "create_calendar_event",
        lambda **kwargs: {
            "id": "mock_cal_test",
            "event_id": "mock_cal_test",
            "htmlLink": "https://calendar.google.com/calendar/render?action=TEMPLATE&text=Test",
            "summary": kwargs.get("summary"),
            "description": kwargs.get("description"),
            "location": kwargs.get("location"),
            "start": {"dateTime": "2026-08-02T20:00:00+05:30"},
            "end": {"dateTime": "2026-08-02T22:00:00+05:30"},
            "attendees": [{"email": e} for e in kwargs.get("attendee_emails", [])],
            "mock": True,
            "auth_error": "test_stub",
        },
    )
    res = client.post(
        "/api/concierge/night-out",
        json={"guests": ["swayam", "sobaan"], "venue": "6 Digs · Kothrud", "guest_count": 3},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "awaiting_approval"
    assert body.get("approval_request_id")
    assert "6 Digs" in (body.get("venue") or "")
    assert body.get("calendar_html_link")
    assert body.get("maps_url")

    approvals = client.get("/api/concierge/approvals").json()["items"]
    assert any(a["request_id"] == body["approval_request_id"] for a in approvals)
    match = next(a for a in approvals if a["request_id"] == body["approval_request_id"])
    plan = (match.get("staged_payload") or {}).get("dineout_plan") or {}
    assert "6 Digs" in str(plan.get("restaurantName") or match.get("summary") or "")

    # Approve → book + split receipt
    approved = client.post(f"/api/hitl/approve/{body['approval_request_id']}", json={"approved": True})
    assert approved.status_code == 200

    receipt = client.get("/api/concierge/receipts/latest").json()
    assert receipt.get("receipt")
    meta = receipt["receipt"]
    assert meta.get("shares")
    assert len(meta["shares"]) >= 3
    assert meta.get("calendar_html_link")
    assert meta.get("maps_url")
    assert meta.get("booking_id") or meta.get("venue")

    kinds = [e["kind"] for e in list_qol_events(limit=30)]
    assert "night_out_receipt" in kinds
