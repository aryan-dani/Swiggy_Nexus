"""APScheduler + external /internal/tick for Render free-tier cron."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.db.store import record_qol_event

log = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

        jobstores = {
            "default": SQLAlchemyJobStore(url=settings.DATABASE_URL),
        }
        _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="Asia/Kolkata")
        return _scheduler
    except Exception as e:  # noqa: BLE001
        log.warning("APScheduler init failed (%s); using no-op", e)
        return None


def start_scheduler() -> None:
    sched = get_scheduler()
    if sched and not sched.running:
        try:
            sched.start()
            log.info("APScheduler started")
        except Exception as e:  # noqa: BLE001
            log.warning("APScheduler start failed: %s", e)


def schedule_zero_touch_reminders(state: dict[str, Any]) -> tuple[str | None, str | None]:
    """Schedule reminder jobs relative to event time (best-effort)."""
    sched = get_scheduler()
    event_id = state.get("event_id") or "evt"
    im_job = f"im-remind-{event_id}"
    food_job = f"food-remind-{event_id}"
    if not sched:
        record_qol_event(
            kind="schedule_note",
            title="Scheduler unavailable — orders already placed on approve",
            detail=event_id,
            event_id=event_id,
        )
        return None, None

    now = datetime.now()
    try:
        if not sched.running:
            start_scheduler()
        sched.add_job(
            _remind_job,
            "date",
            run_date=now + timedelta(minutes=1),
            id=im_job,
            replace_existing=True,
            kwargs={"kind": "instamart", "event_id": event_id, "order_id": state.get("instamart_order_id")},
        )
        sched.add_job(
            _remind_job,
            "date",
            run_date=now + timedelta(minutes=2),
            id=food_job,
            replace_existing=True,
            kwargs={"kind": "food", "event_id": event_id, "order_id": state.get("food_order_id")},
        )
    except Exception as e:  # noqa: BLE001
        log.warning("schedule_zero_touch_reminders: %s", e)
        return None, None
    return im_job, food_job


def _remind_job(kind: str, event_id: str, order_id: str | None = None) -> None:
    record_qol_event(
        kind=f"leg_reminder_{kind}",
        title=f"{kind} leg reminder",
        detail=f"order={order_id}",
        event_id=event_id,
        meta={"order_id": order_id},
    )


async def run_tick() -> dict[str, Any]:
    """Called by /internal/tick — runs weather + QoL scans."""
    from app.services.qol_triggers import run_all_qol_checks

    results = await run_all_qol_checks()
    return {"ok": True, "results": results, "ts": datetime.utcnow().isoformat()}
