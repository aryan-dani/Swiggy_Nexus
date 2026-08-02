"""Google Calendar API Integration & Webhook Watch Channel Setup."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from app.config import settings

log = logging.getLogger(__name__)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarAuthError(RuntimeError):
    """OAuth token missing, expired, or revoked — re-run google_auth_setup."""


def _token_path() -> Path:
    return Path(settings.GOOGLE_CALENDAR_TOKEN_PATH)


def _credentials_path() -> Path:
    return Path(settings.GOOGLE_CALENDAR_CREDENTIALS_PATH)


def load_calendar_credentials(*, persist_refresh: bool = True) -> Any | None:
    """Load OAuth creds; refresh + rewrite token file when expired."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as e:
        log.warning("[GOOGLE CALENDAR] google-auth not installed: %s", e)
        return None

    token_path = _token_path()
    if not token_path.exists():
        log.warning("[GOOGLE CALENDAR] No token at %s — run scripts/google_auth_setup.py", token_path)
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), CALENDAR_SCOPES)
    except Exception as e:
        log.warning("[GOOGLE CALENDAR] Could not read token: %s", e)
        return None

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            if persist_refresh:
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(creds.to_json(), encoding="utf-8")
                log.info("[GOOGLE CALENDAR] Refreshed OAuth token → %s", token_path)
            return creds
        except Exception as e:
            log.error(
                "[GOOGLE CALENDAR] Refresh failed (%s). Re-auth: python scripts/google_auth_setup.py",
                e,
            )
            return None

    log.warning("[GOOGLE CALENDAR] Token invalid with no refresh — run google_auth_setup.py")
    return None


def get_calendar_service() -> Any:
    """Build Google Calendar API service instance if credentials exist."""
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        log.warning("[GOOGLE CALENDAR] google-api-python-client missing: %s", e)
        return None

    creds = load_calendar_credentials()
    if not creds:
        return None
    try:
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.warning("[GOOGLE CALENDAR] Service build failed: %s", e)
        return None


def calendar_connection_status() -> dict[str, Any]:
    """Ops/health: is live Calendar insert possible right now?"""
    creds_file = _credentials_path().exists()
    token_file = _token_path().exists()
    creds = load_calendar_credentials(persist_refresh=True)
    return {
        "credentials_file": creds_file,
        "token_file": token_file,
        "live": bool(creds and creds.valid),
        "hint": (
            None
            if creds and creds.valid
            else "Run: python scripts/google_auth_setup.py  (browser OAuth once)"
        ),
    }


def fetch_calendar_event(calendar_id: str, event_id: str) -> dict[str, Any] | None:
    """Fetch event details from Google Calendar API. Fail-closed without live OAuth."""
    service = get_calendar_service()
    if not service:
        log.warning(
            "[GOOGLE CALENDAR] No live service — refusing mock fetch for %s "
            "(use /api/concierge/trigger to simulate)",
            event_id,
        )
        return None

    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return event
    except Exception as e:
        log.error("[GOOGLE CALENDAR] Failed to fetch event %s: %s", event_id, e)
        return None


def update_calendar_event_description(calendar_event_id: str, new_description: str) -> bool:
    """Patch Calendar event description. Returns False when OAuth is missing (no pretend success)."""
    service = get_calendar_service()
    if not service:
        log.warning(
            "[GOOGLE CALENDAR] Skip description patch for %s — no live OAuth",
            calendar_event_id,
        )
        return False

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


def _template_html_link(
    *,
    summary: str,
    location: str,
    description: str,
    start_dt: Any,
    end_dt: Any,
) -> str:
    """Pre-filled Google Calendar compose URL — opens a real create form (never a fake eid)."""

    def _stamp(dt: Any) -> str:
        # Floating local time for TEMPLATE (no Z) works with ctz=
        return dt.strftime("%Y%m%dT%H%M%S")

    params = (
        f"action=TEMPLATE"
        f"&text={quote(summary)}"
        f"&dates={_stamp(start_dt)}/{_stamp(end_dt)}"
        f"&details={quote(description)}"
        f"&location={quote(location)}"
        f"&ctz=Asia/Kolkata"
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def _mock_event_payload(
    *,
    summary: str,
    location: str,
    description: str,
    emails: list[str],
    start_dt: Any,
    end_dt: Any,
    reason: str,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    event_id = f"mock_cal_{int(datetime.now(timezone.utc).timestamp())}"
    html_link = _template_html_link(
        summary=summary,
        location=location,
        description=description,
        start_dt=start_dt,
        end_dt=end_dt,
    )
    log.warning(
        "[GOOGLE CALENDAR] Mock mode (%s) — template link only, event NOT on your calendar. "
        "Fix: python scripts/google_auth_setup.py",
        reason,
    )
    return {
        "id": event_id,
        "event_id": event_id,
        "htmlLink": html_link,
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
        "attendees": [{"email": e} for e in emails],
        "mock": True,
        "auth_error": reason,
        "maps_hint": maps_url_for(location),
    }


def _is_nexus_ai_email(email: str) -> bool:
    return email.strip().lower().endswith("@nexus.ai")


def create_calendar_event(
    *,
    summary: str,
    location: str,
    description: str,
    attendee_emails: list[str],
    start_iso: str | None = None,
    duration_minutes: int = 120,
    allow_mock: bool | None = None,
) -> dict[str, Any]:
    """Create a Calendar event and invite guests.

    Demo addresses ending in @nexus.ai stay in description/local plan but are
    never invited via the Google API (they bounce). sendUpdates is "none" when
    no real attendees remain.

    When OAuth is missing/revoked:
    - allow_mock=True → template compose URL (works in browser; not auto-booked)
    - allow_mock=False → raises CalendarAuthError
    Default allow_mock follows settings.GOOGLE_CALENDAR_ALLOW_MOCK.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    if allow_mock is None:
        allow_mock = bool(settings.GOOGLE_CALENDAR_ALLOW_MOCK)

    emails = [e.strip() for e in attendee_emails if e and e.strip()]
    invite_emails = [e for e in emails if not _is_nexus_ai_email(e)]
    ist = ZoneInfo("Asia/Kolkata")
    if start_iso:
        try:
            start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=ist)
            else:
                start_dt = start_dt.astimezone(ist)
        except ValueError:
            start_dt = datetime.now(ist) + timedelta(hours=3)
    else:
        start_dt = datetime.now(ist) + timedelta(hours=3)
        minute = 30 if start_dt.minute < 30 else 0
        if minute == 0:
            start_dt = start_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            start_dt = start_dt.replace(minute=30, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    service = get_calendar_service()
    if not service:
        reason = "OAuth token missing or revoked"
        if not allow_mock:
            raise CalendarAuthError(
                f"{reason}. Run: python scripts/google_auth_setup.py"
            )
        return _mock_event_payload(
            summary=summary,
            location=location,
            description=description,
            emails=emails,
            start_dt=start_dt,
            end_dt=end_dt,
            reason=reason,
        )

    body: dict[str, Any] = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Kolkata"},
    }
    if invite_emails:
        body["attendees"] = [{"email": e} for e in invite_emails]
    send_updates = "all" if invite_emails else "none"
    if emails and not invite_emails:
        log.info(
            "[GOOGLE CALENDAR] Omitting %d @nexus.ai demo attendee(s) from live invite; sendUpdates=none",
            len(emails),
        )
    try:
        event = (
            service.events()
            .insert(
                calendarId=settings.PRIMARY_CALENDAR_ID,
                body=body,
                sendUpdates=send_updates,
            )
            .execute()
        )
        event_id = event.get("id") or ""
        html = event.get("htmlLink") or ""
        log.info("[GOOGLE CALENDAR] Created LIVE event %s link=%s", event_id, html)
        return {
            "id": event_id,
            "event_id": event_id,
            "htmlLink": html,
            "summary": event.get("summary") or summary,
            "description": event.get("description") or description,
            "location": event.get("location") or location,
            "start": event.get("start") or {},
            "end": event.get("end") or {},
            # Prefer local plan emails (incl. nexus.ai) when Google omitted them
            "attendees": event.get("attendees") or [{"email": e} for e in emails],
            "mock": False,
            "auth_error": None,
        }
    except Exception as e:
        log.error("[GOOGLE CALENDAR] Insert failed: %s", e)
        reason = f"Calendar insert failed: {e}"
        if not allow_mock:
            raise CalendarAuthError(
                f"{reason}. If token is revoked, run: python scripts/google_auth_setup.py"
            ) from e
        return _mock_event_payload(
            summary=summary,
            location=location,
            description=description,
            emails=emails,
            start_dt=start_dt,
            end_dt=end_dt,
            reason=reason,
        )


def maps_url_for(location: str, lat: float | None = None, lng: float | None = None) -> str:
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    return f"https://www.google.com/maps/search/?api=1&query={quote(location or 'Pune')}"


def setup_calendar_watch(webhook_url: str, channel_id: str = "nexus-concierge-watch") -> dict[str, Any] | None:
    """Register Google Calendar watch channel. Returns None without live OAuth."""
    service = get_calendar_service()
    if not service:
        log.warning("[GOOGLE CALENDAR] Skip watch setup — no live OAuth (%s)", webhook_url)
        return None

    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": webhook_url,
        "token": settings.GOOGLE_PUBSUB_VERIFICATION_TOKEN,
    }

    try:
        watch_resp = service.events().watch(calendarId=settings.PRIMARY_CALENDAR_ID, body=body).execute()
        log.info("[GOOGLE CALENDAR] Watch channel established: %s", watch_resp)
        return watch_resp
    except Exception as e:
        log.error("[GOOGLE CALENDAR] Failed to establish watch channel: %s", e)
        return None
