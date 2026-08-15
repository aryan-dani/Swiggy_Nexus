"""Interactive Swiggy MCP OAuth 2.1 PKCE login (DCR + local callback).

Opens the browser for phone + OTP, captures the redirect on localhost,
exchanges the code for an access token, and writes credentials/swiggy_token.json.

Usage (repo root):
  python scripts/swiggy_oauth_login.py

Then smoke-test:
  python scripts/swiggy_mcp_smoke.py

Env (optional):
  SWIGGY_CLIENT_ID   — skip DCR if already registered
  SWIGGY_REDIRECT_URI — default http://127.0.0.1:8765/callback
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")

AUTH_BASE = "https://mcp.swiggy.com/auth"
DEFAULT_REDIRECT = "http://127.0.0.1:8765/callback"
TOKEN_PATH = Path("credentials/swiggy_token.json")


def _pkce() -> tuple[str, str]:
    import base64
    import hashlib
    import secrets

    verifier_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).decode("utf-8").rstrip("=")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def register_client(redirect_uri: str) -> str:
    existing = os.environ.get("SWIGGY_CLIENT_ID", "").strip()
    if existing:
        return existing
    payload = {
        "client_name": "Swiggy Nexus",
        "redirect_uris": [redirect_uri, "http://localhost:8765/callback"],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(f"{AUTH_BASE}/register", json=payload)
        resp.raise_for_status()
        data = resp.json()
    client_id = data.get("client_id")
    if not client_id:
        raise RuntimeError(f"DCR response missing client_id: {data}")
    print(f"DCR ok — client_id={client_id}")
    return str(client_id)


class _CallbackState:
    code: str | None = None
    error: str | None = None
    event = threading.Event()


def _serve_callback(redirect_uri: str, state: _CallbackState) -> HTTPServer:
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8765
    path = parsed.path or "/callback"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            req = urlparse(self.path)
            if req.path != path:
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(req.query)
            if qs.get("error"):
                state.error = qs["error"][0]
            else:
                state.code = (qs.get("code") or [None])[0]
            state.event.set()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Swiggy OAuth complete</h2>"
                b"<p>You can close this tab and return to the terminal.</p></body></html>"
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    httpd = HTTPServer((host, port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


async def exchange(code: str, verifier: str, redirect_uri: str, client_id: str) -> dict:
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{AUTH_BASE}/token", json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Token exchange failed ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
    data["expires_at"] = time.time() + float(data.get("expires_in", 432000))
    data["client_id"] = client_id
    data["obtained_at"] = time.time()
    return data


async def _run() -> None:
    redirect = os.environ.get("SWIGGY_REDIRECT_URI", DEFAULT_REDIRECT).strip() or DEFAULT_REDIRECT
    client_id = register_client(redirect)
    verifier, challenge = _pkce()
    import secrets

    oauth_state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": oauth_state,
        "scope": "mcp:tools mcp:resources mcp:prompts",
    }
    auth_url = f"{AUTH_BASE}/authorize?{urlencode(params)}"

    cb = _CallbackState()
    httpd = _serve_callback(redirect, cb)
    print("\n=== Swiggy MCP OAuth ===")
    print("1. Browser will open (or paste the URL below).")
    print("2. Complete phone + OTP on Swiggy.")
    print("3. You will be redirected to localhost — keep this terminal open.\n")
    print(auth_url)
    print()
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("Waiting for redirect (5 min timeout)…")
    ok = cb.event.wait(timeout=300)
    httpd.shutdown()
    if not ok:
        raise SystemExit("Timed out waiting for OAuth redirect.")
    if cb.error:
        raise SystemExit(f"OAuth error: {cb.error}")
    if not cb.code:
        raise SystemExit("No authorization code in redirect.")

    token = await exchange(cb.code, verifier, redirect, client_id)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Persist without printing the raw access_token
    to_store = {
        "access_token": token.get("access_token"),
        "token_type": token.get("token_type", "Bearer"),
        "expires_in": token.get("expires_in"),
        "expires_at": token.get("expires_at"),
        "scope": token.get("scope"),
        "client_id": client_id,
        "obtained_at": token.get("obtained_at"),
    }
    TOKEN_PATH.write_text(json.dumps(to_store, indent=2), encoding="utf-8")

    access = token.get("access_token") or ""
    print("\nSuccess. Token saved to credentials/swiggy_token.json")
    print(f"  token_type={token.get('token_type')} expires_in={token.get('expires_in')}s")
    print(f"  access_token length={len(access)} (value not printed)")
    print("\nAdd to backend/.env (do NOT commit):")
    print("  USE_MOCK_MCP=false")
    print("  SWIGGY_CLIENT_ID=" + client_id)
    print("  SWIGGY_OAUTH_TOKEN=<paste from credentials/swiggy_token.json access_token>")
    print("\nThen run:  python scripts/swiggy_mcp_smoke.py")


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as e:  # noqa: BLE001
        print(f"OAuth helper failed: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
