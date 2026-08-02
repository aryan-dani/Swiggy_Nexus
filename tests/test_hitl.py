"""HITL approve/reject API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.store import create_approval, get_approval, init_durable_tables
from app.main import app
from app.services import qol_triggers

client = TestClient(app)


def setup_function():
    init_durable_tables()


def test_qol_approval_executes_checkout_path():
    approval = create_approval(
        event_id="hitl-test-1",
        thread_id="hitl-test-1",
        trigger_type="guest_sos",
        title="Test guests",
        summary="test",
        cost_breakdown={"mode": "IM"},
        staged_payload={
            "mode": "ZERO_TOUCH_HOST",
            "staged_im_cart": {
                "selectedAddressId": "addr_kp_001",
                "items": [
                    {"spinId": "spin_cola_2l", "quantity": 1},
                    {"spinId": "spin_chips_lays_f", "quantity": 1},
                ],
                "estimated_total_inr": 145,
            },
            "staged_food_cart": {"cartItems": [], "addressId": "addr_kp_001"},
        },
    )
    rid = approval["request_id"]
    res = client.post(f"/api/hitl/approve/{rid}", json={"approved": True})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "COMPLETED"
    assert get_approval(rid)["status"] == "APPROVED"


def test_reject_marks_rejected():
    approval = create_approval(
        event_id="hitl-test-2",
        thread_id="hitl-test-2",
        trigger_type="bhajiya_chai",
        title="Reject me",
        summary="x",
        cost_breakdown={},
        staged_payload={"mode": "ZERO_TOUCH_HOST", "staged_im_cart": {"items": []}},
    )
    rid = approval["request_id"]
    res = client.post(f"/api/hitl/reject/{rid}")
    assert res.status_code == 200
    assert res.json()["status"] == "REJECTED"
    assert get_approval(rid)["status"] == "REJECTED"


def test_reject_calendar_without_checkpoint_does_not_spawn_new_hitl(monkeypatch):
    """Reject must not restart the concierge graph when MemorySaver has no interrupt."""
    from app.db.store import list_approvals
    from app.services import notifications as notif

    sends: list[str] = []

    async def _capture(*_a, **kwargs):
        sends.append(str(kwargs.get("request_id") or ""))
        return True

    monkeypatch.setattr(notif, "send_approval_request", _capture)

    approval = create_approval(
        event_id="hitl-orphan-reject",
        thread_id="hitl-orphan-reject",
        trigger_type="calendar_concierge",
        title="Orphan checkpoint",
        summary="reject me",
        cost_breakdown={"mode": "DINEOUT", "total_inr": 2800},
        staged_payload={"mode": "DINEOUT", "dineout_plan": {}},
    )
    rid = approval["request_id"]
    before = {a["request_id"] for a in list_approvals(status=None, limit=200)}

    res = client.post(f"/api/hitl/reject/{rid}")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "REJECTED"
    assert get_approval(rid)["status"] == "REJECTED"
    # final_state must not be a fresh graph run that minted another REQ
    final = body.get("final_state") or {}
    assert final.get("approval_request_id") in (None, rid)
    assert final.get("resume") in ("no_interrupt", "no_checkpoint", None) or final.get(
        "approval_status"
    ) == "REJECTED"

    after = {a["request_id"] for a in list_approvals(status=None, limit=200)}
    assert after == before  # no fresh REQ-* minted on reject
    assert sends == []  # no Telegram/console HITL spam


def test_approvals_list():
    create_approval(
        event_id="hitl-test-3",
        thread_id="hitl-test-3",
        trigger_type="fuel_guard",
        title="List me",
        summary="x",
        cost_breakdown={},
        staged_payload={},
    )
    res = client.get("/api/hitl/approvals")
    assert res.status_code == 200
    assert len(res.json()["items"]) >= 1


def test_approval_survives_restart_resume():
    """Approvals are SQLite-durable — re-init + re-read must still allow approve."""
    approval = create_approval(
        event_id="hitl-restart-1",
        thread_id="hitl-restart-1",
        trigger_type="guest_sos",
        title="Survive restart",
        summary="durable",
        cost_breakdown={"mode": "IM"},
        staged_payload={
            "mode": "ZERO_TOUCH_HOST",
            "staged_im_cart": {
                "selectedAddressId": "addr_kp_001",
                "items": [
                    {"spinId": "spin_cola_2l", "quantity": 1},
                    {"spinId": "spin_chips_lays_f", "quantity": 1},
                ],
                "estimated_total_inr": 145,
            },
            "staged_food_cart": {"cartItems": [], "addressId": "addr_kp_001"},
        },
    )
    rid = approval["request_id"]

    # Simulate process restart: re-run schema init and reload row from disk.
    init_durable_tables()
    reloaded = get_approval(rid)
    assert reloaded is not None
    assert reloaded["status"] == "PENDING"
    assert reloaded["staged_payload"]["staged_im_cart"]["items"]

    res = client.post(f"/api/hitl/approve/{rid}", json={"approved": True})
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"
    assert get_approval(rid)["status"] == "APPROVED"
