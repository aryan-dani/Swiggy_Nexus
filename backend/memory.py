"""Persistent memory layer for Swiggy Nexus.

Tables
------
user_profile      — key/value preferences (dietary restrictions, favourite cuisine, etc.)
session_history   — multi-turn conversation turns per session_id
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

DB_PATH = os.path.join(os.path.dirname(__file__), "nexus_memory.db")


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_history_sid
            ON session_history (session_id, timestamp)
        """)


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------


def get_user_preferences() -> dict[str, Any]:
    preferences: dict[str, Any] = {}
    if not os.path.exists(DB_PATH):
        init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_profile")
        for k, v in cursor.fetchall():
            try:
                preferences[k] = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                preferences[k] = v
    return preferences


def set_user_preference(key: str, value: Any) -> None:
    if not os.path.exists(DB_PATH):
        init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )


# ---------------------------------------------------------------------------
# Conversation history (multi-turn)
# ---------------------------------------------------------------------------


def save_turn(session_id: str, role: str, content: str) -> None:
    """Persist a single conversation turn for multi-turn LLM context."""
    if not os.path.exists(DB_PATH):
        init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO session_history (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content[:8000]),  # cap content length
        )


def get_conversation_history(session_id: str, limit: int = 20) -> list[dict[str, str]]:
    """Return the most recent ``limit`` turns for a session, oldest first."""
    if not os.path.exists(DB_PATH):
        init_db()
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content, timestamp
            FROM session_history
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = cursor.fetchall()
    # Reverse so oldest turn is first
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]


def clear_conversation_history(session_id: str) -> None:
    """Delete all turns for a session (e.g. on new chat)."""
    if not os.path.exists(DB_PATH):
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM session_history WHERE session_id = ?", (session_id,))


def list_sessions() -> list[str]:
    """Return all known session IDs (for debug)."""
    if not os.path.exists(DB_PATH):
        return []
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT session_id FROM session_history ORDER BY session_id")
        return [row[0] for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# DB initialization on import (only if file doesn't exist)
# ---------------------------------------------------------------------------

if not os.path.exists(DB_PATH):
    init_db()
    set_user_preference("dietary_restrictions", "Vegetarian")
    set_user_preference("favorite_cuisine", "Italian")
else:
    # Ensure schema is up-to-date (idempotent)
    init_db()
