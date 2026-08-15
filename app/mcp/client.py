"""Asynchronous Swiggy MCP Client Layer.

Communicates with Swiggy's 3 endpoints (Food, Instamart, Dineout) using
Streamable HTTP JSON-RPC 2.0 or in-process local mock dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Literal, Optional

import httpx

from app.config import settings
from app.mcp.oauth import SwiggyOAuthPKCE
from backend.mcp_client import (
    LocalMCPError,
    parse_live_mcp_body,
    call_tool as call_mock_tool,
)

log = logging.getLogger(__name__)

Vertical = Literal["food", "im", "dineout"]


class SwiggyMCPError(RuntimeError):
    """Exception raised when Swiggy MCP returns an error payload."""

    def __init__(self, error_data: dict[str, Any]) -> None:
        self.code = error_data.get("code", "MCP_ERROR")
        self.message = error_data.get("message", str(error_data))
        self.payload = error_data
        super().__init__(f"[{self.code}] {self.message}")


class AsyncSwiggyMCPClient:
    """Async client for Swiggy Model Context Protocol servers."""

    def __init__(self, oauth_manager: SwiggyOAuthPKCE | None = None) -> None:
        self.oauth = oauth_manager or SwiggyOAuthPKCE()
        self.endpoints: dict[Vertical, str] = {
            "food": settings.SWIGGY_FOOD_ENDPOINT,
            "im": settings.SWIGGY_IM_ENDPOINT,
            "dineout": settings.SWIGGY_DINEOUT_ENDPOINT,
        }

    async def call_tool_async(
        self,
        vertical: Vertical,
        method: str,
        params: dict[str, Any],
        max_retries: int = 3,
    ) -> Any:
        """Call a tool on the specified Swiggy MCP vertical with error handling & retries."""
        log.info(f"[MCP CLIENT] Calling {vertical}.{method} with params: {params}")

        # Local mock mode handling
        if settings.USE_MOCK_MCP:
            return await self._call_local_mock(vertical, method, params)

        # Production Streamable HTTP MCP mode
        endpoint = self.endpoints[vertical]
        token = self.oauth.get_valid_access_token()

        from backend.mcp_aliases import to_canonical

        canonical = to_canonical(vertical, method)

        headers = {
            "Content-Type": "application/json",
            # Match live Streamable HTTP clients (JSON or SSE data frames).
            "Accept": "application/json, text/event-stream",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # JSON-RPC 2.0 envelope payload for Swiggy MCP
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": canonical,
                "arguments": params,
            },
            "id": 1,
        }

        delay = 0.5
        last_exception: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(endpoint, json=json_rpc_payload, headers=headers)

                    if resp.status_code == 401:
                        raise SwiggyMCPError({
                            "code": "UNAUTHENTICATED",
                            "message": "Swiggy OAuth access token is expired or invalid.",
                        })

                    resp.raise_for_status()
                    ctype = (resp.headers.get("content-type") or "").lower()
                    if "text/event-stream" in ctype:
                        body = None
                        for line in resp.text.splitlines():
                            if line.startswith("data:"):
                                chunk = line[5:].strip()
                                if chunk and chunk != "[DONE]":
                                    body = json.loads(chunk)
                                    break
                        if body is None:
                            raise SwiggyMCPError(
                                {
                                    "code": "EMPTY_SSE",
                                    "message": "No data frames in MCP SSE response",
                                }
                            )
                    else:
                        body = resp.json()

                    envelope = parse_live_mcp_body(body if isinstance(body, dict) else {})
                    if envelope.get("success"):
                        return envelope.get("data")
                    err_data = envelope.get("error") or {"message": "Operation failed"}
                    raise SwiggyMCPError(
                        err_data if isinstance(err_data, dict) else {"message": str(err_data)}
                    )

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_exception = e
                log.warning(
                    f"[MCP CLIENT] Attempt {attempt}/{max_retries} failed for {vertical}.{method}: {e}"
                )
                if attempt == max_retries:
                    break
                await asyncio.sleep(delay)
                delay *= 2

        raise SwiggyMCPError({
            "code": "HTTP_FAILURE",
            "message": f"Failed to execute MCP tool {vertical}.{method}: {last_exception}",
        })

    async def _call_local_mock(
        self, vertical: Vertical, method: str, params: dict[str, Any]
    ) -> Any:
        """Bridge to local mock MCP infrastructure asynchronously."""
        loop = asyncio.get_running_loop()
        try:
            # Run in thread pool to avoid blocking async loop
            return await loop.run_in_executor(
                None, call_mock_tool, vertical, method, params
            )
        except LocalMCPError as e:
            raise SwiggyMCPError(e.payload)
        except Exception as e:
            raise SwiggyMCPError({"code": "MOCK_ERROR", "message": str(e)})


# Global client instance
mcp_client = AsyncSwiggyMCPClient()
