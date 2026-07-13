"""Tests for mcp_server/tool_aliases.py."""
from __future__ import annotations

import pytest
from mcp_server.tool_aliases import (
    DINEOUT_ALIASES,
    FOOD_ALIASES,
    IM_ALIASES,
    resolve_method,
)


# ---------------------------------------------------------------------------
# Food aliases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("public_name,expected", FOOD_ALIASES.items())
def test_food_aliases_resolve(public_name: str, expected: str):
    assert resolve_method("food", public_name) == expected


def test_food_unknown_method_passthrough():
    assert resolve_method("food", "custom_tool_xyz") == "custom_tool_xyz"


def test_food_strips_whitespace():
    assert resolve_method("food", "  get_restaurant_menu  ") == "get_menu"


# ---------------------------------------------------------------------------
# IM aliases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("public_name,expected", IM_ALIASES.items())
def test_im_aliases_resolve(public_name: str, expected: str):
    assert resolve_method("im", public_name) == expected


def test_im_unknown_method_passthrough():
    assert resolve_method("im", "brand_new_tool") == "brand_new_tool"


# ---------------------------------------------------------------------------
# Dineout aliases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("public_name,expected", DINEOUT_ALIASES.items())
def test_dineout_aliases_resolve(public_name: str, expected: str):
    assert resolve_method("dineout", public_name) == expected


def test_dineout_unknown_method_passthrough():
    assert resolve_method("dineout", "mystery_method") == "mystery_method"


# ---------------------------------------------------------------------------
# Unknown vertical
# ---------------------------------------------------------------------------

def test_unknown_vertical_passthrough():
    assert resolve_method("payments", "charge_card") == "charge_card"


# ---------------------------------------------------------------------------
# Critical alias spot-checks
# ---------------------------------------------------------------------------

def test_food_get_restaurant_menu_resolves_to_get_menu():
    assert resolve_method("food", "get_restaurant_menu") == "get_menu"


def test_food_update_food_cart_resolves_to_add_to_cart():
    assert resolve_method("food", "update_food_cart") == "add_to_cart"


def test_food_place_food_order_resolves_to_place_order():
    assert resolve_method("food", "place_food_order") == "place_order"


def test_im_update_cart_resolves_to_add_to_cart():
    assert resolve_method("im", "update_cart") == "add_to_cart"


def test_dineout_search_restaurants_dineout():
    assert resolve_method("dineout", "search_restaurants_dineout") == "search_restaurants"


def test_dineout_get_available_slots():
    assert resolve_method("dineout", "get_available_slots") == "check_availability"
