"""HITL FastAPI routes — Telegram webhook + local long-poll + REST approve/reject."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.db.store import list_approvals
from app.schemas import ApprovalBody
from app.services import qol_triggers
from app.services.hitl_decisions import HitlNotFoundError, process_decision

log = logging.getLogger(__name__)
router = APIRouter(tags=["hitl"])

_poll_task: asyncio.Task[None] | None = None


async def _process_decision(request_id: str, approved: bool) -> dict[str, Any]:
    """Router wrapper — maps HitlNotFoundError to HTTP 404."""
    try:
        return await process_decision(request_id, approved)
    except HitlNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def _html_result(title: str, body: str, ok: bool) -> HTMLResponse:
    color = "#059669" if ok else "#b91c1c"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
    <style>body{{font-family:system-ui;max-width:28rem;margin:3rem auto;padding:1.5rem;
    border:2px solid #000;border-radius:8px}} h1{{color:{color};font-size:1.25rem}}
    p{{color:#334155;line-height:1.5}}</style></head>
    <body><h1>{title}</h1><p>{body}</p>
    <p style="font-size:12px;color:#64748b">You can close this tab and return to Concierge Ops.</p>
    </body></html>"""
    return HTMLResponse(html)


@router.post("/api/hitl/approve/{request_id}")
async def approve(request_id: str, body: ApprovalBody | None = None) -> dict[str, Any]:
    approved = True if body is None else body.approved
    return await _process_decision(request_id, approved)


@router.get("/api/hitl/approve/{request_id}")
async def approve_get(request_id: str) -> HTMLResponse:
    """Browser / Telegram URL-button friendly approve."""
    try:
        result = await _process_decision(request_id, True)
        status = result.get("status", "COMPLETED")
        return _html_result(
            f"✅ {status}",
            f"Request <code>{request_id}</code> approved. Write tools (checkout / book_table) have run on the mock MCP.",
            True,
        )
    except HTTPException as e:
        return _html_result("❌ Failed", str(e.detail), False)


@router.post("/api/hitl/reject/{request_id}")
async def reject(request_id: str) -> dict[str, Any]:
    return await _process_decision(request_id, False)


@router.get("/api/hitl/reject/{request_id}")
async def reject_get(request_id: str) -> HTMLResponse:
    try:
        result = await _process_decision(request_id, False)
        return _html_result(
            f"🚫 {result.get('status', 'REJECTED')}",
            f"Request <code>{request_id}</code> rejected. No orders were placed.",
            False,
        )
    except HTTPException as e:
        return _html_result("❌ Failed", str(e.detail), False)


@router.get("/api/hitl/approvals")
def approvals(status: str | None = "PENDING") -> dict[str, Any]:
    return {"items": list_approvals(status=status)}


async def process_telegram_update(data: dict[str, Any]) -> dict[str, str]:
    """Shared handler for webhook + long-poll updates."""
    message = data.get("message") or {}
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")

    if text.startswith("/guests"):
        parts = text.split()
        count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 6
        await qol_triggers.guest_sos(count)
        await _telegram_reply(chat_id, f"Guest SOS staged for {count} people — check approvals.")
        return {"ok": "guests"}
    if text.startswith("/fuel"):
        qol_triggers.force_fuel_guard(True)
        await qol_triggers.check_fuel_guard()
        await _telegram_reply(chat_id, "Fuel guard checked — approval may be pending.")
        return {"ok": "fuel"}
    if text.startswith("/start") or text.startswith("/help"):
        from app.services.llm import active_provider_label

        await _telegram_reply(
            chat_id,
            "Swiggy Nexus concierge.\n"
            "Just talk to me normally — 'order paneer biryani', 'book a table for 4 "
            "tonight', 'get milk and bread'. Voice notes work too.\n"
            "Night out: say it in plain English (or voice) — e.g. "
            "'Plan a night out with friends this Saturday — dinner then drinks, "
            "then split the bill' — or /nightout for the guided wizard.\n"
            "I stage everything and wait for your Approve tap before spending.\n"
            f"Brain: {active_provider_label()}\n"
            "Commands: /nightout · /status · /guests 6 · /fuel · /approve REQ-… · /reject REQ-…",
        )
        return {"ok": "help"}
    if text.startswith("/nightout") or text.startswith("/night_out"):
        from app.services.telegram_night_out import begin_night_out_wizard

        await begin_night_out_wizard(chat_id)
        return {"ok": "nightout"}
    if text.startswith("/status"):
        pending = list_approvals("PENDING")
        await _telegram_reply(
            chat_id,
            f"Pending approvals: {len(pending)}\n"
            + (
                "\n".join(f"- {p['request_id']}: {p['title']}" for p in pending[:10])
                or "(none)"
            ),
        )
        return {"ok": "status"}
    if text.startswith("/approve"):
        parts = text.split()
        if len(parts) > 1:
            result = await _process_decision(parts[1], True)
            await _telegram_reply(chat_id, f"✅ {parts[1]} → {result.get('status')}")
        return {"ok": "approve"}
    if text.startswith("/reject"):
        parts = text.split()
        if len(parts) > 1:
            result = await _process_decision(parts[1], False)
            await _telegram_reply(chat_id, f"🚫 {parts[1]} → {result.get('status')}")
        return {"ok": "reject"}

    # Voice note → transcript → same agent loop.
    voice = message.get("voice") or message.get("audio") or {}
    if voice.get("file_id") and chat_id:
        from app.services.telegram_agent import run_telegram_agent
        from app.services.voice import transcribe_telegram_voice

        transcript = await transcribe_telegram_voice(voice["file_id"])
        if not transcript:
            await _telegram_reply(
                chat_id, "Couldn't transcribe that voice note — try again or type it."
            )
            return {"ok": "voice_failed"}
        await _telegram_reply(chat_id, f'🎙 "{transcript}"')
        await run_telegram_agent(chat_id, transcript, source="voice")
        return {"ok": "voice"}

    # Night-out wizard venue typing (before free-form agent)
    if text and chat_id and not text.startswith("/"):
        from app.services.telegram_night_out import handle_venue_text

        if await handle_venue_text(chat_id, text):
            return {"ok": "nightout_venue_text"}

    # Anything else that is not a slash command goes to the LLM agent.
    if text and chat_id and not text.startswith("/"):
        from app.services.telegram_agent import run_telegram_agent

        await run_telegram_agent(chat_id, text)
        return {"ok": "agent"}

    cq = data.get("callback_query") or {}
    cb = cq.get("data") or ""
    cq_id = cq.get("id")
    cq_msg = cq.get("message") or {}
    cq_chat = (cq_msg.get("chat") or {}).get("id")
    cq_mid = cq_msg.get("message_id")

    if cb.startswith("approve:"):
        rid = cb.split(":", 1)[1]
        result = await _process_decision(rid, True)
        status = result.get("status", "COMPLETED")
        if cq_id:
            await _answer_callback(cq_id, f"Approved · {status}")
        await _edit_telegram_message(
            cq_chat,
            cq_mid,
            f"✅ *APPROVED* `{rid}`\nStatus: `{status}`\nMock MCP writes executed.",
        )
        return {"ok": "approve_cb"}
    if cb.startswith("reject:"):
        rid = cb.split(":", 1)[1]
        result = await _process_decision(rid, False)
        status = result.get("status", "REJECTED")
        if cq_id:
            await _answer_callback(cq_id, f"Rejected · {status}")
        await _edit_telegram_message(
            cq_chat,
            cq_mid,
            f"🚫 *REJECTED* `{rid}`\nStatus: `{status}`\nNo orders placed.",
        )
        return {"ok": "reject_cb"}

    if cq_id:
        await _answer_callback(cq_id)

    if cb.startswith("now:"):
        from app.services.telegram_night_out import handle_night_out_callback

        await handle_night_out_callback(
            cq_chat,
            cb,
            message_id=int(cq_mid) if cq_mid is not None else None,
        )
        return {"ok": "nightout_cb"}

    if cb.startswith("qol:rooftop:"):
        await qol_triggers.handle_rooftop_choice(cb.split(":")[-1])
    elif cb.startswith("qol:bhajiya:"):
        await qol_triggers.handle_bhajiya_choice(cb.split(":")[-1])
    elif cb.startswith("qol:fuel:"):
        await qol_triggers.handle_fuel_choice(cb.split(":")[-1])
    elif cb.startswith("qol:ipl:"):
        await qol_triggers.handle_ipl_choice(cb.split(":")[-1])

    return {"ok": "true"}


@router.post("/api/hitl/telegram/webhook")
async def telegram_webhook(request: Request) -> dict[str, str]:
    data = await request.json()
    return await process_telegram_update(data)


async def _answer_callback(callback_query_id: str, text: str | None = None) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = False
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json=payload)


async def _edit_telegram_message(chat_id: Any, message_id: Any, text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id or not message_id:
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            url,
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": []},
            },
        )


async def _telegram_reply(chat_id: Any, text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        print(text)
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})


def _is_local_base() -> bool:
    base = settings.BASE_URL.rstrip("/")
    return "localhost" in base or "127.0.0.1" in base


async def register_telegram_webhook() -> None:
    """Register webhook when public; otherwise start long-polling for local demos."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    if _is_local_base():
        # Drop pending updates so a prior chat / leftover voice note does not
        # suddenly fire "Thinking…" / Approve mid Beat-1 (browser-only WOW).
        log.info("Local BASE_URL — starting Telegram long-poll (callbacks work without ngrok)")
        await _delete_webhook(drop_pending=True)
        start_telegram_poller()
        return

    hook = f"{settings.BASE_URL.rstrip('/')}/api/hitl/telegram/webhook"
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={"url": hook})
        log.info("Telegram webhook register: %s %s", resp.status_code, resp.text[:200])


async def _delete_webhook(*, drop_pending: bool = False) -> None:
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook"
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(url, json={"drop_pending_updates": drop_pending})


async def _poll_loop() -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    log.info("Telegram long-poll started")
    while True:
        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                resp = await client.get(
                    url,
                    params={"offset": offset, "timeout": 25, "allowed_updates": '["message","callback_query"]'},
                )
                data = resp.json()
            if not data.get("ok"):
                log.warning("Telegram getUpdates not ok: %s", data)
                await asyncio.sleep(3)
                continue
            for upd in data.get("result") or []:
                offset = int(upd["update_id"]) + 1
                try:
                    await process_telegram_update(upd)
                except Exception as e:  # noqa: BLE001
                    log.exception("Telegram update failed: %s", e)
        except asyncio.CancelledError:
            log.info("Telegram long-poll stopped")
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram poll error: %s", e)
            await asyncio.sleep(3)


def start_telegram_poller() -> None:
    global _poll_task
    if _poll_task and not _poll_task.done():
        return
    _poll_task = asyncio.create_task(_poll_loop(), name="telegram-long-poll")


async def stop_telegram_poller() -> None:
    global _poll_task
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    _poll_task = None
