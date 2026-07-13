"""Route MCP-style method + params into the correct mock vertical.

Adds timing instrumentation and basic input validation.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from mcp_server.dineout.dispatcher import invoke as dineout_invoke
from mcp_server.food.dispatcher import invoke as food_invoke
from mcp_server.im.dispatcher import invoke as instamart_invoke

log = logging.getLogger(__name__)

Vertical = Literal["food", "im", "dineout"]

_VALID_VERTICALS: frozenset[str] = frozenset({"food", "im", "dineout"})


def invoke_vertical(
    vertical: Vertical, method: str | None, params: dict[str, Any] | None
) -> dict[str, Any]:
    # --- Input validation ---
    if vertical not in _VALID_VERTICALS:
        log.warning("Unknown vertical", extra={"vertical": vertical})
        return {
            "success": False,
            "error": {"code": "UNKNOWN_VERTICAL", "message": f"Unknown vertical: {vertical}"},
        }

    if not method or not isinstance(method, str):
        return {
            "success": False,
            "error": {"code": "VALIDATION", "message": "method is required and must be a string"},
        }

    if params is not None and not isinstance(params, dict):
        return {
            "success": False,
            "error": {"code": "VALIDATION", "message": "params must be a dict or null"},
        }

    # --- Dispatch with timing ---
    t0 = time.perf_counter()
    ok: bool
    data: Any
    err: dict[str, Any] | None

    try:
        if vertical == "food":
            ok, data, err = food_invoke(method, params)
        elif vertical == "im":
            ok, data, err = instamart_invoke(method, params)
        else:
            ok, data, err = dineout_invoke(method, params)
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        log.error(
            "Unhandled exception in dispatcher",
            extra={"vertical": vertical, "method": method, "elapsed_ms": elapsed_ms, "error": str(exc)},
        )
        return {
            "success": False,
            "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
        }

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    log.debug(
        "Tool dispatched",
        extra={"vertical": vertical, "method": method, "ok": ok, "elapsed_ms": elapsed_ms},
    )

    if ok:
        return {"success": True, "data": data, "_elapsed_ms": elapsed_ms}

    return {
        "success": False,
        "error": err or {"message": "Unknown error"},
        "_elapsed_ms": elapsed_ms,
    }