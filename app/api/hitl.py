"""HITL FastAPI routes — Telegram webhook + REST approve/reject."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.db.store import decide_approval, get_approval, list_approvals, record_qol_event
from app.graph.workflow import concierge_graph
from app.schemas import ApprovalBody
from app.services import qol_triggers

log = logging.getLogger(__name__)
router = APIRouter(tags=["hitl"])


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
        # Fall back: run write tools from durable staged payload
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

    # QoL micro-triggers: execute staged payload directly
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


@router.post("/api/hitl/approve/{request_id}")
async def approve(request_id: str, body: ApprovalBody | None = None) -> dict[str, Any]:
    approved = True if body is None else body.approved
    return await _process_decision(request_id, approved)


@router.post("/api/hitl/reject/{request_id}")
async def reject(request_id: str) -> dict[str, Any]:
    return await _process_decision(request_id, False)


@router.get("/api/hitl/approvals")
def approvals(status: str | None = "PENDING") -> dict[str, Any]:
    return {"items": list_approvals(status=status)}


@router.post("/api/hitl/telegram/webhook")
async def telegram_webhook(request: Request) -> dict[str, str]:
    data = await request.json()
    # Commands
    message = data.get("message") or {}
    text = (message.get("text") or "").strip()
    if text.startswith("/guests"):
        parts = text.split()
        count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 6
        await qol_triggers.guest_sos(count)
        return {"ok": "guests"}
    if text.startswith("/fuel"):
        qol_triggers.force_fuel_guard(True)
        await qol_triggers.check_fuel_guard()
        return {"ok": "fuel"}
    if text.startswith("/status"):
        pending = list_approvals("PENDING")
        await _telegram_reply(
            message.get("chat", {}).get("id"),
            f"Pending approvals: {len(pending)}\n"
            + "\n".join(f"- {p['request_id']}: {p['title']}" for p in pending[:10]),
        )
        return {"ok": "status"}
    if text.startswith("/approve"):
        parts = text.split()
        if len(parts) > 1:
            await _process_decision(parts[1], True)
        return {"ok": "approve"}
    if text.startswith("/reject"):
        parts = text.split()
        if len(parts) > 1:
            await _process_decision(parts[1], False)
        return {"ok": "reject"}

    # Callback buttons
    cq = data.get("callback_query") or {}
    cb = cq.get("data") or ""
    cq_id = cq.get("id")
    if cq_id:
        await _answer_callback(cq_id)

    if cb.startswith("approve:"):
        await _process_decision(cb.split(":", 1)[1], True)
    elif cb.startswith("reject:"):
        await _process_decision(cb.split(":", 1)[1], False)
    elif cb.startswith("qol:rooftop:"):
        await qol_triggers.handle_rooftop_choice(cb.split(":")[-1])
    elif cb.startswith("qol:bhajiya:"):
        await qol_triggers.handle_bhajiya_choice(cb.split(":")[-1])
    elif cb.startswith("qol:fuel:"):
        await qol_triggers.handle_fuel_choice(cb.split(":")[-1])
    elif cb.startswith("qol:ipl:"):
        await qol_triggers.handle_ipl_choice(cb.split(":")[-1])

    return {"ok": "true"}


async def _answer_callback(callback_query_id: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json={"callback_query_id": callback_query_id})


async def _telegram_reply(chat_id: Any, text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        print(text)
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})


async def register_telegram_webhook() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    base = settings.BASE_URL.rstrip("/")
    if "localhost" in base or "127.0.0.1" in base:
        log.info("Skipping Telegram webhook register on localhost")
        return
    hook = f"{base}/api/hitl/telegram/webhook"
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={"url": hook})
        log.info("Telegram webhook register: %s %s", resp.status_code, resp.text[:200])
