from __future__ import annotations

import random
import uuid
from typing import Any

from mock_data.instamart_catalog import PRODUCTS
from mcp_server.common import get_param, simulated_latency_jitter_ms, tool_log

_im_cart_store: dict[str, dict[str, Any]] = {}


def _error(code: str, message: str) -> tuple[bool, None, dict[str, Any]]:
    return False, None, {"code": code, "message": message}


def handle_search_products(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    q = str(get_param(params, "query", "q") or "").lower().strip()
    rows = PRODUCTS
    if q:
        rows = [p for p in PRODUCTS if q in p["name"].lower() or q in p.get("category", "").lower()]
        if not rows:
            rows = PRODUCTS
    summary = "full catalog"
    tool_log("im", "search_products", params or {}, f"{len(rows)} SKUs matched ({summary})")
    return True, {"products": rows, "query": q or None}, None


def handle_add_to_cart(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    request_id = str(get_param(params, "requestId", "request_id") or "").strip()
    raw_items = get_param(params, "items", "lines")
    if not request_id:
        return _error("VALIDATION", "requestId is required")
    if not isinstance(raw_items, list) or not raw_items:
        return _error("VALIDATION", "items must be non-empty")

    sku_map = {p["product_id"]: p for p in PRODUCTS}
    lines: list[dict[str, Any]] = []
    subtotal = 0
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("product_id") or row.get("productId") or "").strip()
        qty = int(row.get("qty", 1) or 1)
        p = sku_map.get(pid)
        if not p:
            return _error("VALIDATION", f"Unknown product_id {pid}")
        unit = int(p["price_inr"])
        lt = unit * qty
        subtotal += lt
        lines.append(
            {"product_id": pid, "name": p["name"], "qty": qty, "unit_price_inr": unit, "line_total_inr": lt}
        )

    cart_id = f"cart_im_{request_id}"
    blob = {"cart_id": cart_id, "lines": lines, "subtotal_inr": subtotal}
    _im_cart_store[cart_id] = blob
    tool_log("im", "add_to_cart", params or {}, f"cart={cart_id} subtotal INR {subtotal}")
    return True, blob, None


def handle_checkout(params: dict[str, Any]) -> tuple[bool, dict | None, dict | None]:
    simulated_latency_jitter_ms()
    cart_id = get_param(params, "cartId", "cart_id")
    if not cart_id or str(cart_id) not in _im_cart_store:
        return _error("VALIDATION", "Valid cart_id required")
    cart = _im_cart_store[str(cart_id)]
    oid = f"IM_ORD_{uuid.uuid4().hex[:8].upper()}"
    eta = random.randint(18, 45)
    msg = "Instamart order packed and out for delivery."
    data = {
        "order_id": oid,
        "cart_id": cart_id,
        "eta_mins": eta,
        "subtotal_inr": cart.get("subtotal_inr"),
        "message": msg,
    }
    tool_log("im", "checkout", params or {}, f"placed {oid}, ETA ~{eta}m")
    del _im_cart_store[str(cart_id)]
    return True, data, None


_TOOLS = {
    "search_products": handle_search_products,
    "add_to_cart": handle_add_to_cart,
    "checkout": handle_checkout,
}


def invoke(method: str | None, params: dict[str, Any] | None) -> tuple[bool, Any, dict[str, Any] | None]:
    if not method or not isinstance(method, str):
        return _error("VALIDATION", "method is required")
    fn = _TOOLS.get(method.strip())
    if not fn:
        return _error("UNKNOWN_METHOD", f"Unknown tool: {method}")
    return fn(dict(params or {}))
