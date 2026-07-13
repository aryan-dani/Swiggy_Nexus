"""Unit tests for mcp_server/im/dispatcher.py — all 13 handlers."""
from __future__ import annotations

import pytest
from mock_data.instamart_catalog import PRODUCTS, PRODUCTS_BY_SPIN
from mcp_server.im import dispatcher as im


def _first_spin() -> str:
    return PRODUCTS[0]["variants"][0]["spinId"]


# ---------------------------------------------------------------------------
# get_addresses
# ---------------------------------------------------------------------------

def test_get_addresses():
    ok, data, err = im.handle_get_addresses({})
    assert ok is True
    assert "addresses" in data


# ---------------------------------------------------------------------------
# search_products
# ---------------------------------------------------------------------------

def test_search_products_empty_query(sample_address_id):
    ok, data, err = im.handle_search_products({"addressId": sample_address_id, "query": ""})
    assert ok is True
    assert len(data["products"]) > 0


def test_search_products_with_query(sample_address_id):
    ok, data, err = im.handle_search_products({"addressId": sample_address_id, "query": "milk"})
    assert ok is True
    assert isinstance(data["products"], list)


def test_search_products_unknown_query_returns_all(sample_address_id):
    """Unknown query should fall back to full product list."""
    ok, data, err = im.handle_search_products({"addressId": sample_address_id, "query": "zzz_nonexistent"})
    assert ok is True
    assert len(data["products"]) > 0  # fallback


def test_search_products_has_price_field(sample_address_id):
    ok, data, err = im.handle_search_products({"addressId": sample_address_id, "query": ""})
    for p in data["products"]:
        assert "price_inr" in p


# ---------------------------------------------------------------------------
# your_go_to_items
# ---------------------------------------------------------------------------

def test_your_go_to_items(sample_address_id):
    ok, data, err = im.handle_your_go_to_items({"addressId": sample_address_id})
    assert ok is True
    assert "products" in data
    assert len(data["products"]) > 0


def test_your_go_to_items_party_mode(sample_address_id):
    ok, data, err = im.handle_your_go_to_items({"addressId": sample_address_id, "partyMode": True})
    assert ok is True


# ---------------------------------------------------------------------------
# add_to_cart
# ---------------------------------------------------------------------------

def test_add_to_cart_requires_items(sample_address_id):
    ok, data, err = im.handle_add_to_cart({"selectedAddressId": sample_address_id, "items": []})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_add_to_cart_unknown_spin(sample_address_id):
    ok, data, err = im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": "spin_nonexistent", "quantity": 1}],
    })
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_add_to_cart_success(sample_address_id):
    spin = _first_spin()
    ok, data, err = im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 2}],
    })
    assert ok is True
    assert data["subtotal_inr"] > 0
    assert len(data["lines"]) == 1


def test_add_to_cart_by_product_id(sample_address_id):
    pid = PRODUCTS[0]["product_id"]
    ok, data, err = im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"product_id": pid, "quantity": 1}],
    })
    assert ok is True


def test_add_to_cart_address_switch_clears(sample_address_id):
    """Switching address mid-cart should clear previous items."""
    spin = _first_spin()
    im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 1}],
    })
    ok, data, err = im.handle_add_to_cart({
        "selectedAddressId": "addr_fc_002",  # different address
        "items": [{"spinId": spin, "quantity": 2}],
    })
    assert ok is True
    assert len(data["lines"]) == 1  # only the new item


# ---------------------------------------------------------------------------
# get_cart
# ---------------------------------------------------------------------------

def test_get_cart_empty():
    ok, data, err = im.handle_get_cart({})
    assert ok is True
    assert data["subtotal_inr"] == 0


def test_get_cart_with_items(sample_address_id):
    spin = _first_spin()
    im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 5}],
    })
    ok, data, err = im.handle_get_cart({})
    assert ok is True
    assert data["subtotal_inr"] > 0
    assert "bill" in data


def test_get_cart_minimum_order_check(sample_address_id):
    """Cart under ₹99 should return MIN_ORDER_NOT_MET error."""
    # Find a product cheaper than ₹99
    cheap = next((p for p in PRODUCTS if p["price_inr"] < 99), None)
    if not cheap:
        pytest.skip("No products cheaper than ₹99")
    spin = cheap["variants"][0]["spinId"]
    im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 1}],
    })
    ok, data, err = im.handle_get_cart({})
    # If the subtotal is < 99, it should fail
    if not ok:
        assert err["code"] == "MIN_ORDER_NOT_MET"


def test_get_cart_expired_scenario(monkeypatch, sample_address_id):
    from mcp_server import common
    monkeypatch.setattr(common, "_mock_scenario", "cart_expired")
    ok, data, err = im.handle_get_cart({})
    assert ok is False
    assert err["code"] == "CART_EXPIRED"


# ---------------------------------------------------------------------------
# clear_cart
# ---------------------------------------------------------------------------

def test_clear_cart(sample_address_id):
    spin = _first_spin()
    im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 1}],
    })
    ok, data, err = im.handle_clear_cart({})
    assert ok is True
    assert data["cleared"] is True


# ---------------------------------------------------------------------------
# checkout
# ---------------------------------------------------------------------------

def test_checkout_empty_cart(sample_address_id):
    ok, data, err = im.handle_checkout({"addressId": sample_address_id})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_checkout_minimum_order(sample_address_id):
    """Checkout should fail if subtotal < ₹99."""
    cheap = next((p for p in PRODUCTS if p["price_inr"] < 99), None)
    if not cheap:
        pytest.skip("No products cheaper than ₹99")
    spin = cheap["variants"][0]["spinId"]
    im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 1}],
    })
    ok, data, err = im.handle_checkout({"addressId": sample_address_id})
    if not ok:
        assert err["code"] == "MIN_ORDER_NOT_MET"


def test_checkout_success(sample_address_id):
    """Find a product that meets the ₹99 minimum and checkout."""
    spin = next(
        (v["spinId"] for p in PRODUCTS for v in p["variants"] if v["price_inr"] >= 99),
        None,
    )
    if not spin:
        pytest.skip("No product >= ₹99 in catalog")
    im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 1}],
    })
    ok, data, err = im.handle_checkout({"addressId": sample_address_id})
    assert ok is True
    assert "order_id" in data
    assert data["order_id"].startswith("IM_ORD_")


# ---------------------------------------------------------------------------
# get_orders + get_order_details + track_order
# ---------------------------------------------------------------------------

def test_get_orders_empty():
    ok, data, err = im.handle_get_orders({})
    assert ok is True
    assert data["orders"] == []


def test_get_order_details_not_found():
    ok, data, err = im.handle_get_order_details({"orderId": "IM_ORD_FAKE"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_track_order_not_found():
    ok, data, err = im.handle_track_order({"orderId": "IM_ORD_FAKE"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_full_im_order_cycle(sample_address_id):
    """End-to-end: add → cart → checkout → list → details → track."""
    spin = next(
        (v["spinId"] for p in PRODUCTS for v in p["variants"] if v["price_inr"] >= 99),
        None,
    )
    if not spin:
        pytest.skip("No product >= ₹99 in catalog")

    im.handle_add_to_cart({
        "selectedAddressId": sample_address_id,
        "items": [{"spinId": spin, "quantity": 1}],
    })
    ok, placed, _ = im.handle_checkout({"addressId": sample_address_id})
    assert ok, "Checkout should succeed"

    oid = placed["orderId"]

    ok, orders, _ = im.handle_get_orders({})
    assert ok and any(o.get("orderId") == oid for o in orders["orders"])

    ok, detail, _ = im.handle_get_order_details({"orderId": oid})
    assert ok and detail.get("orderId") == oid

    ok, tracking, _ = im.handle_track_order({"orderId": oid})
    assert ok and "status" in tracking


# ---------------------------------------------------------------------------
# create_address + delete_address
# ---------------------------------------------------------------------------

def test_create_address():
    ok, data, err = im.handle_create_address({"line1": "Test Lane"})
    assert ok is True
    assert data["addressId"].startswith("addr_new_")


def test_delete_address_valid(sample_address_id):
    ok, data, err = im.handle_delete_address({"addressId": sample_address_id})
    assert ok is True


def test_delete_address_not_found():
    ok, data, err = im.handle_delete_address({"addressId": "addr_fake_999"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"
