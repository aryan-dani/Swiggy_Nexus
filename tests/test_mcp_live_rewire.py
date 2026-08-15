"""Alias + live body parse + catalog schema coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.mcp_aliases import (
    DINEOUT_CANONICAL,
    FOOD_CANONICAL,
    IM_CANONICAL,
    resolve_llm_tool,
    to_canonical,
    to_legacy_handler,
)
from backend.mcp_client import parse_live_mcp_body
from backend.tool_schemas import TOOLS, get_tool_names

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "mcp-live-catalog.json"


def test_canonical_roundtrip_food_menu():
    assert to_canonical("food", "get_menu") == "get_restaurant_menu"
    assert to_legacy_handler("food", "get_restaurant_menu") == "get_menu"
    assert to_canonical("food", "add_to_cart") == "update_food_cart"
    assert to_legacy_handler("food", "update_food_cart") == "add_to_cart"


def test_llm_aliases_map_to_canonical():
    assert resolve_llm_tool("food_add_to_cart") == ("food", "update_food_cart")
    assert resolve_llm_tool("food_get_menu") == ("food", "get_restaurant_menu")
    assert resolve_llm_tool("food_place_order") == ("food", "place_food_order")
    assert resolve_llm_tool("im_add_to_cart") == ("im", "update_cart")
    assert resolve_llm_tool("dineout_search_restaurants") == ("dineout", "search_restaurants_dineout")
    assert resolve_llm_tool("dineout_check_availability") == ("dineout", "get_available_slots")
    assert resolve_llm_tool("dineout_render_restaurants_dineout") == (
        "dineout",
        "render_restaurants_dineout",
    )


def test_parse_live_prefers_structured_content():
    body = {
        "jsonrpc": "2.0",
        "result": {
            "content": [{"type": "text", "text": "Found 1 address (ID: abc)"}],
            "structuredContent": {
                "addresses": [{"id": "abc123", "addressTag": "Home"}],
                "total": 1,
            },
        },
    }
    env = parse_live_mcp_body(body)
    assert env["success"] is True
    data = env["data"]
    assert data["addresses"][0]["addressId"] == "abc123"
    assert data["addresses"][0]["label"] == "Home"


def test_parse_tools_list_result():
    body = {
        "jsonrpc": "2.0",
        "result": {"tools": [{"name": "get_addresses", "inputSchema": {}}]},
    }
    env = parse_live_mcp_body(body)
    assert env["success"] is True
    assert env["data"][0]["name"] == "get_addresses"


@pytest.mark.skipif(not CATALOG.exists(), reason="catalog not generated")
def test_schemas_cover_live_catalog():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    live_names: set[tuple[str, str]] = set()
    for server, blob in (catalog.get("servers") or {}).items():
        for t in blob.get("tools") or []:
            live_names.add((server, t["name"]))

    # Every live tool must resolve from some LLM schema name
    llm_names = get_tool_names()
    mapped = set()
    for n in llm_names:
        try:
            mapped.add(resolve_llm_tool(n))
        except KeyError:
            pytest.fail(f"schema tool not aliasable: {n}")

    missing = live_names - mapped
    assert not missing, f"Catalog tools missing from LLM schemas: {sorted(missing)}"

    assert len(TOOLS) >= 40  # 44 live as of 2026-08-15
    assert len(FOOD_CANONICAL) == 18
    assert len(IM_CANONICAL) == 14
    assert len(DINEOUT_CANONICAL) == 12


def test_fixture_get_addresses_shape():
    path = ROOT / "docs" / "mcp-fixtures" / "food" / "get_addresses.json"
    if not path.exists():
        pytest.skip("fixture missing")
    blob = json.loads(path.read_text(encoding="utf-8"))
    data = blob.get("data") or {}
    assert "addresses" in data or "_keys" in data
