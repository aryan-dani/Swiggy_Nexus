"""FastAPI entry: health, CORS, request-ID middleware, chat + SSE streaming."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# Allow `uvicorn main:app` from backend/ as well as `uvicorn backend.main:app` from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# Load environment variables from backend/.env file (if present)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path)

from backend.logging_config import (
    configure_logging,
    get_logger,
    install_request_id_filter,
    set_request_id,
)
from backend.llm_orchestrator import run_llm_agent as run_agent_stream
from backend.tool_schemas import get_tool_names
from mcp_server.http_routes import router as mock_mcp_router
from app.api.webhooks import router as concierge_router
from backend.sidebar_demo import (
    analytics_snapshot,
    archive_list,
    dev_mode_toggle,
    library_pins,
    pro_pitch,
    record_new_chat,
)

# Initialise logging before anything else
configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
install_request_id_filter()
log = get_logger(__name__)

_START_TIME = time.time()

DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
DEFAULT_ORIGIN_REGEX = r"https://.*\.(onrender|vercel)\.app"


def _parse_origins() -> list[str]:
    raw = os.environ.get("FRONTEND_ORIGIN") or os.environ.get("CORS_ORIGINS") or DEFAULT_ORIGINS
    return [o.strip() for o in raw.split(",") if o.strip()]


def _parse_origin_regex() -> str | None:
    raw = os.environ.get("CORS_ORIGIN_REGEX", "").strip()
    if raw:
        return raw
    if os.environ.get("RENDER") == "true":
        return DEFAULT_ORIGIN_REGEX
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        from app.services.scheduler import start_scheduler
        from app.api.hitl import register_telegram_webhook, stop_telegram_poller

        start_scheduler()
        await register_telegram_webhook()
    except Exception as e:  # noqa: BLE001
        log.warning("Concierge startup hooks failed: %s", e)
    yield
    try:
        from app.api.hitl import stop_telegram_poller

        await stop_telegram_poller()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(title="Swiggy Nexus API", version="0.3.0", lifespan=lifespan)

app.include_router(mock_mcp_router)
app.include_router(concierge_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(),
    allow_origin_regex=_parse_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    set_request_id(rid)
    log.info(
        "Request started",
        extra={"method": request.method, "path": request.url.path, "request_id": rid},
    )
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    log.info(
        "Request finished",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "request_id": rid,
        },
    )
    return response


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    context: dict[str, Any] | None = None


class DevModeBody(BaseModel):
    enabled: bool = False


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "swiggy-nexus-backend",
        "version": "0.3.0",
        "groq_configured": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "concierge": True,
        "use_mock_mcp": os.environ.get("USE_MOCK_MCP", "true"),
    }


@app.get("/health/concierge")
def health_concierge() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "indian-qol-concierge",
        "version": "0.3.0",
        "use_mock_mcp": os.environ.get("USE_MOCK_MCP", "true"),
        "notification_platform": os.environ.get("NOTIFICATION_PLATFORM", "console"),
        "groq_configured": bool(os.environ.get("GROQ_API_KEY", "").strip()),
    }


@app.get("/api/health/detailed")
def health_detailed() -> dict[str, Any]:
    """Extended health check with uptime, tool coverage, and env info."""
    uptime_s = int(time.time() - _START_TIME)
    tool_names = get_tool_names()
    return {
        "status": "ok",
        "service": "swiggy-nexus-backend",
        "version": "0.3.0",
        "uptime_seconds": uptime_s,
        "groq_configured": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "groq_model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "tool_count": len(tool_names),
        "tools": tool_names,
        "verticals": ["food", "im", "dineout"],
        "concierge": True,
    }


# ---------------------------------------------------------------------------
# Sidebar endpoints
# ---------------------------------------------------------------------------


@app.get("/api/sidebar/summary")
def sidebar_summary() -> dict[str, Any]:
    """One round-trip for shell boot — all dummy."""
    return {
        "analytics": analytics_snapshot(),
        "library": library_pins(),
        "archive_preview": archive_list()[:3],
    }


@app.post("/api/sidebar/new-chat")
def sidebar_new_chat() -> dict[str, Any]:
    row = record_new_chat()
    return {
        "ok": True,
        "message": "New chat registered on demo backend.",
        **row,
    }


@app.get("/api/sidebar/analytics")
def sidebar_analytics() -> dict[str, Any]:
    return analytics_snapshot()


@app.get("/api/sidebar/archive")
def sidebar_archive() -> dict[str, Any]:
    return {"items": archive_list()}


@app.get("/api/sidebar/library")
def sidebar_library() -> dict[str, Any]:
    return {"pins": library_pins()}


@app.get("/api/sidebar/pro")
def sidebar_pro() -> dict[str, Any]:
    return pro_pitch()


@app.post("/api/sidebar/dev-mode")
def sidebar_dev_mode(body: DevModeBody) -> dict[str, Any]:
    return dev_mode_toggle(body.model_dump())


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------


def _format_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@app.post("/api/chat/stream")
def chat_stream(body: ChatBody) -> StreamingResponse:
    """SSE stream of agent events (thinking, tool, feed, assistant, done)."""

    def generate() -> Any:
        try:
            for ev in run_agent_stream(body.message, body.context):
                yield _format_sse(ev)
        except Exception as e:  # noqa: BLE001
            log.error("Chat stream error", extra={"error": str(e)})
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
def chat_sync(body: ChatBody) -> dict[str, Any]:
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
