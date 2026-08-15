"""Call Swiggy MCP tools — live mcp.swiggy.com when token present, else local mock.

Feature flags:
- ``USE_MOCK_MCP=false`` → always live (requires Bearer token)
- ``USE_MOCK_MCP=true`` → always local mock / fixture replay
- unset: **live if** ``SWIGGY_OAUTH_TOKEN`` or ``credentials/swiggy_token.json`` exists,
  otherwise mock (CI / offline)

Live transport: JSON-RPC 2.0 ``tools/list`` + ``tools/call`` on
``https://mcp.swiggy.com/{food|im|dineout}``.

Mock path: in-process ``invoke_vertical`` (canonical names mapped to legacy handlers)
or fixture replay when ``MCP_REPLAY_FIXTURES=1``.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator, Literal

import httpx

from backend.mcp_aliases import to_canonical, to_legacy_handler
from mcp_server.facade import invoke_vertical

Vertical = Literal["food", "im", "dineout"]

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="mcp_http")

# Per-request override from chat context ``use_mock_mcp`` (frontend toggle).
_mock_override: ContextVar[bool | None] = ContextVar("mcp_mock_override", default=None)

_DEFAULT_LIVE = {
    "food": "https://mcp.swiggy.com/food",
    "im": "https://mcp.swiggy.com/im",
    "dineout": "https://mcp.swiggy.com/dineout",
}
_ENDPOINT_ENV = {
    "food": "SWIGGY_FOOD_ENDPOINT",
    "im": "SWIGGY_IM_ENDPOINT",
    "dineout": "SWIGGY_DINEOUT_ENDPOINT",
}

_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "docs" / "mcp-fixtures"


def _truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


def _load_bearer_token() -> str | None:
    token = os.environ.get("SWIGGY_OAUTH_TOKEN", "").strip()
    if token:
        return token
    for cand in (
        Path("credentials/swiggy_token.json"),
        Path("backend/credentials/swiggy_token.json"),
    ):
        if not cand.exists():
            continue
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            access = data.get("access_token")
            if isinstance(access, str) and access.strip():
                return access.strip()
        except Exception:
            continue
    return None


def live_token_configured() -> bool:
    return _load_bearer_token() is not None


def set_mock_mcp_override(use_mock: bool | None) -> Any:
    """Set per-request mock/live. Pass None to clear and fall back to env."""
    return _mock_override.set(use_mock)


def reset_mock_mcp_override(token: Any) -> None:
    _mock_override.reset(token)


@contextmanager
def mock_mcp_override(use_mock: bool | None) -> Iterator[None]:
    """Context manager for chat/Telegram request scopes."""
    tok = set_mock_mcp_override(use_mock)
    try:
        yield
    finally:
        reset_mock_mcp_override(tok)


def apply_mock_override_from_context(context: dict[str, Any] | None) -> Any:
    """Read ``use_mock_mcp`` from chat context; return token for reset_mock_mcp_override."""
    ctx = context or {}
    if "use_mock_mcp" not in ctx:
        return set_mock_mcp_override(None)
    raw = ctx.get("use_mock_mcp")
    if isinstance(raw, bool):
        return set_mock_mcp_override(raw)
    if isinstance(raw, str):
        return set_mock_mcp_override(raw.strip().lower() in ("1", "true", "yes"))
    return set_mock_mcp_override(bool(raw))


def use_mock_mcp() -> bool:
    """Prefer live when a token is present unless USE_MOCK_MCP / override forces mock."""
    override = _mock_override.get()
    if override is not None:
        return override
    raw = os.environ.get("USE_MOCK_MCP")
    if raw is not None and raw.strip() != "":
        if raw.strip().lower() in ("0", "false", "no"):
            return False
        if raw.strip().lower() in ("1", "true", "yes"):
            return True
    return _load_bearer_token() is None


def _client_tool_log(method: str, params: dict[str, Any], summary: str, path: str) -> None:
    print(f"[TOOL CALL] {method}")
    print(f"[ARGS] {json.dumps(params, default=str, ensure_ascii=False)}")
    print(f"[RESPONSE] {summary} [{path}]")


class LocalMCPError(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(json.dumps(payload))


def _summarize(envelope: dict[str, Any]) -> str:
    if envelope.get("success"):
        d = envelope.get("data")
        if isinstance(d, dict) and "restaurants" in d:
            return f"{len(d['restaurants'])} restaurants returned"
        if isinstance(d, dict) and "addresses" in d:
            return f"{len(d['addresses'])} addresses returned"
        if isinstance(d, dict) and "order_id" in d:
            return f"order placed {d.get('order_id')}"
        if isinstance(d, dict) and "booking_id" in d:
            return f"booking {d.get('booking_id')}"
        if isinstance(d, dict) and "products" in d:
            return f"{len(d['products'])} products"
        if isinstance(d, dict) and "cart_id" in d:
            return "cart updated"
        if isinstance(d, dict) and "categories" in d:
            return "menu loaded"
        if isinstance(d, dict) and "slots" in d:
            sl = d["slots"]
            return f"{len(sl)} slots"
        if isinstance(d, dict) and "locations" in d:
            return f"{len(d['locations'])} locations"
        if isinstance(d, dict) and "cleared" in d:
            return "cart cleared"
        if isinstance(d, dict) and "tools" in d:
            return f"{len(d['tools'])} tools"
        if isinstance(d, list):
            return f"{len(d)} tools"
        return "ok"
    err = envelope.get("error") or {}
    return f"error: {err.get('message', err)}"


def _live_endpoint(server: Vertical) -> str:
    env_key = _ENDPOINT_ENV[server]
    return os.environ.get(env_key, _DEFAULT_LIVE[server]).rstrip("/")


def _normalize_address(addr: dict[str, Any]) -> dict[str, Any]:
    out = dict(addr)
    aid = out.get("addressId") or out.get("id") or out.get("address_id")
    if aid is not None and str(aid).strip():
        out["addressId"] = str(aid)
    if not out.get("label"):
        tag = out.get("addressTag") or out.get("addressCategory")
        if tag:
            out["label"] = str(tag)
    return out


def _normalize_tool_data(data: Any) -> Any:
    if isinstance(data, list):
        if data and all(isinstance(x, dict) for x in data):
            if any("id" in x or "addressId" in x or "addressTag" in x for x in data):
                return {"addresses": [_normalize_address(x) for x in data]}
        return data
    if not isinstance(data, dict):
        return data
    out = dict(data)
    addrs = out.get("addresses")
    if isinstance(addrs, list):
        out["addresses"] = [
            _normalize_address(a) if isinstance(a, dict) else a for a in addrs
        ]
    return out


def _try_parse_json_text(text: str) -> Any | None:
    raw = text.strip()
    if not raw:
        return None
    candidates = [raw]
    if "```" in raw:
        parts = raw.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            if block.lstrip().lower().startswith("json"):
                block = block.split("\n", 1)[-1]
            candidates.insert(0, block.strip())
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return None


def _parse_live_body(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize live JSON-RPC / MCP CallToolResult into {success, data|error}."""
    if "error" in body and "jsonrpc" in body:
        err = body["error"]
        if isinstance(err, dict):
            return {
                "success": False,
                "error": {
                    "code": err.get("code", "MCP_ERROR"),
                    "message": err.get("message", str(err)),
                },
            }
        return {"success": False, "error": {"code": "MCP_ERROR", "message": str(err)}}

    result = body.get("result", body)
    if isinstance(result, dict) and "success" in result:
        data = result.get("data")
        out = dict(result)
        if data is not None:
            out["data"] = _normalize_tool_data(data)
        return out

    if isinstance(result, dict) and result.get("structuredContent") is not None:
        sc = result["structuredContent"]
        if isinstance(sc, dict) and "success" in sc:
            data = sc.get("data")
            out = dict(sc)
            if data is not None:
                out["data"] = _normalize_tool_data(data)
            return out
        return {"success": True, "data": _normalize_tool_data(sc)}

    if isinstance(result, dict) and "content" in result:
        texts = []
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")))
        joined = "\n".join(texts).strip()
        if joined:
            parsed = _try_parse_json_text(joined)
            if parsed is not None:
                if isinstance(parsed, dict) and "success" in parsed:
                    data = parsed.get("data")
                    out = dict(parsed)
                    if data is not None:
                        out["data"] = _normalize_tool_data(data)
                    return out
                return {"success": True, "data": _normalize_tool_data(parsed)}
            return {"success": True, "data": {"raw_text": joined[:500]}}
        return {"success": True, "data": result}

    if isinstance(result, dict) and "data" in result:
        return {"success": True, "data": _normalize_tool_data(result.get("data"))}

    # tools/list: result.tools = [...]
    if isinstance(result, dict) and "tools" in result:
        return {"success": True, "data": result["tools"]}

    return {"success": True, "data": _normalize_tool_data(result)}


parse_live_mcp_body = _parse_live_body


def _live_headers() -> dict[str, str]:
    token = _load_bearer_token()
    if not token:
        raise LocalMCPError(
            {
                "code": "UNAUTHENTICATED",
                "message": (
                    "No SWIGGY_OAUTH_TOKEN (or credentials/swiggy_token.json). "
                    "Run: python scripts/swiggy_oauth_login.py"
                ),
            }
        )
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }


def _post_live_jsonrpc(server: Vertical, payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = _live_endpoint(server)
    headers = _live_headers()

    def _post() -> dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 401:
                return {
                    "success": False,
                    "error": {
                        "code": "UNAUTHENTICATED",
                        "message": "Swiggy OAuth token expired — re-run swiggy_oauth_login.py",
                    },
                }
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            if "text/event-stream" in ctype:
                for line in resp.text.splitlines():
                    if line.startswith("data:"):
                        chunk = line[5:].strip()
                        if chunk and chunk != "[DONE]":
                            return _parse_live_body(json.loads(chunk))
                raise LocalMCPError(
                    {"code": "EMPTY_SSE", "message": "No data frames in MCP SSE response"}
                )
            return _parse_live_body(resp.json())

    return _executor.submit(_post).result(timeout=120.0)


def _call_live(server: Vertical, method: str, params: dict[str, Any]) -> dict[str, Any]:
    canonical = to_canonical(server, method)
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": canonical, "arguments": params or {}},
        "id": 1,
    }
    return _post_live_jsonrpc(server, payload)


def list_tools(server: Vertical) -> list[dict[str, Any]]:
    """JSON-RPC tools/list against live (or catalog file when mocking)."""
    if use_mock_mcp():
        return _list_tools_mock(server)

    payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
    envelope = _post_live_jsonrpc(server, payload)
    if not envelope.get("success"):
        err = envelope.get("error") or {"message": "tools/list failed"}
        raise LocalMCPError(err if isinstance(err, dict) else {"message": str(err)})
    data = envelope.get("data")
    if isinstance(data, list):
        return [t for t in data if isinstance(t, dict)]
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        return [t for t in data["tools"] if isinstance(t, dict)]
    return []


def _list_tools_mock(server: Vertical) -> list[dict[str, Any]]:
    catalog = Path(__file__).resolve().parents[1] / "docs" / "mcp-live-catalog.json"
    if catalog.exists():
        try:
            blob = json.loads(catalog.read_text(encoding="utf-8"))
            tools = (blob.get("servers") or {}).get(server, {}).get("tools") or []
            return [
                {
                    "name": t.get("name"),
                    "description": t.get("description"),
                    "inputSchema": t.get("inputSchema") or {},
                }
                for t in tools
                if isinstance(t, dict) and t.get("name")
            ]
        except Exception:
            pass
    # Minimal fallback from aliases module
    from backend.mcp_aliases import FOOD_CANONICAL, IM_CANONICAL, DINEOUT_CANONICAL

    names = {
        "food": FOOD_CANONICAL,
        "im": IM_CANONICAL,
        "dineout": DINEOUT_CANONICAL,
    }[server]
    return [{"name": n, "description": n, "inputSchema": {"type": "object"}} for n in sorted(names)]


def _replay_fixture(server: Vertical, method: str) -> dict[str, Any] | None:
    if not _truthy("MCP_REPLAY_FIXTURES", "0"):
        return None
    canonical = to_canonical(server, method)
    path = _FIXTURE_ROOT / server / f"{canonical}.json"
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(blob, dict) and "data" in blob:
            return {"success": True, "data": blob["data"]}
        if isinstance(blob, dict) and blob.get("success") is True:
            return blob
        return {"success": True, "data": blob}
    except Exception:
        return None


def call_tool(server: Vertical, method: str, params: dict[str, Any]) -> Any:
    """Execute one tool call; raises LocalMCPError on logical failure.

    ``method`` may be canonical (``update_food_cart``) or legacy (``add_to_cart``).
    Live always sends the canonical name.
    """
    canonical = to_canonical(server, method)
    params = dict(params or {})

    if not use_mock_mcp():
        envelope = _call_live(server, canonical, params)
        summary = _summarize(
            envelope if isinstance(envelope, dict) else {"success": True, "data": envelope}
        )
        _client_tool_log(canonical, params, summary, f"LIVE POST /{server}")
        if envelope.get("success"):
            return envelope.get("data")
        err = envelope.get("error") or {"code": "UNKNOWN", "message": "failure"}
        raise LocalMCPError(err if isinstance(err, dict) else {"message": str(err)})

    # Fixture replay (CI / offline with captured shapes)
    replayed = _replay_fixture(server, canonical)
    if replayed is not None:
        summary = _summarize(replayed)
        _client_tool_log(canonical, params, summary, f"REPLAY /{server}")
        if replayed.get("success"):
            return replayed.get("data")
        err = replayed.get("error") or {"code": "UNKNOWN", "message": "failure"}
        raise LocalMCPError(err if isinstance(err, dict) else {"message": str(err)})

    legacy = to_legacy_handler(server, canonical)
    base = os.environ.get("LOCAL_MCP_BASE", "http://127.0.0.1:8000").rstrip("/")
    path_seg = {"food": "food", "im": "im", "dineout": "dineout"}[server]
    http_mode = _truthy("LOCAL_MCP_HTTP", "0")

    if http_mode:

        def _post() -> dict[str, Any]:
            url = f"{base}/{path_seg}"
            # Prefer JSON-RPC so local matches live
            body = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": canonical, "arguments": params},
                "id": 1,
            }
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, json=body)
                # Fallback to legacy {method, params} if server is old
                if r.status_code == 422:
                    r = client.post(url, json={"method": legacy, "params": params})
                r.raise_for_status()
                raw = r.json()
                if "jsonrpc" in raw or "result" in raw:
                    return _parse_live_body(raw)
                return raw

        envelope = _executor.submit(_post).result(timeout=120.0)
    else:
        envelope = invoke_vertical(server, legacy, params)

    summary = _summarize(envelope)
    path_label = "inproc" if not http_mode else f"POST /{path_seg}"
    _client_tool_log(canonical, params, summary, path_label)

    if envelope.get("success"):
        return envelope["data"]

    err = envelope.get("error") or {"code": "UNKNOWN", "message": "failure"}
    raise LocalMCPError(err if isinstance(err, dict) else {"message": str(err)})


def unwrap_dict(data: Any) -> dict[str, Any]:
    return data if isinstance(data, dict) else {}
