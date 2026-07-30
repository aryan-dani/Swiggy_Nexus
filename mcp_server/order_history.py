"""Durable Instamart order history (SQLite) — powers the Pantry Depletion Predictor.

Standalone on purpose: no `app.*` imports so the mock MCP layer stays importable
in isolation (tests, in-proc dispatchers, Docker).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DB_PATH = Path(os.environ.get("NEXUS_DB_PATH", "nexus_memory.db")).resolve()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_history_table() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS im_order_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                spin_id TEXT NOT NULL,
                name TEXT DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price_inr INTEGER DEFAULT 0,
                ordered_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_im_hist_spin ON im_order_history(spin_id, ordered_at);
            """
        )
        conn.commit()


def record_im_order(
    order_id: str,
    items: list[dict[str, Any]],
    ordered_at: str | None = None,
) -> None:
    """Persist checkout line items. `items` rows need spinId/name/qty/unit_price_inr."""
    if not items:
        return
    init_history_table()
    ts = ordered_at or datetime.now(timezone.utc).isoformat()
    rows = []
    for it in items:
        spin = str(it.get("spinId") or it.get("spin_id") or "").strip()
        if not spin:
            continue
        rows.append(
            (
                order_id,
                spin,
                str(it.get("name") or ""),
                int(it.get("quantity") or it.get("qty") or 1),
                int(it.get("unit_price_inr") or it.get("price_inr") or 0),
                ts,
            )
        )
    if not rows:
        return
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO im_order_history (order_id, spin_id, name, quantity, unit_price_inr, ordered_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def list_im_history(days: int = 60) -> list[dict[str, Any]]:
    init_history_table()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT order_id, spin_id, name, quantity, unit_price_inr, ordered_at"
            " FROM im_order_history WHERE ordered_at >= ? ORDER BY ordered_at ASC",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def history_is_empty() -> bool:
    init_history_table()
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM im_order_history").fetchone()
    return int(row["n"]) == 0


# ── Synthetic seed ────────────────────────────────────────────────────────────
# ~30 days of believable household reorders so the predictor demos instantly.

_SEED_PLAN: list[tuple[str, str, int, int, float]] = [
    # (spin_id, name, unit_price_inr, qty, reorder_interval_days)
    ("spin_milk_1l", "Amul Taaza Milk 1L", 52, 2, 3.0),
    ("spin_bread", "Britannia Wheat Bread", 45, 1, 4.0),
    ("spin_eggs_12", "Farm Fresh Eggs 12 pcs", 98, 1, 7.0),
    ("spin_dal_1kg", "Toor Dal 1kg", 145, 1, 15.0),
    ("spin_tea_green", "Tetley Green Tea", 180, 1, 20.0),
]


def clear_history() -> int:
    """Drop all recorded Instamart history. Returns rows removed."""
    init_history_table()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM im_order_history")
        conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0


def reseed_demo_history(days: int = 32) -> int:
    """Reset to the believable household baseline (used before recording a demo).

    Demo runs and tests append real checkouts, which quickly turns the pantry radar
    into nonsense like "Coca-Cola every 0.1 days". This restores the clean pattern.
    """
    clear_history()
    seed_synthetic_history_if_empty(days=days)
    return len(list_im_history(days=days + 5))


def seed_synthetic_history_if_empty(days: int = 32) -> bool:
    """Populate im_order_history with a month of periodic staple orders. Returns True if seeded."""
    if not history_is_empty():
        return False
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        for spin_id, name, price, qty, interval in _SEED_PLAN:
            t = now - timedelta(days=days)
            i = 0
            # Stop generating seed entries when within 0.4 intervals of 'now'
            # to ensure items show up as running low (days_left <= threshold) for demo predictability.
            while t <= now - timedelta(days=interval * 0.4):
                oid = f"IM_SEED_{spin_id[-6:]}_{i}"
                conn.execute(
                    "INSERT INTO im_order_history (order_id, spin_id, name, quantity, unit_price_inr, ordered_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (oid, spin_id, name, qty, price, t.isoformat()),
                )
                t += timedelta(days=interval)
                i += 1
        conn.commit()
    return True
