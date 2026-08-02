"""Telegram Night Out wizard — guests → venue → slot → one Approve (edits one message)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.services import night_out_wizard as wiz

log = logging.getLogger(__name__)


async def _send(chat_id: Any, text: str, reply_markup: dict | None = None) -> int | None:
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        log.info("[TG NOW] %s\n%s", chat_id, text)
        return None
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            log.warning("TG send failed: %s", resp.text[:200])
            return None
        try:
            return int((resp.json().get("result") or {}).get("message_id"))
        except (TypeError, ValueError):
            return None


async def _edit(
    chat_id: Any,
    message_id: int | None,
    text: str,
    reply_markup: dict | None = None,
) -> int | None:
    """Edit in place; fall back to send if edit fails or no message_id."""
    if not message_id:
        return await _send(chat_id, text, reply_markup)
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        log.info("[TG NOW edit %s] %s", message_id, text)
        return message_id
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return message_id
        # "message is not modified" is fine
        body = resp.text.lower()
        if "not modified" in body:
            return message_id
        log.warning("TG edit failed (%s) — sending new", resp.text[:160])
        return await _send(chat_id, text, reply_markup)


def _guest_keyboard(draft: dict[str, Any]) -> dict[str, Any]:
    selected = set(draft.get("guests") or [])
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for chip in draft.get("guest_chips") or wiz.GUEST_CHIPS:
        mark = "✓ " if chip["id"] in selected else ""
        label = f"{mark}{chip['label']}"
        if chip.get("host"):
            label = f"✓ {chip['label']} (host)"
        row.append({"text": label, "callback_data": f"now:guest:{chip['id']}"})
        if len(row) >= 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "Next → Restaurant", "callback_data": "now:guests_done"}])
    rows.append([{"text": "Cancel", "callback_data": "now:cancel"}])
    return {"inline_keyboard": rows}


def _venue_keyboard(draft: dict[str, Any]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    for i, v in enumerate((draft.get("venues") or [])[:6]):
        name = str(v.get("name") or "Venue")[:28]
        rid = str(v.get("restaurant_id") or i)
        rows.append([{"text": name, "callback_data": f"now:venue:{rid}"}])
    rows.append([{"text": "Cancel", "callback_data": "now:cancel"}])
    return {"inline_keyboard": rows}


def _slot_keyboard(draft: dict[str, Any]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for s in (draft.get("slots") or [])[:8]:
        label = str(s.get("label") or "")
        row.append({"text": label, "callback_data": f"now:slot:{label}"})
        if len(row) >= 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "Cancel", "callback_data": "now:cancel"}])
    return {"inline_keyboard": rows}


def _approve_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "✅ Approve · Calendar + book + split", "callback_data": "now:approve"}],
            [{"text": "Cancel", "callback_data": "now:cancel"}],
        ]
    }


def _guest_caption(draft: dict[str, Any]) -> str:
    chip_map = {c["id"]: c["label"] for c in (draft.get("guest_chips") or wiz.GUEST_CHIPS)}
    names = [chip_map.get(g, g.title()) for g in (draft.get("guests") or [])]
    return (
        "Night out · who is coming?\n"
        f"Selected: {', '.join(names)}\n"
        "Tap names to toggle, then Next."
    )


async def begin_night_out_wizard(chat_id: Any, *, hint: str | None = None) -> dict[str, Any]:
    draft = wiz.start_wizard(chat_id=str(chat_id))
    text = _guest_caption(draft)
    if hint:
        text = f"{hint}\n\n{text}"
    mid = await _send(chat_id, text, reply_markup=_guest_keyboard(draft))
    if mid:
        wiz.set_tg_message_id(draft["wizard_id"], mid)
    return draft


async def handle_night_out_callback(
    chat_id: Any,
    data: str,
    *,
    message_id: int | None = None,
) -> str:
    """Handle now:* callbacks. Edits the same Telegram message through the wizard."""
    parts = data.split(":")
    if len(parts) < 2:
        return "bad_cb"

    action = parts[1]
    draft_pub = wiz.wizard_for_chat(chat_id)

    async def _paint(text: str, markup: dict | None, wid: str | None = None) -> None:
        mid = message_id
        if wid:
            mid = wiz.get_tg_message_id(wid) or message_id
        new_mid = await _edit(chat_id, mid, text, markup)
        if wid and new_mid:
            wiz.set_tg_message_id(wid, new_mid)

    if action == "cancel":
        wid = (draft_pub or {}).get("wizard_id")
        wiz.clear_chat_wizard(chat_id)
        await _paint("Night out cancelled.", None, wid)
        return "cancelled"

    if action == "start":
        await begin_night_out_wizard(chat_id)
        return "started"

    if not draft_pub and action != "start":
        await _send(chat_id, "Night out expired — send /nightout to start again.")
        return "expired"

    wizard_id = str((draft_pub or {}).get("wizard_id") or "")
    if message_id:
        wiz.set_tg_message_id(wizard_id, message_id)

    try:
        if action == "guest" and len(parts) >= 3:
            draft = wiz.toggle_guest(wizard_id, parts[2])
            await _paint(_guest_caption(draft), _guest_keyboard(draft), wizard_id)
            return "guest_toggled"

        if action == "guests_done":
            wiz.set_guests(wizard_id, list((draft_pub or {}).get("guests") or []))
            venues = await wiz.search_venues(wizard_id, "Pune")
            await _paint(
                "Pick a restaurant (or type a name like '6 Digs' / 'Malaka'):",
                _venue_keyboard(venues),
                wizard_id,
            )
            return "venues"

        if action == "venue" and len(parts) >= 3:
            rid = parts[2]
            name = None
            for v in (draft_pub or {}).get("venues") or []:
                if str(v.get("restaurant_id")) == rid:
                    name = v.get("name")
                    break
            draft = await wiz.set_venue(wizard_id, restaurant_id=rid, name=name)
            await _paint(
                f"Slots at {draft.get('venue')}:",
                _slot_keyboard(draft),
                wizard_id,
            )
            return "slots"

        if action == "slot" and len(parts) >= 3:
            if len(parts) >= 4:
                label = f"{parts[2]}:{parts[3]}"
            else:
                label = parts[2]
            draft = wiz.set_slot(wizard_id, slot=label)
            await _paint(
                wiz.summary_text(draft) + "\n\nOne tap books the table and splits the bill.",
                _approve_keyboard(),
                wizard_id,
            )
            return "ready_approve"

        if action == "approve":
            # Single gate: stage Calendar + table, then auto-approve (book + split).
            await _paint("Staging Calendar + table…", None, wizard_id)
            result = await wiz.confirm_wizard(wizard_id, suppress_hitl_telegram=True)
            rid = result.get("approval_request_id")
            status = "STAGED"
            if rid:
                from app.services.hitl_decisions import process_decision

                decided = await process_decision(str(rid), True)
                status = str(decided.get("status") or "COMPLETED")
            text = (
                f"✅ Night out {status}\n"
                f"{result.get('venue')} · {result.get('slot') or ''} · "
                f"{result.get('guest_count')} guests\n"
                f"Calendar {'mock' if result.get('calendar_mock') else 'live'} · "
                f"table booked · bill split equal."
            )
            if rid:
                text += f"\n({rid})"
            await _paint(text, None, wizard_id)
            return "approved"

    except Exception as e:  # noqa: BLE001
        log.warning("Night out wizard cb failed: %s", e)
        await _paint(f"Wizard error: {e}", None, wizard_id or None)
        return "error"

    return "noop"


async def handle_venue_text(chat_id: Any, text: str) -> bool:
    """If user is on venue step and types a name, treat as venue search/pick."""
    draft = wiz.wizard_for_chat(chat_id)
    if not draft or draft.get("step") != "venue":
        return False
    q = text.strip()
    if not q or q.startswith("/"):
        return False
    wizard_id = draft["wizard_id"]
    mid = wiz.get_tg_message_id(wizard_id)
    try:
        venues = await wiz.search_venues(wizard_id, q)
        matches = venues.get("venues") or []
        if not matches:
            await _edit(chat_id, mid, f"No venues for '{q}'. Try another name.", _venue_keyboard(venues))
            return True
        if len(matches) == 1:
            v = matches[0]
            draft2 = await wiz.set_venue(
                wizard_id,
                restaurant_id=v.get("restaurant_id"),
                name=v.get("name"),
            )
            new_mid = await _edit(
                chat_id,
                mid,
                f"Slots at {draft2.get('venue')}:",
                _slot_keyboard(draft2),
            )
            if new_mid:
                wiz.set_tg_message_id(wizard_id, new_mid)
        else:
            new_mid = await _edit(
                chat_id,
                mid,
                f"Pick one for '{q}':",
                _venue_keyboard(venues),
            )
            if new_mid:
                wiz.set_tg_message_id(wizard_id, new_mid)
        return True
    except Exception as e:  # noqa: BLE001
        await _edit(chat_id, mid, f"Search failed: {e}", None)
        return True
