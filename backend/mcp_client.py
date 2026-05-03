"""Call local mock MCP (/food, /im, /dineout).

Default: **in-process** `invoke_vertical` — avoids deadlock when `/api/chat/stream` and MCP
live on one uvicorn worker.

Set ``LOCAL_MCP_HTTP=1`` to POST JSON to ``LOCAL_MCP_BASE`` (default ``http://127.0.0.1:8000``).
With HTTP mode run **multiple workers**, e.g. ``uvicorn ... --workers 2``, or nested calls stall.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

import httpx

from mcp_server.facade import invoke_vertical

Vertical = Literal["food", "im", "dineout"]

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="local_mcp_http")


def _client_tool_log(method: str, params: dict[str, Any], summary: str, path: str) -> None:
    print(f"[TOOL CALL] {method}")
    print(f"[ARGS] {json.dumps(params, default=str, ensure_ascii=False)}")
    print(f"[RESPONSE] {summary} [{path}]")


class LocalMCPError(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(json.dumps(payload))


def call_tool(server: Vertical, method: str, params: dict[str, Any]) -> Any:
    """Execute one mock tool call; raises LocalMCPError on logical failure."""

    base = os.environ.get("LOCAL_MCP_BASE", "http://127.0.0.1:8000").rstrip("/")
    path_seg = {"food": "food", "im": "im", "dineout": "dineout"}[server]

    http_mode = os.environ.get("LOCAL_MCP_HTTP", "0").strip().lower() in ("1", "true", "yes")

    def _summarize(envelope: dict[str, Any]) -> str:
        if envelope.get("success"):
            d = envelope.get("data")
            if isinstance(d, dict) and "restaurants" in d:
                return f"{len(d['restaurants'])} restaurants returned"
            if isinstance(d, dict) and "addresses" in d:
                return f"{len(d['addresses'])} addresses returned"
            if isinstance(d, dict) and "order_id" in d:
                return f"order placed {d.get('order_id')}"
            if isinstance(d, dict) and "booking_id" in d:
                return f"booking {d.get('booking_id')}"
            if isinstance(d, dict) and "products" in d:
                return f"{len(d['products'])} products"
            if isinstance(d, dict) and "cart_id" in d:
                return "cart updated"
            if isinstance(d, dict) and "categories" in d:
                return "menu loaded"
            if isinstance(d, dict) and "slots" in d:
                return f"{len(d['slots'])} slots"
            return "ok"
        err = envelope.get("error") or {}
        return f"error: {err.get('message', err)}"

    if http_mode:

        def _post() -> dict[str, Any]:
            url = f"{base}/{path_seg}"
            body = {"method": method, "params": params}
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, json=body)
                r.raise_for_status()
                return r.json()

        envelope = _executor.submit(_post).result(timeout=120.0)
    else:
        envelope = invoke_vertical(server, method, params)

    summary = _summarize(envelope)
    path_label = "inproc" if not http_mode else f"POST /{path_seg}"
    _client_tool_log(method, params, summary, path_label)

    if envelope.get("success"):
        return envelope["data"]

    err = envelope.get("error") or {"code": "UNKNOWN", "message": "failure"}
    raise LocalMCPError(err if isinstance(err, dict) else {"message": str(err)})


def unwrap_dict(data: Any) -> dict[str, Any]:
    return data if isinstance(data, dict) else {}
