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
from app.services.night_out import plan_dinner_party, plan_night_out
from backend.memory import get_conversation_history, save_turn
from backend.tool_schemas import TELEGRAM_TOOLS_FOR_LLM

log = logging.getLogger(__name__)

HISTORY_TURNS = 6
MAX_TOOL_ROUNDS = 6

# Exact camera line for Beat 2 (voice). Close paraphrases also match.
DEMO_NIGHT_OUT_SENTENCE = (
    "Plan a night out with friends this Saturday — dinner then drinks, then split the bill"
)

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
    "nexus_plan_night_out": "Planning night out (Calendar + table + split)",
    "nexus_plan_dinner_party": "Planning dinner party (Calendar + food + split)",
}


def _system_prompt() -> str:
    return (
        "You are Swiggy Nexus on Telegram — Food, Instamart, Dineout in India.\n"
        "Texting style: under 6 short lines, plain text, prices like 249 INR.\n"
        "Never invent IDs — copy restaurantId/itemId/spinId from tool results only.\n"
        f"Default address {settings.DEFAULT_ADDRESS_ID}; skip get_addresses unless asked.\n"
        "Friends + restaurant + book table + split → call nexus_plan_night_out ONLY when "
        "the user already named guests AND a restaurant AND a time; otherwise tell them "
        "to use /nightout (guided wizard) — never invent 6 Digs or a default slot.\n"
        "Hosting at home + order food + split → nexus_plan_dinner_party.\n"
        "Dish orders → food_search_menu → add_to_cart → food_place_order. "
        "Groceries → search → add → im_checkout. Table alone → search → availability → book_table.\n"
        "place_order / checkout / book_table / nexus_plan_* only STAGE for Approve — never say ordered.\n"
        "Instamart min 99 INR; food cart max 1000 INR. No cancel API — 080-67466729.\n"
        "Mock MCP demo: real tool names, synthetic catalog."
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
# Night Out NL short-circuit (demo Beat 2 — no LLM tool loop)
# ---------------------------------------------------------------------------


def _norm_intent_tokens(text: str) -> list[str]:
    cleaned = "".join(
        ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (text or "")
    )
    return cleaned.split()


def looks_like_night_out_intent(text: str) -> bool:
    """True for the demo sentence and close paraphrases — deterministic, no LLM."""
    tokens = _norm_intent_tokens(text)
    if not tokens:
        return False
    blob = " ".join(tokens)
    has_night_out = "night out" in blob or "nightout" in blob.replace(" ", "")
    has_plan = any(w in tokens for w in ("plan", "planning", "planned", "organize", "book"))
    has_friends = "friends" in tokens or "friend" in tokens
    has_dinner_drinks = "dinner" in tokens and ("drink" in blob or "drinks" in tokens)
    has_split = "split" in tokens and ("bill" in tokens or "bills" in tokens)
    # Exact-ish demo line (voice ASR may drop em dash / punctuation)
    if has_night_out and (has_friends or has_dinner_drinks or has_split):
        return True
    if has_plan and has_night_out:
        return True
    if has_dinner_drinks and has_split and ("saturday" in tokens or has_friends):
        return True
    return False


async def _short_circuit_night_out(
    chat_id: Any,
    text: str,
    *,
    status_id: int | None,
    source: str,
) -> dict[str, Any]:
    """Stage Calendar + table + split with Taste Vault defaults — then HITL Approve."""
    session_key = f"tg:{chat_id}"
    await _edit(chat_id, status_id, "🌙 Planning night out…")
    await _typing(chat_id)

    result = await plan_night_out(
        guest_names=["himali", "siya", "swayam"],
        preferred_slot="20:00",
    )
    rid = result.get("approval_request_id")
    venue = result.get("venue") or "6 Digs"
    guests = result.get("guest_count") or 4

    await _edit(
        chat_id,
        status_id,
        f"✅ Night out staged · {venue} · {guests} guests",
    )

    body = (
        f"⏸ Night out staged\n"
        f"{venue} · Saturday · {guests} guests · dinner then drinks\n"
        f"Calendar + table + equal split ready.\n"
        f"Nothing booked until you Approve."
    )
    if rid:
        body += f"\n({rid})"
        await _send(
            chat_id,
            body,
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve", "callback_data": f"approve:{rid}"},
                        {"text": "❌ Reject", "callback_data": f"reject:{rid}"},
                    ]
                ]
            },
        )
    else:
        await _send(chat_id, body + "\n\nOpen Concierge Ops to approve.")

    reply = (
        f"Night out at {venue} is staged for approval "
        f"({guests} guests, equal bill split)."
    )
    save_turn(session_key, "user", text)
    save_turn(session_key, "assistant", reply)
    record_qol_event(
        kind="agent_reply",
        title=f"Night-out short-circuit ({source})",
        detail=f"deterministic · {rid or 'no-rid'}",
        severity="info",
        meta={"short_circuit": "night_out", "approval_request_id": rid},
        event_id=session_key,
    )
    return {
        "ok": True,
        "provider": "deterministic",
        "tools": ["nexus_plan_night_out"],
        "halted": True,
        "short_circuit": "night_out",
        "approval_request_id": rid,
    }


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------


async def run_telegram_agent(chat_id: Any, text: str, *, source: str = "text") -> dict[str, Any]:
    """Handle one free-text (or transcribed voice) Telegram message."""
    session_key = f"tg:{chat_id}"
    await _typing(chat_id)
    status_id = await _send(chat_id, "🧠 Thinking…")
    status_cleared = False

    async def _clear_status(msg: str) -> None:
        nonlocal status_cleared
        if status_id and not status_cleared:
            await _edit(chat_id, status_id, msg)
            status_cleared = True

    try:
        # Demo Beat 2: NL / voice night-out → skip flaky LLM tool loops entirely.
        if looks_like_night_out_intent(text):
            out = await _short_circuit_night_out(
                chat_id, text, status_id=status_id, source=source
            )
            status_cleared = True
            return out

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
            if name == "nexus_plan_night_out":
                guests = args.get("guests") or args.get("guest_names") or []
                if isinstance(guests, str):
                    guests = [
                        g.strip()
                        for g in guests.replace(" and ", ",").split(",")
                        if g.strip()
                    ]
                venue = str(args.get("venue") or "").strip()
                slot = str(args.get("slot") or args.get("preferred_slot") or "").strip()
                start_iso = args.get("start_iso")
                # Incomplete → walk the user through the wizard instead of inventing 6 Digs.
                if not venue or (not slot and not start_iso):
                    from app.services.telegram_night_out import begin_night_out_wizard

                    await begin_night_out_wizard(
                        chat_id,
                        hint="Let's plan this properly — I'll ask guests, restaurant, then time.",
                    )
                    return {HALT_KEY: True, "status": "wizard_started"}
                result = await plan_night_out(
                    guest_names=list(guests),
                    venue=venue,
                    venue_query=str(args.get("venue_query") or venue),
                    guest_count=args.get("guest_count"),
                    start_iso=str(start_iso) if start_iso else None,
                    preferred_slot=slot or None,
                )
                result[HALT_KEY] = True
                rid = result.get("approval_request_id")
                if rid:
                    await _send(
                        chat_id,
                        f"⏸ Night out staged\n"
                        f"{result.get('venue')} · {result.get('guest_count')} guests"
                        f"{(' · ' + slot) if slot else ''}\n"
                        f"Calendar + table ready. Approve in Concierge or tap below.\n"
                        f"({rid})",
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {"text": "✅ Approve", "callback_data": f"approve:{rid}"},
                                    {"text": "❌ Reject", "callback_data": f"reject:{rid}"},
                                ]
                            ]
                        },
                    )
                return result
            if name == "nexus_plan_dinner_party":
                guests = args.get("guests") or []
                if isinstance(guests, str):
                    guests = [
                        g.strip()
                        for g in guests.replace(" and ", ",").split(",")
                        if g.strip()
                    ]
                result = await plan_dinner_party(
                    guest_names=list(guests),
                    dish_query=str(args.get("dish_query") or "paneer biryani"),
                    guest_count=args.get("guest_count"),
                )
                result[HALT_KEY] = True
                rid = result.get("approval_request_id")
                if rid:
                    await _send(
                        chat_id,
                        f"⏸ Dinner party staged\n"
                        f"{result.get('guest_count')} guests · Approve to order + split\n"
                        f"({rid})",
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {"text": "✅ Approve", "callback_data": f"approve:{rid}"},
                                    {"text": "❌ Reject", "callback_data": f"reject:{rid}"},
                                ]
                            ]
                        },
                    )
                return result
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
                tools=TELEGRAM_TOOLS_FOR_LLM,
            )
        except LLMUnavailable as e:
            await _clear_status(f"⚠️ {e}")
            return {"ok": False, "reason": "llm_unavailable"}
        except Exception as e:  # noqa: BLE001
            log.exception("Telegram agent failed")
            blob = str(e).lower()
            if "rate_limit" in blob or "429" in blob or "quota" in blob:
                note = (
                    "⚠️ My LLM quota is exhausted for now. Set GEMINI_API_KEY for the primary "
                    "brain, or wait for the Groq limit to reset. "
                    f"(Configured brain: {active_provider_label()})"
                )
            else:
                note = "⚠️ My planner hiccuped mid-step. Say that again and I'll retry."
            await _clear_status(note)
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

        if trail:
            await _clear_status("✅ Ran:\n" + "\n".join(trail[-6:]))
        else:
            await _clear_status("✅ Done")

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
    except Exception as e:  # noqa: BLE001 — never leave a permanent Thinking bubble
        log.exception("Telegram agent crashed before reply")
        await _clear_status("⚠️ Something broke mid-step. Say that again and I'll retry.")
        record_qol_event(
            kind="agent_error",
            title="Telegram agent crash",
            detail=str(e)[:200],
            severity="warn",
            event_id=session_key,
        )
        return {"ok": False, "reason": "agent_crash", "error": str(e)[:200]}
    finally:
        if status_id and not status_cleared:
            await _edit(chat_id, status_id, "⚠️ Interrupted — try again.")
