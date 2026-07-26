"""HITL FastAPI routes — Telegram webhook + local long-poll + REST approve/reject."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.db.store import decide_approval, get_approval, list_approvals, record_qol_event
from app.graph.workflow import concierge_graph
from app.schemas import ApprovalBody
from app.services import qol_triggers

log = logging.getLogger(__name__)
router = APIRouter(tags=["hitl"])

_poll_task: asyncio.Task[None] | None = None


async def _resume_graph(thread_id: str, approved: bool, approval: dict[str, Any]) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        await concierge_graph.aupdate_state(
            config,
            {"approval_status": "APPROVED" if approved else "REJECTED"},
        )
        final = await concierge_graph.ainvoke(None, config=config)
        return final or {}
    except Exception as e:  # noqa: BLE001
        log.warning("Graph resume failed for %s: %s — fallback staged execution", thread_id, e)
        if not approved:
            return {"approval_status": "REJECTED"}
        result = await qol_triggers.execute_staged_approval(approval)
        return {"approval_status": "APPROVED", "fallback_execution": result}


async def _process_decision(request_id: str, approved: bool) -> dict[str, Any]:
    approval = get_approval(request_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Unknown approval '{request_id}'")
    if approval["status"] != "PENDING":
        return {"status": approval["status"], "approval": approval, "note": "already decided"}

    updated = decide_approval(request_id, approved)
    trigger = (updated or approval).get("trigger_type") or "calendar_concierge"

    if trigger == "calendar_concierge":
        final = await _resume_graph(approval["thread_id"], approved, updated or approval)
        record_qol_event(
            kind="hitl_approved" if approved else "hitl_rejected",
            title=f"{'Approved' if approved else 'Rejected'} · {request_id}",
            detail=trigger,
            severity="info",
            event_id=approval["event_id"],
        )
        return {
            "status": "COMPLETED" if approved else "REJECTED",
            "approval": updated,
            "final_state": final,
        }

    if not approved:
        record_qol_event(
            kind="hitl_rejected",
            title=f"Rejected · {request_id}",
            detail=trigger,
            severity="warn",
        )
        return {"status": "REJECTED", "approval": updated}

    result = await qol_triggers.execute_staged_approval(updated or approval)
    record_qol_event(
        kind="hitl_approved",
        title=f"Approved · {request_id}",
        detail=trigger,
        severity="info",
        meta=result,
    )
    return {"status": "COMPLETED", "approval": updated, "execution": result}


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
    if text.startswith("/start") or text.lower() in {"hi", "hello", "/help"}:
        await _telegram_reply(
            chat_id,
            "Nexus Concierge HITL bot.\n"
            "You'll get Approve/Reject when a flow pauses.\n"
            "Commands: /status · /guests 6 · /fuel · /approve REQ-… · /reject REQ-…",
        )
        return {"ok": "help"}
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
        log.info("Local BASE_URL — starting Telegram long-poll (callbacks work without ngrok)")
        await _delete_webhook()
        start_telegram_poller()
        return

    hook = f"{settings.BASE_URL.rstrip('/')}/api/hitl/telegram/webhook"
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={"url": hook})
        log.info("Telegram webhook register: %s %s", resp.status_code, resp.text[:200])


async def _delete_webhook() -> None:
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook"
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(url, json={"drop_pending_updates": False})


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
