"""One-command pre-demo checklist — PASS/FAIL for each surface before recording.

Usage
-----
    # With API already running on :8000 and (for local rehearsal) Ollama up:
    .\\backend\\.venv\\Scripts\\python.exe scripts\\demo_preflight.py

    # Against a different base:
    python scripts/demo_preflight.py --api http://127.0.0.1:8000

Expect LLM_PROVIDER=ollama in backend/.env for local rehearsal without Gemini.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")

DEFAULT_API = os.environ.get("NEXUS_API_BASE", "http://127.0.0.1:8000")
TICK_SECRET = os.environ.get("INTERNAL_TICK_SECRET", "nexus-tick-secret")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")


def _ok(label: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"PASS  {label}{suffix}")


def _fail(label: str, detail: str) -> None:
    print(f"FAIL  {label} - {detail}")


def _check_health(client: httpx.Client, base: str) -> bool:
    try:
        r = client.get(f"{base}/health")
        if r.status_code == 200:
            _ok("API /health", r.json().get("status", "ok"))
            return True
        _fail("API /health", f"HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        _fail("API /health", f"{e} (is uvicorn running on {base}?)")
    return False


def _check_agent(client: httpx.Client, base: str) -> bool:
    try:
        r = client.get(f"{base}/api/concierge/agent")
        body = r.json()
        provider = body.get("provider")
        label = body.get("label", "")
        if r.status_code != 200:
            _fail("Agent brain", f"HTTP {r.status_code}")
            return False
        want_ollama = os.environ.get("LLM_PROVIDER", "").strip().lower() == "ollama"
        if want_ollama and provider != "ollama":
            _fail(
                "Agent brain",
                f"expected provider=ollama (LLM_PROVIDER=ollama), got {provider} ({label})",
            )
            return False
        if provider == "none":
            _fail("Agent brain", "no LLM configured")
            return False
        _ok("Agent brain", f"{label} (provider={provider})")
        return True
    except Exception as e:  # noqa: BLE001
        _fail("Agent brain", str(e))
        return False


def _check_ollama() -> bool:
    want = os.environ.get("LLM_PROVIDER", "").strip().lower() == "ollama"
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5.0)
        if r.status_code != 200:
            msg = f"HTTP {r.status_code} at {OLLAMA_BASE}"
            if want:
                _fail("Ollama reachable", msg)
                return False
            print(f"SKIP  Ollama reachable — {msg} (LLM_PROVIDER != ollama)")
            return True
        names = {m.get("name", "") for m in (r.json().get("models") or [])}
        # Ollama may list "qwen2.5:7b-instruct" or with digest suffix
        found = any(
            n == OLLAMA_MODEL or n.startswith(f"{OLLAMA_MODEL}") or OLLAMA_MODEL in n
            for n in names
        )
        if found:
            _ok("Ollama reachable", f"{OLLAMA_MODEL} present at {OLLAMA_BASE}")
            return True
        msg = f"model {OLLAMA_MODEL!r} not in tags ({sorted(names)[:8]}…)"
        if want:
            _fail("Ollama reachable", msg)
            return False
        print(f"SKIP  Ollama reachable — {msg}")
        return True
    except Exception as e:  # noqa: BLE001
        if want:
            _fail("Ollama reachable", f"{e} — run `ollama serve`")
            return False
        print(f"SKIP  Ollama reachable — {e}")
        return True


def _check_reset(client: httpx.Client, base: str) -> bool:
    try:
        r = client.post(
            f"{base}/internal/demo/reset",
            headers={"X-Nexus-Tick-Secret": TICK_SECRET},
        )
        if r.status_code == 200:
            _ok("Demo reset", f"cleared={list((r.json() or {}).get('cleared', {}).keys())[:4]}…")
            return True
        _fail("Demo reset", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:  # noqa: BLE001
        _fail("Demo reset", str(e))
    return False


def _check_paneer() -> bool:
    try:
        # Direct mock MCP — same path the agent uses.
        from backend.mcp_client import call_tool

        data = call_tool(
            "food",
            "search_menu",
            {"query": "paneer biryani", "addressId": "addr_kp_001"},
        )
        items = (data or {}).get("items") or []
        hit = any(
            (i.get("itemId") or i.get("item_id")) == "bh_paneer"
            or "paneer biryani" in str(i.get("name", "")).lower()
            for i in items
        )
        if hit:
            _ok("Paneer search", "bh_paneer / Paneer Biryani found")
            return True
        _fail("Paneer search", f"no paneer biryani in {len(items)} hits")
    except Exception as e:  # noqa: BLE001
        _fail("Paneer search", str(e))
    return False


def _check_calendar(client: httpx.Client, base: str) -> bool:
    payload = {
        "summary": "Preflight hosting #host #swiggy",
        "description": "Preflight calendar approval #host #swiggy",
        "location": "Home",
        "start_time": "Today 19:00",
        "attendee_emails": ["dani@nexus.ai", "priya@nexus.ai"],
    }
    try:
        r = client.post(f"{base}/api/concierge/simulate/calendar", json=payload)
        if r.status_code != 200 or r.json().get("status") != "accepted":
            _fail("Calendar", f"{r.status_code} {r.text[:160]}")
            return False
        event_id = r.json().get("event_id")
        # Background graph on a live server — poll approvals briefly.
        pending: list[dict[str, Any]] = []
        for _ in range(40):
            time.sleep(0.5)
            apr = client.get(f"{base}/api/concierge/approvals", params={"status": "PENDING"})
            pending = (apr.json() or {}).get("items") or []
            if any(a.get("event_id") == event_id for a in pending):
                _ok("Calendar", f"PENDING approval for {event_id}")
                return True
            st = client.get(f"{base}/api/concierge/status/{event_id}")
            if st.status_code == 200 and st.json().get("approval_status") == "PENDING":
                _ok("Calendar", f"PENDING via status for {event_id}")
                return True
        _fail("Calendar", f"no PENDING approval within ~20s (event_id={event_id})")
    except Exception as e:  # noqa: BLE001
        _fail("Calendar", str(e))
    return False


def _check_split(client: httpx.Client, base: str) -> bool:
    try:
        r = client.post(
            f"{base}/api/concierge/split",
            json={
                "total_inr": 900,
                "attendees": ["dani@nexus.ai", "priya@nexus.ai"],
                "title": "Preflight split",
            },
        )
        body = r.json()
        shares = body.get("shares") or []
        if r.status_code == 200 and shares and all("upi_link" in s for s in shares):
            _ok("Bill split", f"{len(shares)} UPI shares")
            return True
        _fail("Bill split", f"{r.status_code} {str(body)[:160]}")
    except Exception as e:  # noqa: BLE001
        _fail("Bill split", str(e))
    return False


def _check_pantry(client: httpx.Client, base: str) -> bool:
    try:
        r = client.get(f"{base}/api/concierge/pantry")
        items = (r.json() or {}).get("items") or []
        if r.status_code == 200 and items:
            _ok("Pantry", f"{len(items)} SKUs")
            return True
        _fail("Pantry", f"empty or HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        _fail("Pantry", str(e))
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    args = parser.parse_args()
    base = args.api.rstrip("/")

    print(f"Swiggy Nexus demo preflight -> {base}")
    print(f"LLM_PROVIDER={os.environ.get('LLM_PROVIDER', '(unset)')}  OLLAMA_MODEL={OLLAMA_MODEL}\n")

    results: list[bool] = []
    with httpx.Client(timeout=60.0) as client:
        results.append(_check_health(client, base))
        results.append(_check_agent(client, base))
        results.append(_check_ollama())
        results.append(_check_reset(client, base))
        results.append(_check_paneer())
        results.append(_check_calendar(client, base))
        results.append(_check_split(client, base))
        results.append(_check_pantry(client, base))

    print("\n--- Manual (cannot fully automate) ---")
    print("1. Telegram: order a paneer biryani... (Approve on HITL)")
    print("2. Chat UI: Run 60s WOW demo")
    print("3. Voice note / Ops: Reject once to show the money gate")
    print("4. For final camera take with Gemini footer: set LLM_PROVIDER=auto + GEMINI_API_KEY")

    failed = sum(1 for x in results if not x)
    print(f"\n{sum(1 for x in results if x)}/{len(results)} automated checks passed.")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    # Ensure repo root is importable for paneer MCP check
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)
    main()
