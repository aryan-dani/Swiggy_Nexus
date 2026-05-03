from __future__ import annotations

import random
import uuid
from typing import Any

from mock_data.dineout_catalog import DEFAULT_SLOTS, DINEOUT_RESTAURANTS
from mcp_server.common import get_param, simulated_latency_jitter_ms, tool_log


def _error(code: str, message: str) -> tuple[bool, None, dict[str, Any]]:
    return False, None, {"code": code, "message": message}


def handle_search_restaurants(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    area_hint = str(get_param(params, "area", "city") or "").lower()
    rows = list(DINEOUT_RESTAURANTS)
    random.shuffle(rows)
    if area_hint:
        filt = [r for r in rows if area_hint in r["area"].lower()]
        rows = filt or rows
    out = [{**r, "booking_type": "TABLE"} for r in rows[: min(6, len(rows))]]
    tool_log("dineout", "search_restaurants", params or {}, f"{len(out)} dine-out venues")
    return True, {"restaurants": out}, None


def handle_check_availability(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    rid = get_param(params, "restaurantId", "restaurant_id")
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    rest = next((r for r in DINEOUT_RESTAURANTS if r["restaurant_id"] == str(rid)), None)
    if not rest:
        return _error("NOT_FOUND", f"Unknown dineout venue {rid}")
    party_size = int(get_param(params, "partySize", "party_size") or 2)
    date = str(get_param(params, "date") or "2026-05-10")
    k = random.randint(5, len(DEFAULT_SLOTS))
    slots = random.sample(DEFAULT_SLOTS, k=min(k, len(DEFAULT_SLOTS)))
    slots.sort()
    data = {
        "restaurant_id": rest["restaurant_id"],
        "name": rest["name"],
        "party_size": party_size,
        "date": date,
        "available": True,
        "slots": slots,
    }
    tool_log(
        "dineout",
        "check_availability",
        params or {},
        f"{len(slots)} slots returned for party {party_size}",
    )
    return True, data, None


def handle_book_table(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    rid = get_param(params, "restaurantId", "restaurant_id")
    slot = get_param(params, "slot", "time")
    guests = int(get_param(params, "partySize", "party_size", "guests") or 2)
    if not rid or not slot:
        return _error("VALIDATION", "restaurantId and slot/time are required")
    rest = next((r for r in DINEOUT_RESTAURANTS if r["restaurant_id"] == str(rid)), None)
    bid = f"DO_BK_{uuid.uuid4().hex[:8].upper()}"
    name = rest["name"] if rest else rid
    data = {
        "booking_id": bid,
        "restaurant_id": str(rid),
        "venue_name": name,
        "guests": guests,
        "slot": str(slot),
        "confirmation_message": (
            f"Table reserved at {name} for {guests} guests · {slot}. "
            "Arrive 10 mins early; deal is prepaid in this mock demo."
        ),
    }
    tool_log("dineout", "book_table", params or {}, f"booking_id={bid}")
    return True, data, None


_TOOLS = {
    "search_restaurants": handle_search_restaurants,
    "check_availability": handle_check_availability,
    "book_table": handle_book_table,
}


def invoke(method: str | None, params: dict[str, Any] | None) -> tuple[bool, Any, dict[str, Any] | None]:
    if not method or not isinstance(method, str):
        return _error("VALIDATION", "method is required")
    fn = _TOOLS.get(method.strip())
    if not fn:
        return _error("UNKNOWN_METHOD", f"Unknown tool: {method}")
    return fn(dict(params or {}))
