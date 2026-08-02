"""Night-out / dinner-party orchestration — Calendar invite + graph staging.

Telegram and Concierge Ops both call these helpers so one natural-language line
can create a Google Calendar event, stage Dineout (or Food), then after Approve
emit a rich night_out_receipt with Maps + equal UPI split.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import settings
from app.db.models import ensure_night_out_guests
from app.db.store import claim_idempotency, record_qol_event
from app.services.google_calendar import CalendarAuthError, create_calendar_event, maps_url_for

log = logging.getLogger(__name__)

HOST_EMAIL = "aryan@nexus.ai"
HOST_ID = "aryan"

GUEST_ALIASES: dict[str, str] = {
    "aryan": "aryan@nexus.ai",
    "himali": "himali@nexus.ai",
    "siya": "siya@nexus.ai",
    "swayam": "swayam@nexus.ai",
    "priya": "priya@nexus.ai",
    "kabir": "kabir@nexus.ai",
    "ananya": "ananya@nexus.ai",
    "rohan": "rohan@nexus.ai",
    "meera": "meera@nexus.ai",
    # legacy aliases
    "dani": "aryan@nexus.ai",
    "daniaryan": "aryan@nexus.ai",
    "sobaan": "siya@nexus.ai",
}

DEFAULT_VENUE = "6 Digs · Kothrud"
DEFAULT_VENUE_QUERY = "6 Digs"


def resolve_guest_emails(
    guests: list[str] | None = None,
    *,
    include_host: bool = True,
) -> list[str]:
    """Map first names / emails → Taste Vault emails; always include host first."""
    ensure_night_out_guests()
    resolved: list[str] = []
    seen: set[str] = set()

    def _add(email: str) -> None:
        e = email.lower().strip()
        if e and e not in seen:
            seen.add(e)
            resolved.append(e)

    if include_host:
        _add(HOST_EMAIL)

    for raw in guests or []:
        token = str(raw or "").strip()
        if not token:
            continue
        if "@" in token:
            _add(token)
            continue
        key = "".join(ch for ch in token.lower() if ch.isalnum())
        mapped = GUEST_ALIASES.get(key)
        if mapped:
            _add(mapped)
        else:
            _add(f"{key}@nexus.ai")

    if len(resolved) < 2:
        _add("himali@nexus.ai")
        _add("siya@nexus.ai")
        _add("swayam@nexus.ai")
    return resolved


async def plan_night_out(
    *,
    guest_names: list[str] | None = None,
    venue: str = DEFAULT_VENUE,
    venue_query: str = DEFAULT_VENUE_QUERY,
    guest_count: int | None = None,
    start_iso: str | None = None,
    preferred_slot: str | None = None,
    preferred_slot_id: str | None = None,
    restaurant_id: str | None = None,
    suppress_hitl_telegram: bool = False,
) -> dict[str, Any]:
    """Create Calendar invite + run Dineout concierge graph (HITL before book_table)."""
    from app.graph import concierge_graph

    emails = resolve_guest_emails(guest_names)
    party = max(int(guest_count or len(emails)), len(emails), 2)
    location = venue or DEFAULT_VENUE
    summary = f"Dinner at {location} #dineout #swiggy"
    names_blob = ", ".join(emails)
    slot_bit = f" Slot {preferred_slot}." if preferred_slot else ""
    description = (
        f"Night out with {names_blob}. Table for {party}.{slot_bit} "
        f"Split the bill equally. #dineout #swiggy"
    )

    cal = create_calendar_event(
        summary=summary,
        location=location,
        description=description,
        attendee_emails=emails,
        start_iso=start_iso,
    )
    event_id = str(cal.get("event_id") or cal.get("id") or f"night_{uuid.uuid4().hex[:10]}")
    html_link = str(cal.get("htmlLink") or "")
    maps = maps_url_for(location)

    claim_idempotency(f"{event_id}:night_out", note="night_out_plan")

    initial_state: dict[str, Any] = {
        "event_id": event_id,
        "event_title": summary,
        "event_time_str": (cal.get("start") or {}).get("dateTime")
        or preferred_slot
        or "Today 20:00",
        "event_location": location,
        "event_description": description,
        "attendee_emails": emails,
        "calendar_event_id": event_id,
        "calendar_html_link": html_link,
        "calendar_mock": bool(cal.get("mock")),
        "maps_url": maps,
        "preferred_restaurant_query": venue_query or restaurant_id or DEFAULT_VENUE_QUERY,
        "preferred_slot": preferred_slot or "",
        "preferred_slot_id": preferred_slot_id,
        "guest_count": party,
        "auto_split_bill": True,
        "trigger_type": "night_out",
        "address_id": settings.DEFAULT_ADDRESS_ID,
        "suppress_hitl_telegram": suppress_hitl_telegram,
        "execution_logs": [],
        "errors": [],
    }

    record_qol_event(
        kind="night_out_planned",
        title=f"Night out staged · {location}",
        detail=f"{party} guests · calendar {'mock' if cal.get('mock') else 'live'}",
        severity="action",
        event_id=event_id,
        meta={
            "calendar_html_link": html_link,
            "maps_url": maps,
            "attendee_emails": emails,
            "venue": location,
            "guest_count": party,
        },
    )

    # Await graph until HITL interrupt so Telegram/Ops get a usable approval id.
    config = {"configurable": {"thread_id": event_id}}
    state = await concierge_graph.ainvoke(initial_state, config=config)
    return {
        "status": "awaiting_approval",
        "event_id": event_id,
        "calendar_html_link": html_link,
        "maps_url": maps,
        "attendee_emails": emails,
        "guest_count": party,
        "venue": location,
        "approval_request_id": state.get("approval_request_id"),
        "mode": state.get("mode"),
        "calendar_mock": bool(cal.get("mock")),
        "calendar_auth_error": cal.get("auth_error"),
        "message": (
            f"Calendar invite ready and table at {location} staged for approval. "
            "Approve in Concierge Ops or Telegram to book + split."
            if not cal.get("mock")
            else (
                f"Table at {location} staged, but Calendar is NOT live "
                f"({cal.get('auth_error') or 'OAuth missing'}). "
                "Run: python scripts/google_auth_setup.py"
            )
        ),
    }


async def plan_dinner_party(
    *,
    guest_names: list[str] | None = None,
    dish_query: str = "paneer biryani",
    guest_count: int | None = None,
    start_iso: str | None = None,
) -> dict[str, Any]:
    """Home dinner party: Calendar + Zero-Touch Host graph (Food/IM) + split after approve."""
    from app.graph import concierge_graph

    emails = resolve_guest_emails(guest_names)
    party = max(int(guest_count or len(emails)), len(emails), 2)
    location = "Home"
    summary = f"Dinner party · {dish_query} #host #swiggy"
    description = (
        f"Hosting {', '.join(emails)}. Ordering {dish_query}. "
        f"Split the bill equally. #host #swiggy"
    )

    cal = create_calendar_event(
        summary=summary,
        location=location,
        description=description,
        attendee_emails=emails,
        start_iso=start_iso,
    )
    event_id = str(cal.get("event_id") or cal.get("id") or f"party_{uuid.uuid4().hex[:10]}")
    html_link = str(cal.get("htmlLink") or "")
    maps = maps_url_for(f"{settings.HOME_CITY} home", settings.HOME_LAT, settings.HOME_LNG)

    claim_idempotency(f"{event_id}:dinner_party", note="dinner_party_plan")

    initial_state: dict[str, Any] = {
        "event_id": event_id,
        "event_title": summary,
        "event_time_str": (cal.get("start") or {}).get("dateTime") or "Today 20:00",
        "event_location": location,
        "event_description": description,
        "attendee_emails": emails,
        "calendar_event_id": event_id,
        "calendar_html_link": html_link,
        "calendar_mock": bool(cal.get("mock")),
        "maps_url": maps,
        "guest_count": party,
        "auto_split_bill": True,
        "preferred_food_query": dish_query,
        "trigger_type": "dinner_party",
        "address_id": settings.DEFAULT_ADDRESS_ID,
        "execution_logs": [],
        "errors": [],
    }

    record_qol_event(
        kind="dinner_party_planned",
        title=f"Dinner party staged · {dish_query}",
        detail=f"{party} guests",
        severity="action",
        event_id=event_id,
        meta={
            "calendar_html_link": html_link,
            "maps_url": maps,
            "attendee_emails": emails,
            "dish_query": dish_query,
        },
    )

    config = {"configurable": {"thread_id": event_id}}
    state = await concierge_graph.ainvoke(initial_state, config=config)
    return {
        "status": "awaiting_approval",
        "event_id": event_id,
        "calendar_html_link": html_link,
        "maps_url": maps,
        "attendee_emails": emails,
        "guest_count": party,
        "approval_request_id": state.get("approval_request_id"),
        "mode": state.get("mode"),
        "calendar_mock": bool(cal.get("mock")),
        "calendar_auth_error": cal.get("auth_error"),
        "message": (
            "Calendar invite ready and food/IM carts staged for approval. "
            "Approve to place orders and split the bill."
            if not cal.get("mock")
            else (
                f"Carts staged, but Calendar is NOT live ({cal.get('auth_error') or 'OAuth missing'}). "
                "Run: python scripts/google_auth_setup.py"
            )
        ),
    }
