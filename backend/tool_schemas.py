"""Tool schemas generated from docs/mcp-live-catalog.json (+ Nexus helpers).

Run ``python scripts/swiggy_mcp_tools_list.py`` then restart the API after catalog changes.
LLM-facing names stay prefixed (``food_*``, ``im_*``, ``dineout_*``) and map via
``backend.mcp_aliases.resolve_llm_tool`` to canonical MCP names.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.mcp_aliases import llm_alias_for

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "docs" / "mcp-live-catalog.json"

# Prefer stable LLM names for common tools (HITL / prompts already use these).
_PREFERRED_LLM_NAME: dict[tuple[str, str], str] = {
    ("food", "get_restaurant_menu"): "food_get_menu",
    ("food", "update_food_cart"): "food_add_to_cart",
    ("food", "place_food_order"): "food_place_order",
    ("im", "update_cart"): "im_add_to_cart",
    ("dineout", "search_restaurants_dineout"): "dineout_search_restaurants",
    ("dineout", "get_available_slots"): "dineout_check_availability",
}


def _load_catalog() -> dict[str, Any]:
    if not _CATALOG_PATH.exists():
        return {"servers": {}}
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def _openai_tool(server: str, tool: dict[str, Any]) -> dict[str, Any]:
    canonical = str(tool.get("name") or "")
    llm_name = _PREFERRED_LLM_NAME.get((server, canonical)) or llm_alias_for(server, canonical)  # type: ignore[arg-type]
    schema = tool.get("inputSchema") or {"type": "object", "properties": {}}
    if not isinstance(schema, dict):
        schema = {"type": "object", "properties": {}}
    # Ensure OpenAI-compatible parameters object
    params = {
        "type": schema.get("type") or "object",
        "properties": schema.get("properties") or {},
    }
    if "required" in schema:
        params["required"] = schema["required"]
    desc = (tool.get("description") or canonical).strip()
    if tool.get("money"):
        desc = "[REQUIRES USER APPROVAL] " + desc
    return {
        "type": "function",
        "function": {
            "name": llm_name,
            "description": desc[:1500],
            "parameters": params,
        },
    }


def _build_vertical_tools() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = _load_catalog()
    servers = catalog.get("servers") or {}
    food = [_openai_tool("food", t) for t in (servers.get("food") or {}).get("tools") or []]
    im = [_openai_tool("im", t) for t in (servers.get("im") or {}).get("tools") or []]
    dineout = [_openai_tool("dineout", t) for t in (servers.get("dineout") or {}).get("tools") or []]
    return food, im, dineout


_FOOD_TOOLS, _IM_TOOLS, _DINEOUT_TOOLS = _build_vertical_tools()

TOOLS: list[dict[str, Any]] = [*_FOOD_TOOLS, *_IM_TOOLS, *_DINEOUT_TOOLS]

_NEXUS_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "nexus_plan_night_out",
            "description": (
                "Schedule a Google Calendar dinner invite, stage a Dineout table, "
                "and prepare equal bill split after Approve. "
                "ONLY call when the user already gave guests AND restaurant AND time/slot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "guests": {"type": "array", "items": {"type": "string"}},
                    "venue": {"type": "string"},
                    "guest_count": {"type": "integer"},
                    "slot": {"type": "string"},
                    "start_iso": {"type": "string"},
                },
                "required": ["guests", "venue"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexus_plan_dinner_party",
            "description": (
                "Schedule a home dinner-party Calendar invite, stage Food/Instamart carts, "
                "and equal-split after Approve."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "guests": {"type": "array", "items": {"type": "string"}},
                    "dish_query": {"type": "string"},
                    "guest_count": {"type": "integer"},
                },
                "required": ["guests"],
            },
        },
    },
]

TELEGRAM_TOOLS: list[dict[str, Any]] = [*TOOLS, *_NEXUS_TOOLS]


def _short_desc(text: str, limit: int = 90) -> str:
    first = (text or "").split(".")[0].strip()
    if not first:
        return ""
    if len(first) <= limit:
        return first
    return first[: limit - 1].rstrip() + "…"


def _tools_for_llm(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import copy

    out: list[dict[str, Any]] = []
    for tool in tools:
        t = copy.deepcopy(tool)
        fn = t.get("function") or {}
        fn["description"] = _short_desc(str(fn.get("description") or fn.get("name") or ""))
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        for prop in props.values():
            if isinstance(prop, dict) and "description" in prop:
                prop["description"] = _short_desc(str(prop["description"]), limit=60)
        out.append(t)
    return out


TOOLS_FOR_LLM: list[dict[str, Any]] = _tools_for_llm(TOOLS)
TELEGRAM_TOOLS_FOR_LLM: list[dict[str, Any]] = _tools_for_llm(TELEGRAM_TOOLS)

_VERTICAL_MAP: dict[str, list[dict[str, Any]]] = {
    "food": _FOOD_TOOLS,
    "im": _IM_TOOLS,
    "dineout": _DINEOUT_TOOLS,
}


def get_tools_for_vertical(vertical: str) -> list[dict[str, Any]]:
    return list(_VERTICAL_MAP.get(vertical, []))


def get_tool_names() -> list[str]:
    return [t["function"]["name"] for t in TOOLS]
