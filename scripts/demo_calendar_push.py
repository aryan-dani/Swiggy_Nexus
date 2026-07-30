"""Replay a Google Calendar push at the concierge — one command, no ngrok.

Usage
-----
    python scripts/demo_calendar_push.py                    # hosting night (#host)
    python scripts/demo_calendar_push.py --mode dineout     # dinner out (#dineout)
    python scripts/demo_calendar_push.py --reset            # clear demo state first
    python scripts/demo_calendar_push.py --api http://127.0.0.1:8000

The payload mirrors what Google hands us on a real push, so the on-camera story is
identical to the live watch-channel path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")

DEFAULT_API = os.environ.get("NEXUS_API_BASE", "http://127.0.0.1:8000")
TICK_SECRET = os.environ.get("INTERNAL_TICK_SECRET", "nexus-tick-secret")

PAYLOADS = {
    "host": {
        "summary": "Housewarming with the team #host #swiggy",
        "description": "Hosting 8 people at home. Snacks + dinner please #host #swiggy",
        "location": "Home",
        "start_time": "Today 20:00",
        "attendee_emails": ["dani@nexus.ai", "priya@nexus.ai", "alex@nexus.ai"],
    },
    "dineout": {
        "summary": "Team dinner at Spesso #swiggy",
        "description": "Dinner out with the crew #dineout #swiggy",
        "location": "Italian Spesso",
        "start_time": "Today 20:30",
        "attendee_emails": ["dani@nexus.ai", "alex@nexus.ai"],
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--mode", choices=sorted(PAYLOADS), default="host")
    parser.add_argument("--reset", action="store_true", help="Clear demo state first")
    args = parser.parse_args()

    base = args.api.rstrip("/")

    with httpx.Client(timeout=90.0) as client:
        if args.reset:
            resp = client.post(
                f"{base}/internal/demo/reset",
                headers={"X-Nexus-Tick-Secret": TICK_SECRET},
            )
            print(f"reset → {resp.status_code} {resp.text[:200]}")

        payload = PAYLOADS[args.mode]
        print(f"\nPushing calendar event ({args.mode}):")
        print(json.dumps(payload, indent=2))

        resp = client.post(f"{base}/api/concierge/simulate/calendar", json=payload)
        if resp.status_code != 200:
            print(f"\nFAILED {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
            raise SystemExit(1)
        print(f"\naccepted → {resp.json()}")

    print(
        "\nThe graph is staging in the background. Watch Telegram for the Approve prompt,\n"
        "and the Concierge Ops timeline for the live tool trail."
    )


if __name__ == "__main__":
    main()
