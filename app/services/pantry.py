"""Pantry Depletion Predictor — "Khatam Hone Wala Hai".

Learns reorder cadence per Instamart SKU from durable order history, predicts
when staples run out, and stages a HITL-gated refill cart (official
`update_cart` + `checkout` on approve — same execute path as other QoL flows).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.db.store import create_approval, list_approvals, record_qol_event
from app.services.notifications import send_approval_request
from mcp_server.order_history import (
    list_im_history,
    seed_synthetic_history_if_empty,
)

log = logging.getLogger(__name__)

# Predict-empty threshold — items with days_left <= this go into the refill cart
DAYS_LEFT_THRESHOLD = 2.0


def _parse_ts(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.now(timezone.utc).replace(tzinfo=None)


def get_pantry_status(days: int = 60) -> list[dict[str, Any]]:
    """Per-SKU consumption model from order history. Sorted by urgency."""
    seed_synthetic_history_if_empty()
    history = list_im_history(days=days)

    by_spin: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        by_spin[row["spin_id"]].append(row)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    out: list[dict[str, Any]] = []
    for spin_id, rows in by_spin.items():
        rows.sort(key=lambda r: r["ordered_at"])
        if len(rows) < 2:
            continue  # need at least two orders to learn cadence
        times = [_parse_ts(r["ordered_at"]) for r in rows]
        span_days = max((times[-1] - times[0]).total_seconds() / 86400.0, 0.5)
        interval = span_days / (len(rows) - 1)
        last = times[-1]
        days_since = (now - last).total_seconds() / 86400.0
        days_left = interval - days_since
        predicted_empty = last + timedelta(days=interval)
        latest = rows[-1]
        out.append(
            {
                "spinId": spin_id,
                "name": latest.get("name") or spin_id,
                "unit_price_inr": int(latest.get("unit_price_inr") or 0),
                "usual_quantity": int(latest.get("quantity") or 1),
                "orders_seen": len(rows),
                "avg_interval_days": round(interval, 1),
                "last_ordered_at": last.isoformat(),
                "days_left": round(days_left, 1),
                "predicted_empty_at": predicted_empty.isoformat(),
                "low": days_left <= DAYS_LEFT_THRESHOLD,
            }
        )

    out.sort(key=lambda x: x["days_left"])
    return out


def _has_pending_refill() -> bool:
    return any(
        a.get("trigger_type") == "pantry_refill"
        for a in list_approvals("PENDING") or []
    )


async def check_pantry_refill(force: bool = False) -> dict[str, Any] | None:
    """Scan pantry; if staples are low, stage a refill cart behind HITL."""
    status = get_pantry_status()
    low = [s for s in status if s["low"]]
    if force and not low:
        # Demo mode: treat the two most urgent staples as low
        low = status[:2]
    if not low:
        return None
    if _has_pending_refill() and not force:
        return None

    address_id = settings.DEFAULT_ADDRESS_ID
    items = [
        {
            "spinId": s["spinId"],
            "quantity": max(1, s["usual_quantity"]),
            "name": s["name"],
            "price_inr": s["unit_price_inr"],
        }
        for s in low[:6]
    ]
    est_total = sum((i.get("price_inr") or 0) * i["quantity"] for i in items)

    names = ", ".join(i["name"] for i in items[:4])
    eid = f"pantry-{uuid.uuid4().hex[:6]}"
    approval = create_approval(
        event_id=eid,
        thread_id=eid,
        trigger_type="pantry_refill",
        title="Khatam Hone Wala Hai · pantry refill",
        summary=f"Running low: {names}. Refill via Instamart?",
        cost_breakdown={
            "mode": "IM",
            "total_cost_inr": est_total,
            "items": items,
            "predictions": [
                {"name": s["name"], "days_left": s["days_left"]} for s in low[:6]
            ],
        },
        staged_payload={
            "mode": "ZERO_TOUCH_HOST",
            "staged_im_cart": {
                "selectedAddressId": address_id,
                "items": items,
                "estimated_total_inr": est_total,
            },
            "staged_food_cart": {"cartItems": [], "addressId": address_id},
        },
    )
    await send_approval_request(
        settings.NOTIFICATION_PLATFORM,
        {
            "request_id": approval["request_id"],
            "title": approval["title"],
            "location": "Home",
            "summary": approval["summary"],
        },
        approval["cost_breakdown"],
        f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{approval['request_id']}",
        request_id=approval["request_id"],
    )
    record_qol_event(
        kind="pantry_refill",
        title=f"Pantry low · {len(items)} staples",
        detail=approval["request_id"],
        severity="action",
        meta={"items": [i["name"] for i in items]},
        event_id=eid,
    )
    return {"status": "pending_approval", "approval": approval, "low_items": low}
