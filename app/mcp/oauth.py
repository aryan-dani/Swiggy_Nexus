"""OAuth 2.1 PKCE authentication manager for Swiggy MCP platform.

Handles PKCE code verifier / challenge generation, auth token storage,
expiration checks, and auto-refresh mechanisms.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.config import settings


class SwiggyOAuthPKCE:
    """OAuth 2.1 PKCE manager for Swiggy MCP Streamable HTTP endpoints."""

    def __init__(self, token_path: str | None = None) -> None:
        self.auth_base_url = "https://mcp.swiggy.com/auth"
        self.token_path = Path(token_path or settings.GOOGLE_CALENDAR_TOKEN_PATH).parent / "swiggy_token.json"
        self.token_data: dict[str, Any] = self._load_token()

    def generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge (S256)."""
        verifier_bytes = secrets.token_bytes(32)
        code_verifier = base64.urlsafe_b64encode(verifier_bytes).decode("utf-8").rstrip("=")
        
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        return code_verifier, code_challenge

    def get_authorization_url(self, redirect_uri: str, state: str | None = None) -> tuple[str, str]:
        """Build the authorization URL for user consent with PKCE."""
        code_verifier, code_challenge = self.generate_pkce_pair()
        state = state or secrets.token_urlsafe(16)
        
        params = {
            "response_type": "code",
            # DCR typically issues client_id "swiggy-mcp"; prefer env if set.
            "client_id": settings.SWIGGY_CLIENT_ID or "swiggy-mcp",
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "scope": "mcp:tools mcp:resources mcp:prompts",
        }
        
        from urllib.parse import urlencode
        
        query_string = urlencode(params)
        auth_url = f"{self.auth_base_url}/authorize?{query_string}"
        return auth_url, code_verifier

    async def exchange_code_for_token(
        self, code: str, code_verifier: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Exchange authorization code for JWT access token."""
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "client_id": settings.SWIGGY_CLIENT_ID or "swiggy-mcp",
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{self.auth_base_url}/token", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Add calculated expiration time (seconds)
            data["expires_at"] = time.time() + data.get("expires_in", 432000)
            self.save_token(data)
            return data

    def _load_token(self) -> dict[str, Any]:
        """Load stored access token from disk or settings."""
        if settings.SWIGGY_OAUTH_TOKEN:
            return {
                "access_token": settings.SWIGGY_OAUTH_TOKEN,
                "token_type": "Bearer",
                "expires_at": time.time() + 86400 * 365,
            }
            
        if self.token_path.exists():
            try:
                with open(self.token_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_token(self, token_data: dict[str, Any]) -> None:
        """Persist token data to disk."""
        self.token_data = token_data
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)
        except Exception:
            pass

    def get_valid_access_token(self) -> str | None:
        """Return valid Bearer token or None if missing/expired."""
        token = self.token_data.get("access_token")
        expires_at = self.token_data.get("expires_at", 0)
        
        # Buffer of 60 seconds
        if token and time.time() < (expires_at - 60):
            return str(token)
            
        # Return static environment token if configured
        if settings.SWIGGY_OAUTH_TOKEN:
            return settings.SWIGGY_OAUTH_TOKEN
            
        return None
