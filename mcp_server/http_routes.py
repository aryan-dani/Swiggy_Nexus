"""FastAPI routes for POST /food, /im, /dineout — JSON-RPC tools/list + tools/call.

Also accepts legacy ``{method, params}`` bodies for older clients.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from backend.mcp_aliases import to_legacy_handler
from mcp_server.facade import invoke_vertical

router = APIRouter(tags=["mock-mcp"])


def _tools_list_payload(vertical: str) -> dict[str, Any]:
    from backend.mcp_client import _list_tools_mock

    tools = _list_tools_mock(vertical)  # type: ignore[arg-type]
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": tools},
    }


def _call_result(vertical: str, name: str, arguments: dict[str, Any], req_id: Any = 1) -> dict[str, Any]:
    legacy = to_legacy_handler(vertical, name)  # type: ignore[arg-type]
    envelope = invoke_vertical(vertical, legacy, arguments)  # type: ignore[arg-type]
    if envelope.get("success"):
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": "ok"}],
                "structuredContent": envelope.get("data"),
            },
        }
    err = envelope.get("error") or {"message": "failure"}
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32000,
            "message": err.get("message", str(err)) if isinstance(err, dict) else str(err),
            "data": err,
        },
    }


async def _handle_mcp(vertical: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        return {"success": False, "error": {"code": "VALIDATION", "message": "JSON object required"}}

    # JSON-RPC
    if body.get("jsonrpc") == "2.0" or body.get("method") in ("tools/list", "tools/call"):
        rpc_method = body.get("method")
        req_id = body.get("id", 1)
        params = body.get("params") or {}
        if rpc_method == "tools/list":
            out = _tools_list_payload(vertical)
            out["id"] = req_id
            return out
        if rpc_method == "tools/call":
            name = (params.get("name") if isinstance(params, dict) else None) or ""
            arguments = (params.get("arguments") if isinstance(params, dict) else {}) or {}
            return _call_result(vertical, str(name), dict(arguments), req_id)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {rpc_method}"},
        }

    # Legacy {method, params}
    method = body.get("method")
    params = body.get("params") or {}
    return invoke_vertical(vertical, method, params)  # type: ignore[arg-type]


@router.post("/food")
async def post_food_mcp(request: Request) -> dict[str, Any]:
    return await _handle_mcp("food", request)


@router.post("/im")
async def post_im_mcp(request: Request) -> dict[str, Any]:
    return await _handle_mcp("im", request)


@router.post("/dineout")
async def post_dineout_mcp(request: Request) -> dict[str, Any]:
    return await _handle_mcp("dineout", request)
