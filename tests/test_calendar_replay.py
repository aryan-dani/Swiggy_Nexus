"""Calendar replay endpoint, agent info, and demo reset."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.db.store import init_durable_tables, list_approvals, list_qol_events
from app.main import app

client = TestClient(app)

TAGGED = {
    "summary": "Housewarming with the team #host #swiggy",
    "description": "Hosting 8 people at home #host #swiggy",
    "location": "Home",
    "attendee_emails": ["dani@nexus.ai", "priya@nexus.ai"],
}


def setup_function():
    init_durable_tables()


def test_untagged_event_is_ignored():
    res = client.post(
        "/api/concierge/simulate/calendar",
        json={"summary": "Dentist", "description": "checkup", "location": "Clinic"},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "ignored", "reason": "missing #swiggy/#host"}


def test_tagged_event_runs_the_graph_and_stages_an_approval():
    res = client.post("/api/concierge/simulate/calendar", json=TAGGED)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "accepted"
    assert body["source"] == "replay"
    event_id = body["event_id"]

    kinds = [e["kind"] for e in list_qol_events(limit=50)]
    assert "calendar_push" in kinds

    # TestClient runs background tasks synchronously, so the graph has already paused.
    pending = list_approvals("PENDING")
    assert any(a["event_id"] == event_id for a in pending), "expected a staged approval"

    status = client.get(f"/api/concierge/status/{event_id}")
    assert status.status_code == 200
    assert status.json()["approval_status"] == "PENDING"


def test_each_replay_gets_a_fresh_event_id():
    """The fixed mock `updated` timestamp used to make repeat takes idempotency-blocked."""
    first = client.post("/api/concierge/simulate/calendar", json=TAGGED).json()
    second = client.post("/api/concierge/simulate/calendar", json=TAGGED).json()
    assert first["event_id"] != second["event_id"]
    assert second["status"] == "accepted"


def test_explicit_event_id_is_deduped():
    # Unique per run: the idempotency table is a real file that outlives the suite.
    payload = {**TAGGED, "event_id": f"cal_dedupe_{uuid.uuid4().hex[:8]}"}
    assert client.post("/api/concierge/simulate/calendar", json=payload).json()["status"] == "accepted"
    assert client.post("/api/concierge/simulate/calendar", json=payload).json() == {
        "status": "ignored",
        "reason": "duplicate",
    }


def test_agent_info_endpoint():
    res = client.get("/api/concierge/agent")
    assert res.status_code == 200
    body = res.json()
    assert set(body["hitl_gated_tools"]) == {
        "dineout_book_table",
        "food_place_order",
        "im_checkout",
    }
    assert "label" in body and "configured" in body


def test_demo_reset_requires_secret_and_clears_state():
    client.post("/api/concierge/simulate/calendar", json=TAGGED)
    assert list_approvals("PENDING") or list_qol_events(limit=5)

    assert client.post("/internal/demo/reset").status_code == 401
    assert (
        client.post(
            "/internal/demo/reset", headers={"X-Nexus-Tick-Secret": "wrong"}
        ).status_code
        == 401
    )

    ok = client.post(
        "/internal/demo/reset", headers={"X-Nexus-Tick-Secret": "nexus-tick-secret"}
    )
    assert ok.status_code == 200
    cleared = ok.json()["cleared"]
    assert "approval_requests" in cleared
    assert "qol_events" in cleared
    assert "idempotency_keys" in cleared
    assert "concierge_executions" in cleared
    # Pantry cadence is restored to the demo baseline, not just emptied
    assert cleared.get("pantry_history_rows", 0) > 0

    assert list_approvals("PENDING") == []
    assert list_qol_events(limit=5) == []

    # Idempotency wiped, so a previously-used explicit id works again
    reused = {**TAGGED, "event_id": "cal_reset_probe"}
    assert client.post("/api/concierge/simulate/calendar", json=reused).json()["status"] == "accepted"
    client.post("/internal/demo/reset", headers={"X-Nexus-Tick-Secret": "nexus-tick-secret"})
