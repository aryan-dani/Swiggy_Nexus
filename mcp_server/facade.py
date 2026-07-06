"""Route MCP-style method + params into the correct mock vertical."""

from __future__ import annotations

from typing import Any, Literal

from mcp_server.dineout.dispatcher import invoke as dineout_invoke
from mcp_server.food.dispatcher import invoke as food_invoke
from mcp_server.im.dispatcher import invoke as instamart_invoke

Vertical = Literal["food", "im", "dineout"]


def invoke_vertical(vertical: Vertical, method: str | None, params: dict[str, Any] | None) -> dict[str, Any]:
    ok: bool
    data: Any
    err: dict[str, Any] | None
    if vertical == "food":
        ok, data, err = food_invoke(method, params)
    elif vertical == "im":
        ok, data, err = instamart_invoke(method, params)
    else:
        ok, data, err = dineout_invoke(method, params)
    if ok:
        return {"success": True, "data": data}
    return {"success": False, "error": err or {"message": "Unknown error"}}