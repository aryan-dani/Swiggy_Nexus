import json
import os
import uuid
from typing import Any, Generator

from backend.mcp_client import call_tool, LocalMCPError
from backend.memory import get_user_preferences, set_user_preference

# ---------------------------------------------------------------------------
# Tool schema — 23 LLM-callable tools covering Food (10), Instamart (7),
# Dineout (6). Names use the <vertical>_<method> prefix convention so the
# dispatch block can split them without a lookup table.
# ---------------------------------------------------------------------------
TOOLS = [
    # ── Food ──────────────────────────────────────────────────────────────
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
    # ── Instamart ─────────────────────────────────────────────────────────
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
    # ── Dineout ───────────────────────────────────────────────────────────
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


def _sse_tool(
    server_key: str, http_path: str, method: str, params: dict[str, Any], data: Any
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "vertical": server_key,
        "server_path": http_path,
        "method": method,
        "params": params,
        "result": {"success": True, "data": data},
        "demo_note": "local_mock_mcp",
    }


REVIEWER_SCENARIOS = ("chrono_host", "deadlock", "flowstate", "zerowaste", "sentiment", "dialectic")

SCENARIO_PROMPTS: dict[str, str] = {
    "chrono_host": (
        "Chrono-Host: plan a multi-vertical evening (Dineout table + Instamart party supplies + Food dessert). "
        "Use parallel tool calls across food, im, and dineout. Stage carts; do not auto-place without user confirm."
    ),
    "deadlock": "Social deadlock breaker: find a dinner compromise for a picky group using Dineout search and availability.",
    "flowstate": "Flow-state fueler: quick Instamart delivery for deep-work snacks and coffee.",
    "zerowaste": "Zero-waste meal: search pantry gaps on Instamart for a recipe, minimize waste.",
    "sentiment": "Sentiment thermostat: suggest comfort food options; stage carts but never auto-checkout.",
    "dialectic": "Dialectic dinner: search restaurants for a debate-night meal pick.",
}


def _build_system_prompt(prefs_str: str, scenario_hint: str) -> str:
    return (
        "You are Swiggy Nexus, an autonomous agentic copilot for Swiggy's three verticals: "
        "Food delivery, Instamart groceries, and Dineout table reservations.\n\n"
        f"User Preferences: {prefs_str}{scenario_hint}\n\n"
        "## Core rules\n"
        "1. ALWAYS start by resolving location: call food_get_addresses (Food/Instamart) or "
        "dineout_get_saved_locations (Dineout) before any search.\n"
        "2. For food orders: search_restaurants → get_menu → add_to_cart → get_food_cart → confirm → place_order\n"
        "3. For grocery orders: search_products → add_to_cart → get_cart → confirm → checkout\n"
        "4. For Dineout: get_saved_locations → search_restaurants → get_restaurant_details → "
        "check_availability → confirm slot + party size → book_table\n"
        "5. NEVER auto-place an order. ALWAYS get explicit user confirmation (yes/confirm/proceed) "
        "before calling place_order or checkout.\n"
        "6. CART CAP: Cart total must be under ₹1000 (beta restriction). If cart >= ₹1000, "
        "tell user to use the Swiggy app instead.\n"
        "7. PAYMENT: COD only in v1. Do NOT mention online payment options.\n"
        "8. CART + RESTAURANT SWITCH: Warn the user that switching restaurants will clear their cart.\n"
        "9. COUPON NOTE: A coupon is only 'applied' if coupon_discount > 0. Never say a coupon "
        "saved money unless the discount amount is > 0.\n"
        "10. AVAILABILITY: Only recommend restaurants with availabilityStatus='OPEN' (Food) or "
        "availability='AVAILABLE' (Dineout).\n"
        "11. Always call food_get_food_cart after every food_add_to_cart — the cart widget is "
        "NOT updated otherwise.\n"
        "12. For multi-vertical requests (e.g. dinner out + dessert delivered), use parallel "
        "tool calls in a single turn.\n"
        "13. CANCELLATION: If user asks to cancel an order, tell them to call Swiggy customer "
        "care at 080-67466729. Do NOT call any cancel tool.\n"
        "14. Stream tool calls visibly. Prefer several MCP tool calls over a brief reply.\n"
        "15. For Instamart quick reorders, offer im_your_go_to_items before search.\n"
    )


def run_llm_agent(user_message: str, context: dict[str, Any] | None) -> Generator[dict[str, Any], None, None]:
    ctx = context or {}
    api_key = os.environ.get("GROQ_API_KEY", "").strip()

    # Rich scripted demos only when no LLM is configured.
    if not api_key and ctx.get("scenario") in REVIEWER_SCENARIOS:
        from backend.agent import run_agent_stream as deterministic

        yield from deterministic(user_message, ctx)
        return

    if not api_key:
        yield {"type": "thinking", "payload": {"text": "GROQ_API_KEY missing. Falling back to deterministic mode."}}
        from backend.agent import run_agent_stream as fallback

        yield from fallback(user_message, context)
        return

    # Import Groq SDK lazily so the module can be imported even if the SDK
    # isn't installed in the running Python environment.
    try:
        # pyrefly: ignore [missing-import]
        from groq import Groq
    except Exception:
        yield {"type": "thinking", "payload": {"text": "Groq SDK not available. Falling back to deterministic mode."}}
        from backend.agent import run_agent_stream as fallback

        yield from fallback(user_message, context)
        return

    client = Groq(api_key=api_key)
    session_id = str(uuid.uuid4())

    yield {
        "type": "thinking",
        "payload": {"text": f"Groq {os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')} · agentic MCP tool loop"},
    }

    prefs = get_user_preferences()
    prefs_str = json.dumps(prefs) if prefs else "None"

    scenario = ctx.get("scenario")
    scenario_hint = ""
    if isinstance(scenario, str) and scenario in SCENARIO_PROMPTS:
        scenario_hint = f"\nActive reviewer scenario ({scenario}): {SCENARIO_PROMPTS[scenario]}"

    party = ctx.get("partySize")
    event = ctx.get("event")
    if not party and isinstance(event, dict):
        party = event.get("guests")
    if party:
        scenario_hint += f"\nParty size: {party}."

    system_prompt = _build_system_prompt(prefs_str, scenario_hint)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    feed_items: list[dict[str, Any]] = []
    seen_feed_keys: set[str] = set()

    def _add_feed(item: dict[str, Any]) -> None:
        """Deduplicate feed items by (type, title) key."""
        key = f"{item.get('type')}|{item.get('title')}"
        if key not in seen_feed_keys:
            seen_feed_keys.add(key)
            feed_items.append(item)

    while True:
        try:
            resp = client.chat.completions.create(
                model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            yield {"type": "assistant", "payload": {"text": f"LLM error: {str(e)}"}}
            yield {"type": "done", "payload": {"assistant_reply": f"LLM error: {str(e)}", "feed_items": feed_items}}
            break

        msg = resp.choices[0].message

        if not msg.tool_calls:
            assistant_reply = msg.content or "Done."
            yield {"type": "assistant", "payload": {"text": assistant_reply}}
            # Emit feed once at the end of the agentic loop (not per iteration)
            if feed_items:
                yield {"type": "feed", "payload": {"items": list(feed_items)}}
            yield {"type": "done", "payload": {"assistant_reply": assistant_reply, "feed_items": feed_items}}
            break

        # Append the assistant message with tool calls
        messages.append(msg)

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            # Groq may emit "null" / non-object arguments — never let None reach `in` checks.
            if not isinstance(args, dict):
                args = {}

            # Split "food_search_restaurants" → vertical="food", method="search_restaurants"
            parts = name.split("_", 1)
            if len(parts) == 2:
                vertical, method = parts
            else:
                vertical, method = "food", name

            # Inject session_id automatically when tool expects requestId
            if "requestId" in args:
                args["requestId"] = session_id
            if "request_id" in args:
                args["request_id"] = session_id

            yield {"type": "thinking", "payload": {"text": f"Executor · {name}"}}

            try:
                data = call_tool(vertical, method, args)
                tool_payload = _sse_tool(vertical, f"/{vertical}", method, args, data)
                tool_payload["method"] = name
                tool_payload["phase"] = "Executor"
                yield {"type": "tool", "payload": tool_payload}

                # ── Feed rendering ──────────────────────────────────────
                if method == "search_restaurants" and isinstance(data, dict) and "restaurants" in data:
                    for r in data.get("restaurants") or []:
                        _add_feed({
                            "type": "restaurant" if vertical == "food" else "dineout",
                            "title": r.get("name", "Venue"),
                            "subtitle": f"★ {r.get('rating')} · {', '.join(r.get('cuisines') or [])}",
                            "meta": {"restaurant_id": r.get("restaurant_id") or r.get("id")},
                        })
                elif method == "search_menu" and isinstance(data, dict) and "items" in data:
                    for item in data.get("items") or []:
                        veg_badge = "🟢" if item.get("vegetarian") else "🔴"
                        _add_feed({
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
                            },
                        })
                elif method in ("get_menu", "get_restaurant_menu") and isinstance(data, dict):
                    for cat in data.get("categories") or []:
                        for item in cat.get("items") or []:
                            veg_badge = "🟢" if item.get("vegetarian") else "🔴"
                            _add_feed({
                                "type": "food",
                                "title": item.get("name", "Item"),
                                "subtitle": f"{veg_badge} ₹{item.get('price_inr')} · {cat.get('name', '')}",
                                "meta": {
                                    "item_id": item.get("item_id"),
                                    "price_inr": item.get("price_inr"),
                                },
                            })
                elif method == "search_products" and isinstance(data, dict) and "products" in data:
                    for p in data.get("products") or []:
                        _add_feed({
                            "type": "grocery",
                            "title": p.get("name", "Product"),
                            "subtitle": f"₹{p.get('price_inr', '?')} · {p.get('category', '')}",
                            "meta": {
                                "product_id": p.get("product_id"),
                                "price_inr": p.get("price_inr"),
                                "spinId": (p.get("variants") or [{}])[0].get("spinId"),
                            },
                        })
                elif method == "your_go_to_items" and isinstance(data, dict) and "products" in data:
                    for p in data.get("products") or []:
                        _add_feed({
                            "type": "grocery",
                            "title": f"⚡ {p.get('name', 'Item')}",
                            "subtitle": f"₹{p.get('price_inr', '?')} · Quick reorder",
                            "meta": {
                                "product_id": p.get("product_id"),
                                "price_inr": p.get("price_inr"),
                            },
                        })
                elif method == "get_restaurant_details" and isinstance(data, dict):
                    _add_feed({
                        "type": "dineout",
                        "title": data.get("name", "Restaurant"),
                        "subtitle": (
                            f"★ {data.get('rating')} · "
                            f"{', '.join(data.get('cuisines', []))} · "
                            f"₹{data.get('costForTwo')}/2"
                        ),
                        "meta": {"restaurant_id": data.get("restaurantId")},
                    })
                elif method in ("get_food_cart", "get_cart") and isinstance(data, dict):
                    total = data.get("bill", {}).get("total_inr") or data.get("total_inr")
                    items_count = len(data.get("items", []))
                    _add_feed({
                        "type": "cart_summary",
                        "title": "Cart Summary",
                        "subtitle": f"{items_count} item(s) · ₹{total or '?'} total",
                        "meta": data,
                    })
                elif method in ("fetch_food_coupons",) and isinstance(data, dict) and data.get("coupons"):
                    for c in (data.get("coupons") or [])[:3]:
                        _add_feed({
                            "type": "coupon",
                            "title": f"🏷️ {c.get('code', 'COUPON')}",
                            "subtitle": c.get("description", ""),
                            "meta": c,
                        })
                elif method in ("place_order", "checkout") and isinstance(data, dict):
                    _add_feed({
                        "type": f"{vertical}_order",
                        "title": data.get("message", "Order placed ✓"),
                        "subtitle": f"ETA ~{data.get('eta_mins', '?')} mins",
                        "meta": data,
                    })
                elif method == "book_table" and isinstance(data, dict):
                    _add_feed({
                        "type": "booking",
                        "title": "Table Reserved ✓",
                        "subtitle": data.get("confirmation_message", data.get("booking_id", "")),
                        "meta": data,
                    })
                elif method in ("track_food_order", "track_order") and isinstance(data, dict):
                    status = data.get("status", "In Progress")
                    _add_feed({
                        "type": "tracking",
                        "title": f"Order Tracking · {status}",
                        "subtitle": f"ETA ~{data.get('eta_mins', '?')} mins",
                        "meta": data,
                    })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(data),
                })
            except LocalMCPError as e:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": e.payload}),
                })
            except Exception as e:  # noqa: BLE001 — one bad tool call must not kill the SSE stream
                yield {
                    "type": "thinking",
                    "payload": {"text": f"Executor recovered from {name}: {e}"},
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": {"code": "EXECUTOR_ERROR", "message": str(e)}}),
                })
