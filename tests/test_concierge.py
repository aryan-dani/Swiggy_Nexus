"""Concierge HITL + routing tests (mock MCP)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.models import init_db
from app.db.profiler import get_group_preferences
from app.db.store import init_durable_tables, list_approvals
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _db():
    init_db()
    init_durable_tables()


def test_profiler_group_preferences():
    profile = get_group_preferences(["dani@nexus.ai", "priya@nexus.ai"])
    assert profile.attendee_count == 2
    assert profile.must_be_vegan is True
    assert profile.must_be_vegetarian is True
    assert profile.max_spice_tolerance == 2
    assert "peanuts" in profile.all_allergies
    assert "lactose" in profile.all_allergies


def test_concierge_manual_trigger_flow():
    payload = {
        "event_title": "Friday Team Social",
        "event_time": "2026-07-26T19:00:00+05:30",
        "event_location": "Home",
        "attendee_emails": ["dani@nexus.ai", "priya@nexus.ai"],
        "description": "Team social #swiggy #host",
    }
    response = client.post("/api/concierge/trigger", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "paused_at_hitl_checkpoint"
    assert data["mode"] == "ZERO_TOUCH_HOST"
    request_id = data["approval_request_id"]
    assert request_id and request_id.startswith("REQ-")

    # Book_table / place_order must NOT have run yet — no booking id until approve
    snap = data.get("state_snapshot") or {}
    assert snap.get("dineout_booking_id") in (None, "")
    assert snap.get("approval_status") == "PENDING"

    approve_res = client.post(f"/api/hitl/approve/{request_id}", json={"approved": True})
    assert approve_res.status_code == 200
    approve_data = approve_res.json()
    assert approve_data["status"] == "COMPLETED"


def test_dineout_stages_without_booking_before_hitl():
    payload = {
        "event_title": "Bistro Night",
        "event_location": "Italian Spesso",
        "attendee_emails": ["dani@nexus.ai", "alex@nexus.ai"],
        "description": "Dinner #dineout #swiggy",
    }
    response = client.post("/api/concierge/trigger", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "DINEOUT"
    snap = data["state_snapshot"]
    assert snap.get("dineout_plan") or snap.get("dineout_restaurant_id")
    assert not snap.get("dineout_booking_id")


def test_reject_clears_without_orders():
    payload = {
        "event_title": "Cancel me",
        "event_location": "Home",
        "attendee_emails": ["dani@nexus.ai"],
        "description": "#host #swiggy",
    }
    data = client.post("/api/concierge/trigger", json=payload).json()
    rid = data["approval_request_id"]
    rejected = client.post(f"/api/hitl/reject/{rid}").json()
    assert rejected["status"] == "REJECTED"


def test_guest_sos_creates_approval():
    res = client.post("/api/concierge/simulate/guests", json={"count": 6})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pending_approval"
    assert body["approval"]["request_id"].startswith("REQ-")
    pending = list_approvals("PENDING")
    assert any(p["request_id"] == body["approval"]["request_id"] for p in pending)


def test_health_concierge():
    r = client.get("/health/concierge")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
