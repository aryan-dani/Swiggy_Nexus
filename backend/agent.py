"""Streaming Nexus agent over **local mock** MCP (`/food`, `/im`, `/dineout`).

Deterministic scripted demo flows. Activated when no GROQ_API_KEY is set
or when a reviewer scenario is specified in the context.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Generator, Literal

from backend.mcp_client import LocalMCPError, call_tool

log = logging.getLogger(__name__)

Vertical = Literal["food", "im", "dineout", "chrono"]


def _detect_vertical(message: str, ctx: dict[str, Any]) -> Vertical:
    mlow = message.lower()
    if ctx.get("scenario") == "chrono_host":
        return "chrono"
    if ctx.get("scenario") in ("sentiment",):
        return "im"
    if ctx.get("scenario") in ("dialectic",):
        return "food"
    ctx_v = ctx.get("vertical")
    if ctx_v == "dineout" or ctx.get("scenario") == "team_dinner":
        return "dineout"
    if ctx_v == "instamart":
        return "im"

    if any(
        k in mlow
        for k in (
            "plan my evening",
            "housewarming",
            "chrono host",
            "evening plan",
            "dinner out and dessert",
        )
    ):
        return "chrono"
    if any(
        k in mlow
        for k in (
            "dineout",
            "reservation",
            "book a table",
            "team dinner",
            "party of",
            "table for",
            "restaurant night",
            "fine dining",
        )
    ):
        return "dineout"
    if any(
        k in mlow
        for k in (
            "instamart",
            "grocery",
            "groceries",
            "stock up",
            "ingredient",
            "snacks aisle",
            "milk delivery",
            "bread and eggs",
        )
    ):
        return "im"
    return "food"


def _is_food_pizza_flow(message: str) -> bool:
    m = message.lower()
    if any(
        p in m
        for p in ("order pizza", "order a pizza", "pizza delivery", "get me pizza", "get a pizza", "checkout pizza")
    ):
        return True
    if any(b in m for b in ("order", "buy", "checkout", "place order")) and "pizza" in m:
        return True
    return "buy pizza" in m


def _thinking(text: str) -> dict[str, Any]:
    return {"type": "thinking", "payload": {"text": text}}


def _sse_tool(server_key: str, http_path: str, method: str, params: dict[str, Any], data: Any) -> dict[str, Any]:
    """Build a JSON-RPC-shaped SSE tool event payload."""
    return {
        "jsonrpc": "2.0",
        "vertical": server_key,
        "server_path": http_path,
        "method": method,
        "params": params,
        "result": {"success": True, "data": data},
        "demo_note": "local_mock_mcp",
    }


def _pick_address_id(ctx: dict[str, Any], addrs: dict[str, Any]) -> str:
    aid = str(ctx.get("addressId") or ctx.get("address_id") or "")
    plist = addrs.get("addresses") or []
    if not aid and plist:
        aid = str(plist[0].get("addressId", ""))
    return aid


def _pick_pizza_restaurant(sr: dict[str, Any]) -> str | None:
    rows = sr.get("restaurants") or []
    for r in rows:
        cuisines = [c.lower() for c in (r.get("cuisines") or [])]
        name = str(r.get("name", "")).lower()
        if "pizza" in cuisines or "domino" in name:
            return str(r["restaurant_id"])
    return str(rows[0]["restaurant_id"]) if rows else None


def _compose_food_discovery_feed(addrs_blob: dict[str, Any], sr_blob: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for a in addrs_blob.get("addresses") or []:
        items.append(
            {
                "type": "address",
                "title": a.get("label", "Saved address"),
                "subtitle": f"{a.get('line1')} · {a.get('area')}, Pune {a.get('pin', '')}".strip(),
                "meta": {"addressId": a.get("addressId")},
            }
        )
    for r in sr_blob.get("restaurants") or []:
        eta = r.get("eta_mins", "?")
        items.append(
            {
                "type": "restaurant",
                "title": r.get("name", "Restaurant"),
                "subtitle": f"★ {r.get('rating', '—')} · ETA ~{eta} min · {', '.join(r.get('cuisines') or [])}",
                "meta": {
                    "restaurant_id": r.get("restaurant_id"),
                    "eta_mins": r.get("eta_mins"),
                },
            }
        )
    return items


def run_food_browse(uuid_session: str, ctx: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    yield _thinking("Fetching saved Pune addresses via mock `food.get_addresses`.")
    addrs_any = call_tool("food", "get_addresses", {})
    addrs = addrs_any if isinstance(addrs_any, dict) else {}
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_addresses", {}, addrs_any)}

    addr_id = _pick_address_id(ctx, addrs)
    yield _thinking(f"Picked address `{addr_id}` → `food.search_restaurants`.")
    sr_any = call_tool("food", "search_restaurants", {"addressId": addr_id})
    sr = sr_any if isinstance(sr_any, dict) else {}
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "search_restaurants", {"addressId": addr_id}, sr_any)}

    feed = _compose_food_discovery_feed(addrs, sr)
    n = len(sr.get("restaurants") or [])
    reply = f"Showing {n} restaurant options near your Pune pin."
    yield {"type": "feed", "payload": {"items": feed}}
    yield {"type": "assistant", "payload": {"text": reply}}
    yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": feed}}


def run_food_pizza_order(uuid_session: str, ctx: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    yield _thinking("Food delivery flow: addresses → restaurants → Domino's-ish menu → cart → place_order.")

    addrs_any = call_tool("food", "get_addresses", {})
    addrs = addrs_any if isinstance(addrs_any, dict) else {}
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_addresses", {}, addrs_any)}
    addr_id = _pick_address_id(ctx, addrs)

    sr_any = call_tool("food", "search_restaurants", {"addressId": addr_id})
    sr = sr_any if isinstance(sr_any, dict) else {}
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "search_restaurants", {"addressId": addr_id}, sr_any)}

    rid = _pick_pizza_restaurant(sr)
    if not rid:
        reply = "No restaurants matched the pizza heuristic in this stub run."
        yield {"type": "assistant", "payload": {"text": reply}}
        yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": []}}
        return

    menu_any = call_tool("food", "get_menu", {"restaurantId": rid})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_menu", {"restaurantId": rid}, menu_any)}

    cart_params = {
        "requestId": uuid_session,
        "restaurantId": rid,
        "addressId": addr_id,
        "lines": [{"item_id": "dom_mar_med", "qty": 1}],
    }
    cart_any = call_tool("food", "add_to_cart", cart_params)
    cart = cart_any if isinstance(cart_any, dict) else {}
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "add_to_cart", cart_params, cart_any)}
    cid = str(cart.get("cart_id", f"cart_fd_{uuid_session}"))

    order_any = call_tool("food", "place_order", {"requestId": uuid_session, "cartId": cid, "addressId": addr_id, "paymentMethod": "COD"})
    order = order_any if isinstance(order_any, dict) else {}
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "place_order", {"cart_id": cid}, order_any)}

    feed_rest = _compose_food_discovery_feed(addrs, sr)
    feed = feed_rest[: min(8, len(feed_rest))]
    feed.append(
        {
            "type": "order_confirmation",
            "title": order.get("message") or "Order placed",
            "subtitle": f"Order {order.get('order_id')} · ETA ~{order.get('eta_mins')} min · COD mock",
            "meta": order,
        }
    )
    reply = str(order.get("message")) if order.get("message") else "Pizza checkout complete (mock)."
    yield {"type": "feed", "payload": {"items": feed}}
    yield {"type": "assistant", "payload": {"text": reply}}
    yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": feed}}


def run_instamart(uuid_session: str, message: str) -> Generator[dict[str, Any], None, None]:
    q = "".join(ch for ch in message if ch.isprintable()).strip().lower()
    snippet = ""
    for token in ("milk", "bread", "eggs", ""):
        if token and token in q:
            snippet = token
            break
    yield _thinking("`im.search_products` for quick grocery staples.")
    prods = call_tool("im", "search_products", {"query": snippet or "milk", "addressId": "addr_kp_001"})
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "search_products", {"query": snippet or "milk"}, prods)}
    plist = []
    if isinstance(prods, dict):
        plist = prods.get("products") or []

    picks = plist[: min(12, len(plist))]
    line_items: list[dict[str, Any]] = []
    pid_milk = "im_milk_f"
    pid_bread = "im_bread"
    if any(p.get("product_id") == pid_milk for p in picks):
        line_items.append({"product_id": pid_milk, "qty": 1})
    elif picks:
        v0 = (picks[0].get("variants") or [{}])[0]
        spin = v0.get("spinId") if isinstance(v0, dict) else None
        line_items.append({"spinId": spin, "product_id": picks[0]["product_id"], "qty": 1} if spin else {"product_id": picks[0]["product_id"], "qty": 1})
    if any(p.get("product_id") == pid_bread for p in picks):
        line_items.append({"product_id": pid_bread, "qty": 1})

    yield _thinking("`im.add_to_cart` assembling a basket.")
    cart = call_tool(
        "im",
        "add_to_cart",
        {"requestId": uuid_session, "selectedAddressId": "addr_kp_001", "items": line_items},
    )
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "add_to_cart", {"items": line_items}, cart)}
    cid = ""
    if isinstance(cart, dict):
        cid = str(cart.get("cart_id", f"cart_im_{uuid_session}"))

    out = call_tool("im", "checkout", {"requestId": uuid_session, "cartId": cid})
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "checkout", {"cart_id": cid}, out)}

    feed: list[dict[str, Any]] = []
    for p in plist[:8]:
        feed.append(
            {
                "type": "instamart",
                "title": p.get("name"),
                "subtitle": f"₹{p.get('price_inr')} · {p.get('category', '')}",
                "meta": {"product_id": p.get("product_id")},
            }
        )
    if isinstance(out, dict):
        feed.append(
            {
                "type": "instamart_order",
                "title": out.get("message", "Groceries on the way"),
                "subtitle": f"ETA ~{out.get('eta_mins')} min · {out.get('order_id')}",
                "meta": out,
            }
        )

    reply = str(out.get("message")) if isinstance(out, dict) else "Checkout complete."
    yield {"type": "feed", "payload": {"items": feed}}
    yield {"type": "assistant", "payload": {"text": reply}}
    yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": feed}}


def run_dineout(ctx: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    yield _thinking("Dine-out path: listings → slots → booked table.")

    lst = call_tool("dineout", "search_restaurants", {})
    yield {"type": "tool", "payload": _sse_tool("dineout", "/dineout", "search_restaurants", {}, lst)}
    rest_id = ""
    if isinstance(lst, dict) and lst.get("restaurants"):
        rest_id = str(lst["restaurants"][0]["restaurant_id"])

    party = ctx.get("party_size", ctx.get("partySize", 4))
    avail = call_tool(
        "dineout",
        "check_availability",
        {
            "restaurantId": rest_id or "do_bk_801",
            "partySize": party,
            "date": ctx.get("date", "2026-05-10"),
        },
    )
    yield {
        "type": "tool",
        "payload": _sse_tool(
            "dineout",
            "/dineout",
            "check_availability",
            {"restaurantId": rest_id, "partySize": party},
            avail,
        ),
    }
    slot = ""
    if isinstance(avail, dict):
        slots = avail.get("slots") or []
        slot = slots[0] if slots else "19:00"

    bk = call_tool(
        "dineout",
        "book_table",
        {
            "restaurantId": rest_id or "do_bk_801",
            "partySize": party,
            "slot": slot,
        },
    )
    yield {"type": "tool", "payload": _sse_tool("dineout", "/dineout", "book_table", {"slot": slot}, bk)}

    feed: list[dict[str, Any]] = []
    if isinstance(lst, dict):
        for r in lst.get("restaurants") or []:
            feed.append(
                {
                    "type": "dineout",
                    "title": r.get("name"),
                    "subtitle": f"★ {r.get('rating')} · {', '.join(r.get('cuisines') or [])}",
                    "meta": {"restaurant_id": r.get("restaurant_id")},
                }
            )
    if isinstance(avail, dict):
        feed.append(
            {
                "type": "dineout_slot_pack",
                "title": "Tonight availability",
                "subtitle": ", ".join(avail.get("slots") or []),
                "meta": avail,
            }
        )
    if isinstance(bk, dict):
        feed.append(
            {
                "type": "booking",
                "title": bk.get("confirmation_message", "Booked"),
                "subtitle": bk.get("booking_id"),
                "meta": bk,
            }
        )

    reply = str(bk.get("confirmation_message")) if isinstance(bk, dict) else "Booking saved."
    yield {"type": "feed", "payload": {"items": feed}}
    yield {"type": "assistant", "payload": {"text": reply}}
    yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": feed}}


def run_chrono_host(uuid_session: str, ctx: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    """Combined Dineout + Instamart + Food evening planner (staged, no auto-place)."""
    from backend.memory import set_user_preference
    import json

    event = ctx.get("event") if isinstance(ctx.get("event"), dict) else {}
    guests = int(event.get("guests") or ctx.get("partySize") or ctx.get("party_size") or 12)
    cuisine = str(event.get("cuisineHint") or "italian").lower()
    event_title = str(event.get("title") or "Your evening")

    yield _thinking("Planner · Chrono-Host: orchestrating Dineout + Instamart + Food across one evening.")

    # --- Dineout leg ---
    yield _thinking("Dineout: resolving saved locations.")
    locs_any = call_tool("dineout", "get_saved_locations", {})
    yield {"type": "tool", "payload": _sse_tool("dineout", "/dineout", "get_saved_locations", {}, locs_any)}
    locs = locs_any if isinstance(locs_any, dict) else {}
    loc0 = (locs.get("locations") or [{}])[0]
    lat, lng = loc0.get("lat"), loc0.get("lng")

    yield _thinking(f"Dineout: searching {cuisine} restaurants for {guests} guests.")
    dine_params = {"query": cuisine, "latitude": lat, "longitude": lng}
    dine_search = call_tool("dineout", "search_restaurants_dineout", dine_params)
    yield {"type": "tool", "payload": _sse_tool("dineout", "/dineout", "search_restaurants_dineout", dine_params, dine_search)}
    ds = dine_search if isinstance(dine_search, dict) else {}
    rest_id = str((ds.get("restaurants") or [{}])[0].get("restaurant_id", "do_italian_804"))

    slot_params = {"restaurantId": rest_id, "guestCount": guests, "date": "2026-07-12", "partySize": guests}
    slots_any = call_tool("dineout", "get_available_slots", slot_params)
    yield {"type": "tool", "payload": _sse_tool("dineout", "/dineout", "get_available_slots", slot_params, slots_any)}
    slots_blob = slots_any if isinstance(slots_any, dict) else {}
    slot0 = (slots_blob.get("slots") or [{}])[0]
    slot_label = slot0.get("label", "20:00")

    # --- Instamart leg ---
    yield _thinking("Instamart: party supplies for the housewarming.")
    addr_any = call_tool("food", "get_addresses", {})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_addresses", {}, addr_any)}
    addrs = addr_any if isinstance(addr_any, dict) else {}
    addr_id = _pick_address_id(ctx, addrs)

    im_search = call_tool("im", "search_products", {"addressId": addr_id, "query": "party"})
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "search_products", {"query": "party"}, im_search)}
    im_prods = (im_search.get("products") if isinstance(im_search, dict) else []) or []
    im_lines: list[dict[str, Any]] = []
    for p in im_prods[:4]:
        v = (p.get("variants") or [{}])[0]
        spin = v.get("spinId")
        if spin:
            im_lines.append({"spinId": spin, "quantity": 2 if "plate" in p.get("name", "").lower() else 1})

    im_cart_params = {"requestId": uuid_session, "selectedAddressId": addr_id, "items": im_lines}
    im_cart_any = call_tool("im", "update_cart", im_cart_params)
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "update_cart", im_cart_params, im_cart_any)}
    im_cart_view = call_tool("im", "get_cart", {"requestId": uuid_session})
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "get_cart", {"requestId": uuid_session}, im_cart_view)}

    # --- Food dessert leg (staged) ---
    yield _thinking("Food: staging gelato dessert for ~10 PM (reminder — no scheduled delivery in v1).")
    dessert_search = call_tool("food", "search_restaurants", {"addressId": addr_id, "query": "gelato"})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "search_restaurants", {"query": "gelato"}, dessert_search)}
    ds_food = dessert_search if isinstance(dessert_search, dict) else {}
    gelato_rid = str((ds_food.get("restaurants") or [{}])[0].get("restaurant_id", "fd_gelato_108"))

    menu_any = call_tool("food", "get_restaurant_menu", {"restaurantId": gelato_rid, "addressId": addr_id})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_restaurant_menu", {"restaurantId": gelato_rid}, menu_any)}

    food_cart_params = {
        "requestId": uuid_session,
        "restaurantId": gelato_rid,
        "addressId": addr_id,
        "cartItems": [{"itemId": "gv_pistachio", "quantity": 2}],
        "lines": [{"item_id": "gv_pistachio", "qty": 2}],
    }
    food_cart_any = call_tool("food", "update_food_cart", food_cart_params)
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "update_food_cart", food_cart_params, food_cart_any)}
    food_cart_view = call_tool("food", "get_food_cart", {"requestId": uuid_session, "addressId": addr_id})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_food_cart", {"addressId": addr_id}, food_cart_view)}

    _rest0 = (ds.get("restaurants") or [{}])[0]
    bundle = {
        "event": event_title,
        "dineout": {
            "restaurantId": rest_id,
            "restaurant": _rest0.get("name"),
            "slot": slot_label,
            "guests": guests,
            "status": "STAGED",
            "costForTwo": _rest0.get("costForTwo") or _rest0.get("price_for_two_inr"),
        },
        "instamart": im_cart_view if isinstance(im_cart_view, dict) else {},
        "food": food_cart_view if isinstance(food_cart_view, dict) else {},
    }
    set_user_preference("last_event_bundle", json.dumps(bundle))

    dine_name = (ds.get("restaurants") or [{}])[0].get("name", "Restaurant")
    im_total = (im_cart_view or {}).get("total", "?") if isinstance(im_cart_view, dict) else "?"
    food_total = (food_cart_view or {}).get("total", "?") if isinstance(food_cart_view, dict) else "?"

    feed: list[dict[str, Any]] = [
        {
            "type": "event_bundle",
            "title": f"Evening plan · {event_title}",
            "subtitle": "Dineout + Instamart + Food dessert — review each leg",
            "meta": bundle,
        },
        {
            "type": "dineout",
            "title": dine_name,
            "subtitle": f"Table for {guests} · {slot_label} · confirm to book",
            "meta": {"restaurant_id": rest_id, "slot": slot_label, "guests": guests},
        },
    ]
    for p in im_prods[:4]:
        feed.append({
            "type": "instamart",
            "title": p.get("name"),
            "subtitle": "Party supplies (staged)",
            "meta": {"product_id": p.get("product_id")},
        })
    feed.append({
        "type": "restaurant",
        "title": "Gelato dessert @ 10 PM",
        "subtitle": f"Staged cart ₹{food_total} — I'll remind you to place at 10 PM",
        "meta": {"restaurant_id": gelato_rid},
    })

    reply = (
        f"Here's your evening bundle for **{event_title}**:\n\n"
        f"1. **Dineout** — {dine_name}, table for {guests} at {slot_label}. Reply **confirm table** to book.\n"
        f"2. **Instamart** — party supplies staged (₹{im_total}). Reply **confirm groceries** to checkout.\n"
        f"3. **Food** — gelato dessert staged (₹{food_total}). Swiggy can't schedule delivery yet — "
        f"I'll remind you at **10 PM** to place; reply **confirm dessert** when ready.\n\n"
        "Nothing has been placed automatically."
    )
    yield {"type": "feed", "payload": {"items": feed}}
    yield {"type": "assistant", "payload": {"text": reply}}
    yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": feed}}


def _error_bundle(message: str) -> Generator[dict[str, Any], None, None]:
    feed = [{"type": "error", "title": "Local MCP mock", "subtitle": message, "meta": {}}]
    yield {"type": "thinking", "payload": {"text": "Caught a tool error."}}
    yield {"type": "feed", "payload": {"items": feed}}
    yield {"type": "assistant", "payload": {"text": "Something blocked the MCP chain — check Developer Mode traces."}}
    yield {"type": "done", "payload": {"assistant_reply": None, "feed_items": feed}}


def _confirm_leg(
    leg: str, sid: str, ctx: dict[str, Any]
) -> Generator[dict[str, Any], None, None]:
    """Generic confirm handler for table / groceries / dessert legs."""
    if leg == "table":
        guests = int(ctx.get("partySize") or 6)
        bk = call_tool("dineout", "book_table", {
            "restaurantId": "do_italian_804",
            "partySize": guests,
            "slot": "20:00",
            "slotId": 4204,
        })
        yield _thinking("Executor • dineout book_table confirmed.")
        yield {"type": "tool", "payload": _sse_tool("dineout", "/dineout", "book_table", {}, bk)}
        feed = [{
            "type": "booking",
            "title": str(bk.get("venue_name", "Restaurant") if isinstance(bk, dict) else "Restaurant"),
            "subtitle": "CONFIRMED",
            "meta": bk if isinstance(bk, dict) else {},
        }]
        reply = "Table **confirmed** via book_table (mock)."
        yield {"type": "feed", "payload": {"items": feed}}
        yield {"type": "assistant", "payload": {"text": reply}}
        yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": feed}}

    elif leg == "groceries":
        cart = call_tool("im", "get_cart", {"requestId": sid})
        yield _thinking("Executor • im get_cart before checkout.")
        yield {"type": "tool", "payload": _sse_tool("im", "/im", "get_cart", {}, cart)}
        out = call_tool("im", "checkout", {"requestId": sid})
        yield {"type": "tool", "payload": _sse_tool("im", "/im", "checkout", {}, out)}
        reply = "Instamart **checkout** complete (mock)."
        yield {"type": "assistant", "payload": {"text": reply}}
        yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": []}}

    elif leg == "dessert":
        addr_any = call_tool("food", "get_addresses", {})
        addrs = addr_any if isinstance(addr_any, dict) else {}
        addr_id = _pick_address_id(ctx, addrs)
        cart = call_tool("food", "get_food_cart", {"requestId": sid, "addressId": addr_id})
        yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_food_cart", {}, cart)}
        out = call_tool("food", "place_food_order", {"requestId": sid, "addressId": addr_id})
        yield {"type": "tool", "payload": _sse_tool("food", "/food", "place_food_order", {}, out)}
        reply = "Dessert **placed** via place_food_order (mock). 10 PM reminder is manual in v1."
        yield {"type": "assistant", "payload": {"text": reply}}
        yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": []}}


def run_agent_stream(user_message: str, context: dict[str, Any] | None):
    """Yield SSE events: thinking | tool | feed | assistant | done."""
    ctx = context or {}
    sid = str(uuid.uuid4())

    mlow = user_message.lower()
    if "confirm table" in mlow:
        yield from _confirm_leg("table", sid, ctx)
        return
    if "confirm groceries" in mlow or "confirm grocery" in mlow:
        yield from _confirm_leg("groceries", sid, ctx)
        return
    if "confirm dessert" in mlow:
        yield from _confirm_leg("dessert", sid, ctx)
        return

    vertical = _detect_vertical(user_message, ctx)
    try:
        if vertical == "chrono":
            gen = run_chrono_host(sid, ctx)
        elif vertical == "food":
            gen = (
                run_food_pizza_order(sid, ctx)
                if _is_food_pizza_flow(user_message)
                else run_food_browse(sid, ctx)
            )
        elif vertical == "im":
            gen = run_instamart(sid, user_message)
        else:
            gen = run_dineout(ctx)
        yield from gen
    except LocalMCPError as e:
        yield from _error_bundle(str(e))
