"""HITL approve/reject decisions — shared by REST routes and Telegram wizard.

Kept out of FastAPI routers so Telegram night-out can approve without importing
the API module (avoids circular imports).
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.store import decide_approval, get_approval, record_qol_event
from app.graph.workflow import concierge_graph
from app.services import qol_triggers

log = logging.getLogger(__name__)


class HitlNotFoundError(LookupError):
    """Unknown approval request id."""


async def resume_graph(thread_id: str, approved: bool, approval: dict[str, Any]) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snap = await concierge_graph.aget_state(config)
        # Only resume when LangGraph is actually paused after hitl_notify
        # (`next` lists the pending nodes). Empty `values` / empty `next` means
        # MemorySaver has no interrupt — ainvoke(None) would RESTART the graph
        # from entry and mint a fresh HITL (Baoli / Concierge spam).
        next_nodes = tuple(getattr(snap, "next", None) or ()) if snap else ()
        if not next_nodes:
            log.warning(
                "No resumable interrupt for thread %s (next=%s) — skip ainvoke",
                thread_id,
                next_nodes,
            )
            if not approved:
                return {"approval_status": "REJECTED", "resume": "no_interrupt"}
            result = await qol_triggers.execute_staged_approval(approval)
            return {
                "approval_status": "APPROVED",
                "fallback_execution": result,
                "resume": "no_interrupt",
            }

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


async def process_decision(request_id: str, approved: bool) -> dict[str, Any]:
    approval = get_approval(request_id)
    if not approval:
        raise HitlNotFoundError(f"Unknown approval '{request_id}'")
    if approval["status"] != "PENDING":
        return {"status": approval["status"], "approval": approval, "note": "already decided"}

    updated = decide_approval(request_id, approved)
    trigger = (updated or approval).get("trigger_type") or "calendar_concierge"

    if trigger in ("calendar_concierge", "night_out", "dinner_party"):
        final = await resume_graph(approval["thread_id"], approved, updated or approval)
        record_qol_event(
            kind="hitl_approved" if approved else "hitl_rejected",
            title=f"{'Approved' if approved else 'Rejected'} · {request_id}",
            detail=trigger,
            severity="info",
            event_id=approval["event_id"],
            meta={"trigger": trigger, "night_out_receipt": (final or {}).get("night_out_receipt")},
        )
        return {
            "status": "COMPLETED" if approved else "REJECTED",
            "approval": updated,
            "final_state": final,
            "receipt": (final or {}).get("night_out_receipt"),
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
