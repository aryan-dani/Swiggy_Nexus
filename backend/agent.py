"""Streaming Nexus agent over **local mock** MCP (`/food`, `/im`, `/dineout`)."""

from __future__ import annotations

import uuid
from typing import Any, Generator, Literal

from backend.mcp_client import LocalMCPError, call_tool

Vertical = Literal["food", "im", "dineout"]


def _detect_vertical(message: str, ctx: dict[str, Any]) -> Vertical:
    mlow = message.lower()
    ctx_v = ctx.get("vertical")
    if ctx_v == "dineout" or ctx.get("scenario") == "team_dinner":
        return "dineout"
    if ctx_v == "instamart":
        return "im"

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


def _sse_tool(server_key: Vertical, http_path: str, method: str, params: dict[str, Any], data: Any) -> dict[str, Any]:
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
        "lines": [{"item_id": "dom_mar_med", "qty": 1}],
    }
    cart_any = call_tool("food", "add_to_cart", cart_params)
    cart = cart_any if isinstance(cart_any, dict) else {}
    yield {"type": "tool", "payload": _sse_tool("food", "/food", "add_to_cart", cart_params, cart_any)}
    cid = str(cart.get("cart_id", ""))

    order_any = call_tool("food", "place_order", {"cart_id": cid, "payment_mode": "COD"})
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
    prods = call_tool("im", "search_products", {"query": snippet or None})
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "search_products", {"query": snippet or None}, prods)}
    plist = []
    if isinstance(prods, dict):
        plist = prods.get("products") or []

    picks = plist[: min(12, len(plist))]
    line_items: list[dict[str, Any]] = []
    pid_milk = "im_milk_f"
    pid_bread = "im_bread"
    if any(p["product_id"] == pid_milk for p in picks):
        line_items.append({"product_id": pid_milk, "qty": 1})
    elif picks:
        line_items.append({"product_id": picks[0]["product_id"], "qty": 1})
    if any(p["product_id"] == pid_bread for p in picks):
        line_items.append({"product_id": pid_bread, "qty": 1})

    yield _thinking("`im.add_to_cart` assembling a basket.")
    cart = call_tool(
        "im",
        "add_to_cart",
        {"request_id": uuid_session, "items": line_items},
    )
    yield {"type": "tool", "payload": _sse_tool("im", "/im", "add_to_cart", {"items": line_items}, cart)}
    cid = ""
    if isinstance(cart, dict):
        cid = str(cart.get("cart_id", ""))

    out = call_tool("im", "checkout", {"cart_id": cid})
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


def _error_bundle(message: str) -> Generator[dict[str, Any], None, None]:
    feed = [{"type": "error", "title": "Local MCP mock", "subtitle": message, "meta": {}}]
    yield {"type": "thinking", "payload": {"text": "Caught a tool error."}}
    yield {"type": "feed", "payload": {"items": feed}}
    yield {"type": "assistant", "payload": {"text": "Something blocked the MCP chain — check Developer Mode traces."}}
    yield {"type": "done", "payload": {"assistant_reply": None, "feed_items": feed}}


def run_agent_stream(user_message: str, context: dict[str, Any] | None):
    """Yield SSE events: thinking | tool | feed | assistant | done."""
    ctx = context or {}
    sid = str(uuid.uuid4())

    vertical = _detect_vertical(user_message, ctx)
    try:
        if vertical == "food":
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
