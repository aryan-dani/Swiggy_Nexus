"""Telegram spam hardening — mute under pytest, HITL dedupe, no @nexus.ai invites."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db.store import find_pending_approval, init_durable_tables, list_approvals
from app.main import app
from app.services import google_calendar as gcal

client = TestClient(app)

TAGGED = {
    "summary": "Housewarming with the team #host #swiggy",
    "description": "Hosting 8 people at home #host #swiggy",
    "location": "Home",
    "attendee_emails": ["dani@nexus.ai", "priya@nexus.ai"],
}


def setup_function():
    init_durable_tables()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_simulate_calendar_does_not_hit_telegram_http(monkeypatch: pytest.MonkeyPatch):
    """Autouse mute: simulate/calendar must not POST to api.telegram.org."""
    telegram_posts: list[str] = []
    real_post = httpx.AsyncClient.post

    async def spy_post(self, url, *args, **kwargs):
        url_s = str(url)
        if "api.telegram.org" in url_s:
            telegram_posts.append(url_s)
        return await real_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", spy_post)

    res = client.post("/api/concierge/simulate/calendar", json=TAGGED)
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"
    assert telegram_posts == [], f"unexpected Telegram HTTP: {telegram_posts}"


def test_hitl_notify_dedupes_pending_for_same_event(monkeypatch: pytest.MonkeyPatch):
    """Two hitl_notify calls for the same event_id → one PENDING / one send."""
    from app.graph.nodes import hitl_notify_node

    event_id = f"spam-dedupe-{uuid.uuid4().hex[:8]}"
    sends: list[dict] = []

    async def spy_send(*_args, **kwargs):
        sends.append(kwargs)
        return True

    monkeypatch.setattr("app.graph.nodes.send_approval_request", spy_send)

    state = {
        "event_id": event_id,
        "mode": "ZERO_TOUCH_HOST",
        "event_title": "Housewarming with the team",
        "trigger_type": "calendar_concierge",
        "instamart_total": 100.0,
        "food_total": 200.0,
        "attendee_emails": ["dani@nexus.ai"],
        "execution_logs": [],
    }

    first = _run(hitl_notify_node(state))
    second = _run(hitl_notify_node(state))

    assert first["approval_request_id"] == second["approval_request_id"]
    assert first["approval_status"] == "PENDING"
    assert second["approval_status"] == "PENDING"
    assert len(sends) == 1

    pending = [a for a in list_approvals("PENDING") if a["event_id"] == event_id]
    assert len(pending) == 1
    assert find_pending_approval(event_id, "calendar_concierge")["request_id"] == first[
        "approval_request_id"
    ]


def test_create_calendar_omits_nexus_ai_from_live_insert(monkeypatch: pytest.MonkeyPatch):
    """Live events().insert must not invite swayam@nexus.ai (or any @nexus.ai)."""
    captured: dict = {}

    def insert(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return MagicMock(
            execute=lambda: {
                "id": "live_evt_spam_test",
                "htmlLink": "https://calendar.google.com/event?eid=spam",
                "summary": kwargs["body"].get("summary"),
                "description": kwargs["body"].get("description"),
                "location": kwargs["body"].get("location"),
                "start": kwargs["body"].get("start") or {},
                "end": kwargs["body"].get("end") or {},
                "attendees": kwargs["body"].get("attendees") or [],
            }
        )

    mock_service = MagicMock()
    mock_service.events.return_value.insert = insert
    monkeypatch.setattr(gcal, "get_calendar_service", lambda: mock_service)

    event = gcal.create_calendar_event(
        summary="Night Out #dineout #swiggy",
        location="6 Digs · Kothrud",
        description="Dinner with Swayam #dineout #swiggy",
        attendee_emails=["swayam@nexus.ai", "aryan@nexus.ai"],
        allow_mock=False,
    )

    assert event["mock"] is False
    assert "attendees" not in captured.get("body", {})
    assert captured.get("sendUpdates") == "none"
    body_emails = [
        a.get("email") for a in (captured.get("body") or {}).get("attendees") or []
    ]
    assert "swayam@nexus.ai" not in body_emails
    assert "aryan@nexus.ai" not in body_emails
