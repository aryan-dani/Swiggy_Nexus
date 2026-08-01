"""LangGraph supervisor — stage → notify → interrupt → execute → calendar."""

from __future__ import annotations

import logging
from typing import Any, Literal

import app  # noqa: F401 — installs langchain.debug shim before langgraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from app.graph.nodes import (
    ai_sommelier_node,
    calendar_mutate_node,
    cleanup_reject_node,
    execute_transactions_node,
    hitl_notify_node,
    parse_and_route_node,
    profile_attendees_node,
    schedule_legs_node,
    stage_dineout_node,
    stage_zero_touch_node,
)
from app.graph.state import ConciergeState

log = logging.getLogger(__name__)


def route_by_mode(state: ConciergeState) -> Literal["stage_dineout", "stage_zero_touch"]:
    if state.get("mode") == "DINEOUT":
        return "stage_dineout"
    return "stage_zero_touch"


def check_dineout_success(state: ConciergeState) -> Literal["ai_sommelier", "stage_zero_touch"]:
    if state.get("dineout_error"):
        return "stage_zero_touch"
    return "ai_sommelier"


def route_after_resume(state: ConciergeState) -> Literal["execute_transactions", "cleanup_reject"]:
    if state.get("approval_status") == "REJECTED":
        return "cleanup_reject"
    return "execute_transactions"


def _build_checkpointer() -> Any:
    """MemorySaver for the LangGraph interrupt (ainvoke is async).

    Do NOT use sync SqliteSaver here — it crashes ainvoke with
    \"SqliteSaver does not support async methods\". Approvals and staged
    payloads are already durable in the app SQLite store; the graph
    checkpoint only needs to survive for the life of the process (so run
    uvicorn without --reload during demos).

    LANGGRAPH_SQLITE=1 is accepted for backwards compatibility but maps to
    MemorySaver until AsyncSqliteSaver is reliable with the pinned aiosqlite.
    """
    import os

    if os.environ.get("LANGGRAPH_SQLITE", "").strip() in ("1", "true", "yes"):
        log.info(
            "LANGGRAPH_SQLITE requested — using MemorySaver (async-safe). "
            "Keep uvicorn without --reload so pending HITL interrupts survive."
        )
    return MemorySaver()


def create_concierge_workflow() -> Any:
    workflow = StateGraph(ConciergeState)

    workflow.add_node("profile_attendees", profile_attendees_node)
    workflow.add_node("parse_and_route", parse_and_route_node)
    workflow.add_node("stage_dineout", stage_dineout_node)
    workflow.add_node("stage_zero_touch", stage_zero_touch_node)
    workflow.add_node("ai_sommelier", ai_sommelier_node)
    workflow.add_node("hitl_notify", hitl_notify_node)
    workflow.add_node("execute_transactions", execute_transactions_node)
    workflow.add_node("cleanup_reject", cleanup_reject_node)
    workflow.add_node("schedule_legs", schedule_legs_node)
    workflow.add_node("calendar_mutate", calendar_mutate_node)

    workflow.set_entry_point("profile_attendees")
    workflow.add_edge("profile_attendees", "parse_and_route")
    workflow.add_conditional_edges(
        "parse_and_route",
        route_by_mode,
        {"stage_dineout": "stage_dineout", "stage_zero_touch": "stage_zero_touch"},
    )
    workflow.add_conditional_edges(
        "stage_dineout",
        check_dineout_success,
        {"ai_sommelier": "ai_sommelier", "stage_zero_touch": "stage_zero_touch"},
    )
    workflow.add_edge("stage_zero_touch", "ai_sommelier")
    workflow.add_edge("ai_sommelier", "hitl_notify")
    # Interrupt AFTER hitl_notify so the approval is persisted + Telegram sent
    workflow.add_conditional_edges(
        "hitl_notify",
        route_after_resume,
        {
            "execute_transactions": "execute_transactions",
            "cleanup_reject": "cleanup_reject",
        },
    )
    workflow.add_edge("execute_transactions", "schedule_legs")
    workflow.add_edge("schedule_legs", "calendar_mutate")
    workflow.add_edge("cleanup_reject", "calendar_mutate")
    workflow.add_edge("calendar_mutate", END)

    checkpointer = _build_checkpointer()
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["hitl_notify"],
    )


concierge_graph = create_concierge_workflow()
