"""Feed renderer — maps tool call results to FeedItem dicts.

Extracted from llm_orchestrator.py to keep the agentic loop focused.
Replaces the 100-line if/elif chain with a registry-pattern dispatcher.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

FeedItem = dict[str, Any]


# ---------------------------------------------------------------------------
# Per-method renderers
# ---------------------------------------------------------------------------


def _render_search_restaurants(vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    items: list[FeedItem] = []
    card_type = "restaurant" if vertical == "food" else "dineout"
    for r in data.get("restaurants", []):
        items.append(
            {
                "type": card_type,
                "title": r.get("name", "Venue"),
                "subtitle": (
                    f"★ {r.get('rating')} · "
                    f"{', '.join(r.get('cuisines') or [])} · "
                    f"ETA ~{r.get('eta_mins', '?')} min"
                    if vertical == "food"
                    else f"★ {r.get('rating')} · {', '.join(r.get('cuisines') or [])}"
                ),
                "meta": {"restaurant_id": r.get("restaurant_id") or r.get("id")},
            }
        )
    return items


def _render_search_menu(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    items: list[FeedItem] = []
    for item in data.get("items", []):
        veg_badge = "🟢" if item.get("vegetarian") else "🔴"
        items.append(
            {
                "type": "food",
                "title": item.get("name", "Dish"),
                "subtitle": (
                    f"{veg_badge} ₹{item.get('price_inr')} · "
                    f"{item.get('restaurantName', '')} · ★{item.get('restaurantRating', '')}"
                ),
                "meta": {
                    "item_id": item.get("item_id"),
                    "restaurant_id": item.get("restaurantId"),
                    "price_inr": item.get("price_inr"),
                    "vegetarian": item.get("vegetarian"),
                },
            }
        )
    return items


def _render_get_menu(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    items: list[FeedItem] = []
    for cat in data.get("categories", []):
        for item in cat.get("items", []):
            veg_badge = "🟢" if item.get("vegetarian") else "🔴"
            items.append(
                {
                    "type": "food",
                    "title": item.get("name", "Item"),
                    "subtitle": f"{veg_badge} ₹{item.get('price_inr')} · {cat.get('name', '')}",
                    "meta": {
                        "item_id": item.get("item_id"),
                        "price_inr": item.get("price_inr"),
                        "vegetarian": item.get("vegetarian"),
                    },
                }
            )
    return items


def _render_search_products(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    items: list[FeedItem] = []
    for p in data.get("products", []):
        items.append(
            {
                "type": "grocery",
                "title": p.get("name", "Product"),
                "subtitle": f"₹{p.get('price_inr', '?')} · {p.get('category', '')}",
                "meta": {
                    "product_id": p.get("product_id"),
                    "price_inr": p.get("price_inr"),
                    "spinId": (p.get("variants") or [{}])[0].get("spinId"),
                },
            }
        )
    return items


def _render_your_go_to_items(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    items: list[FeedItem] = []
    for p in data.get("products", []):
        items.append(
            {
                "type": "grocery",
                "title": f"⚡ {p.get('name', 'Item')}",
                "subtitle": f"₹{p.get('price_inr', '?')} · Quick reorder",
                "meta": {
                    "product_id": p.get("product_id"),
                    "price_inr": p.get("price_inr"),
                    "spinId": (p.get("variants") or [{}])[0].get("spinId"),
                },
            }
        )
    return items


def _render_get_restaurant_details(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    return [
        {
            "type": "dineout",
            "title": data.get("name", "Restaurant"),
            "subtitle": (
                f"★ {data.get('rating')} · "
                f"{', '.join(data.get('cuisines', []))} · "
                f"₹{data.get('costForTwo')}/2"
            ),
            "meta": {"restaurant_id": data.get("restaurantId")},
        }
    ]


def _render_cart(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    total = data.get("bill", {}).get("total_inr") or data.get("total") or data.get("total_inr")
    items_count = len(data.get("items", []))
    return [
        {
            "type": "cart_summary",
            "title": "Cart Summary",
            "subtitle": f"{items_count} item(s) · ₹{total or '?'} total",
            "meta": data,
        }
    ]


def _render_coupons(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    items: list[FeedItem] = []
    for c in (data.get("coupons") or [])[:3]:
        items.append(
            {
                "type": "coupon",
                "title": f"🏷️ {c.get('code', 'COUPON')}",
                "subtitle": c.get("description", ""),
                "meta": c,
            }
        )
    return items


def _render_order_placed(vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    return [
        {
            "type": f"{vertical}_order",
            "title": data.get("message", "Order placed ✓"),
            "subtitle": f"ETA ~{data.get('eta_mins', '?')} mins",
            "meta": data,
        }
    ]


def _render_book_table(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    return [
        {
            "type": "booking",
            "title": "Table Reserved ✓",
            "subtitle": data.get("confirmation_message", data.get("booking_id", "")),
            "meta": data,
        }
    ]


def _render_tracking(_vertical: str, data: dict[str, Any]) -> list[FeedItem]:
    status = data.get("status", "In Progress")
    return [
        {
            "type": "tracking",
            "title": f"Order Tracking · {status}",
            "subtitle": f"ETA ~{data.get('eta_mins', '?')} mins",
            "meta": data,
        }
    ]


# ---------------------------------------------------------------------------
# Registry: method → renderer function
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Any] = {
    "search_restaurants": _render_search_restaurants,
    "search_menu": _render_search_menu,
    "get_menu": _render_get_menu,
    "get_restaurant_menu": _render_get_menu,
    "search_products": _render_search_products,
    "your_go_to_items": _render_your_go_to_items,
    "get_restaurant_details": _render_get_restaurant_details,
    "get_food_cart": _render_cart,
    "get_cart": _render_cart,
    "fetch_food_coupons": _render_coupons,
    "place_order": _render_order_placed,
    "checkout": _render_order_placed,
    "book_table": _render_book_table,
    "track_food_order": _render_tracking,
    "track_order": _render_tracking,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_feed_items(vertical: str, method: str, data: Any) -> list[FeedItem]:
    """Convert a tool call result into zero or more FeedItem dicts.

    Args:
        vertical: 'food' | 'im' | 'dineout'
        method:   The bare method name (e.g. 'search_restaurants', not the full prefixed tool name)
        data:     The unwrapped tool result data (already extracted from the envelope)

    Returns:
        A (possibly empty) list of feed items ready for the SSE ``feed`` event.
    """
    if not isinstance(data, dict):
        return []
    renderer = _REGISTRY.get(method)
    if renderer is None:
        return []
    try:
        return renderer(vertical, data) or []
    except Exception:  # noqa: BLE001
        return []
