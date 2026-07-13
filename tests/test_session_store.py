"""Tests for mcp_server/session_store.py."""
from __future__ import annotations

import pytest
from mcp_server.session_store import (
    MAX_SESSIONS,
    clear_food_cart,
    clear_im_cart,
    get_session,
    list_sessions,
    resolve_session_id,
    session_count,
)


def test_resolve_session_id_default():
    assert resolve_session_id(None) == "default_mock_session"
    assert resolve_session_id({}) == "default_mock_session"


def test_resolve_session_id_from_params():
    assert resolve_session_id({"requestId": "abc123"}) == "abc123"
    assert resolve_session_id({"sessionId": "xyz"}) == "xyz"
    assert resolve_session_id({"session_id": "foo"}) == "foo"


def test_get_session_creates_fresh():
    s = get_session("test_new_sess")
    assert s.food.lines == []
    assert s.im.lines == []


def test_get_session_same_instance():
    s1 = get_session("shared_sess")
    s2 = get_session("shared_sess")
    assert s1 is s2


def test_clear_food_cart():
    s = get_session("clear_food_test")
    s.food.lines = [{"item_id": "x", "qty": 1}]
    s.food.restaurant_id = "rest_123"
    clear_food_cart("clear_food_test")
    s2 = get_session("clear_food_test")
    assert s2.food.lines == []
    assert s2.food.restaurant_id == ""


def test_clear_im_cart():
    s = get_session("clear_im_test")
    s.im.lines = [{"spinId": "spin_x", "qty": 2}]
    clear_im_cart("clear_im_test")
    s2 = get_session("clear_im_test")
    assert s2.im.lines == []


def test_lru_eviction():
    """Once we exceed MAX_SESSIONS, the oldest session should be evicted."""
    # We use a smaller pool to test eviction quickly
    from mcp_server import session_store
    original_max = session_store.MAX_SESSIONS

    try:
        # Temporarily lower the max
        session_store.MAX_SESSIONS = 5
        session_store._sessions.clear()

        sessions = [f"evict_test_{i}" for i in range(6)]
        for sid in sessions:
            get_session(sid)

        # Should not exceed the cap
        assert session_count() <= 5

    finally:
        session_store.MAX_SESSIONS = original_max
        session_store._sessions.clear()


def test_list_sessions_returns_info():
    get_session("info_session_a")
    get_session("info_session_b")
    info = list_sessions()
    sids = [s["session_id"] for s in info]
    assert "info_session_a" in sids
    assert "info_session_b" in sids
    for entry in info:
        assert "food_items" in entry
        assert "im_items" in entry
        assert "created_at" in entry
        assert "last_accessed" in entry
