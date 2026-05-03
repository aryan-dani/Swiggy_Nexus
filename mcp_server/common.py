"""Shared helpers for local mock MCP handlers."""

from __future__ import annotations

import json
import random
import time
from typing import Any


def simulated_latency_jitter_ms() -> None:
    delay = random.uniform(0.3, 0.8)
    time.sleep(delay)


def tool_log(side: str, method: str, args: dict[str, Any], response_summary: str) -> None:
    """Structured console logs for demos (stderr-friendly)."""
    print(f"[TOOL CALL] [{side}] {method}")
    print(f"[ARGS] {json.dumps(args, default=str, ensure_ascii=False)}")
    print(f"[RESPONSE] {response_summary}")


def pick_eta(r: dict[str, Any]) -> int:
    lo = int(r.get("eta_mins_min", 28))
    hi = int(r.get("eta_mins_max", 40))
    return random.randint(lo, hi)


def get_param(params: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in params:
            return params[k]
    return None
