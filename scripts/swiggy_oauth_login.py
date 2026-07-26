"""Interactive helper for Swiggy MCP OAuth 2.1 PKCE (staging)."""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")


async def _run() -> None:
    from app.mcp.oauth import SwiggyOAuthPKCE

    oauth = SwiggyOAuthPKCE()
    redirect = "http://127.0.0.1:8765/callback"
    url, verifier = oauth.get_authorization_url(redirect)
    print("Open this URL, complete phone OTP, then paste the ?code= value:\n")
    print(url)
    code = input("\nAuthorization code: ").strip()
    if not code:
        raise SystemExit("No code")
    token = await oauth.exchange_code_for_token(code, verifier, redirect)
    print("\nSet in Render / .env:")
    print(f"SWIGGY_OAUTH_TOKEN={token.get('access_token')}")
    print("USE_MOCK_MCP=false")


def main() -> None:
    try:
        asyncio.run(_run())
    except Exception as e:  # noqa: BLE001
        print(f"OAuth helper failed: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
