"""Mock MCP unit tests."""
from __future__ import annotations

import pytest

from mcp_server.food.dispatcher import invoke as food_invoke
from mcp_server.im.dispatcher import invoke as im_invoke
from mcp_server.dineout.dispatcher import invoke as dine_invoke


@pytest.fixture(autouse=True)
def session_id():
    return "test_sess_unit"


def test_food_get_addresses():
    ok, data, err = food_invoke("get_addresses", {})
    assert ok and err is None
    assert len(data["addresses"]) >= 3
    assert "_latitude" not in data["addresses"][0]


def test_food_search_production_fields():
    ok, data, _ = food_invoke("search_restaurants", {"addressId": "addr_kp_001", "query": "pizza"})
    assert ok
    r0 = data["restaurants"][0]
    assert "availabilityStatus" in r0
    assert "distanceKm" in r0


def test_food_alias_get_restaurant_menu():
    ok, data, _ = food_invoke("get_restaurant_menu", {"restaurantId": "fd_dom_101", "addressId": "addr_kp_001"})
    assert ok
    assert data["restaurant_id"] == "fd_dom_101"


def test_food_session_cart():
    sid = "cart_test_food"
    ok, _, err = food_invoke(
        "update_food_cart",
        {
            "requestId": sid,
            "restaurantId": "fd_dom_101",
            "addressId": "addr_kp_001",
            "lines": [{"item_id": "dom_mar_med", "qty": 1}],
        },
    )
    assert ok and err is None
    ok2, cart, _ = food_invoke("get_food_cart", {"requestId": sid})
    assert ok2 and len(cart["items"]) == 1
    assert cart["availablePaymentMethods"] == ["COD"]


def test_im_spin_id_cart():
    sid = "cart_test_im"
    ok, _, err = im_invoke(
        "update_cart",
        {
            "requestId": sid,
            "selectedAddressId": "addr_kp_001",
            "items": [{"spinId": "spin_milk_500", "quantity": 4}, {"spinId": "spin_chips_lays", "quantity": 3}],
        },
    )
    assert ok and err is None
    ok2, cart, _ = im_invoke("get_cart", {"requestId": sid})
    assert ok2 and cart["total"] >= 99


def test_im_your_go_to_items():
    ok, data, _ = im_invoke("your_go_to_items", {"addressId": "addr_kp_001"})
    assert ok and len(data["products"]) >= 1


def test_dineout_saved_locations():
    ok, data, _ = dine_invoke("get_saved_locations", {})
    assert ok and len(data["locations"]) >= 3


def test_dineout_structured_slots():
    ok, data, _ = dine_invoke(
        "get_available_slots",
        {"restaurantId": "do_italian_804", "guestCount": 12, "date": "2026-07-12"},
    )
    assert ok
    assert isinstance(data["slots"][0], dict)
    assert "slotId" in data["slots"][0]


def test_dineout_alias_search():
    ok, data, _ = dine_invoke("search_restaurants_dineout", {"query": "italian", "latitude": 18.53, "longitude": 73.89})
    assert ok and len(data["restaurants"]) >= 1
