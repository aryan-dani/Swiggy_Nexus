from __future__ import annotations

import random
import uuid
from typing import Any

from mock_data.active_orders import get_booking, save_booking
from mock_data.dineout_catalog import DINEOUT_RESTAURANTS, structured_slots
from mock_data.pune_addresses import ADDRESSES
from mcp_server.common import get_mock_scenario, get_param, simulated_latency_jitter_ms, tool_log
from mcp_server.tool_aliases import resolve_method


def _error(code: str, message: str) -> tuple[bool, None, dict[str, Any]]:
    return False, None, {"code": code, "message": message}


def handle_get_saved_locations(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    locs = []
    for a in ADDRESSES:
        locs.append({
            "addressId": a["addressId"],
            "label": a.get("label"),
            "lat": a.get("_latitude"),
            "lng": a.get("_longitude"),
            "latitude": a.get("_latitude"),
            "longitude": a.get("_longitude"),
        })
    data = {"locations": locs}
    tool_log("dineout", "get_saved_locations", params or {}, f"{len(locs)} locations")
    return True, data, None


def handle_search_restaurants(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    query = str(get_param(params, "query", "q") or "").lower().strip()
    lat = get_param(params, "lat", "latitude")
    lng = get_param(params, "lng", "longitude")
    area_hint = str(get_param(params, "area", "city") or "").lower()
    rows = list(DINEOUT_RESTAURANTS)
    if query:
        rows = [
            r for r in rows
            if query in r["name"].lower()
            or any(query in c.lower() for c in r.get("cuisines", []))
            or query in r.get("area", "").lower()
        ] or list(DINEOUT_RESTAURANTS)
    if area_hint:
        filt = [r for r in rows if area_hint in r["area"].lower()]
        rows = filt or rows
    random.shuffle(rows)
    out = []
    for r in rows[:8]:
        out.append({
            "id": r["restaurant_id"],
            "restaurant_id": r["restaurant_id"],
            "name": r["name"],
            "rating": r["rating"],
            "cuisines": r["cuisines"],
            "area": r["area"],
            "costForTwo": r.get("costForTwo", r.get("price_for_two_inr")),
            "availability": r.get("availability", "AVAILABLE"),
            "booking_type": "TABLE",
            "latitude": lat or r.get("_lat"),
            "longitude": lng or r.get("_lng"),
        })
    tool_log("dineout", "search_restaurants", params or {}, f"{len(out)} venues")
    return True, {"restaurants": out}, None


def handle_check_availability(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    if get_mock_scenario() == "slot_gone":
        return _error("SLOT_UNAVAILABLE", "Selected slot is no longer available")
    rid = get_param(params, "restaurantId", "restaurant_id")
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    rest = next((r for r in DINEOUT_RESTAURANTS if r["restaurant_id"] == str(rid)), None)
    if not rest:
        return _error("NOT_FOUND", f"Unknown dineout venue {rid}")
    if rest.get("availability") == "UNAVAILABLE":
        return _error("RESTAURANT_NOT_BOOKABLE", "Restaurant is not bookable on Dineout")
    party_size = int(get_param(params, "partySize", "party_size", "guestCount") or 2)
    date = str(get_param(params, "date") or "2026-07-12")
    slots = structured_slots(str(rid), date, party_size)
    data = {
        "restaurant_id": rest["restaurant_id"],
        "restaurantId": rest["restaurant_id"],
        "name": rest["name"],
        "party_size": party_size,
        "guestCount": party_size,
        "date": date,
        "available": True,
        "slots": slots,
    }
    tool_log("dineout", "check_availability", params or {}, f"{len(slots)} structured slots")
    return True, data, None


def handle_book_table(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    rid = get_param(params, "restaurantId", "restaurant_id")
    slot = get_param(params, "slot", "time", "slotId")
    slot_id = get_param(params, "slotId")
    item_id = get_param(params, "itemId")
    reservation_time = get_param(params, "reservationTime")
    guests = int(get_param(params, "partySize", "party_size", "guestCount", "guests") or 2)
    lat = get_param(params, "latitude", "lat")
    lng = get_param(params, "longitude", "lng")
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    if not slot and not slot_id:
        return _error("VALIDATION", "slot or slotId is required")
    rest = next((r for r in DINEOUT_RESTAURANTS if r["restaurant_id"] == str(rid)), None)
    bid = f"DO_BK_{uuid.uuid4().hex[:8].upper()}"
    name = rest["name"] if rest else str(rid)
    slot_label = str(slot) if slot else f"slot {slot_id}"
    data = {
        "booking_id": bid,
        "bookingId": bid,
        "restaurant_id": str(rid),
        "restaurantId": str(rid),
        "venue_name": name,
        "guests": guests,
        "guestCount": guests,
        "slot": slot_label,
        "slotId": slot_id,
        "itemId": item_id,
        "reservationTime": reservation_time,
        "latitude": lat,
        "longitude": lng,
        "status": "CONFIRMED",
        "confirmation_message": (
            f"Table reserved at {name} for {guests} guests · {slot_label}. "
            "Arrive 10 minutes early. Free reservation (mock)."
        ),
    }
    save_booking(data)
    tool_log("dineout", "book_table", params or {}, f"booking_id={bid}")
    return True, data, None


def handle_get_booking_status(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    # Production docs use orderId; mock historically used bookingId — accept both.
    bid = str(
        get_param(params, "orderId", "order_id", "bookingId", "booking_id") or ""
    )
    bk = get_booking(bid)
    if not bk:
        return _error("NOT_FOUND", f"Booking/order {bid or '(empty)'} not found")
    # Echo both IDs so clients using either field work.
    if isinstance(bk, dict):
        bk = {
            **bk,
            "orderId": bk.get("orderId") or bk.get("booking_id") or bk.get("bookingId") or bid,
            "bookingId": bk.get("bookingId") or bk.get("booking_id") or bid,
        }
    tool_log("dineout", "get_booking_status", params or {}, bk.get("status", "CONFIRMED"))
    return True, bk, None


def handle_create_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    data = {"cartId": f"do_cart_{uuid.uuid4().hex[:6]}", "message": "Dineout cart created (mock)"}
    return True, data, None


def handle_get_restaurant_details(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    """Return rich venue details — ratings, amenities, deals, timings."""
    simulated_latency_jitter_ms()
    rid = str(get_param(params, "restaurantId", "restaurant_id") or "").strip()
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    rest = next((r for r in DINEOUT_RESTAURANTS if r["restaurant_id"] == rid), None)
    if not rest:
        return _error("NOT_FOUND", f"Dineout restaurant {rid} not found")
    data = {
        "restaurantId": rid,
        "id": rid,
        "name": rest["name"],
        "rating": rest["rating"],
        "cuisines": rest["cuisines"],
        "area": rest["area"],
        "costForTwo": rest.get("costForTwo", rest.get("price_for_two_inr")),
        "availability": rest.get("availability", "AVAILABLE"),
        "latitude": rest.get("_lat"),
        "longitude": rest.get("_lng"),
        "address": f"{rest['area']}, Pune",
        "description": (
            f"{rest['name']} is a {' & '.join(rest['cuisines'])} restaurant in {rest['area']}. "
            f"Rated {rest['rating']}/5 with excellent ambiance and a curated menu."
        ),
        "amenities": ["Parking", "Air Conditioning", "Wi-Fi", "Card Accepted"],
        "openingHours": "12:00 PM – 11:00 PM",
        "offers": [
            {"title": "20% off on pre-bookings", "code": "DINE20"},
            {"title": "Complimentary welcome drink", "code": None},
        ],
        "images": [],
    }
    tool_log("dineout", "get_restaurant_details", params or {}, rest["name"])
    return True, data, None


def handle_report_error(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    return True, {"reportLink": "mailto:builders@swiggy.in"}, None


def handle_render_restaurants_dineout(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    """Widget helper — return same search payload for mock."""
    return handle_search_restaurants(params)


def handle_get_payment_options(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    return True, {"paymentOptions": [{"id": "FREE", "label": "Free reservation", "available": True}]}, None


def handle_check_payment_status(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    return True, {"status": "NOT_STARTED"}, None


def handle_confirm_order(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    return False, None, {"code": "VALIDATION", "message": "confirm_order is HITL-only; mock refuses"}


_TOOLS = {
    "get_saved_locations": handle_get_saved_locations,
    "search_restaurants": handle_search_restaurants,
    "get_restaurant_details": handle_get_restaurant_details,
    "check_availability": handle_check_availability,
    "book_table": handle_book_table,
    "get_booking_status": handle_get_booking_status,
    "create_cart": handle_create_cart,
    "report_error": handle_report_error,
    "render_restaurants_dineout": handle_render_restaurants_dineout,
    "get_payment_options": handle_get_payment_options,
    "check_payment_status": handle_check_payment_status,
    "confirm_order": handle_confirm_order,
}


def invoke(method: str | None, params: dict[str, Any] | None) -> tuple[bool, Any, dict[str, Any] | None]:
    if not method or not isinstance(method, str):
        return _error("VALIDATION", "method is required")
    resolved = resolve_method("dineout", method)
    fn = _TOOLS.get(resolved)
    if not fn:
        return _error("UNKNOWN_METHOD", f"Unknown tool: {method}")
    return fn(dict(params or {}))
