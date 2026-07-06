from __future__ import annotations

import random
import uuid
from typing import Any

from mock_data.active_orders import get_im_order, save_im_order
from mock_data.go_to_items import items_for_address
from mock_data.instamart_catalog import PRODUCTS, PRODUCTS_BY_SPIN
from mock_data.pune_addresses import ADDRESSES, get_address_by_id, public_address
from mcp_server.common import get_mock_scenario, get_param, simulated_latency_jitter_ms, tool_log
from mcp_server.food.dispatcher import handle_get_addresses as food_get_addresses
from mcp_server.session_store import clear_im_cart, get_session, resolve_session_id
from mcp_server.tool_aliases import resolve_method


def _error(code: str, message: str) -> tuple[bool, None, dict[str, Any]]:
    return False, None, {"code": code, "message": message}


def handle_get_addresses(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    return food_get_addresses(params)


def handle_search_products(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    address_id = get_param(params, "addressId", "address_id")
    q = str(get_param(params, "query", "q") or "").lower().strip()
    rows = PRODUCTS
    if q:
        rows = [
            p for p in PRODUCTS
            if q in p["name"].lower() or q in p.get("category", "").lower()
        ] or PRODUCTS
    out = []
    for p in rows[:20]:
        # Get price from first variant or top-level price field
        variants = p.get("variants", [])
        price_inr = None
        if variants:
            price_inr = variants[0].get("price_inr")
        if price_inr is None:
            price_inr = p.get("price_inr")
        out.append({
            "product_id": p["product_id"],
            "name": p["name"],
            "category": p["category"],
            "price_inr": price_inr,
            "variants": variants,
        })
    data = {"products": out, "query": q or None, "addressId": address_id}
    tool_log("im", "search_products", params or {}, f"{len(out)} products")
    return True, data, None


def handle_your_go_to_items(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    address_id = str(get_param(params, "addressId", "address_id") or "addr_kp_001")
    party = bool(get_param(params, "party", "partyMode"))
    items = items_for_address(address_id, party=party)
    data = {"products": items, "addressId": address_id}
    tool_log("im", "your_go_to_items", params or {}, f"{len(items)} go-to items")
    return True, data, None


def handle_add_to_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    sid = resolve_session_id(params)
    session = get_session(sid)
    addr = str(get_param(params, "selectedAddressId", "addressId", "address_id") or session.im.selected_address_id or "")
    raw_items = get_param(params, "items", "lines")
    if not isinstance(raw_items, list) or not raw_items:
        return _error("VALIDATION", "items must be a non-empty list")

    if session.im.selected_address_id and addr and session.im.selected_address_id != addr and session.im.lines:
        clear_im_cart(sid)
        session = get_session(sid)

    lines: list[dict[str, Any]] = []
    subtotal = 0
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        spin = str(row.get("spinId") or row.get("spin_id") or "").strip()
        pid = str(row.get("product_id") or row.get("productId") or "").strip()
        qty = int(row.get("qty", row.get("quantity", 1)) or 1)
        sku = PRODUCTS_BY_SPIN.get(spin) if spin else None
        if not sku and pid:
            sku = next((p for p in PRODUCTS if p["product_id"] == pid), None)
            if sku and sku.get("variants"):
                spin = sku["variants"][0]["spinId"]
                sku = PRODUCTS_BY_SPIN.get(spin)
        if not sku:
            return _error("VALIDATION", f"Unknown spinId/product: {spin or pid}")
        unit = int(sku["price_inr"])
        lt = unit * qty
        subtotal += lt
        lines.append({
            "spinId": spin,
            "product_id": sku["product_id"],
            "name": sku["name"],
            "qty": qty,
            "quantity": qty,
            "unit_price_inr": unit,
            "line_total_inr": lt,
        })

    session.im.selected_address_id = addr or session.im.selected_address_id or "addr_kp_001"
    session.im.lines = lines
    cart_id = f"cart_im_{sid}"
    blob = {"cart_id": cart_id, "lines": lines, "items": lines, "subtotal_inr": subtotal, "total": subtotal}
    tool_log("im", "add_to_cart", params or {}, f"cart={cart_id} subtotal INR {subtotal}")
    return True, blob, None


def handle_get_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    if get_mock_scenario() == "cart_expired":
        return _error("CART_EXPIRED", "Instamart cart expired")
    sid = resolve_session_id(params)
    session = get_session(sid)
    subtotal = sum(int(l.get("line_total_inr", 0)) for l in session.im.lines)
    if subtotal > 0 and subtotal < 99:
        return _error("MIN_ORDER_NOT_MET", "Minimum order is ₹99 for Instamart")
    data = {
        "items": session.im.lines,
        "selectedAddressId": session.im.selected_address_id,
        "subtotal_inr": subtotal,
        "total": subtotal,
        "bill": {"itemTotal": subtotal, "delivery": 0, "grandTotal": subtotal},
        "availablePaymentMethods": ["COD"],
    }
    tool_log("im", "get_cart", params or {}, f"{len(session.im.lines)} items")
    return True, data, None


def handle_clear_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    sid = resolve_session_id(params)
    clear_im_cart(sid)
    tool_log("im", "clear_cart", params or {}, "cleared")
    return True, {"cleared": True}, None


def handle_checkout(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    sid = resolve_session_id(params)
    session = get_session(sid)
    cart_id = get_param(params, "cartId", "cart_id") or f"cart_im_{sid}"
    if not session.im.lines:
        return _error("VALIDATION", "Cart is empty")
    subtotal = sum(int(l.get("line_total_inr", 0)) for l in session.im.lines)
    if subtotal < 99:
        return _error("MIN_ORDER_NOT_MET", "Minimum order is ₹99")
    oid = f"IM_ORD_{uuid.uuid4().hex[:8].upper()}"
    eta = random.randint(18, 45)
    msg = "Swiggy Instamart order placed successfully. Packed and out for delivery."
    data = {
        "order_id": oid,
        "orderId": oid,
        "cart_id": cart_id,
        "eta_mins": eta,
        "subtotal_inr": subtotal,
        "message": msg,
    }
    save_im_order(data)
    clear_im_cart(sid)
    tool_log("im", "checkout", params or {}, f"placed {oid}")
    return True, data, None


def handle_get_orders(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    from mock_data.active_orders import list_im_orders
    simulated_latency_jitter_ms()
    orders = list_im_orders()
    data = {"orders": orders}
    tool_log("im", "get_orders", params or {}, f"{len(orders)} orders")
    return True, data, None


def handle_get_order_details(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    oid = str(get_param(params, "orderId", "order_id") or "")
    order = get_im_order(oid)
    if not order:
        return _error("NOT_FOUND", f"Order {oid} not found")
    return True, order, None


def handle_track_order(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    oid = str(get_param(params, "orderId", "order_id") or "")
    order = get_im_order(oid)
    if not order:
        return _error("NOT_FOUND", f"Order {oid} not found")
    data = {"orderId": oid, "status": "OUT_FOR_DELIVERY", "eta_mins": order.get("eta_mins", 20)}
    return True, data, None


def handle_create_address(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    aid = f"addr_new_{uuid.uuid4().hex[:6]}"
    data = {"addressId": aid, "message": "Address created (mock)"}
    tool_log("im", "create_address", params or {}, aid)
    return True, data, None


def handle_delete_address(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    aid = str(get_param(params, "addressId", "address_id") or "")
    if not get_address_by_id(aid):
        return _error("NOT_FOUND", f"Address {aid} not found")
    tool_log("im", "delete_address", params or {}, aid)
    return True, {"deleted": aid}, None


def handle_report_error(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    return True, {"reportLink": "mailto:builders@swiggy.in", "summary": "mock report"}, None


_TOOLS = {
    "get_addresses": handle_get_addresses,
    "search_products": handle_search_products,
    "your_go_to_items": handle_your_go_to_items,
    "add_to_cart": handle_add_to_cart,
    "get_cart": handle_get_cart,
    "clear_cart": handle_clear_cart,
    "checkout": handle_checkout,
    "get_orders": handle_get_orders,
    "get_order_details": handle_get_order_details,
    "track_order": handle_track_order,
    "create_address": handle_create_address,
    "delete_address": handle_delete_address,
    "report_error": handle_report_error,
}


def invoke(method: str | None, params: dict[str, Any] | None) -> tuple[bool, Any, dict[str, Any] | None]:
    if not method or not isinstance(method, str):
        return _error("VALIDATION", "method is required")
    resolved = resolve_method("im", method)
    fn = _TOOLS.get(resolved)
    if not fn:
        return _error("UNKNOWN_METHOD", f"Unknown tool: {method}")
    return fn(dict(params or {}))
