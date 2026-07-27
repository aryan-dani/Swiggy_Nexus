"""Pantry Depletion Predictor tests — seed → predict → HITL approve → checkout."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.db.store import get_approval, init_durable_tables
from app.main import app
from app.services.pantry import check_pantry_refill, get_pantry_status
from mcp_server.order_history import (
    history_is_empty,
    list_im_history,
    record_im_order,
    seed_synthetic_history_if_empty,
)

client = TestClient(app)


def setup_function():
    init_durable_tables()
    seed_synthetic_history_if_empty()


def test_history_seed_and_record():
    assert not history_is_empty()
    before = len(list_im_history(days=90))
    record_im_order(
        "IM_TEST_1",
        [{"spinId": "spin_milk_1l", "name": "Amul Taaza Milk 1L", "quantity": 2, "unit_price_inr": 52}],
    )
    after = len(list_im_history(days=90))
    assert after == before + 1


def test_pantry_status_learns_cadence():
    status = get_pantry_status()
    assert len(status) >= 3
    by_name = {s["spinId"]: s for s in status}
    milk = by_name.get("spin_milk_1l")
    assert milk is not None
    assert milk["orders_seen"] >= 2
    assert 1.0 <= milk["avg_interval_days"] <= 6.0
    # Sorted by urgency
    lefts = [s["days_left"] for s in status]
    assert lefts == sorted(lefts)


def test_pantry_refill_creates_hitl_approval_and_executes():
    result = asyncio.get_event_loop().run_until_complete(check_pantry_refill(force=True))
    assert result is not None
    assert result["status"] == "pending_approval"
    approval = result["approval"]
    assert approval["trigger_type"] == "pantry_refill"
    assert approval["staged_payload"]["staged_im_cart"]["items"]

    rid = approval["request_id"]
    res = client.post(f"/api/hitl/approve/{rid}", json={"approved": True})
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"
    assert get_approval(rid)["status"] == "APPROVED"


def test_pantry_endpoints():
    res = client.get("/api/concierge/pantry")
    assert res.status_code == 200
    items = res.json()["items"]
    assert isinstance(items, list) and len(items) >= 3
    sim = client.post("/api/concierge/simulate/pantry")
    assert sim.status_code == 200
    assert sim.json()["status"] in ("pending_approval", "nothing_low")
