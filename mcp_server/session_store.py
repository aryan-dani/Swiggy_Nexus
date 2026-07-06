"""Server-side session carts for mock MCP (multi-turn state)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_DEFAULT_SESSION = "default_mock_session"


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


_sessions: dict[str, SessionState] = {}


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
    if sid not in _sessions:
        _sessions[sid] = SessionState()
    return _sessions[sid]


def clear_food_cart(session_id: str) -> None:
    s = get_session(session_id)
    s.food = FoodCart()


def clear_im_cart(session_id: str) -> None:
    s = get_session(session_id)
    s.im = ImCart()
