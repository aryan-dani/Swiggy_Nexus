"""Durable SQLite stores for approvals, QoL timeline, idempotency, and watch channels."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

_DB_PATH = Path(settings.DATABASE_URL.replace("sqlite:///", "")).resolve()
if str(_DB_PATH).endswith("nexus_memory.db") is False and "sqlite" in settings.DATABASE_URL:
    _DB_PATH = Path("nexus_memory.db").resolve()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_durable_tables() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                trigger_type TEXT NOT NULL DEFAULT 'calendar_concierge',
                status TEXT NOT NULL DEFAULT 'PENDING',
                title TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                cost_breakdown_json TEXT DEFAULT '{}',
                staged_payload_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                decided_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);
            CREATE INDEX IF NOT EXISTS idx_approval_event ON approval_requests(event_id);

            CREATE TABLE IF NOT EXISTS qol_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT DEFAULT '',
                severity TEXT DEFAULT 'info',
                meta_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_qol_created ON qol_events(created_at DESC);

            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                note TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS watch_channels (
                channel_id TEXT PRIMARY KEY,
                resource_id TEXT,
                calendar_id TEXT,
                expires_at TEXT,
                token TEXT,
                meta_json TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS dish_histories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                dish_name TEXT NOT NULL,
                restaurant_name TEXT NOT NULL,
                rating INTEGER DEFAULT 5,
                vertical TEXT DEFAULT 'food',
                ordered_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS concierge_executions (
                event_id TEXT PRIMARY KEY,
                request_id TEXT,
                status TEXT,
                mode TEXT,
                state_json TEXT DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def create_approval(
    *,
    event_id: str,
    thread_id: str,
    trigger_type: str,
    title: str,
    summary: str,
    cost_breakdown: dict[str, Any],
    staged_payload: dict[str, Any],
    request_id: str | None = None,
) -> dict[str, Any]:
    rid = request_id or f"REQ-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "request_id": rid,
        "event_id": event_id,
        "thread_id": thread_id,
        "trigger_type": trigger_type,
        "status": "PENDING",
        "title": title,
        "summary": summary,
        "cost_breakdown": cost_breakdown,
        "staged_payload": staged_payload,
        "created_at": now,
        "decided_at": None,
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO approval_requests
            (request_id, event_id, thread_id, trigger_type, status, title, summary,
             cost_breakdown_json, staged_payload_json, created_at)
            VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?)
            """,
            (
                rid,
                event_id,
                thread_id,
                trigger_type,
                title,
                summary,
                json.dumps(cost_breakdown),
                json.dumps(staged_payload),
                now,
            ),
        )
        conn.commit()
    return row


def find_pending_approval(
    event_id: str,
    trigger_type: str | None = None,
) -> dict[str, Any] | None:
    """Newest PENDING approval for event_id, optionally scoped by trigger_type."""
    with _connect() as conn:
        if trigger_type:
            cur = conn.execute(
                """
                SELECT * FROM approval_requests
                WHERE event_id = ? AND status = 'PENDING' AND trigger_type = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (event_id, trigger_type),
            )
        else:
            cur = conn.execute(
                """
                SELECT * FROM approval_requests
                WHERE event_id = ? AND status = 'PENDING'
                ORDER BY created_at DESC LIMIT 1
                """,
                (event_id,),
            )
        row = cur.fetchone()
    return _approval_row(row) if row else None


def get_approval(request_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)
        )
        row = cur.fetchone()
    return _approval_row(row) if row else None


def list_approvals(status: str | None = "PENDING", limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        if status:
            cur = conn.execute(
                """
                SELECT * FROM approval_requests WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (status, limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM approval_requests ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
    return [_approval_row(r) for r in rows]


def decide_approval(request_id: str, approved: bool) -> dict[str, Any] | None:
    status = "APPROVED" if approved else "REJECTED"
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE approval_requests
            SET status = ?, decided_at = ?
            WHERE request_id = ? AND status = 'PENDING'
            """,
            (status, now, request_id),
        )
        conn.commit()
    return get_approval(request_id)


def _approval_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "request_id": row["request_id"],
        "event_id": row["event_id"],
        "thread_id": row["thread_id"],
        "trigger_type": row["trigger_type"],
        "status": row["status"],
        "title": row["title"],
        "summary": row["summary"],
        "cost_breakdown": json.loads(row["cost_breakdown_json"] or "{}"),
        "staged_payload": json.loads(row["staged_payload_json"] or "{}"),
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
    }


def record_qol_event(
    *,
    kind: str,
    title: str,
    detail: str = "",
    severity: str = "info",
    meta: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    eid = event_id or f"qol-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO qol_events (event_id, kind, title, detail, severity, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (eid, kind, title, detail, severity, json.dumps(meta or {}), now),
        )
        conn.commit()
    return {
        "event_id": eid,
        "kind": kind,
        "title": title,
        "detail": detail,
        "severity": severity,
        "meta": meta or {},
        "created_at": now,
    }


def list_qol_events(limit: int = 40) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT * FROM qol_events ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = cur.fetchall()
    return [
        {
            "event_id": r["event_id"],
            "kind": r["kind"],
            "title": r["title"],
            "detail": r["detail"],
            "severity": r["severity"],
            "meta": json.loads(r["meta_json"] or "{}"),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def claim_idempotency(key: str, note: str = "") -> bool:
    """Return True if this is the first time we see the key."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO idempotency_keys (key, created_at, note) VALUES (?, ?, ?)",
                (key, now, note),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def save_execution(event_id: str, payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO concierge_executions (event_id, request_id, status, mode, state_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                request_id=excluded.request_id,
                status=excluded.status,
                mode=excluded.mode,
                state_json=excluded.state_json,
                updated_at=excluded.updated_at
            """,
            (
                event_id,
                payload.get("request_id"),
                payload.get("status"),
                payload.get("mode"),
                json.dumps(payload.get("state") or payload),
                now,
            ),
        )
        conn.commit()


def get_execution(event_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT * FROM concierge_executions WHERE event_id = ?", (event_id,)
        )
        row = cur.fetchone()
    if not row:
        return None
    state = json.loads(row["state_json"] or "{}")
    return {
        "event_id": row["event_id"],
        "request_id": row["request_id"],
        "status": row["status"],
        "mode": row["mode"],
        "state": state,
        "updated_at": row["updated_at"],
    }


def record_dish_history(
    user_email: str,
    dish_name: str,
    restaurant_name: str,
    *,
    rating: int = 5,
    vertical: str = "food",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO dish_histories
            (user_email, dish_name, restaurant_name, rating, vertical, ordered_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_email, dish_name, restaurant_name, rating, vertical, now),
        )
        conn.commit()


def upsert_watch_channel(
    channel_id: str,
    *,
    resource_id: str | None = None,
    calendar_id: str | None = None,
    expires_at: str | None = None,
    token: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO watch_channels (channel_id, resource_id, calendar_id, expires_at, token, meta_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                resource_id=excluded.resource_id,
                calendar_id=excluded.calendar_id,
                expires_at=excluded.expires_at,
                token=excluded.token,
                meta_json=excluded.meta_json
            """,
            (
                channel_id,
                resource_id,
                calendar_id,
                expires_at,
                token,
                json.dumps(meta or {}),
            ),
        )
        conn.commit()


def reset_demo_state() -> dict[str, Any]:
    """Clear everything a recording take can dirty: approvals, timeline, idempotency
    keys, execution snapshots, MCP carts, and Telegram chat history."""
    init_durable_tables()
    cleared: dict[str, Any] = {}
    with _connect() as conn:
        for table in (
            "approval_requests",
            "qol_events",
            "idempotency_keys",
            "concierge_executions",
        ):
            cur = conn.execute(f"DELETE FROM {table}")  # noqa: S608 — fixed table names
            cleared[table] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        conn.commit()

    # In-memory MCP carts / orders
    try:
        from mcp_server.session_store import reset_all_sessions

        cleared["mcp_sessions"] = reset_all_sessions()
    except Exception as e:  # noqa: BLE001
        cleared["mcp_sessions_error"] = str(e)

    # Restore the believable pantry baseline (demo runs pollute reorder cadence)
    try:
        from mcp_server.order_history import reseed_demo_history

        cleared["pantry_history_rows"] = reseed_demo_history()
    except Exception as e:  # noqa: BLE001
        cleared["pantry_history_error"] = str(e)

    # Telegram conversation memory (separate SQLite file)
    try:
        from backend.memory import clear_conversation_history, list_sessions

        telegram_sessions = [s for s in list_sessions() if s.startswith("tg:")]
        for session_id in telegram_sessions:
            clear_conversation_history(session_id)
        cleared["telegram_sessions"] = len(telegram_sessions)
    except Exception as e:  # noqa: BLE001
        cleared["telegram_sessions_error"] = str(e)

    return {"status": "reset", "cleared": cleared}


# Initialize on import
init_durable_tables()
