"""Standalone FastAPI entry for the Indian QoL Concierge."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.hitl import register_telegram_webhook, stop_telegram_poller
from app.api.webhooks import router as concierge_router
from app.config import settings
from app.services.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    await register_telegram_webhook()
    yield
    await stop_telegram_poller()


app = FastAPI(
    title="Indian QoL Concierge & Swiggy MCP Orchestrator",
    version="1.0.0",
    description="Calendar + weather + Taste Vault + LangGraph + Swiggy MCP",
    lifespan=lifespan,
)

DEFAULT_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
DEFAULT_ORIGIN_REGEX = r"https://.*\.(onrender|vercel)\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_ORIGINS,
    allow_origin_regex=DEFAULT_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(concierge_router)


@app.get("/health")
@app.get("/health/concierge")
def concierge_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "use_mock_mcp": str(settings.USE_MOCK_MCP),
        "notification_platform": settings.NOTIFICATION_PLATFORM,
    }
