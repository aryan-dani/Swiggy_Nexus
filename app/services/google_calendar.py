"""Google Calendar API Integration & Webhook Watch Channel Setup."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

log = logging.getLogger(__name__)


def get_calendar_service() -> Any:
    """Build Google Calendar API service instance if credentials exist."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_path = settings.GOOGLE_CALENDAR_TOKEN_PATH
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, ["https://www.googleapis.com/auth/calendar"])
            return build("calendar", "v3", credentials=creds)
    except Exception as e:
        log.warning(f"[GOOGLE CALENDAR] Service build skipped (No OAuth token or SDK error): {e}")
    return None


def fetch_calendar_event(calendar_id: str, event_id: str) -> dict[str, Any] | None:
    """Fetch event details from Google Calendar API."""
    service = get_calendar_service()
    if not service:
        log.info(f"[GOOGLE CALENDAR MOCK] Fetching event {event_id} from mock data")
        return {
            "id": event_id,
            "summary": "Team Friday Night Social #swiggy",
            "description": "Weekly team catchup and dinner #swiggy",
            "location": "Home",
            "start": {"dateTime": "2026-07-26T19:00:00+05:30"},
            "attendees": [
                {"email": "dani@nexus.ai"},
                {"email": "priya@nexus.ai"},
                {"email": "alex@nexus.ai"},
            ],
            "updated": "2026-07-26T11:00:00Z",
        }

    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return event
    except Exception as e:
        log.error(f"[GOOGLE CALENDAR] Failed to fetch event {event_id}: {e}")
        return None


def update_calendar_event_description(calendar_event_id: str, new_description: str) -> bool:
    """Patch the original Google Calendar event description with updated markdown details."""
    service = get_calendar_service()
    if not service:
        log.info("[GOOGLE CALENDAR MOCK] Patched event %s description successfully.", calendar_event_id)
        return True

    try:
        service.events().patch(
            calendarId=settings.PRIMARY_CALENDAR_ID,
            eventId=calendar_event_id,
            body={"description": new_description},
        ).execute()
        log.info("[GOOGLE CALENDAR] Successfully patched event %s description.", calendar_event_id)
        return True
    except Exception as e:
        log.error("[GOOGLE CALENDAR] Failed to patch event %s: %s", calendar_event_id, e)
        return False


def setup_calendar_watch(webhook_url: str, channel_id: str = "nexus-concierge-watch") -> dict[str, Any] | None:
    """Register Google Cloud Pub/Sub Webhook push channel watch for Calendar events."""
    service = get_calendar_service()
    if not service:
        log.info(f"[GOOGLE CALENDAR MOCK] Setup watch registered for {webhook_url}")
        return {"id": channel_id, "resourceId": "mock-resource-id", "expiration": "1785000000000"}

    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": webhook_url,
        "token": settings.GOOGLE_PUBSUB_VERIFICATION_TOKEN,
    }

    try:
        watch_resp = service.events().watch(calendarId=settings.PRIMARY_CALENDAR_ID, body=body).execute()
        log.info(f"[GOOGLE CALENDAR] Watch channel established: {watch_resp}")
        return watch_resp
    except Exception as e:
        log.error(f"[GOOGLE CALENDAR] Failed to establish watch channel: {e}")
        return None
