"""Canonical Swiggy MCP tool names + LLM prefix aliases.

Live ``tools/list`` is the source of truth for *what exists*.
This module maps LLM-facing names (``food_add_to_cart``) onto
``(server, canonical_name)`` for ``tools/call``.

Legacy mock handler names (``get_menu``, ``add_to_cart``) are also accepted
so Chrono-Host / older callers keep working until fully migrated.
"""

from __future__ import annotations

from typing import Literal

Vertical = Literal["food", "im", "dineout"]

# ---------------------------------------------------------------------------
# Canonical inventory (docs + live expectation). Updated after tools/list.
# ---------------------------------------------------------------------------

# Synced from live tools/list 2026-08-15 (docs/mcp-live-catalog.json). Catalog wins.
FOOD_CANONICAL: frozenset[str] = frozenset(
    {
        "get_addresses",
        "search_restaurants",
        "search_menu",
        "get_restaurant_menu",
        "get_food_cart",
        "update_food_cart",
        "flush_food_cart",
        "place_food_order",
        "fetch_food_coupons",
        "apply_food_coupon",
        "get_food_orders",
        "get_food_order_details",
        "track_food_order",
        "get_food_delivery_status",
        "report_error",
        "get_payment_options",
        "check_payment_status",
        "confirm_order",
    }
)

IM_CANONICAL: frozenset[str] = frozenset(
    {
        "get_addresses",
        "search_products",
        "your_go_to_items",
        "get_cart",
        "update_cart",
        "clear_cart",
        "checkout",
        "get_orders",
        "track_order",
        "get_delivery_status",
        "report_error",
        "get_payment_options",
        "check_payment_status",
        "confirm_order",
    }
)

DINEOUT_CANONICAL: frozenset[str] = frozenset(
    {
        "get_saved_locations",
        "search_restaurants_dineout",
        "get_restaurant_details",
        "render_restaurants_dineout",
        "get_available_slots",
        "book_table",
        "create_cart",
        "get_booking_status",
        "report_error",
        "get_payment_options",
        "check_payment_status",
        "confirm_order",
    }
)

# Money / irreversible — HITL only; never probe live without approval.
WRITE_TOOLS_CANONICAL: frozenset[str] = frozenset(
    {
        "place_food_order",
        "checkout",
        "book_table",
        "confirm_order",
        "create_address",
        "delete_address",
        "apply_food_coupon",
        "apply_coupon",
    }
)

# Legacy mock handler → canonical (for in-process mock + old agent calls)
_LEGACY_TO_CANONICAL: dict[tuple[str, str], str] = {
    ("food", "get_menu"): "get_restaurant_menu",
    ("food", "add_to_cart"): "update_food_cart",
    ("food", "place_order"): "place_food_order",
    ("im", "add_to_cart"): "update_cart",
    ("dineout", "search_restaurants"): "search_restaurants_dineout",
    ("dineout", "check_availability"): "get_available_slots",
}

# Canonical → legacy mock handler (mcp_server dispatchers)
_CANONICAL_TO_LEGACY: dict[tuple[str, str], str] = {
    ("food", "get_restaurant_menu"): "get_menu",
    ("food", "update_food_cart"): "add_to_cart",
    ("food", "place_food_order"): "place_order",
    ("im", "update_cart"): "add_to_cart",
    ("dineout", "search_restaurants_dineout"): "search_restaurants",
    ("dineout", "get_available_slots"): "check_availability",
}

# LLM prefixed name → (server, canonical)
# Built from common patterns; extend when catalog regenerates schemas.
_LLM_ALIASES: dict[str, tuple[Vertical, str]] = {
    # Food
    "food_get_addresses": ("food", "get_addresses"),
    "food_search_restaurants": ("food", "search_restaurants"),
    "food_search_menu": ("food", "search_menu"),
    "food_get_menu": ("food", "get_restaurant_menu"),
    "food_get_restaurant_menu": ("food", "get_restaurant_menu"),
    "food_add_to_cart": ("food", "update_food_cart"),
    "food_update_food_cart": ("food", "update_food_cart"),
    "food_get_food_cart": ("food", "get_food_cart"),
    "food_flush_food_cart": ("food", "flush_food_cart"),
    "food_fetch_food_coupons": ("food", "fetch_food_coupons"),
    "food_apply_food_coupon": ("food", "apply_food_coupon"),
    "food_place_order": ("food", "place_food_order"),
    "food_place_food_order": ("food", "place_food_order"),
    "food_get_food_orders": ("food", "get_food_orders"),
    "food_get_food_order_details": ("food", "get_food_order_details"),
    "food_track_food_order": ("food", "track_food_order"),
    "food_get_food_delivery_status": ("food", "get_food_delivery_status"),
    "food_get_payment_options": ("food", "get_payment_options"),
    "food_check_payment_status": ("food", "check_payment_status"),
    "food_confirm_order": ("food", "confirm_order"),
    "food_report_error": ("food", "report_error"),
    # Instamart
    "im_get_addresses": ("im", "get_addresses"),
    "im_search_products": ("im", "search_products"),
    "im_your_go_to_items": ("im", "your_go_to_items"),
    "im_add_to_cart": ("im", "update_cart"),
    "im_update_cart": ("im", "update_cart"),
    "im_get_cart": ("im", "get_cart"),
    "im_clear_cart": ("im", "clear_cart"),
    "im_list_coupons": ("im", "list_coupons"),
    "im_apply_coupon": ("im", "apply_coupon"),
    "im_checkout": ("im", "checkout"),
    "im_get_orders": ("im", "get_orders"),
    "im_get_order_details": ("im", "get_order_details"),
    "im_track_order": ("im", "track_order"),
    "im_get_delivery_status": ("im", "get_delivery_status"),
    "im_create_address": ("im", "create_address"),
    "im_delete_address": ("im", "delete_address"),
    "im_get_payment_options": ("im", "get_payment_options"),
    "im_check_payment_status": ("im", "check_payment_status"),
    "im_confirm_order": ("im", "confirm_order"),
    "im_report_error": ("im", "report_error"),
    # Dineout
    "dineout_get_saved_locations": ("dineout", "get_saved_locations"),
    "dineout_search_restaurants": ("dineout", "search_restaurants_dineout"),
    "dineout_search_restaurants_dineout": ("dineout", "search_restaurants_dineout"),
    "dineout_get_restaurant_details": ("dineout", "get_restaurant_details"),
    "dineout_render_restaurants_dineout": ("dineout", "render_restaurants_dineout"),
    "dineout_check_availability": ("dineout", "get_available_slots"),
    "dineout_get_available_slots": ("dineout", "get_available_slots"),
    "dineout_create_cart": ("dineout", "create_cart"),
    "dineout_book_table": ("dineout", "book_table"),
    "dineout_get_booking_status": ("dineout", "get_booking_status"),
    "dineout_get_payment_options": ("dineout", "get_payment_options"),
    "dineout_check_payment_status": ("dineout", "check_payment_status"),
    "dineout_confirm_order": ("dineout", "confirm_order"),
    "dineout_report_error": ("dineout", "report_error"),
}


def resolve_llm_tool(name: str) -> tuple[Vertical, str]:
    """Map an LLM / Telegram tool name to (server, canonical MCP name)."""
    n = (name or "").strip()
    if n in _LLM_ALIASES:
        return _LLM_ALIASES[n]

    # Fallback: food_*, im_*, dineout_* with remainder already canonical
    for prefix, server in (("food_", "food"), ("im_", "im"), ("dineout_", "dineout")):
        if n.startswith(prefix):
            rest = n[len(prefix) :]
            canon = to_canonical(server, rest)  # type: ignore[arg-type]
            return server, canon  # type: ignore[return-value]

    raise KeyError(f"Unknown MCP tool alias: {name!r}")


def to_canonical(server: Vertical, method: str) -> str:
    """Normalize a method name to the live MCP canonical name."""
    m = (method or "").strip()
    return _LEGACY_TO_CANONICAL.get((server, m), m)


def to_legacy_handler(server: Vertical, method: str) -> str:
    """Map canonical → in-process mock dispatcher handler name."""
    m = to_canonical(server, method)
    return _CANONICAL_TO_LEGACY.get((server, m), m)


def is_write_tool(canonical_name: str) -> bool:
    return canonical_name in WRITE_TOOLS_CANONICAL


def llm_alias_for(server: Vertical, canonical: str) -> str:
    """Prefer a stable LLM-facing name for schemas."""
    # Prefer existing explicit aliases that match
    for llm_name, (srv, can) in _LLM_ALIASES.items():
        if srv == server and can == canonical:
            # Prefer short legacy-style food_add_to_cart over food_update_food_cart
            if llm_name.endswith(f"_{canonical}") or llm_name in (
                "food_add_to_cart",
                "food_get_menu",
                "food_place_order",
                "im_add_to_cart",
                "dineout_search_restaurants",
                "dineout_check_availability",
            ):
                return llm_name
    return f"{server}_{canonical}"
