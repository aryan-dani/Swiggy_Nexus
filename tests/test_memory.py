"""Tests for backend/memory.py — preferences and conversation history."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import pytest


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    """Redirect the memory module to a throwaway DB for each test."""
    db_path = str(tmp_path / "test_nexus.db")
    import backend.memory as mem
    monkeypatch.setattr(mem, "DB_PATH", db_path)
    mem.init_db()
    yield db_path


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------

def test_set_and_get_preference():
    from backend.memory import get_user_preferences, set_user_preference
    set_user_preference("cuisine", "Thai")
    prefs = get_user_preferences()
    assert prefs["cuisine"] == "Thai"


def test_preference_overwrite():
    from backend.memory import get_user_preferences, set_user_preference
    set_user_preference("cuisine", "Italian")
    set_user_preference("cuisine", "Mexican")
    prefs = get_user_preferences()
    assert prefs["cuisine"] == "Mexican"


def test_preference_json_roundtrip():
    from backend.memory import get_user_preferences, set_user_preference
    set_user_preference("diet", ["veg", "gluten-free"])
    prefs = get_user_preferences()
    assert prefs["diet"] == ["veg", "gluten-free"]


def test_preference_dict_value():
    from backend.memory import get_user_preferences, set_user_preference
    set_user_preference("config", {"max_eta": 30})
    prefs = get_user_preferences()
    assert prefs["config"]["max_eta"] == 30


def test_get_preferences_empty_db():
    """New DB should return empty dict."""
    from backend.memory import get_user_preferences
    prefs = get_user_preferences()
    assert isinstance(prefs, dict)


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

def test_save_and_retrieve_history():
    from backend.memory import get_conversation_history, save_turn
    save_turn("session_1", "user", "What's for dinner?")
    save_turn("session_1", "assistant", "Here are some options…")
    history = get_conversation_history("session_1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_history_is_session_scoped():
    from backend.memory import get_conversation_history, save_turn
    save_turn("session_a", "user", "Hello from A")
    save_turn("session_b", "user", "Hello from B")
    hist_a = get_conversation_history("session_a")
    hist_b = get_conversation_history("session_b")
    assert len(hist_a) == 1
    assert hist_a[0]["content"] == "Hello from A"
    assert len(hist_b) == 1
    assert hist_b[0]["content"] == "Hello from B"


def test_history_respects_limit():
    from backend.memory import get_conversation_history, save_turn
    for i in range(25):
        save_turn("sid", "user", f"message {i}")
    history = get_conversation_history("sid", limit=10)
    assert len(history) == 10


def test_history_oldest_first():
    from backend.memory import get_conversation_history, save_turn
    save_turn("sid2", "user", "first")
    save_turn("sid2", "user", "second")
    history = get_conversation_history("sid2")
    assert history[0]["content"] == "first"
    assert history[1]["content"] == "second"


def test_clear_conversation_history():
    from backend.memory import clear_conversation_history, get_conversation_history, save_turn
    save_turn("session_x", "user", "remember me?")
    clear_conversation_history("session_x")
    history = get_conversation_history("session_x")
    assert history == []


def test_clear_only_affects_target_session():
    from backend.memory import clear_conversation_history, get_conversation_history, save_turn
    save_turn("session_keep", "user", "keep this")
    save_turn("session_del", "user", "delete this")
    clear_conversation_history("session_del")
    assert get_conversation_history("session_keep")[0]["content"] == "keep this"
    assert get_conversation_history("session_del") == []


def test_list_sessions():
    from backend.memory import list_sessions, save_turn
    save_turn("alpha", "user", "test")
    save_turn("beta", "assistant", "reply")
    sessions = list_sessions()
    assert "alpha" in sessions
    assert "beta" in sessions


def test_content_cap_at_8000_chars():
    from backend.memory import get_conversation_history, save_turn
    long_content = "x" * 10000
    save_turn("session_long", "user", long_content)
    history = get_conversation_history("session_long")
    assert len(history[0]["content"]) <= 8000


def test_empty_session_history():
    from backend.memory import get_conversation_history
    history = get_conversation_history("nonexistent_session")
    assert history == []
