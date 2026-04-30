"""Mock MCP layer: JSON-RPC-style tool dispatch with synthetic Swiggy-like data."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any


def _rpc_log(method: str, params: dict[str, Any], result: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
        "result": result,
        "ts": time.time(),
    }


def food_search_restaurants(cuisine: str, lat: float, long: float) -> list[dict[str, Any]]:
    """Mock Food delivery search."""
    base = cuisine or "any"
    return [
        {
            "id": "mock-food-1",
            "name": f"Nexus Kitchen — {base.title()} Hub",
            "rating": 4.6,
            "eta_mins": 28,
            "tag": "Fast delivery",
            "cuisine": base,
            "lat": lat,
            "long": long,
        },
        {
            "id": "mock-food-2",
            "name": "Demo Diner Express",
            "rating": 4.3,
            "eta_mins": 35,
            "tag": "Budget-friendly",
            "cuisine": base,
            "lat": lat,
            "long": long,
        },
        {
            "id": "mock-food-3",
            "name": "Synth Spice Grove",
            "rating": 4.8,
            "eta_mins": 32,
            "tag": "Top rated (demo)",
            "cuisine": base,
            "lat": lat,
            "long": long,
        },
    ]


def instamart_get_inventory(category: str) -> list[dict[str, Any]]:
    """Mock Instamart SKU list."""
    cat = (category or "groceries").lower()
    catalog: dict[str, list[dict[str, Any]]] = {
        "snacks": [
            {"sku": "imx-101", "name": "Demo Crunch Mix 200g", "price_inr": 99, "in_stock": True},
            {"sku": "imx-102", "name": "Nexus Energy Bar (pack of 6)", "price_inr": 240, "in_stock": True},
        ],
        "beverages": [
            {"sku": "imx-201", "name": "Sparkling Demo Cola 500ml", "price_inr": 45, "in_stock": True},
            {"sku": "imx-202", "name": "Cold Brew Stub (demo)", "price_inr": 120, "in_stock": False},
        ],
        "groceries": [
            {"sku": "imx-301", "name": "Instant Noodles (demo pack)", "price_inr": 55, "in_stock": True},
            {"sku": "imx-302", "name": "Organic Basmati 1kg (synthetic)", "price_inr": 189, "in_stock": True},
        ],
    }
    return catalog.get(cat, catalog["groceries"])


def dineout_check_availability(
    restaurant_id: str, party_size: int, time: str
) -> dict[str, Any]:
    """Mock Dineout table availability."""
    rid = restaurant_id or "demo-rest"
    return {
        "restaurant_id": rid,
        "party_size": party_size,
        "time_slot": time,
        "available": True,
        "slots": ["18:00", "18:30", "19:00", "19:30", "20:00"],
        "note": "Synthetic slots for POC — not real Swiggy data.",
    }


_METHODS: dict[str, Any] = {
    "food_search_restaurants": food_search_restaurants,
    "instamart_get_inventory": instamart_get_inventory,
    "dineout_check_availability": dineout_check_availability,
}


def dispatch(method: str, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """
    JSON-RPC-style dispatch. Returns (result, log_entry for Developer Mode).
    Raises KeyError for unknown method, TypeError for bad params.
    """
    if method not in _METHODS:
        raise KeyError(f"Unknown MCP method: {method}")

    fn = _METHODS[method]
    call_params = dict(params)
    if method == "dineout_check_availability" and "time_slot" in call_params and "time" not in call_params:
        call_params["time"] = call_params.pop("time_slot")
    result = fn(**call_params)
    log = _rpc_log(method, params, result)
    return result, log


def dispatch_safe(method: str, params: dict[str, Any]) -> tuple[Any, dict[str, Any] | None, str | None]:
    """Returns (result, log, error_message). error_message set on failure."""
    try:
        result, log = dispatch(method, params)
        return result, log, None
    except (KeyError, TypeError) as e:
        return None, None, str(e)
