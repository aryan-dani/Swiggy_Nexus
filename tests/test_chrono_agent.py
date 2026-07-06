"""Chrono-Host agent stream test (in-process mock)."""
from __future__ import annotations

from backend.agent import run_agent_stream


def test_chrono_host_stream():
    events = list(
        run_agent_stream(
            "Plan my evening for 12 — dinner out and dessert at home",
            {"scenario": "chrono_host", "event": {"guests": 12, "cuisineHint": "italian", "title": "Housewarming"}},
        )
    )
    types = [e["type"] for e in events]
    assert "tool" in types
    assert types.count("tool") >= 8
    assert events[-1]["type"] == "done"
    reply = events[-1]["payload"].get("assistant_reply", "")
    assert "confirm" in reply.lower() or "staged" in reply.lower()
