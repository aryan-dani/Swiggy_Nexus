"""Calendar webhooks, concierge trigger/status, ops + internal tick."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.api.hitl import router as hitl_router
from app.config import settings
from app.db.store import (
    claim_idempotency,
    get_execution,
    list_approvals,
    list_qol_events,
    record_qol_event,
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
from app.services import qol_triggers
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
    if expected and x_goog_channel_token and x_goog_channel_token != expected:
        raise HTTPException(status_code=403, detail="Invalid channel token")

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
        attendees = ["dani@nexus.ai", "priya@nexus.ai"]

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
    from app.api.hitl import _process_decision

    approved = True if body is None else body.approved
    return await _process_decision(request_id, approved)


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
