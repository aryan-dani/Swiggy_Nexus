from __future__ import annotations

import random
import uuid
from typing import Any

from mock_data.food_catalog import MENU_BY_RESTAURANT, RESTAURANTS
from mock_data.pune_addresses import ADDRESSES
from mcp_server.common import get_param, pick_eta, simulated_latency_jitter_ms, tool_log

_food_cart_store: dict[str, dict[str, Any]] = {}


def _error(code: str, message: str) -> tuple[bool, None, dict[str, Any]]:
    return False, None, {"code": code, "message": message}


def _flatten_menu_prices(restaurant_id: str) -> dict[str, int]:
    out: dict[str, int] = {}
    blob = MENU_BY_RESTAURANT.get(restaurant_id)
    if not blob:
        return out
    for cat in blob.get("categories", []):
        for it in cat.get("items", []):
            out[str(it["item_id"])] = int(it["price_inr"])
    return out


def handle_get_addresses(params: dict[str, Any]) -> tuple[bool, dict[str, Any] | None, dict | None]:
    simulated_latency_jitter_ms()
    data = {"addresses": list(ADDRESSES)}
    tool_log("food", "get_addresses", params or {}, f"{len(ADDRESSES)} addresses returned")
    return True, data, None


def handle_search_restaurants(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    address_id = get_param(params, "addressId", "address_id")
    if not address_id:
        return _error("VALIDATION", "addressId is required")
    addr = next((a for a in ADDRESSES if a["addressId"] == address_id), None)
    if not addr:
        return _error("NOT_FOUND", f"Unknown addressId: {address_id}")

    shuffled = list(RESTAURANTS)
    random.shuffle(shuffled)
    rows = []
    for r in shuffled[:5]:
        eta = pick_eta(r)
        rows.append(
            {
                "restaurant_id": r["restaurant_id"],
                "name": r["name"],
                "rating": r["rating"],
                "eta_mins": eta,
                "cuisines": r["cuisines"],
                "tag": r["tag"],
                "price_for_two_inr": r["price_for_two_inr"],
            }
        )

    data = {"addressId": address_id, "area": addr.get("area"), "restaurants": rows}
    tool_log("food", "search_restaurants", params or {}, f"{len(rows)} restaurants returned for {address_id}")
    return True, data, None


def handle_get_menu(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    rid = get_param(params, "restaurantId", "restaurant_id")
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    menu = MENU_BY_RESTAURANT.get(str(rid))
    if not menu:
        return _error("NOT_FOUND", f"No menu for restaurantId={rid}")
    tool_log("food", "get_menu", params or {}, f"menu loaded for {rid}")
    return True, dict(menu), None


def handle_add_to_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    request_id = str(get_param(params, "requestId", "request_id") or "").strip()
    rid = str(get_param(params, "restaurantId", "restaurant_id") or "").strip()
    raw_lines = get_param(params, "lines", "items")
    if not request_id:
        return _error("VALIDATION", "requestId is required for session-scoped cart")
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    if not isinstance(raw_lines, list) or not raw_lines:
        return _error("VALIDATION", "lines must be a non-empty list")

    prices = _flatten_menu_prices(rid)
    lines_out: list[dict[str, Any]] = []
    subtotal = 0
    for row in raw_lines:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("item_id") or row.get("itemId") or "").strip()
        qty = int(row.get("qty", row.get("quantity", 1)) or 1)
        unit = prices.get(item_id)
        if unit is None:
            return _error("VALIDATION", f"Unknown item_id {item_id} for restaurant {rid}")
        line_total = unit * qty
        subtotal += line_total
        lines_out.append(
            {
                "item_id": item_id,
                "qty": qty,
                "unit_price_inr": unit,
                "line_total_inr": line_total,
            }
        )

    cart_id = f"cart_fd_{request_id}"
    blob = {"cart_id": cart_id, "restaurant_id": rid, "lines": lines_out, "subtotal_inr": subtotal}
    _food_cart_store[cart_id] = blob
    tool_log("food", "add_to_cart", params or {}, f"cart {cart_id}, subtotal INR {subtotal}")
    return True, blob, None


def handle_place_order(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    cart_id = get_param(params, "cartId", "cart_id")
    if not cart_id or str(cart_id) not in _food_cart_store:
        return _error("VALIDATION", "Valid cart_id is required (call add_to_cart first in this demo)")

    cart = _food_cart_store[str(cart_id)]
    rid = cart["restaurant_id"]
    rest = next((r for r in RESTAURANTS if r["restaurant_id"] == rid), None)
    eta = pick_eta(rest) if rest else random.randint(28, 40)
    oid = f"FD_ORD_{uuid.uuid4().hex[:8].upper()}"
    msg = f"Order confirmed. Delivery in {eta} mins."
    data = {
        "order_id": oid,
        "cart_id": cart_id,
        "restaurant_id": rid,
        "eta_mins": eta,
        "subtotal_inr": cart.get("subtotal_inr"),
        "payment_mode": params.get("paymentMode") or params.get("payment_mode") or "COD",
        "message": msg,
    }
    tool_log("food", "place_order", params or {}, f"order_id={oid}, ETA {eta}m")
    del _food_cart_store[str(cart_id)]
    return True, data, None


_TOOLS: dict[str, Any] = {
    "get_addresses": handle_get_addresses,
    "search_restaurants": handle_search_restaurants,
    "get_menu": handle_get_menu,
    "add_to_cart": handle_add_to_cart,
    "place_order": handle_place_order,
}


def invoke(method: str | None, params: dict[str, Any] | None) -> tuple[bool, Any, dict[str, Any] | None]:
    if not method or not isinstance(method, str):
        return _error("VALIDATION", "method is required")
    fn = _TOOLS.get(method.strip())
    if not fn:
        return _error("UNKNOWN_METHOD", f"Unknown tool: {method}")
    p = dict(params or {})
    return fn(p)
