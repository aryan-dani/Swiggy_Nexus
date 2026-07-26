"""Register a Google Calendar push notification channel (requires public BASE_URL)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")

TOKEN_PATH = Path(os.environ.get("GOOGLE_CALENDAR_TOKEN_PATH", "credentials/google_token.json"))
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
CAL_ID = os.environ.get("PRIMARY_CALENDAR_ID", "primary")
CHANNEL_TOKEN = os.environ.get("GOOGLE_PUBSUB_VERIFICATION_TOKEN", "nexus-pubsub-secret-token")


def main() -> None:
    if not BASE_URL or "localhost" in BASE_URL:
        raise SystemExit("Set public BASE_URL (ngrok / Render) before creating a watch channel")
    if not TOKEN_PATH.exists():
        raise SystemExit(f"Missing {TOKEN_PATH} — run scripts/google_auth_setup.py")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    service = build("calendar", "v3", credentials=creds)
    body = {
        "id": str(uuid.uuid4()),
        "type": "web_hook",
        "address": f"{BASE_URL}/webhooks/calendar",
        "token": CHANNEL_TOKEN,
    }
    resp = service.events().watch(calendarId=CAL_ID, body=body).execute()
    print(resp)


if __name__ == "__main__":
    main()
