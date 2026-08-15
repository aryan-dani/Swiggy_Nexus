from __future__ import annotations

import random
import uuid
from typing import Any

from mock_data.active_orders import get_food_order, list_food_orders, save_food_order
from mock_data.food_catalog import FOOD_COUPONS, MENU_BY_RESTAURANT, RESTAURANTS
from mock_data.pune_addresses import ADDRESSES, get_address_by_id, public_address
from mcp_server.common import get_mock_scenario, get_param, pick_eta, simulated_latency_jitter_ms, tool_log
from mcp_server.session_store import clear_food_cart, get_session, resolve_session_id
from mcp_server.tool_aliases import resolve_method


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


def _flatten_menu_names(restaurant_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    blob = MENU_BY_RESTAURANT.get(restaurant_id)
    if not blob:
        return out
    for cat in blob.get("categories", []):
        for it in cat.get("items", []):
            out[str(it["item_id"])] = str(it.get("name") or it["item_id"])
    return out


def _restaurant_row(r: dict) -> dict[str, Any]:
    eta = pick_eta(r)
    rid = r["restaurant_id"]
    return {
        "id": rid,
        "restaurant_id": rid,
        "name": r["name"],
        "rating": r["rating"],
        "eta_mins": eta,
        "distanceKm": r.get("distance_km", round(random.uniform(1.5, 8.0), 1)),
        "availabilityStatus": r.get("availability_status", "OPEN"),
        "deliveryTimeRange": f"{r.get('eta_mins_min', 25)}-{r.get('eta_mins_max', 40)} MIN",
        "deliveryTimeSpoken": f"about {eta} minutes",
        "cuisines": r["cuisines"],
        "tag": r.get("tag"),
        "price_for_two_inr": r.get("price_for_two_inr"),
    }


def handle_get_addresses(params: dict[str, Any]) -> tuple[bool, dict[str, Any] | None, dict | None]:
    simulated_latency_jitter_ms()
    data = {"addresses": [public_address(a) for a in ADDRESSES]}
    tool_log("food", "get_addresses", params or {}, f"{len(ADDRESSES)} addresses returned")
    return True, data, None


def _query_tokens(query: str) -> list[str]:
    return [t for t in query.lower().replace(",", " ").split() if len(t) > 2]


def _haystack_match(query: str, *fields: str) -> bool:
    """Match full query or all meaningful tokens (so 'paneer biryani' hits cuisine 'Biryani')."""
    q = query.lower().strip()
    if not q:
        return True
    hay = " ".join(str(f).lower() for f in fields if f)
    if q in hay:
        return True
    tokens = _query_tokens(q)
    return bool(tokens) and all(t in hay for t in tokens)


def handle_search_restaurants(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    address_id = get_param(params, "addressId", "address_id")
    query = str(get_param(params, "query", "q") or "").lower().strip()
    sort_by = str(get_param(params, "sortBy") or "").lower().strip()
    if not address_id:
        return _error("VALIDATION", "addressId is required")
    addr = get_address_by_id(str(address_id))
    if not addr:
        return _error("NOT_FOUND", f"Unknown addressId: {address_id}")

    rows = list(RESTAURANTS)
    if query:
        rows = [
            r for r in rows
            if _haystack_match(
                query,
                r["name"],
                " ".join(r.get("cuisines", [])),
                str(r.get("tag", "")),
            )
        ] or list(RESTAURANTS)

    # Optional deterministic sorting instead of random shuffle
    if sort_by == "rating":
        rows = sorted(rows, key=lambda r: r.get("rating", 0), reverse=True)
    elif sort_by == "eta":
        rows = sorted(rows, key=lambda r: r.get("eta_mins_min", 30))
    elif sort_by == "distance":
        rows = sorted(rows, key=lambda r: r.get("distance_km", 5.0))
    else:
        random.shuffle(rows)

    out_rows = [_restaurant_row(r) for r in rows[:8]]
    data = {
        "addressId": address_id,
        "area": addr.get("area") or addr.get("locality"),
        "restaurants": out_rows,
        "nextOffset": len(out_rows),
    }
    tool_log("food", "search_restaurants", params or {}, f"{len(out_rows)} restaurants")
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
    sid = resolve_session_id(params)
    session = get_session(sid)
    rid = str(get_param(params, "restaurantId", "restaurant_id") or "").strip()
    address_id = str(get_param(params, "addressId", "address_id") or session.food.address_id or "").strip()
    restaurant_name = str(get_param(params, "restaurantName", "restaurant_name") or "")
    raw_lines = get_param(params, "lines", "items", "cartItems")
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    if not isinstance(raw_lines, list) or not raw_lines:
        return _error("VALIDATION", "lines/cartItems must be a non-empty list")

    flush_msg = None
    if session.food.restaurant_id and session.food.restaurant_id != rid and session.food.lines:
        clear_food_cart(sid)
        session = get_session(sid)
        flush_msg = f"Previous cart from another restaurant was cleared."

    prices = _flatten_menu_prices(rid)
    names = _flatten_menu_names(rid)
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
        lines_out.append({
            "item_id": item_id,
            "itemId": item_id,
            "name": names.get(item_id, item_id),
            "qty": qty,
            "quantity": qty,
            "unit_price_inr": unit,
            "line_total_inr": line_total,
            "valid_addons": [],
        })

    session.food.restaurant_id = rid
    session.food.restaurant_name = restaurant_name or next((r["name"] for r in RESTAURANTS if r["restaurant_id"] == rid), rid)
    session.food.address_id = address_id
    session.food.lines = lines_out

    cart_id = f"cart_fd_{sid}"
    blob = {
        "cart_id": cart_id,
        "restaurant_id": rid,
        "restaurantId": rid,
        "lines": lines_out,
        "items": lines_out,
        "subtotal_inr": subtotal,
        "total": subtotal - session.food.coupon_discount_inr,
        "message": flush_msg,
    }
    tool_log("food", "add_to_cart", params or {}, f"cart {cart_id}, subtotal INR {subtotal}")
    return True, blob, None


def handle_get_food_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    if get_mock_scenario() == "cart_expired":
        return _error("CART_EXPIRED", "Cart expired — please rebuild your order.")
    sid = resolve_session_id(params)
    session = get_session(sid)
    fc = session.food
    subtotal = sum(int(l.get("line_total_inr", 0)) for l in fc.lines)
    delivery = 40 if fc.lines else 0
    discount = fc.coupon_discount_inr
    total = max(0, subtotal + delivery - discount)
    data = {
        "cart_id": f"cart_fd_{sid}",
        "restaurantId": fc.restaurant_id,
        "restaurantName": fc.restaurant_name,
        "addressId": fc.address_id,
        "items": fc.lines,
        "lines": fc.lines,
        "subtotal_inr": subtotal,
        "deliveryCharge": delivery,
        "total": total,
        "availablePaymentMethods": ["COD"],
        "offers": {"coupon_applied": {"code": fc.coupon_code, "coupon_discount": discount}},
    }
    tool_log("food", "get_food_cart", params or {}, f"{len(fc.lines)} items, total INR {total}")
    return True, data, None


def handle_flush_food_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    sid = resolve_session_id(params)
    clear_food_cart(sid)
    tool_log("food", "flush_food_cart", params or {}, "cart cleared")
    return True, {"cleared": True}, None


def handle_fetch_food_coupons(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    cod = [c for c in FOOD_COUPONS if not c.get("requiresOnlinePayment")]
    data = {"coupons": cod}
    tool_log("food", "fetch_food_coupons", params or {}, f"{len(cod)} coupons")
    return True, data, None


def handle_apply_food_coupon(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    code = str(get_param(params, "code", "couponCode") or "").strip().upper()
    coupon = next((c for c in FOOD_COUPONS if c["code"] == code), None)
    if not coupon:
        return _error("COUPON_INVALID", f"Coupon {code} is not valid")
    if coupon.get("requiresOnlinePayment"):
        return _error("COUPON_REQUIRES_ONLINE_PAYMENT", "This coupon requires online payment")
    sid = resolve_session_id(params)
    session = get_session(sid)
    session.food.coupon_code = code
    session.food.coupon_discount_inr = int(coupon.get("discount_inr", 0))
    tool_log("food", "apply_food_coupon", params or {}, f"applied {code}")
    return True, {"code": code, "discount_inr": session.food.coupon_discount_inr}, None


def handle_place_order(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    sid = resolve_session_id(params)
    session = get_session(sid)
    cart_id = get_param(params, "cartId", "cart_id") or f"cart_fd_{sid}"
    address_id = str(get_param(params, "addressId", "address_id") or session.food.address_id or "")
    if not session.food.lines:
        return _error("VALIDATION", "Cart is empty — add items first")

    subtotal = sum(int(l.get("line_total_inr", 0)) for l in session.food.lines)
    total = subtotal + 40 - session.food.coupon_discount_inr
    if total >= 1000:
        return _error("VALIDATION", "Cart exceeds ₹1000 cap for Builders Club mock orders")

    rid = session.food.restaurant_id
    rest = next((r for r in RESTAURANTS if r["restaurant_id"] == rid), None)
    eta = pick_eta(rest) if rest else random.randint(28, 40)
    oid = f"FD_ORD_{uuid.uuid4().hex[:8].upper()}"
    msg = f"Swiggy order placed successfully. Delivery in {eta} mins. Payment: COD."
    data = {
        "order_id": oid,
        "orderId": oid,
        "cart_id": cart_id,
        "restaurant_id": rid,
        "addressId": address_id,
        "eta_mins": eta,
        "subtotal_inr": subtotal,
        "total": total,
        "paymentMethod": params.get("paymentMethod") or params.get("payment_mode") or "COD",
        "message": msg,
    }
    save_food_order(data)
    clear_food_cart(sid)
    tool_log("food", "place_order", params or {}, f"order_id={oid}, ETA {eta}m")
    return True, data, None


def handle_get_food_orders(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    orders = list_food_orders()
    data = {"orders": [{"orderId": o.get("orderId"), "status": "ACTIVE", **o} for o in orders]}
    tool_log("food", "get_food_orders", params or {}, f"{len(orders)} orders")
    return True, data, None


def handle_get_food_order_details(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    oid = str(get_param(params, "orderId", "order_id") or "")
    order = get_food_order(oid)
    if not order:
        return _error("NOT_FOUND", f"Order {oid} not found")
    tool_log("food", "get_food_order_details", params or {}, oid)
    return True, order, None


def handle_track_food_order(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    oid = str(get_param(params, "orderId", "order_id") or "")
    order = get_food_order(oid)
    if not order:
        return _error("NOT_FOUND", f"Order {oid} not found")
    data = {
        "orderId": oid,
        "status": "OUT_FOR_DELIVERY",
        "eta_mins": order.get("eta_mins", 25),
        "deliveryTimeSpoken": f"about {order.get('eta_mins', 25)} minutes",
    }
    tool_log("food", "track_food_order", params or {}, data["status"])
    return True, data, None


def handle_get_restaurant_details(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    """Return rich Food restaurant details: full menu counts, cuisines, ETA, amenities."""
    simulated_latency_jitter_ms()
    rid = str(get_param(params, "restaurantId", "restaurant_id") or "").strip()
    if not rid:
        return _error("VALIDATION", "restaurantId is required")
    rest = next((r for r in RESTAURANTS if r["restaurant_id"] == rid), None)
    if not rest:
        return _error("NOT_FOUND", f"Food restaurant {rid} not found")
    menu = MENU_BY_RESTAURANT.get(rid, {})
    item_count = sum(len(cat.get("items", [])) for cat in menu.get("categories", []))
    data = {
        "restaurantId": rid,
        "id": rid,
        "name": rest["name"],
        "rating": rest["rating"],
        "cuisines": rest.get("cuisines", []),
        "availabilityStatus": rest.get("availability_status", "OPEN"),
        "eta_mins": pick_eta(rest),
        "deliveryTimeRange": f"{rest.get('eta_mins_min', 25)}-{rest.get('eta_mins_max', 40)} MIN",
        "price_for_two_inr": rest.get("price_for_two_inr"),
        "tag": rest.get("tag"),
        "menu_item_count": item_count,
        "category_count": len(menu.get("categories", [])),
        "amenities": ["Free delivery on first order", "FSSAI certified", "Contactless delivery"],
        "offers": [
            {"title": "40% off up to ₹80", "code": "SWIGGY40"},
            {"title": "Free delivery above ₹199", "code": None},
        ],
    }
    tool_log("food", "get_restaurant_details", params or {}, rest["name"])
    return True, data, None


def handle_search_menu(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    """Cross-restaurant dish search with veg filter + pagination."""
    simulated_latency_jitter_ms()
    address_id = get_param(params, "addressId", "address_id") or ""
    query = str(get_param(params, "query", "q") or "").lower().strip()
    scoped_rid = str(get_param(params, "restaurantIdOfAddedItem", "restaurantId") or "").strip()
    veg_filter = int(get_param(params, "vegFilter") or 0)
    offset = int(get_param(params, "offset") or 0)

    if not query:
        return _error("VALIDATION", "query is required for search_menu")

    results: list[dict[str, Any]] = []
    restaurants_to_search = (
        [(rid, data) for rid, data in MENU_BY_RESTAURANT.items() if rid == scoped_rid]
        if scoped_rid
        else list(MENU_BY_RESTAURANT.items())
    )

    for rid, menu_data in restaurants_to_search:
        rest = next((r for r in RESTAURANTS if r["restaurant_id"] == rid), None)
        if not rest or rest.get("availability_status") == "CLOSED":
            continue
        for cat in menu_data.get("categories", []):
            for item in cat.get("items", []):
                if not _haystack_match(query, item.get("name", ""), item.get("description", "")):
                    continue
                if veg_filter == 1 and not item.get("vegetarian", False):
                    continue
                price_inr = item.get("price_inr", 0)
                results.append({
                    "itemId": item["item_id"],
                    "item_id": item["item_id"],
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "price_inr": price_inr,
                    "vegetarian": item.get("vegetarian", True),
                    "hasVariants": item.get("hasVariants", False),
                    "hasAddons": item.get("hasAddons", False),
                    "category": cat["name"],
                    "restaurantId": rid,
                    "restaurantName": rest["name"],
                    "restaurantRating": rest["rating"],
                    "eta_mins": pick_eta(rest),
                    "availabilityStatus": rest.get("availability_status", "OPEN"),
                    "shortDescription": f"{item['name']} from {rest['name']}, ₹{price_inr}",
                    "longDescription": (
                        f"{item.get('description', item['name'])} · "
                        f"{rest['name']} · ★{rest['rating']} · ₹{price_inr}"
                    ),
                })

    page_items = results[offset: offset + 10]
    next_offset = offset + 10 if (offset + 10) < len(results) else None
    data = {
        "items": page_items,
        "query": query,
        "addressId": address_id,
        "totalCount": len(results),
        "nextOffset": next_offset,
        "scopedToRestaurant": scoped_rid or None,
        "vegFilter": veg_filter,
    }
    tool_log("food", "search_menu", params or {}, f"{len(page_items)} items (total {len(results)})")
    return True, data, None


def handle_report_error(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    data = {
        "reportLink": "mailto:builders@swiggy.in?subject=Mock%20error%20report",
        "summary": "Error report generated (mock)",
    }
    tool_log("food", "report_error", params or {}, "report link")
    return True, data, None


def handle_get_payment_options(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    data = {
        "paymentOptions": [{"id": "COD", "label": "Cash on Delivery", "available": True}],
        "message": "Mock payment options (COD only)",
    }
    tool_log("food", "get_payment_options", params or {}, "1 option")
    return True, data, None


def handle_check_payment_status(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    data = {"status": "NOT_STARTED", "message": "No in-flight payment (mock)"}
    tool_log("food", "check_payment_status", params or {}, "NOT_STARTED")
    return True, data, None


def handle_confirm_order(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    return _error("VALIDATION", "confirm_order is HITL-only on live; mock refuses without PENDING_PAYMENT")


def handle_get_food_delivery_status(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    data = {"terminal": True, "message": "Widget-only ETA poller (mock stub)"}
    tool_log("food", "get_food_delivery_status", params or {}, "stub")
    return True, data, None


_TOOLS: dict[str, Any] = {
    "get_addresses": handle_get_addresses,
    "search_restaurants": handle_search_restaurants,
    "get_menu": handle_get_menu,
    "search_menu": handle_search_menu,
    "get_restaurant_details": handle_get_restaurant_details,
    "add_to_cart": handle_add_to_cart,
    "get_food_cart": handle_get_food_cart,
    "flush_food_cart": handle_flush_food_cart,
    "fetch_food_coupons": handle_fetch_food_coupons,
    "apply_food_coupon": handle_apply_food_coupon,
    "place_order": handle_place_order,
    "get_food_orders": handle_get_food_orders,
    "get_food_order_details": handle_get_food_order_details,
    "track_food_order": handle_track_food_order,
    "report_error": handle_report_error,
    "get_payment_options": handle_get_payment_options,
    "check_payment_status": handle_check_payment_status,
    "confirm_order": handle_confirm_order,
    "get_food_delivery_status": handle_get_food_delivery_status,
}


def invoke(method: str | None, params: dict[str, Any] | None) -> tuple[bool, Any, dict[str, Any] | None]:
    if not method or not isinstance(method, str):
        return _error("VALIDATION", "method is required")
    resolved = resolve_method("food", method)
    fn = _TOOLS.get(resolved)
    if not fn:
        return _error("UNKNOWN_METHOD", f"Unknown tool: {method}")
    return fn(dict(params or {}))
