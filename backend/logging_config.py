"""Structured JSON logging for Swiggy Nexus.

Usage
-----
    from backend.logging_config import get_logger, configure_logging

    configure_logging()           # call once in main.py
    log = get_logger(__name__)
    log.info("request started", extra={"request_id": rid, "path": "/api/chat"})
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge any extra fields the caller passed via ``extra=``
        for key, val in record.__dict__.items():
            if key not in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "id",
                "levelname",
                "levelno",
                "lineno",
                "message",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            ):
                payload[key] = val

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

_configured = False


def configure_logging(level: str = "INFO", json_mode: bool = True) -> None:
    """Configure root logger — call once at process startup."""
    global _configured
    if _configured:
        return
    _configured = True

    handler = logging.StreamHandler(sys.stdout)
    if json_mode:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quieten noisy 3rd-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (configure_logging should be called first)."""
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Request ID context (thread-local)
# ---------------------------------------------------------------------------
import threading

_ctx = threading.local()


def set_request_id(rid: str) -> None:
    _ctx.request_id = rid


def get_request_id() -> str:
    return getattr(_ctx, "request_id", "-")


class RequestIdFilter(logging.Filter):
    """Inject ``request_id`` into every log record on this thread."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def install_request_id_filter() -> None:
    """Attach the filter to the root logger (safe to call multiple times)."""
    root = logging.getLogger()
    for h in root.handlers:
        if not any(isinstance(f, RequestIdFilter) for f in h.filters):
            h.addFilter(RequestIdFilter())
