"""Server-side session carts for mock MCP (multi-turn state).

Sessions are kept in an in-process dict with LRU eviction once the pool
exceeds MAX_SESSIONS, so the server doesn't leak memory indefinitely.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

_DEFAULT_SESSION = "default_mock_session"
MAX_SESSIONS = 200  # evict oldest when exceeded


@dataclass
class FoodCart:
    restaurant_id: str = ""
    restaurant_name: str = ""
    address_id: str = ""
    lines: list[dict[str, Any]] = field(default_factory=list)
    coupon_code: str | None = None
    coupon_discount_inr: int = 0


@dataclass
class ImCart:
    selected_address_id: str = ""
    lines: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SessionState:
    food: FoodCart = field(default_factory=FoodCart)
    im: ImCart = field(default_factory=ImCart)
    applied_coupon: str | None = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)


# Use an OrderedDict so we can do O(1) LRU eviction
_sessions: OrderedDict[str, SessionState] = OrderedDict()


def _evict_lru() -> None:
    """Remove the least-recently-used session if the pool is full."""
    while len(_sessions) >= MAX_SESSIONS:
        _sessions.popitem(last=False)  # FIFO = oldest first


def resolve_session_id(params: dict[str, Any] | None) -> str:
    if not params:
        return _DEFAULT_SESSION
    for key in ("requestId", "request_id", "sessionId", "session_id"):
        val = params.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return _DEFAULT_SESSION


def get_session(session_id: str | None = None, params: dict[str, Any] | None = None) -> SessionState:
    sid = session_id or resolve_session_id(params)
    if sid in _sessions:
        session = _sessions[sid]
        session.last_accessed = time.time()
        # Move to end (most recently used)
        _sessions.move_to_end(sid)
        return session
    # New session — evict if needed
    _evict_lru()
    state = SessionState()
    _sessions[sid] = state
    return state


def clear_food_cart(session_id: str) -> None:
    s = get_session(session_id)
    s.food = FoodCart()


def clear_im_cart(session_id: str) -> None:
    s = get_session(session_id)
    s.im = ImCart()


def list_sessions() -> list[dict[str, Any]]:
    """Return debug info for all active sessions."""
    return [
        {
            "session_id": sid,
            "food_items": len(s.food.lines),
            "im_items": len(s.im.lines),
            "created_at": s.created_at,
            "last_accessed": s.last_accessed,
        }
        for sid, s in _sessions.items()
    ]


def session_count() -> int:
    return len(_sessions)
