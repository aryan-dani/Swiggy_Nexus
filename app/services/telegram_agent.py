"""Telegram LLM agent — natural-language Swiggy ordering with a human approval gate.

Read tools run freely. The three money tools (`food_place_order`, `im_checkout`,
`dineout_book_table`) are intercepted: the agent stages an approval row and sends
inline Approve/Reject buttons instead of spending anything. Tapping Approve goes
through the existing HITL path, so Telegram, the web dashboard and the calendar
flow all share one gate.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from app.config import settings
from app.db.store import create_approval, record_qol_event
from app.mcp.client import mcp_client, SwiggyMCPError
from app.services.llm import (
    HALT_KEY,
    LLMUnavailable,
    active_provider_label,
    run_tool_conversation,
)
from backend.memory import get_conversation_history, save_turn

log = logging.getLogger(__name__)

HISTORY_TURNS = 12
MAX_TOOL_ROUNDS = 6

# Money tools — never executed by the model.
WRITE_TOOLS = {"food_place_order", "im_checkout", "dineout_book_table"}

_ADDRESS_KEYS = ("addressId", "selectedAddressId")

_TOOL_CAPTIONS = {
    "food_get_addresses": "Fetching saved addresses",
    "food_search_restaurants": "Searching restaurants",
    "food_search_menu": "Searching dishes",
    "food_get_menu": "Loading menu",
    "food_add_to_cart": "Adding to food cart",
    "food_get_food_cart": "Reading food cart",
    "food_fetch_food_coupons": "Checking coupons",
    "food_apply_food_coupon": "Applying coupon",
    "food_track_food_order": "Tracking order",
    "im_search_products": "Searching Instamart",
    "im_your_go_to_items": "Loading your regulars",
    "im_add_to_cart": "Adding to Instamart cart",
    "im_get_cart": "Reading Instamart cart",
    "im_track_order": "Tracking delivery",
    "im_get_orders": "Loading past orders",
    "dineout_get_saved_locations": "Loading saved locations",
    "dineout_search_restaurants": "Searching Dineout venues",
    "dineout_get_restaurant_details": "Loading venue details",
    "dineout_check_availability": "Checking table slots",
    "food_place_order": "Staging food order for approval",
    "im_checkout": "Staging Instamart checkout for approval",
    "dineout_book_table": "Staging table booking for approval",
}


def _system_prompt() -> str:
    return (
        "You are Swiggy Nexus on Telegram — an autonomous concierge for Swiggy Food "
        "delivery, Instamart groceries, and Dineout table bookings in India.\n\n"
        "STYLE: You are texting. Keep replies under 6 short lines. Plain text only, no "
        "Markdown formatting characters. Prices in rupees, written like 249 INR or Rs 249. "
        "Warm, brisk, a little Hinglish is fine.\n\n"
        "HOW YOU WORK:\n"
        "1. Use the tools for every fact. NEVER invent an ID. Every restaurantId, itemId and "
        "spinId must be copied verbatim from an earlier tool result in this conversation. "
        "Placeholder-looking ids such as res_001 or item_01 are always wrong — if you do not "
        "have a real id yet, call the search or menu tool first.\n"
        f"2. Default delivery address is {settings.DEFAULT_ADDRESS_ID}; only call "
        "food_get_addresses if the user asks about addresses.\n"
        "3. To order food when the user names a DISH (e.g. 'paneer biryani'): call "
        "food_search_menu with that dish query first. Pick the best matching itemId/"
        "restaurantId from the results, food_add_to_cart with those real ids, then "
        "food_place_order. Do NOT open a random restaurant menu and give up if the dish "
        "is missing there — use search_menu (or try another restaurant from search). "
        "Only load get_menu when the user names a restaurant or you already have the "
        "itemId. For groceries: search products, add to cart, then im_checkout. For a "
        "table: search Dineout, check availability, then dineout_book_table. Do not "
        "re-read the cart more than once before ordering.\n"
        "4. food_place_order, im_checkout and dineout_book_table DO NOT place anything. They "
        "stage the request and send the human an Approve button. When one returns "
        "'awaiting_human_approval', tell the user exactly what is staged, the total, and that "
        "you are waiting for them to tap Approve. Never say an order was placed or confirmed.\n"
        "5. Instamart has a 99 INR minimum order. Food carts cap at 1000 INR.\n"
        "6. If a tool errors, say what failed in one line and offer an alternative.\n"
        "7. Cancellation is not available via API — tell users to call Swiggy care on "
        "080-67466729.\n\n"
        "This is a Builders Club demo running on a mock Swiggy MCP: real tool names and "
        "shapes, synthetic catalog, no real money."
    )


# ---------------------------------------------------------------------------
# Telegram wire helpers (kept local so app.api.hitl can import this module)
# ---------------------------------------------------------------------------


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


async def _post(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.TELEGRAM_BOT_TOKEN:
        log.info("[telegram:%s] %s", method, payload.get("text") or payload)
        return {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api(method), json=payload)
            return resp.json() if resp.content else {}
    except Exception as e:  # noqa: BLE001 — never let Telegram I/O kill the agent
        log.warning("Telegram %s failed: %s", method, e)
        return {}


async def _typing(chat_id: Any) -> None:
    await _post("sendChatAction", {"chat_id": chat_id, "action": "typing"})


async def _send(chat_id: Any, text: str, reply_markup: dict[str, Any] | None = None) -> int | None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    data = await _post("sendMessage", payload)
    return ((data or {}).get("result") or {}).get("message_id")


async def _edit(chat_id: Any, message_id: int | None, text: str) -> None:
    if not message_id:
        return
    await _post(
        "editMessageText",
        {"chat_id": chat_id, "message_id": message_id, "text": text},
    )


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _split_tool(name: str) -> tuple[str, str]:
    parts = name.split("_", 1)
    if len(parts) == 2 and parts[0] in ("food", "im", "dineout"):
        return parts[0], parts[1]
    return "food", name


def _with_defaults(vertical: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
    """Inject the demo address so a chatty model can skip the address lookup."""
    out = dict(args)
    needs_address = vertical in ("food", "im") and method not in ("get_addresses",)
    if needs_address and not any(out.get(k) for k in _ADDRESS_KEYS):
        out["addressId"] = settings.DEFAULT_ADDRESS_ID
        if vertical == "im":
            out["selectedAddressId"] = settings.DEFAULT_ADDRESS_ID
    if vertical == "dineout":
        out.setdefault("latitude", settings.HOME_LAT)
        out.setdefault("longitude", settings.HOME_LNG)
    return out


async def _read_cart(vertical: str) -> dict[str, Any]:
    method = "get_cart" if vertical == "im" else "get_food_cart"
    try:
        data = await mcp_client.call_tool_async(
            vertical, method, {"addressId": settings.DEFAULT_ADDRESS_ID}
        )
        return data if isinstance(data, dict) else {}
    except SwiggyMCPError as e:
        log.warning("Cart read failed for %s: %s", vertical, e.message)
        return {}


def _cart_lines(cart: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "lines"):
        rows = cart.get(key)
        if isinstance(rows, list) and rows:
            return rows
    return []


def _cart_total(cart: dict[str, Any]) -> float:
    bill = cart.get("bill") if isinstance(cart.get("bill"), dict) else {}
    for source in (cart, bill):
        for key in ("total", "total_inr", "grandTotal", "subtotal_inr"):
            value = source.get(key)
            if isinstance(value, (int, float)) and value:
                return float(value)
    return 0.0


async def _stage_write_tool(
    chat_id: Any, tool_name: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Turn a money tool call into a pending approval plus inline buttons."""
    event_id = f"tg-{uuid.uuid4().hex[:8]}"
    address_id = settings.DEFAULT_ADDRESS_ID

    if tool_name == "im_checkout":
        cart = await _read_cart("im")
        lines = _cart_lines(cart)
        if not lines:
            return {
                "status": "error",
                "message": "Instamart cart is empty — add items before checkout.",
            }
        items = [
            {
                "spinId": line.get("spinId"),
                "quantity": int(line.get("quantity") or line.get("qty") or 1),
                "name": line.get("name"),
                "price_inr": line.get("unit_price_inr") or line.get("price_inr"),
            }
            for line in lines
            if line.get("spinId")
        ]
        total = _cart_total(cart) or sum(
            (i.get("price_inr") or 0) * i["quantity"] for i in items
        )
        title = "Instamart checkout"
        summary = ", ".join(str(i.get("name") or i["spinId"]) for i in items[:5])
        staged_payload = {
            "mode": "ZERO_TOUCH_HOST",
            "source": "telegram_agent",
            "staged_im_cart": {
                "selectedAddressId": address_id,
                "items": items,
                "estimated_total_inr": total,
            },
            "staged_food_cart": {"cartItems": [], "addressId": address_id},
        }
        cost_breakdown = {"mode": "IM", "total_cost_inr": total, "items": items}

    elif tool_name == "food_place_order":
        cart = await _read_cart("food")
        lines = _cart_lines(cart)
        if not lines:
            return {
                "status": "error",
                "message": "Food cart is empty — add dishes before placing the order.",
            }
        cart_items = [
            {
                "itemId": line.get("item_id") or line.get("itemId"),
                "quantity": int(line.get("quantity") or line.get("qty") or 1),
                "name": line.get("name")
                or line.get("item_name")
                or line.get("item_id")
                or line.get("itemId"),
                "price_inr": line.get("unit_price_inr") or line.get("price_inr"),
            }
            for line in lines
            if line.get("item_id") or line.get("itemId")
        ]
        restaurant_id = (
            args.get("restaurantId")
            or cart.get("restaurant_id")
            or cart.get("restaurantId")
        )
        total = _cart_total(cart)
        title = "Food order"
        summary = ", ".join(str(c.get("name") or c["itemId"]) for c in cart_items[:5])
        staged_payload = {
            "mode": "ZERO_TOUCH_HOST",
            "source": "telegram_agent",
            "staged_im_cart": {"items": [], "selectedAddressId": address_id},
            "staged_food_cart": {
                "restaurantId": restaurant_id,
                "addressId": address_id,
                "cartItems": cart_items,
                "estimated_total_inr": total,
            },
        }
        cost_breakdown = {"mode": "FOOD", "total_cost_inr": total, "items": cart_items}

    else:  # dineout_book_table
        guests = int(args.get("guestCount") or args.get("partySize") or 2)
        slot = str(args.get("slot") or args.get("slotId") or "19:30")
        restaurant_id = args.get("restaurantId")
        title = "Dineout table"
        summary = f"{guests} guests at {slot}"
        total = 0.0
        staged_payload = {
            "mode": "DINEOUT",
            "source": "telegram_agent",
            "dineout_plan": {
                "restaurantId": restaurant_id,
                "slot_label": slot,
                "guestCount": guests,
                "latitude": args.get("latitude") or settings.HOME_LAT,
                "longitude": args.get("longitude") or settings.HOME_LNG,
            },
        }
        cost_breakdown = {"mode": "DINEOUT", "guest_count": guests, "slot": slot}

    approval = create_approval(
        event_id=event_id,
        thread_id=event_id,
        trigger_type="voice_order",
        title=f"{title} (Telegram agent)",
        summary=summary or title,
        cost_breakdown=cost_breakdown,
        staged_payload=staged_payload,
    )
    request_id = approval["request_id"]

    cost_line = f"\nTotal: Rs {round(total)}" if total else ""
    await _send(
        chat_id,
        f"⏸ Human approval needed\n{title}\n{summary}{cost_line}\n\n"
        f"Nothing has been ordered yet. ({request_id})",
        reply_markup={
            "inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": f"approve:{request_id}"},
                    {"text": "❌ Reject", "callback_data": f"reject:{request_id}"},
                ]
            ]
        },
    )

    record_qol_event(
        kind="agent_staged",
        title=f"Telegram agent staged {title}",
        detail=request_id,
        severity="action",
        meta={"tool": tool_name, "total_inr": total},
        event_id=event_id,
    )

    return {
        HALT_KEY: True,
        "status": "awaiting_human_approval",
        "request_id": request_id,
        "staged": title,
        "total_inr": total,
        "message": (
            "Staged for human approval. Approve/Reject buttons were sent to the user. "
            "Do not retry this tool. Tell the user what is staged and that you are waiting."
        ),
    }


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------


async def run_telegram_agent(chat_id: Any, text: str, *, source: str = "text") -> dict[str, Any]:
    """Handle one free-text (or transcribed voice) Telegram message."""
    session_key = f"tg:{chat_id}"
    await _typing(chat_id)
    status_id = await _send(chat_id, "🧠 Thinking…")

    trail: list[str] = []

    async def on_tool_start(name: str, args: dict[str, Any]) -> None:
        caption = _TOOL_CAPTIONS.get(name, name)
        trail.append(f"• {caption}")
        await _typing(chat_id)
        await _edit(chat_id, status_id, "🧠 Working…\n" + "\n".join(trail[-6:]))
        record_qol_event(
            kind="agent_tool",
            title=f"Agent · {name}",
            detail=caption,
            severity="info",
            meta={"tool": name, "args": args, "surface": "telegram"},
            event_id=session_key,
        )

    async def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name in WRITE_TOOLS:
            return await _stage_write_tool(chat_id, name, args)
        vertical, method = _split_tool(name)
        params = _with_defaults(vertical, method, args)
        try:
            data = await mcp_client.call_tool_async(vertical, method, params)
        except SwiggyMCPError as e:
            return {"status": "error", "code": e.code, "message": e.message}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "message": str(e)}
        return data if isinstance(data, dict) else {"result": data}

    history = [
        {"role": turn["role"], "content": turn["content"]}
        for turn in get_conversation_history(session_key, limit=HISTORY_TURNS)
    ]

    try:
        result = await run_tool_conversation(
            system_prompt=_system_prompt(),
            user_message=text,
            execute_tool=execute_tool,
            history=history,
            on_tool_start=on_tool_start,
            max_rounds=MAX_TOOL_ROUNDS,
        )
    except LLMUnavailable as e:
        await _edit(chat_id, status_id, f"⚠️ {e}")
        return {"ok": False, "reason": "llm_unavailable"}
    except Exception as e:  # noqa: BLE001
        log.exception("Telegram agent failed")
        blob = str(e).lower()
        if "rate_limit" in blob or "429" in blob or "quota" in blob:
            note = (
                "⚠️ My LLM quota is exhausted for now. Set GEMINI_API_KEY for the primary "
                "brain, or wait for the Groq limit to reset."
            )
        else:
            note = "⚠️ My planner hiccuped mid-step. Say that again and I'll retry."
        await _edit(chat_id, status_id, note)
        record_qol_event(
            kind="agent_error",
            title="Telegram agent error",
            detail=str(e)[:200],
            severity="warn",
            event_id=session_key,
        )
        return {"ok": False, "reason": "agent_error"}

    tool_count = len(result.tool_names)
    footer = f"\n\n— {active_provider_label()} · {tool_count} MCP tool" + (
        "s" if tool_count != 1 else ""
    )
    reply = result.text or "Done."

    if status_id and trail:
        await _edit(chat_id, status_id, "✅ Ran:\n" + "\n".join(trail[-6:]))
    elif status_id:
        await _edit(chat_id, status_id, "✅ Done")

    await _send(chat_id, reply + footer)

    save_turn(session_key, "user", text)
    save_turn(session_key, "assistant", reply)

    record_qol_event(
        kind="agent_reply",
        title=f"Agent replied on Telegram ({source})",
        detail=f"{tool_count} tools · {result.provider}",
        severity="info",
        meta={"tools": result.tool_names, "provider": result.provider},
        event_id=session_key,
    )

    return {
        "ok": True,
        "provider": result.provider,
        "tools": result.tool_names,
        "halted": result.halted,
    }
