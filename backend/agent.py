"""Streaming Nexus agent over **local mock** MCP (`/food`, `/im`, `/dineout`).

Deterministic scripted demo flows. Activated when no GROQ_API_KEY is set
or when a reviewer scenario is specified in the context.
"""

from __future__ import annotations

import logging
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
            "plan my housewarming",
            "plan a festive",
            "plan a team dinner",
            "plan a date-night",
            "plan a date night",
            "housewarming",
            "chrono host",
            "evening plan",
            "dinner out and dessert",
            "thali energy",
            "festive dinner",
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


def _resolve_session_id(ctx: dict[str, Any] | None) -> str:
    """Stable MCP cart session across Chrono stage → confirm turns.

    Must match the frontend ``requestId`` (localStorage) so drawers and chat
    confirm hit the same in-memory mock cart. Never mint a fresh UUID per
    message — that left Confirm groceries checking out an empty cart.
    """
    ctx = ctx or {}
    for key in ("requestId", "request_id", "sessionId", "session_id"):
        val = ctx.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return "default_mock_session"


def _im_line_summaries(cart_view: Any) -> list[dict[str, Any]]:
    """Normalize Instamart cart lines for bundle / feed UX."""
    if not isinstance(cart_view, dict):
        return []
    rows = cart_view.get("items") or cart_view.get("lines") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        qty = int(row.get("qty") or row.get("quantity") or 1)
        unit = int(row.get("unit_price_inr") or row.get("price_inr") or 0)
        line_total = int(row.get("line_total_inr") or (unit * qty))
        out.append(
            {
                "name": str(row.get("name") or row.get("spinId") or "Item"),
                "qty": qty,
                "unit_price_inr": unit,
                "line_total_inr": line_total,
                "spinId": row.get("spinId"),
                "product_id": row.get("product_id"),
            }
        )
    return out


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


_DESSERT_HINTS = ("dessert", "desserts", "ice cream", "gelato", "sweet", "bakery", "kulfi", "mochi")


def _is_dessert_restaurant(row: dict[str, Any]) -> bool:
    hay = " ".join(
        [
            str(row.get("name", "")),
            " ".join(str(c) for c in (row.get("cuisines") or [])),
            str(row.get("tag", "")),
        ]
    ).lower()
    return any(h in hay for h in _DESSERT_HINTS)


def _pick_dessert_restaurant(rows: list[dict[str, Any]], pick_seed: int) -> dict[str, Any]:
    """Prefer dessert/ice-cream venues when search falls back to the full catalog."""
    typed = [r for r in rows if isinstance(r, dict)]
    dessertish = [r for r in typed if _is_dessert_restaurant(r)]
    pool = dessertish or typed or [{}]
    return pool[pick_seed % len(pool)]


def _first_menu_item_id(menu: Any) -> str | None:
    """Resolve a cartable item_id from get_restaurant_menu / get_menu response."""
    if not isinstance(menu, dict):
        return None
    for cat in menu.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        for it in cat.get("items") or []:
            if not isinstance(it, dict):
                continue
            iid = str(it.get("item_id") or it.get("itemId") or "").strip()
            if iid:
                return iid
    return None


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
    import hashlib

    event = ctx.get("event") if isinstance(ctx.get("event"), dict) else {}
    guests = int(event.get("guests") or ctx.get("partySize") or ctx.get("party_size") or 12)
    cuisine = str(event.get("cuisineHint") or "italian").lower()
    event_title = str(event.get("title") or "Your evening")
    im_query = str(event.get("imQuery") or "party plates napkins drinks")
    dessert_query = str(event.get("dessertQuery") or "gelato")
    # Stable-but-varying pick across demos so the same cuisine doesn't always show #1
    pick_seed = int(hashlib.md5(f"{event_title}:{cuisine}:{guests}".encode()).hexdigest()[:8], 16)

    yield _thinking(
        f"Planner · Chrono-Host: {event_title} · {guests} guests · {cuisine} — "
        "orchestrating Dineout + Instamart + Food."
    )

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
    dine_list = [r for r in (ds.get("restaurants") or []) if isinstance(r, dict)] or [{}]
    rest_pick = dine_list[pick_seed % len(dine_list)]
    rest_id = str(rest_pick.get("restaurant_id", "do_italian_804"))

    slot_params = {"restaurantId": rest_id, "guestCount": guests, "date": "2026-07-12", "partySize": guests}
    slots_any = call_tool("dineout", "get_available_slots", slot_params)
    yield {"type": "tool", "payload": _sse_tool("dineout", "/dineout", "get_available_slots", slot_params, slots_any)}
    slots_blob = slots_any if isinstance(slots_any, dict) else {}
    slot0 = (slots_blob.get("slots") or [{}])[0]
    slot_label = slot0.get("label", "20:00")

    # --- Instamart leg ---
    yield _thinking(f"Instamart: staging supplies — “{im_query}”.")
    addr_any = call_tool("food", "get_addresses", {})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_addresses", {}, addr_any)}
    addrs = addr_any if isinstance(addr_any, dict) else {}
    addr_id = _pick_address_id(ctx, addrs)

    im_search = call_tool("im", "search_products", {"addressId": addr_id, "query": im_query})
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "search_products", {"query": im_query}, im_search)}
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
    im_line_summaries = _im_line_summaries(im_cart_view)
    im_cart_id = (
        (im_cart_any or {}).get("cart_id")
        if isinstance(im_cart_any, dict)
        else None
    ) or (im_cart_view.get("cart_id") if isinstance(im_cart_view, dict) else None) or f"cart_im_{uuid_session}"

    # --- Food dessert leg (staged) ---
    yield _thinking(f"Food: staging “{dessert_query}” dessert for ~10 PM (reminder — no scheduled delivery in v1).")
    dessert_search = call_tool("food", "search_restaurants", {"addressId": addr_id, "query": dessert_query})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "search_restaurants", {"query": dessert_query}, dessert_search)}
    ds_food = dessert_search if isinstance(dessert_search, dict) else {}
    food_list = [r for r in (ds_food.get("restaurants") or []) if isinstance(r, dict)] or [{}]
    dessert_pick = _pick_dessert_restaurant(food_list, pick_seed)
    dessert_rid = str(dessert_pick.get("restaurant_id", "fd_gelato_108"))
    dessert_name = str(dessert_pick.get("name") or dessert_query.title())

    menu_any = call_tool("food", "get_restaurant_menu", {"restaurantId": dessert_rid, "addressId": addr_id})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_restaurant_menu", {"restaurantId": dessert_rid}, menu_any)}

    # Always stage an item that belongs to this restaurant's menu — never a hardcoded foreign id.
    dessert_item_id = _first_menu_item_id(menu_any)
    if not dessert_item_id:
        dessert_rid = "fd_gelato_108"
        dessert_name = "Gelato Vivo"
        dessert_item_id = "gv_pistachio"

    food_cart_params = {
        "requestId": uuid_session,
        "restaurantId": dessert_rid,
        "addressId": addr_id,
        "cartItems": [{"itemId": dessert_item_id, "quantity": 2}],
        "lines": [{"item_id": dessert_item_id, "qty": 2}],
    }
    food_cart_any = call_tool("food", "update_food_cart", food_cart_params)
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "update_food_cart", food_cart_params, food_cart_any)}
    food_cart_view = call_tool("food", "get_food_cart", {"requestId": uuid_session, "addressId": addr_id})
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_food_cart", {"addressId": addr_id}, food_cart_view)}

    _rest0 = rest_pick if isinstance(rest_pick, dict) else {}
    im_bundle = dict(im_cart_view) if isinstance(im_cart_view, dict) else {}
    im_bundle["cart_id"] = im_cart_id
    im_bundle["requestId"] = uuid_session
    im_bundle["items"] = im_line_summaries or im_bundle.get("items") or []
    food_bundle = dict(food_cart_view) if isinstance(food_cart_view, dict) else {}
    food_bundle["requestId"] = uuid_session
    if isinstance(food_cart_any, dict) and food_cart_any.get("cart_id"):
        food_bundle["cart_id"] = food_cart_any["cart_id"]

    bundle = {
        "event": event_title,
        "requestId": uuid_session,
        "dineout": {
            "restaurantId": rest_id,
            "restaurant": _rest0.get("name"),
            "slot": slot_label,
            "guests": guests,
            "status": "STAGED",
            "costForTwo": _rest0.get("costForTwo") or _rest0.get("price_for_two_inr"),
        },
        "instamart": im_bundle,
        "food": food_bundle,
    }
    set_user_preference("last_event_bundle", json.dumps(bundle))

    dine_name = _rest0.get("name", "Restaurant")
    im_total = im_bundle.get("total", "?")
    food_total = food_bundle.get("total", "?")
    im_lines_txt = ", ".join(
        f"{ln['name']} ×{ln['qty']} (₹{ln['line_total_inr']})" for ln in im_line_summaries
    ) or im_query

    feed: list[dict[str, Any]] = [
        {
            "type": "event_bundle",
            "title": f"Evening plan · {event_title}",
            "subtitle": f"Dineout + Instamart + {dessert_query} — review each leg",
            "meta": bundle,
        },
        {
            "type": "dineout",
            "title": dine_name,
            "subtitle": f"Table for {guests} · {slot_label} · confirm to book",
            "meta": {"restaurant_id": rest_id, "slot": slot_label, "guests": guests},
        },
    ]
    for ln in im_line_summaries:
        feed.append({
            "type": "instamart",
            "title": ln["name"],
            "subtitle": f"×{ln['qty']} · ₹{ln['line_total_inr']} staged",
            "meta": {
                "product_id": ln.get("product_id"),
                "spinId": ln.get("spinId"),
                "qty": ln["qty"],
                "unit_price_inr": ln["unit_price_inr"],
                "line_total_inr": ln["line_total_inr"],
                "price_inr": ln["unit_price_inr"],
            },
        })
    if not im_line_summaries:
        for p in im_prods[:4]:
            feed.append({
                "type": "instamart",
                "title": p.get("name"),
                "subtitle": f"Staged · {im_query.split()[0] if im_query else 'supplies'}",
                "meta": {
                    "product_id": p.get("product_id"),
                    "price_inr": p.get("price_inr") or (p.get("variants") or [{}])[0].get("price"),
                },
            })
    feed.append({
        "type": "restaurant",
        "title": f"{dessert_name} · {dessert_query} @ 10 PM",
        "subtitle": f"Staged cart ₹{food_total} — I'll remind you to place at 10 PM",
        "meta": {"restaurant_id": dessert_rid, "cuisine": dessert_query},
    })

    reply = (
        f"Here's your evening bundle for **{event_title}** ({guests} guests · {cuisine}):\n\n"
        f"1. **Dineout** — {dine_name}, table for {guests} at {slot_label}. Reply **confirm table** to book.\n"
        f"2. **Instamart** — {im_lines_txt} (₹{im_total}). Reply **confirm groceries** to checkout.\n"
        f"3. **Food** — {dessert_query} via {dessert_name} staged (₹{food_total}). "
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
    """Generic confirm handler for table / groceries / dessert legs.

    Browser-only (Beat 1 / Chrono-Host). Never stages HITL or sends Telegram —
    write tools execute against the mock MCP after the user clicks Confirm.
    """
    if leg == "table":
        # Prefer restaurant/slot staged in the Chrono bundle when present.
        dine: dict[str, Any] = {}
        try:
            import json
            from backend.memory import get_user_preferences

            raw = get_user_preferences().get("last_event_bundle")
            if isinstance(raw, str):
                raw = json.loads(raw)
            if isinstance(raw, dict) and isinstance(raw.get("dineout"), dict):
                dine = raw["dineout"]
        except Exception:  # noqa: BLE001
            dine = {}
        guests = int(dine.get("guests") or ctx.get("partySize") or 6)
        rid = str(dine.get("restaurantId") or "do_italian_804")
        slot = str(dine.get("slot") or "20:00")
        bk = call_tool("dineout", "book_table", {
            "restaurantId": rid,
            "partySize": guests,
            "slot": slot,
            "slotId": dine.get("slotId") or 4204,
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
        yield _thinking(f"Executor • im get_cart before checkout (session={sid}).")
        yield {"type": "tool", "payload": _sse_tool("im", "/im", "get_cart", {"requestId": sid}, cart)}
        lines = _im_line_summaries(cart)
        if not lines:
            reply = (
                "Instamart cart is empty for this session — re-run Chrono-Host / WOW so groceries "
                "are staged, then confirm again."
            )
            yield {"type": "assistant", "payload": {"text": reply}}
            yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": []}}
            return
        cart_id = (cart.get("cart_id") if isinstance(cart, dict) else None) or f"cart_im_{sid}"
        out = call_tool("im", "checkout", {"requestId": sid, "cartId": cart_id})
        yield {"type": "tool", "payload": _sse_tool("im", "/im", "checkout", {"requestId": sid, "cartId": cart_id}, out)}
        oid = out.get("order_id") or out.get("orderId") if isinstance(out, dict) else None
        lines_txt = ", ".join(f"{ln['name']} ×{ln['qty']}" for ln in lines)
        reply = (
            f"Instamart **checkout** complete (mock)"
            + (f" · {oid}" if oid else "")
            + f". Placed: {lines_txt}."
        )
        feed = [{
            "type": "order",
            "title": f"Instamart · {oid or 'placed'}",
            "subtitle": lines_txt,
            "meta": out if isinstance(out, dict) else {},
        }]
        yield {"type": "feed", "payload": {"items": feed}}
        yield {"type": "assistant", "payload": {"text": reply}}
        yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": feed}}

    elif leg == "dessert":
        addr_any = call_tool("food", "get_addresses", {})
        addrs = addr_any if isinstance(addr_any, dict) else {}
        addr_id = _pick_address_id(ctx, addrs)
        cart = call_tool("food", "get_food_cart", {"requestId": sid, "addressId": addr_id})
        yield {"type": "tool", "payload": _sse_tool("food", "/food", "get_food_cart", {"requestId": sid}, cart)}
        items = (cart.get("items") or cart.get("lines") or []) if isinstance(cart, dict) else []
        if not items:
            reply = (
                "Food dessert cart is empty for this session — re-run Chrono-Host so dessert is staged, "
                "then confirm again."
            )
            yield {"type": "assistant", "payload": {"text": reply}}
            yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": []}}
            return
        cart_id = (cart.get("cart_id") if isinstance(cart, dict) else None) or f"cart_fd_{sid}"
        out = call_tool(
            "food",
            "place_food_order",
            {"requestId": sid, "addressId": addr_id, "cartId": cart_id},
        )
        yield {
            "type": "tool",
            "payload": _sse_tool(
                "food", "/food", "place_food_order",
                {"requestId": sid, "addressId": addr_id, "cartId": cart_id},
                out,
            ),
        }
        reply = "Dessert **placed** via place_food_order (mock). 10 PM reminder is manual in v1."
        yield {"type": "assistant", "payload": {"text": reply}}
        yield {"type": "done", "payload": {"assistant_reply": reply, "feed_items": []}}


def run_agent_stream(user_message: str, context: dict[str, Any] | None):
    """Yield SSE events: thinking | tool | feed | assistant | done."""
    ctx = context or {}
    sid = _resolve_session_id(ctx)

    mlow = user_message.lower()
    try:
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
