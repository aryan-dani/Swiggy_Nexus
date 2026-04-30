"""In-memory dummy data + counters for sidebar / shell demo endpoints."""

from __future__ import annotations

import time
import uuid
from typing import Any

_session_counter = 0
_session_store: list[dict[str, Any]] = []


def reset_demo_state() -> None:
    global _session_counter, _session_store
    _session_counter = 0
    _session_store = []


def record_new_chat() -> dict[str, Any]:
    global _session_counter
    _session_counter += 1
    n = _session_counter
    entry = {
        "id": str(uuid.uuid4()),
        "label": f"Demo session #{n}",
        "created_at": time.time(),
    }
    _session_store.insert(0, entry)
    del _session_store[20:]
    return {"session_number": n, **entry}


def analytics_snapshot() -> dict[str, Any]:
    return {
        "sessions_started": _session_counter,
        "mock_tool_calls_24h": 127,
        "avg_latency_ms": 42,
        "top_intent": "food_delivery",
        "note": "Synthetic metrics — Builders Club demo only.",
    }


def archive_list() -> list[dict[str, Any]]:
    seeded = [
        {"id": "arch-1", "title": "Team lunch — Koramangala", "kind": "dineout"},
        {"id": "arch-2", "title": "Late-night snacks", "kind": "food"},
        {"id": "arch-3", "title": "Pantry restock", "kind": "instamart"},
    ]
    return _session_store[:5] + seeded


def library_pins() -> list[dict[str, Any]]:
    return [
        {"id": "pin-1", "title": "Saved: Biryani near MG Road", "type": "restaurant"},
        {"id": "pin-2", "title": "Instamart list: coffee + oats", "type": "instamart"},
    ]


def pro_pitch() -> dict[str, Any]:
    return {
        "headline": "Nexus Pro (demo)",
        "bullets": [
            "Higher mock rate limits",
            "Extra pretend dashboards",
            "Still $0 — this is a POC",
        ],
    }


def dev_mode_toggle(body: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(body.get("enabled"))
    return {"received": True, "dev_mode": enabled, "logged_at": time.time()}
