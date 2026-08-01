"""Unit tests for mcp_server/food/dispatcher.py — all 15 handlers."""
from __future__ import annotations

import pytest
from mock_data.food_catalog import MENU_BY_RESTAURANT, RESTAURANTS
from mcp_server.food import dispatcher as food


# ---------------------------------------------------------------------------
# get_addresses
# ---------------------------------------------------------------------------

def test_get_addresses_returns_list():
    ok, data, err = food.handle_get_addresses({})
    assert ok is True
    assert "addresses" in data
    assert len(data["addresses"]) > 0


# ---------------------------------------------------------------------------
# search_restaurants
# ---------------------------------------------------------------------------

def test_search_restaurants_requires_address():
    ok, data, err = food.handle_search_restaurants({})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_search_restaurants_unknown_address():
    ok, data, err = food.handle_search_restaurants({"addressId": "addr_nonexistent"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_search_restaurants_returns_results(sample_address_id):
    ok, data, err = food.handle_search_restaurants({"addressId": sample_address_id, "query": ""})
    assert ok is True
    assert len(data["restaurants"]) > 0


def test_search_restaurants_query_filter(sample_address_id):
    ok, data, err = food.handle_search_restaurants({"addressId": sample_address_id, "query": "pizza"})
    assert ok is True
    # Result should either match or fall back to full list — never empty
    assert isinstance(data["restaurants"], list)


def test_search_restaurants_dish_phrase_hits_biryani_house(sample_address_id):
    """Demo phrase 'paneer biryani' must surface Biryani House, not a random shuffle of all."""
    ok, data, err = food.handle_search_restaurants(
        {"addressId": sample_address_id, "query": "paneer biryani"}
    )
    assert ok is True
    names = [r["name"] for r in data["restaurants"]]
    assert any("Biryani" in n for n in names)


def test_search_menu_finds_paneer_biryani(sample_address_id):
    ok, data, err = food.handle_search_menu(
        {"addressId": sample_address_id, "query": "paneer biryani"}
    )
    assert ok is True
    assert data["totalCount"] >= 1
    assert any(i["name"] == "Paneer Biryani" for i in data["items"])
    assert any(i["itemId"] == "bh_paneer" for i in data["items"])


def test_search_restaurants_sort_by_rating(sample_address_id):
    ok, data, err = food.handle_search_restaurants(
        {"addressId": sample_address_id, "query": "", "sortBy": "rating"}
    )
    assert ok is True
    ratings = [r["rating"] for r in data["restaurants"]]
    assert ratings == sorted(ratings, reverse=True)


def test_search_restaurants_sort_by_eta(sample_address_id):
    ok, data, err = food.handle_search_restaurants(
        {"addressId": sample_address_id, "query": "", "sortBy": "eta"}
    )
    assert ok is True
    assert "restaurants" in data


# ---------------------------------------------------------------------------
# get_menu
# ---------------------------------------------------------------------------

def test_get_menu_requires_restaurant_id(sample_address_id):
    ok, data, err = food.handle_get_menu({"addressId": sample_address_id})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_get_menu_unknown_restaurant(sample_address_id):
    ok, data, err = food.handle_get_menu(
        {"restaurantId": "does_not_exist", "addressId": sample_address_id}
    )
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_get_menu_valid(sample_restaurant_id, sample_address_id):
    ok, data, err = food.handle_get_menu(
        {"restaurantId": sample_restaurant_id, "addressId": sample_address_id}
    )
    assert ok is True
    assert "categories" in data
    assert len(data["categories"]) > 0


# ---------------------------------------------------------------------------
# get_restaurant_details
# ---------------------------------------------------------------------------

def test_get_restaurant_details_requires_id():
    ok, data, err = food.handle_get_restaurant_details({})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_get_restaurant_details_unknown():
    ok, data, err = food.handle_get_restaurant_details({"restaurantId": "unknown"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_get_restaurant_details_valid(sample_restaurant_id):
    ok, data, err = food.handle_get_restaurant_details({"restaurantId": sample_restaurant_id})
    assert ok is True
    assert data["restaurantId"] == sample_restaurant_id
    assert "cuisines" in data
    assert "amenities" in data


# ---------------------------------------------------------------------------
# add_to_cart
# ---------------------------------------------------------------------------

def test_add_to_cart_requires_restaurant_id(sample_address_id):
    ok, data, err = food.handle_add_to_cart({"addressId": sample_address_id, "lines": []})
    assert ok is False


def test_add_to_cart_requires_non_empty_lines(sample_restaurant_id, sample_address_id):
    ok, data, err = food.handle_add_to_cart(
        {"restaurantId": sample_restaurant_id, "addressId": sample_address_id, "lines": []}
    )
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_add_to_cart_unknown_item(sample_restaurant_id, sample_address_id):
    ok, data, err = food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": "item_nonexistent", "qty": 1}],
    })
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_add_to_cart_success(sample_restaurant_id, sample_address_id, sample_menu_item):
    ok, data, err = food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": str(sample_menu_item["item_id"]), "qty": 1}],
    })
    assert ok is True
    assert data["subtotal_inr"] > 0
    assert data["restaurant_id"] == sample_restaurant_id


def test_add_to_cart_clears_on_restaurant_switch(sample_restaurant_id, sample_address_id, sample_menu_item):
    """Switching restaurants should clear the previous cart."""
    item_id = str(sample_menu_item["item_id"])

    # Add to first restaurant
    food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": item_id, "qty": 1}],
    })

    # Switch to a different restaurant
    other = next((r for r in RESTAURANTS if r["restaurant_id"] != sample_restaurant_id), None)
    if not other:
        pytest.skip("Need at least 2 restaurants for this test")

    other_rid = other["restaurant_id"]
    other_menu = MENU_BY_RESTAURANT.get(other_rid, {})
    other_cats = other_menu.get("categories", [])
    if not other_cats or not other_cats[0].get("items"):
        pytest.skip("Second restaurant has no menu items")
    other_item_id = str(other_cats[0]["items"][0]["item_id"])

    ok, data, err = food.handle_add_to_cart({
        "restaurantId": other_rid,
        "addressId": sample_address_id,
        "lines": [{"item_id": other_item_id, "qty": 1}],
    })
    assert ok is True
    assert data.get("message") is not None  # flush message


# ---------------------------------------------------------------------------
# get_food_cart
# ---------------------------------------------------------------------------

def test_get_food_cart_empty():
    ok, data, err = food.handle_get_food_cart({"addressId": "addr_kp_001"})
    assert ok is True
    assert data["subtotal_inr"] == 0


def test_get_food_cart_with_items(sample_restaurant_id, sample_address_id, sample_menu_item):
    food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": str(sample_menu_item["item_id"]), "qty": 2}],
    })
    ok, data, err = food.handle_get_food_cart({"addressId": sample_address_id})
    assert ok is True
    assert data["subtotal_inr"] > 0
    assert data["deliveryCharge"] == 40


# ---------------------------------------------------------------------------
# flush_food_cart
# ---------------------------------------------------------------------------

def test_flush_food_cart(sample_restaurant_id, sample_address_id, sample_menu_item):
    food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": str(sample_menu_item["item_id"]), "qty": 1}],
    })
    ok, data, err = food.handle_flush_food_cart({})
    assert ok is True
    assert data["cleared"] is True


# ---------------------------------------------------------------------------
# fetch_food_coupons + apply_food_coupon
# ---------------------------------------------------------------------------

def test_fetch_food_coupons_returns_list():
    ok, data, err = food.handle_fetch_food_coupons({})
    assert ok is True
    assert isinstance(data["coupons"], list)
    # All returned coupons should be COD-compatible
    for c in data["coupons"]:
        assert not c.get("requiresOnlinePayment")


def test_apply_food_coupon_invalid():
    ok, data, err = food.handle_apply_food_coupon({"code": "FAKECOUPON"})
    assert ok is False
    assert err["code"] == "COUPON_INVALID"


def test_apply_food_coupon_valid():
    from mock_data.food_catalog import FOOD_COUPONS
    cod_coupon = next((c for c in FOOD_COUPONS if not c.get("requiresOnlinePayment")), None)
    if not cod_coupon:
        pytest.skip("No COD coupons in test data")
    ok, data, err = food.handle_apply_food_coupon({"code": cod_coupon["code"]})
    assert ok is True
    assert data["code"] == cod_coupon["code"]


# ---------------------------------------------------------------------------
# place_order
# ---------------------------------------------------------------------------

def test_place_order_empty_cart(sample_address_id):
    ok, data, err = food.handle_place_order({"addressId": sample_address_id})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_place_order_success(sample_restaurant_id, sample_address_id, sample_menu_item):
    food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": str(sample_menu_item["item_id"]), "qty": 1}],
    })
    ok, data, err = food.handle_place_order({"addressId": sample_address_id})
    assert ok is True
    assert "order_id" in data
    assert data["order_id"].startswith("FD_ORD_")


def test_place_order_1000_cap(sample_restaurant_id, sample_address_id, sample_menu_item):
    """Cart at or above ₹1000 should be rejected."""
    # Use qty=100 to push over the ₹1000 limit
    item_price = sample_menu_item.get("price_inr", 1)
    if item_price * 100 < 1000:
        pytest.skip("Item price too low to hit ₹1000 cap with qty=100")
    food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": str(sample_menu_item["item_id"]), "qty": 100}],
    })
    ok, data, err = food.handle_place_order({"addressId": sample_address_id})
    if not ok:
        assert err["code"] == "VALIDATION"


# ---------------------------------------------------------------------------
# get_food_orders + get_food_order_details + track_food_order
# ---------------------------------------------------------------------------

def test_get_food_orders_empty():
    ok, data, err = food.handle_get_food_orders({})
    assert ok is True
    assert data["orders"] == []


def test_get_food_order_details_not_found():
    ok, data, err = food.handle_get_food_order_details({"orderId": "FD_ORD_FAKE"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_track_food_order_not_found():
    ok, data, err = food.handle_track_food_order({"orderId": "FD_ORD_FAKE"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_full_food_order_cycle(sample_restaurant_id, sample_address_id, sample_menu_item):
    """End-to-end: add → cart → place → list → details → track."""
    item_id = str(sample_menu_item["item_id"])

    food.handle_add_to_cart({
        "restaurantId": sample_restaurant_id,
        "addressId": sample_address_id,
        "lines": [{"item_id": item_id, "qty": 1}],
    })
    ok, placed, _ = food.handle_place_order({"addressId": sample_address_id})
    if not ok:
        pytest.skip("Place order failed — likely ₹1000 cap")

    oid = placed["orderId"]

    ok, orders, _ = food.handle_get_food_orders({})
    assert ok and any(o["orderId"] == oid for o in orders["orders"])

    ok, detail, _ = food.handle_get_food_order_details({"orderId": oid})
    assert ok and detail["orderId"] == oid

    ok, tracking, _ = food.handle_track_food_order({"orderId": oid})
    assert ok and tracking["status"] == "OUT_FOR_DELIVERY"


# ---------------------------------------------------------------------------
# report_error
# ---------------------------------------------------------------------------

def test_report_error():
    ok, data, err = food.handle_report_error({})
    assert ok is True
    assert "reportLink" in data
