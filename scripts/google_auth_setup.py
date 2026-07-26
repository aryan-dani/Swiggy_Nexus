"""One-time Google Calendar OAuth — writes credentials/google_token.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREDS = ROOT / "credentials" / "google_credentials.json"
TOKEN = ROOT / "credentials" / "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main() -> None:
    if not CREDS.exists():
        raise SystemExit(
            f"Missing {CREDS}. Download Desktop OAuth client JSON from Google Cloud Console."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
        print(f"Wrote {TOKEN}")
    else:
        print(f"Token already valid: {TOKEN}")


if __name__ == "__main__":
    main()
