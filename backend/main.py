"""FastAPI entry: health, CORS, chat + SSE streaming."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent import run_agent_stream
from mcp_server.http_routes import router as mock_mcp_router
from backend.sidebar_demo import (
    analytics_snapshot,
    archive_list,
    dev_mode_toggle,
    library_pins,
    pro_pitch,
    record_new_chat,
)

DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _parse_origins() -> list[str]:
    raw = os.environ.get("FRONTEND_ORIGIN") or os.environ.get("CORS_ORIGINS") or DEFAULT_ORIGINS
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(title="Swiggy Nexus API", version="0.1.0")

app.include_router(mock_mcp_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    context: dict[str, Any] | None = None


class DevModeBody(BaseModel):
    enabled: bool = False


@app.get("/health")
def health():
    return {"status": "ok", "service": "swiggy-nexus-backend"}


@app.get("/api/sidebar/summary")
def sidebar_summary():
    """One round-trip for shell boot — all dummy."""
    return {
        "analytics": analytics_snapshot(),
        "library": library_pins(),
        "archive_preview": archive_list()[:3],
    }


@app.post("/api/sidebar/new-chat")
def sidebar_new_chat():
    row = record_new_chat()
    return {
        "ok": True,
        "message": "New chat registered on demo backend.",
        **row,
    }


@app.get("/api/sidebar/analytics")
def sidebar_analytics():
    return analytics_snapshot()


@app.get("/api/sidebar/archive")
def sidebar_archive():
    return {"items": archive_list()}


@app.get("/api/sidebar/library")
def sidebar_library():
    return {"pins": library_pins()}


@app.get("/api/sidebar/pro")
def sidebar_pro():
    return pro_pitch()


@app.post("/api/sidebar/dev-mode")
def sidebar_dev_mode(body: DevModeBody):
    return dev_mode_toggle(body.model_dump())


def _format_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@app.post("/api/chat/stream")
def chat_stream(body: ChatBody):
    """SSE stream of agent events (thinking, tool, feed, assistant, done)."""

    def generate():
        try:
            for ev in run_agent_stream(body.message, body.context):
                yield _format_sse(ev)
        except Exception as e:  # noqa: BLE001
            yield _format_sse({"type": "error", "payload": {"message": str(e)}})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
def chat_sync(body: ChatBody):
    """Non-streaming: collect final assistant reply and feed (for simple clients)."""
    assistant_reply = ""
    feed_items: list[dict[str, Any]] = []
    for ev in run_agent_stream(body.message, body.context):
        if ev["type"] == "assistant":
            assistant_reply = ev["payload"].get("text", "")
        if ev["type"] == "feed":
            feed_items = ev["payload"].get("items", [])
        if ev["type"] == "error":
            raise HTTPException(status_code=500, detail=ev["payload"])
        if ev["type"] == "done":
            assistant_reply = ev["payload"].get("assistant_reply") or assistant_reply
            feed_items = ev["payload"].get("feed_items") or feed_items

    return {
        "assistant_reply": assistant_reply,
        "feed_items": feed_items,
    }
