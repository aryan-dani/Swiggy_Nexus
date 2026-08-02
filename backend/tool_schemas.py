"""Tool schema definitions — the 23 LLM-callable tools for Food, Instamart, Dineout.

Separated from llm_orchestrator.py to keep that module focused on orchestration logic.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Food (10 tools)
# ---------------------------------------------------------------------------

_FOOD_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "food_get_addresses",
            "description": (
                "Get the user's saved delivery addresses. ALWAYS call this first "
                "when the user wants to order food or groceries. Present the list "
                "and wait for the user to pick one before proceeding."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_search_restaurants",
            "description": (
                "Search for food delivery restaurants near a saved address. "
                "Only recommend restaurants with availabilityStatus='OPEN'. "
                "Mention distance and ETA for far restaurants."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string", "description": "Address ID from food_get_addresses."},
                    "query": {"type": "string", "description": "Cuisine or restaurant name query."},
                    "sortBy": {
                        "type": "string",
                        "enum": ["rating", "eta", "distance"],
                        "description": "Optional sort order for results.",
                    },
                },
                "required": ["addressId", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_search_menu",
            "description": (
                "Search for specific dishes across all restaurants (or within one). "
                "Use when user asks for a specific dish by name. "
                "Set vegFilter=1 for veg-only results. Use restaurantIdOfAddedItem to scope to current restaurant."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string", "description": "Address ID for delivery."},
                    "query": {"type": "string", "description": "Dish name to search for."},
                    "restaurantIdOfAddedItem": {
                        "type": "string",
                        "description": "Optional — scope search to this restaurant ID.",
                    },
                    "vegFilter": {
                        "type": "integer",
                        "enum": [0, 1],
                        "description": "1 = veg only, 0 = all items (default).",
                    },
                    "offset": {"type": "integer", "description": "Pagination offset (default 0)."},
                },
                "required": ["addressId", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_get_menu",
            "description": "Get the full paginated menu for a specific restaurant by restaurantId.",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "addressId": {"type": "string"},
                    "page": {"type": "integer", "description": "Page number (default 1)."},
                },
                "required": ["restaurantId", "addressId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_add_to_cart",
            "description": (
                "Add items to the food delivery cart. After calling this, ALWAYS "
                "call food_get_food_cart immediately to show the updated cart to the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "addressId": {"type": "string"},
                    "lines": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_id": {"type": "string"},
                                "qty": {"type": "integer"},
                            },
                            "required": ["item_id", "qty"],
                        },
                    },
                },
                "required": ["restaurantId", "addressId", "lines"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_get_food_cart",
            "description": (
                "View the current food delivery cart with bill breakdown. "
                "Call this after every update_food_cart and before place_order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string"},
                },
                "required": ["addressId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_fetch_food_coupons",
            "description": "Fetch available coupons and offers for the current food cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "addressId": {"type": "string"},
                    "couponCode": {
                        "type": "string",
                        "description": "Optional specific coupon to check.",
                    },
                },
                "required": ["restaurantId", "addressId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_apply_food_coupon",
            "description": (
                "Apply a coupon code to the food cart. Only report savings if "
                "coupon_discount > 0. Do NOT say a coupon is applied if discount is 0."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "couponCode": {"type": "string"},
                    "addressId": {"type": "string"},
                },
                "required": ["couponCode", "addressId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_place_order",
            "description": (
                "Place the food delivery order. CRITICAL: ALWAYS get explicit user "
                "confirmation first. Call food_get_food_cart first to show order summary. "
                "Cart total must be under ₹1000 (beta restriction). COD only in v1."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string", "description": "Address ID for delivery."},
                    "paymentMethod": {
                        "type": "string",
                        "enum": ["COD"],
                        "default": "COD",
                        "description": "Payment method — COD only in v1.",
                    },
                },
                "required": ["addressId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_track_food_order",
            "description": "Track the live status of an active food delivery order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "orderId": {
                        "type": "string",
                        "description": "Order ID to track. Omit to return all active orders.",
                    },
                },
                "required": [],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Instamart (7 tools)
# ---------------------------------------------------------------------------

_IM_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "im_search_products",
            "description": (
                "Search for Instamart grocery products. Returns variants with spinIds "
                "and prices. Instamart has a ₹99 minimum order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string"},
                    "query": {"type": "string", "description": "Product name, category, or brand."},
                },
                "required": ["addressId", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "im_your_go_to_items",
            "description": (
                "Fetch the user's frequently ordered Instamart items (quick reorder). "
                "Offer this before search for returning Instamart users."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string"},
                },
                "required": ["addressId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "im_add_to_cart",
            "description": (
                "Add items to the Instamart cart (replaces entire cart). "
                "Use spinId from variants. Do NOT switch address mid-cart — "
                "clear the cart first if the address changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selectedAddressId": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "spinId": {"type": "string"},
                                "quantity": {"type": "integer"},
                            },
                            "required": ["spinId", "quantity"],
                        },
                    },
                },
                "required": ["selectedAddressId", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "im_get_cart",
            "description": "View the current Instamart cart with bill breakdown and available payment methods.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "im_checkout",
            "description": (
                "Checkout the Instamart cart. CRITICAL: ALWAYS get explicit user confirmation first. "
                "Show get_cart summary, verify cart > ₹99 minimum. COD only in v1. "
                "Cart total must be under ₹1000 (beta restriction)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string"},
                    "paymentMethod": {
                        "type": "string",
                        "enum": ["COD"],
                        "default": "COD",
                    },
                },
                "required": ["addressId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "im_track_order",
            "description": "Track a live Instamart order status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "orderId": {"type": "string"},
                    "lat": {"type": "number", "description": "Delivery address latitude."},
                    "lng": {"type": "number", "description": "Delivery address longitude."},
                },
                "required": ["orderId", "lat", "lng"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "im_get_orders",
            "description": "List recent Instamart orders for the current user.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ---------------------------------------------------------------------------
# Dineout (6 tools)
# ---------------------------------------------------------------------------

_DINEOUT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "dineout_get_saved_locations",
            "description": (
                "Get user's saved locations for Dineout restaurant search. "
                "Use when user says 'near my home', 'near my office', 'my location'. "
                "Do NOT use when user mentions a specific city — use lat/lng directly."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_search_restaurants",
            "description": (
                "Search for Dineout (table booking) restaurants. Filter results to "
                "availability='AVAILABLE' only. Bangalore coords: 12.9716, 77.5946. "
                "Pune center: 18.5204, 73.8567."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Cuisine, area, or restaurant name."},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "area": {"type": "string", "description": "Optional area/locality hint."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_get_restaurant_details",
            "description": (
                "Get full details for a Dineout restaurant: ratings, amenities, "
                "opening hours, deals, and address. Always show details BEFORE "
                "asking for slot confirmation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["restaurantId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_check_availability",
            "description": (
                "Check available table booking slots for a Dineout restaurant. "
                "Returns slots for up to 7 days from the requested date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "guestCount": {"type": "integer"},
                    "date": {"type": "string", "description": "YYYY-MM-DD format."},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["restaurantId", "guestCount", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_book_table",
            "description": (
                "Book a Dineout table. NOT idempotent — on failure, call "
                "dineout_get_booking_status before retrying. Only free reservations "
                "are supported (isFree=true). ALWAYS confirm slot, date, and party "
                "size with the user before calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "slotId": {"type": "integer", "description": "slotId from get_available_slots."},
                    "itemId": {"type": "string", "description": "Deal item ID from slot.deals[].itemId."},
                    "reservationTime": {"type": "integer", "description": "Unix timestamp from slot."},
                    "guestCount": {"type": "integer"},
                    "slot": {"type": "string", "description": "Human-readable slot label (e.g. 19:00)."},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["restaurantId", "guestCount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_get_booking_status",
            "description": "Get the status of a Dineout table booking by bookingId.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bookingId": {"type": "string"},
                },
                "required": ["bookingId"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [*_FOOD_TOOLS, *_IM_TOOLS, *_DINEOUT_TOOLS]

_NEXUS_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "nexus_plan_night_out",
            "description": (
                "Schedule a Google Calendar dinner invite, stage a Dineout table, "
                "and prepare equal bill split after Approve. "
                "ONLY call when the user already gave guests AND restaurant AND time/slot. "
                "If any of those are missing, do NOT call this — tell them to use /nightout."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "guests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Friend first names or emails (e.g. Himali, Siya, Swayam).",
                    },
                    "venue": {
                        "type": "string",
                        "description": "Restaurant name/location (required — no default).",
                    },
                    "guest_count": {
                        "type": "integer",
                        "description": "Party size including host. Default = guests + host.",
                    },
                    "slot": {
                        "type": "string",
                        "description": "Preferred table time like 20:00.",
                    },
                    "start_iso": {
                        "type": "string",
                        "description": "ISO start time for the Calendar event.",
                    },
                },
                "required": ["guests", "venue"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexus_plan_dinner_party",
            "description": (
                "Schedule a home dinner-party Calendar invite, stage Food/Instamart carts, "
                "and equal-split after Approve. Use for hosting + ordering food + split."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "guests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Friend first names or emails.",
                    },
                    "dish_query": {
                        "type": "string",
                        "description": "What to order (e.g. paneer biryani).",
                    },
                    "guest_count": {"type": "integer"},
                },
                "required": ["guests"],
            },
        },
    },
]

# Telegram agent tools = MCP verticals + Nexus orchestration helpers.
TELEGRAM_TOOLS: list[dict[str, Any]] = [*TOOLS, *_NEXUS_TOOLS]


def _short_desc(text: str, limit: int = 90) -> str:
    first = (text or "").split(".")[0].strip()
    if not first:
        return ""
    if len(first) <= limit:
        return first
    return first[: limit - 1].rstrip() + "…"


def _tools_for_llm(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same names + parameters as TOOLS, with short descriptions to cut prompt tokens."""
    import copy

    out: list[dict[str, Any]] = []
    for tool in tools:
        t = copy.deepcopy(tool)
        fn = t.get("function") or {}
        fn["description"] = _short_desc(str(fn.get("description") or fn.get("name") or ""))
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        for prop in props.values():
            if isinstance(prop, dict) and "description" in prop:
                prop["description"] = _short_desc(str(prop["description"]), limit=60)
        out.append(t)
    return out


# LLM-facing schemas (Telegram + web chat). Full TOOLS stay for docs / introspection.
TOOLS_FOR_LLM: list[dict[str, Any]] = _tools_for_llm(TOOLS)
TELEGRAM_TOOLS_FOR_LLM: list[dict[str, Any]] = _tools_for_llm(TELEGRAM_TOOLS)

_VERTICAL_MAP: dict[str, list[dict[str, Any]]] = {
    "food": _FOOD_TOOLS,
    "im": _IM_TOOLS,
    "dineout": _DINEOUT_TOOLS,
}


def get_tools_for_vertical(vertical: str) -> list[dict[str, Any]]:
    """Return the subset of tool schemas for a given vertical."""
    return list(_VERTICAL_MAP.get(vertical, []))


def get_tool_names() -> list[str]:
    """Return all registered tool function names."""
    return [t["function"]["name"] for t in TOOLS]
