"""Calendar webhooks, concierge trigger/status, ops + internal tick."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel

from app.api.hitl import router as hitl_router
from app.config import settings
from app.db.store import (
    claim_idempotency,
    get_execution,
    list_approvals,
    list_qol_events,
    record_qol_event,
    reset_demo_state,
    save_execution,
)
from app.graph.workflow import concierge_graph
from app.schemas import (
    ApprovalBody,
    ManualTriggerBody,
    SimulateGuestsBody,
    SimulateIplBody,
    SimulateWeatherBody,
    WeatherAlert,
)
from app.services import bill_split, pantry, qol_triggers
from app.services.google_calendar import fetch_calendar_event
from app.services.match import match_provider
from app.services.scheduler import run_tick
from app.services.weather import get_weather_provider, set_scenario_weather

log = logging.getLogger(__name__)

router = APIRouter()
router.include_router(hitl_router)


@router.post("/webhooks/calendar")
async def calendar_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_channel_id: str | None = Header(None, alias="X-Goog-Channel-ID"),
    x_goog_resource_state: str | None = Header(None, alias="X-Goog-Resource-State"),
    x_goog_message_number: str | None = Header(None, alias="X-Goog-Message-Number"),
    x_goog_channel_token: str | None = Header(None, alias="X-Goog-Channel-Token"),
) -> dict[str, Any]:
    if x_goog_resource_state == "sync":
        return {"status": "ok", "message": "Handshake successful"}

    expected = settings.GOOGLE_PUBSUB_VERIFICATION_TOKEN
    if expected:
        if not x_goog_channel_token or x_goog_channel_token != expected:
            raise HTTPException(status_code=403, detail="Invalid or missing channel token")

    raw_body = await request.body()
    event_data: dict[str, Any] = {}
    try:
        if raw_body:
            body_json = json.loads(raw_body.decode("utf-8"))
            if "message" in body_json and "data" in body_json["message"]:
                decoded = base64.b64decode(body_json["message"]["data"]).decode("utf-8")
                event_data = json.loads(decoded)
            else:
                event_data = body_json
    except Exception as e:  # noqa: BLE001
        log.warning("Calendar body parse: %s", e)

    event_id = (
        event_data.get("id")
        or event_data.get("event_id")
        or f"evt_{x_goog_message_number or uuid.uuid4().hex[:8]}"
    )
    calendar_id = event_data.get("calendar_id", settings.PRIMARY_CALENDAR_ID)
    cal_event = fetch_calendar_event(calendar_id, event_id)
    if not cal_event:
        return {"status": "ignored", "reason": "event not found"}

    description = cal_event.get("description", "")
    summary = cal_event.get("summary", "")
    blob = f"{description} {summary}".lower()
    if "#swiggy" not in blob and "#host" not in blob:
        return {"status": "ignored", "reason": "missing #swiggy/#host"}

    idem = f"{event_id}:{cal_event.get('updated', '')}"
    if not claim_idempotency(idem, note="calendar_webhook"):
        return {"status": "ignored", "reason": "duplicate"}

    attendees = [a.get("email") for a in cal_event.get("attendees", []) if a.get("email")]
    if not attendees:
        attendees = ["aryan@nexus.ai", "himali@nexus.ai"]

    initial_state = {
        "event_id": event_id,
        "event_title": summary or "Swiggy Event",
        "event_time_str": cal_event.get("start", {}).get("dateTime", "Today"),
        "event_location": cal_event.get("location", "Home"),
        "event_description": description,
        "attendee_emails": attendees,
        "calendar_event_id": event_id,
        "trigger_type": "calendar_concierge",
        "execution_logs": [],
        "errors": [],
    }
    background_tasks.add_task(_run_graph_execution, initial_state)
    return {"status": "accepted", "event_id": event_id}


@router.post("/api/concierge/trigger")
async def manual_trigger(body: ManualTriggerBody) -> dict[str, Any]:
    event_id = f"manual_{uuid.uuid4().hex[:10]}"
    initial_state = {
        "event_id": event_id,
        "event_title": body.event_title,
        "event_time_str": body.event_time,
        "event_location": body.event_location,
        "event_description": body.description,
        "attendee_emails": body.attendee_emails,
        "calendar_event_id": event_id,
        "trigger_type": "calendar_concierge",
        "execution_logs": [],
        "errors": [],
    }
    config = {"configurable": {"thread_id": event_id}}
    res_state = await concierge_graph.ainvoke(initial_state, config=config)
    req_id = res_state.get("approval_request_id")
    save_execution(
        event_id,
        {
            "request_id": req_id,
            "status": "paused_at_hitl_checkpoint",
            "mode": res_state.get("mode"),
            "state": res_state,
        },
    )
    return {
        "status": "paused_at_hitl_checkpoint",
        "event_id": event_id,
        "approval_request_id": req_id,
        "mode": res_state.get("mode"),
        "total_cost": res_state.get("total_estimated_cost"),
        "state_snapshot": res_state,
        "approve_endpoint": f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{req_id}",
    }


@router.post("/api/concierge/approve/{request_id}")
async def approve_legacy(request_id: str, body: ApprovalBody | None = None) -> dict[str, Any]:
    """Back-compat wrapper → HITL approve."""
    from app.services.hitl_decisions import HitlNotFoundError, process_decision

    approved = True if body is None else body.approved
    try:
        return await process_decision(request_id, approved)
    except HitlNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/api/concierge/status/{event_id}")
def get_concierge_status(event_id: str) -> dict[str, Any]:
    snapshot = get_execution(event_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"No execution for '{event_id}'")
    state = snapshot.get("state") or {}
    return {
        "event_id": event_id,
        "mode": snapshot.get("mode") or state.get("mode"),
        "approval_status": state.get("approval_status"),
        "approval_request_id": snapshot.get("request_id") or state.get("approval_request_id"),
        "total_estimated_cost": state.get("total_estimated_cost"),
        "execution_logs": state.get("execution_logs", []),
        "snapshot": state,
        "status": snapshot.get("status"),
    }


@router.get("/api/concierge/approvals")
def concierge_approvals(status: str | None = "PENDING") -> dict[str, Any]:
    return {"items": list_approvals(status=status)}


@router.get("/api/concierge/timeline")
def concierge_timeline(limit: int = 40) -> dict[str, Any]:
    return {"items": list_qol_events(limit=limit)}


@router.get("/api/concierge/weather")
async def concierge_weather() -> dict[str, Any]:
    w = await get_weather_provider().get_current()
    return w.model_dump(mode="json")


@router.post("/api/concierge/simulate/weather")
async def simulate_weather(body: SimulateWeatherBody) -> dict[str, Any]:
    alert = set_scenario_weather(
        WeatherAlert(
            source="scenario",
            city=settings.HOME_CITY,
            lat=settings.HOME_LAT,
            lng=settings.HOME_LNG,
            temp_c=body.temp_c,
            rain_mm=body.rain_mm,
            is_raining=body.is_raining,
            is_heavy_rain=body.is_heavy_rain,
            condition=body.condition,
        )
    )
    result = await qol_triggers.check_rooftop_rescue(alert)
    bhajiya = await qol_triggers.check_bhajiya_chai(alert)
    record_qol_event(
        kind="simulate_weather",
        title="Weather simulation",
        detail=body.condition,
        meta=alert.model_dump(mode="json"),
    )
    return {"weather": alert.model_dump(mode="json"), "rooftop": result, "bhajiya": bhajiya}


@router.post("/api/concierge/simulate/guests")
async def simulate_guests(body: SimulateGuestsBody) -> dict[str, Any]:
    return await qol_triggers.guest_sos(body.count)


@router.post("/api/concierge/simulate/ipl")
async def simulate_ipl(body: SimulateIplBody) -> dict[str, Any]:
    state = match_provider.simulate(
        required_run_rate=body.required_run_rate,
        is_timeout=body.is_timeout,
        is_tense_chase=body.is_tense_chase,
        overs=body.overs,
        teams=body.teams,
    )
    fired = await qol_triggers.check_ipl_timeout()
    return {"match": state.model_dump(), "trigger": fired}


@router.post("/api/concierge/simulate/fuel")
async def simulate_fuel() -> dict[str, Any]:
    qol_triggers.force_fuel_guard(True)
    fired = await qol_triggers.check_fuel_guard()
    return {"trigger": fired}


@router.get("/api/concierge/agent")
def concierge_agent() -> dict[str, Any]:
    """Which brain is driving the Telegram agent, and what it may never execute alone."""
    from app.services.llm import active_provider_label, _resolve_provider
    from app.services.telegram_agent import WRITE_TOOLS

    provider, model = _resolve_provider()
    return {
        "provider": provider,
        "model": model,
        "label": active_provider_label(),
        "configured": provider != "none",
        "telegram_ready": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "hitl_gated_tools": sorted(WRITE_TOOLS),
    }


class NightOutBody(BaseModel):
    guests: list[str] = ["himali", "siya", "swayam"]
    venue: str = "6 Digs · Kothrud"
    guest_count: int | None = 4
    start_iso: str | None = None
    preferred_slot: str | None = None
    preferred_slot_id: str | None = None


class DinnerPartyBody(BaseModel):
    guests: list[str] = ["himali", "siya", "swayam"]
    dish_query: str = "paneer biryani"
    guest_count: int | None = 4


class WizardGuestsBody(BaseModel):
    guests: list[str]


class WizardVenueBody(BaseModel):
    restaurant_id: str | None = None
    name: str | None = None


class WizardSlotBody(BaseModel):
    slot: str
    slot_id: str | int | None = None
    start_iso: str | None = None


@router.post("/api/concierge/night-out")
async def concierge_night_out(body: NightOutBody) -> dict[str, Any]:
    """Direct night-out (skips wizard) — prefer /wizard/* for demos."""
    from fastapi import HTTPException

    from app.services.google_calendar import CalendarAuthError
    from app.services.night_out import plan_night_out

    try:
        return await plan_night_out(
            guest_names=body.guests,
            venue=body.venue,
            venue_query="6 Digs" if "6 dig" in body.venue.lower() else body.venue,
            guest_count=body.guest_count,
            start_iso=body.start_iso,
            preferred_slot=body.preferred_slot,
            preferred_slot_id=body.preferred_slot_id,
        )
    except CalendarAuthError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "calendar_auth",
                "message": str(e),
                "fix": "python scripts/google_auth_setup.py",
            },
        ) from e


@router.post("/api/concierge/night-out/wizard/start")
def night_out_wizard_start() -> dict[str, Any]:
    from app.services.night_out_wizard import start_wizard

    return start_wizard()


@router.get("/api/concierge/night-out/wizard/{wizard_id}")
def night_out_wizard_get(wizard_id: str) -> dict[str, Any]:
    from app.services.night_out_wizard import get_wizard

    try:
        return get_wizard(wizard_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Wizard expired or not found") from e


@router.post("/api/concierge/night-out/wizard/{wizard_id}/guests")
def night_out_wizard_guests(wizard_id: str, body: WizardGuestsBody) -> dict[str, Any]:
    from app.services.night_out_wizard import set_guests

    try:
        return set_guests(wizard_id, body.guests)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Wizard expired or not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/concierge/night-out/wizard/{wizard_id}/venues")
async def night_out_wizard_venues(wizard_id: str, q: str = "") -> dict[str, Any]:
    from app.services.night_out_wizard import search_venues

    try:
        return await search_venues(wizard_id, q)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Wizard expired or not found") from e


@router.post("/api/concierge/night-out/wizard/{wizard_id}/venue")
async def night_out_wizard_venue(wizard_id: str, body: WizardVenueBody) -> dict[str, Any]:
    from app.services.night_out_wizard import set_venue

    try:
        return await set_venue(wizard_id, restaurant_id=body.restaurant_id, name=body.name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Wizard expired or not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/concierge/night-out/wizard/{wizard_id}/slot")
def night_out_wizard_slot(wizard_id: str, body: WizardSlotBody) -> dict[str, Any]:
    from app.services.night_out_wizard import set_slot

    try:
        return set_slot(
            wizard_id,
            slot=body.slot,
            slot_id=body.slot_id,
            start_iso=body.start_iso,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Wizard expired or not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/concierge/night-out/wizard/{wizard_id}/confirm")
async def night_out_wizard_confirm(wizard_id: str) -> dict[str, Any]:
    from app.services.google_calendar import CalendarAuthError
    from app.services.night_out_wizard import confirm_wizard

    try:
        return await confirm_wizard(wizard_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Wizard expired or not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CalendarAuthError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "calendar_auth",
                "message": str(e),
                "fix": "python scripts/google_auth_setup.py",
            },
        ) from e


@router.post("/api/concierge/dinner-party")
async def concierge_dinner_party(body: DinnerPartyBody) -> dict[str, Any]:
    """Demo: home dinner party Calendar + food/IM staging + split-after-approve."""
    from fastapi import HTTPException

    from app.services.google_calendar import CalendarAuthError
    from app.services.night_out import plan_dinner_party

    try:
        return await plan_dinner_party(
            guest_names=body.guests,
            dish_query=body.dish_query,
            guest_count=body.guest_count,
        )
    except CalendarAuthError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "calendar_auth",
                "message": str(e),
                "fix": "python scripts/google_auth_setup.py",
            },
        ) from e


@router.get("/api/concierge/calendar/status")
def concierge_calendar_status() -> dict[str, Any]:
    """Whether live Google Calendar inserts will succeed."""
    from app.services.google_calendar import calendar_connection_status

    return calendar_connection_status()


@router.get("/api/concierge/receipts/latest")
def concierge_latest_receipt() -> dict[str, Any]:
    """Latest night_out_receipt QoL meta for the Ops receipt card."""
    for item in list_qol_events(limit=40):
        if item.get("kind") == "night_out_receipt":
            return {"receipt": item.get("meta") or {}, "event": item}
    return {"receipt": None}


@router.get("/api/concierge/pantry")
def concierge_pantry() -> dict[str, Any]:
    """Pantry radar — per-SKU depletion predictions from Instamart history."""
    return {"items": pantry.get_pantry_status()}


@router.post("/api/concierge/simulate/pantry")
async def simulate_pantry() -> dict[str, Any]:
    fired = await pantry.check_pantry_refill(force=True)
    return fired or {"status": "nothing_low"}


class SplitBody(BaseModel):
    total_inr: float
    attendees: list[str]
    order_id: str | None = None
    title: str = "Bill split"


@router.post("/api/concierge/split")
async def concierge_split(body: SplitBody) -> dict[str, Any]:
    """Nexus extension — BHIM-style equal split with mock UPI links."""
    try:
        return await bill_split.split_and_notify(
            body.total_inr,
            body.attendees,
            order_id=body.order_id,
            title=body.title,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class CalendarReplayBody(BaseModel):
    """A Google Calendar event as Google itself would hand it to us."""

    summary: str = "Team Friday Night Social #swiggy"
    description: str = "Weekly team catchup and dinner #swiggy"
    location: str = "Home"
    start_time: str | None = None
    attendee_emails: list[str] = ["aryan@nexus.ai", "himali@nexus.ai", "siya@nexus.ai"]
    event_id: str | None = None


@router.post("/api/concierge/simulate/calendar")
async def simulate_calendar(
    body: CalendarReplayBody, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Replay a calendar push without Google.

    The live `/webhooks/calendar` path needs a public BASE_URL plus a real event that
    `fetch_calendar_event` can load. This endpoint runs the identical gate and graph on a
    supplied payload, so the calendar story is recordable with or without ngrok. Each call
    mints a fresh event id so repeated takes are never swallowed by the idempotency key.
    """
    blob = f"{body.description} {body.summary}".lower()
    if "#swiggy" not in blob and "#host" not in blob:
        return {"status": "ignored", "reason": "missing #swiggy/#host"}

    event_id = body.event_id or f"cal_{uuid.uuid4().hex[:10]}"
    if not claim_idempotency(f"{event_id}:replay", note="calendar_replay"):
        return {"status": "ignored", "reason": "duplicate"}

    initial_state = {
        "event_id": event_id,
        "event_title": body.summary,
        "event_time_str": body.start_time or "Today 19:00",
        "event_location": body.location,
        "event_description": body.description,
        "attendee_emails": body.attendee_emails,
        "calendar_event_id": event_id,
        "trigger_type": "calendar_concierge",
        "execution_logs": [],
        "errors": [],
    }
    record_qol_event(
        kind="calendar_push",
        title=f"Calendar event received · {body.summary}",
        detail=f"{body.location} · {len(body.attendee_emails)} attendees",
        severity="action",
        event_id=event_id,
        meta={"replay": True},
    )
    background_tasks.add_task(_run_graph_execution, initial_state)
    return {"status": "accepted", "event_id": event_id, "source": "replay"}


@router.post("/internal/demo/reset")
def demo_reset(
    x_nexus_tick_secret: str | None = Header(None, alias="X-Nexus-Tick-Secret"),
) -> dict[str, Any]:
    """Wipe demo state so every recording take starts clean."""
    if x_nexus_tick_secret != settings.INTERNAL_TICK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid tick secret")
    return reset_demo_state()


@router.post("/internal/tick")
async def internal_tick(
    x_nexus_tick_secret: str | None = Header(None, alias="X-Nexus-Tick-Secret"),
) -> dict[str, Any]:
    if x_nexus_tick_secret != settings.INTERNAL_TICK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid tick secret")
    return await run_tick()


async def _run_graph_execution(initial_state: dict[str, Any]) -> None:
    event_id = initial_state["event_id"]
    config = {"configurable": {"thread_id": event_id}}
    try:
        res_state = await concierge_graph.ainvoke(initial_state, config=config)
        save_execution(
            event_id,
            {
                "request_id": res_state.get("approval_request_id"),
                "status": "paused_at_hitl_checkpoint",
                "mode": res_state.get("mode"),
                "state": res_state,
            },
        )
    except Exception as e:  # noqa: BLE001
        log.error("Graph dispatch error for %s: %s", event_id, e)
