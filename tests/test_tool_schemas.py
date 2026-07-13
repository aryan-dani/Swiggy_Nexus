"""Tests for backend/tool_schemas.py."""
from __future__ import annotations

import pytest
from backend.tool_schemas import TOOLS, get_tool_names, get_tools_for_vertical


# ---------------------------------------------------------------------------
# TOOLS list structure
# ---------------------------------------------------------------------------

def test_tools_is_non_empty_list():
    assert isinstance(TOOLS, list)
    assert len(TOOLS) > 0


def test_all_tools_have_required_keys():
    for t in TOOLS:
        assert "type" in t
        assert "function" in t
        func = t["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func


def test_all_tool_names_are_unique():
    names = get_tool_names()
    assert len(names) == len(set(names)), "Duplicate tool names detected"


def test_tool_count_matches_expected():
    names = get_tool_names()
    # At minimum: 10 food + 7 im + 6 dineout = 23
    assert len(names) >= 23


def test_all_tools_have_non_empty_description():
    for t in TOOLS:
        desc = t["function"]["description"]
        assert desc and len(desc.strip()) > 20, f"Tool {t['function']['name']} has a too-short description"


# ---------------------------------------------------------------------------
# Vertical filtering
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vertical,prefix", [
    ("food", "food_"),
    ("im", "im_"),
    ("dineout", "dineout_"),
])
def test_get_tools_for_vertical(vertical: str, prefix: str):
    tools = get_tools_for_vertical(vertical)
    assert len(tools) > 0
    for t in tools:
        assert t["function"]["name"].startswith(prefix), (
            f"Tool {t['function']['name']} in {vertical} vertical doesn't start with '{prefix}'"
        )


def test_unknown_vertical_returns_empty():
    tools = get_tools_for_vertical("payments")
    assert tools == []


def test_vertical_tools_are_subsets():
    food = get_tools_for_vertical("food")
    im = get_tools_for_vertical("im")
    dineout = get_tools_for_vertical("dineout")
    all_names = set(get_tool_names())
    for t in food + im + dineout:
        assert t["function"]["name"] in all_names


# ---------------------------------------------------------------------------
# Specific tool presence
# ---------------------------------------------------------------------------

def test_food_search_restaurants_has_sort_by():
    tools = get_tools_for_vertical("food")
    sr = next((t for t in tools if t["function"]["name"] == "food_search_restaurants"), None)
    assert sr is not None
    props = sr["function"]["parameters"]["properties"]
    assert "sortBy" in props


def test_dineout_book_table_has_guest_count():
    tools = get_tools_for_vertical("dineout")
    bt = next((t for t in tools if t["function"]["name"] == "dineout_book_table"), None)
    assert bt is not None
    props = bt["function"]["parameters"]["properties"]
    assert "guestCount" in props


def test_food_place_order_requires_address_id():
    tools = get_tools_for_vertical("food")
    po = next((t for t in tools if t["function"]["name"] == "food_place_order"), None)
    assert po is not None
    required = po["function"]["parameters"].get("required", [])
    assert "addressId" in required
