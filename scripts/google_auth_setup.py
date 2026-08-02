"""One-time Google Calendar OAuth — writes credentials/google_token.json.

Re-run whenever you see mock_cal links or CalendarAuthError / invalid_grant.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREDS = ROOT / "credentials" / "google_credentials.json"
TOKEN = ROOT / "credentials" / "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main() -> None:
    if not CREDS.exists():
        raise SystemExit(
            f"Missing {CREDS}. Download Desktop OAuth client JSON from Google Cloud Console "
            "(APIs → Google Calendar API → Credentials → Desktop app)."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if TOKEN.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        except Exception as e:
            print(f"Existing token unreadable ({e}) — starting fresh OAuth.")
            creds = None

    if creds and creds.valid:
        print(f"Token already valid: {TOKEN}")
        print("Live Calendar inserts should work. Try Night out · 6 Digs again.")
        return

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
            print(f"Refreshed token → {TOKEN}")
            return
        except Exception as e:
            print(f"Refresh failed ({e}). Opening browser for a new consent…")
            try:
                TOKEN.unlink(missing_ok=True)
            except TypeError:
                if TOKEN.exists():
                    TOKEN.unlink()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS), SCOPES)
    # port=0 picks a free port; browser opens for Google consent
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print(f"Wrote fresh token → {TOKEN}")
    print("Done. Restart the API, then run Night out · 6 Digs — Calendar link will be live.")


if __name__ == "__main__":
    main()
