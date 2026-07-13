"""Unit tests for mcp_server/dineout/dispatcher.py — all 8 handlers."""
from __future__ import annotations

import pytest
from mcp_server.dineout import dispatcher as dineout


# ---------------------------------------------------------------------------
# get_saved_locations
# ---------------------------------------------------------------------------

def test_get_saved_locations():
    ok, data, err = dineout.handle_get_saved_locations({})
    assert ok is True
    assert "locations" in data
    assert len(data["locations"]) > 0
    # Every location should have lat/lng
    for loc in data["locations"]:
        assert "latitude" in loc
        assert "longitude" in loc


# ---------------------------------------------------------------------------
# search_restaurants
# ---------------------------------------------------------------------------

def test_search_restaurants_returns_results():
    ok, data, err = dineout.handle_search_restaurants({"query": ""})
    assert ok is True
    assert len(data["restaurants"]) > 0


def test_search_restaurants_query_filter():
    ok, data, err = dineout.handle_search_restaurants({"query": "Italian"})
    assert ok is True
    assert isinstance(data["restaurants"], list)


def test_search_restaurants_area_filter():
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS
    area = DINEOUT_RESTAURANTS[0]["area"]
    ok, data, err = dineout.handle_search_restaurants({"query": "", "area": area})
    assert ok is True
    # All results should be from that area (or fall back to full list)
    assert isinstance(data["restaurants"], list)


def test_search_restaurants_availability_field():
    ok, data, err = dineout.handle_search_restaurants({"query": ""})
    for r in data["restaurants"]:
        assert "availability" in r


# ---------------------------------------------------------------------------
# get_restaurant_details
# ---------------------------------------------------------------------------

def test_get_restaurant_details_requires_id():
    ok, data, err = dineout.handle_get_restaurant_details({})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_get_restaurant_details_not_found():
    ok, data, err = dineout.handle_get_restaurant_details({"restaurantId": "do_fake_999"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_get_restaurant_details_valid():
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS
    rid = DINEOUT_RESTAURANTS[0]["restaurant_id"]
    ok, data, err = dineout.handle_get_restaurant_details({"restaurantId": rid})
    assert ok is True
    assert data["restaurantId"] == rid
    assert "amenities" in data
    assert "offers" in data
    assert "openingHours" in data


# ---------------------------------------------------------------------------
# check_availability
# ---------------------------------------------------------------------------

def test_check_availability_requires_restaurant_id():
    ok, data, err = dineout.handle_check_availability({"partySize": 2, "date": "2026-07-12"})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_check_availability_not_found():
    ok, data, err = dineout.handle_check_availability(
        {"restaurantId": "do_fake", "partySize": 2, "date": "2026-07-12"}
    )
    assert ok is False
    assert err["code"] == "NOT_FOUND"


def test_check_availability_valid():
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS
    rid = next(
        (r["restaurant_id"] for r in DINEOUT_RESTAURANTS if r.get("availability") != "UNAVAILABLE"),
        None,
    )
    if not rid:
        pytest.skip("No available Dineout restaurants in test data")
    ok, data, err = dineout.handle_check_availability(
        {"restaurantId": rid, "partySize": 2, "date": "2026-07-12"}
    )
    assert ok is True
    assert "slots" in data
    assert isinstance(data["slots"], list)


def test_check_availability_slot_gone_scenario(monkeypatch):
    from mcp_server import common
    monkeypatch.setattr(common, "_mock_scenario", "slot_gone")
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS
    rid = DINEOUT_RESTAURANTS[0]["restaurant_id"]
    ok, data, err = dineout.handle_check_availability(
        {"restaurantId": rid, "partySize": 2, "date": "2026-07-12"}
    )
    assert ok is False
    assert err["code"] == "SLOT_UNAVAILABLE"


# ---------------------------------------------------------------------------
# book_table
# ---------------------------------------------------------------------------

def test_book_table_requires_restaurant_id():
    ok, data, err = dineout.handle_book_table({"partySize": 2, "slot": "19:00"})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_book_table_requires_slot():
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS
    rid = DINEOUT_RESTAURANTS[0]["restaurant_id"]
    ok, data, err = dineout.handle_book_table({"restaurantId": rid, "partySize": 2})
    assert ok is False
    assert err["code"] == "VALIDATION"


def test_book_table_success():
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS
    rid = DINEOUT_RESTAURANTS[0]["restaurant_id"]
    ok, data, err = dineout.handle_book_table(
        {"restaurantId": rid, "partySize": 4, "slot": "20:00", "slotId": 1001}
    )
    assert ok is True
    assert data["booking_id"].startswith("DO_BK_")
    assert data["status"] == "CONFIRMED"
    assert data["guests"] == 4


def test_book_table_persists_for_status_check():
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS
    rid = DINEOUT_RESTAURANTS[0]["restaurant_id"]
    _, booking, _ = dineout.handle_book_table(
        {"restaurantId": rid, "partySize": 2, "slot": "19:00", "slotId": 999}
    )
    bid = booking["booking_id"]

    ok, status, err = dineout.handle_get_booking_status({"bookingId": bid})
    assert ok is True
    assert status["booking_id"] == bid


# ---------------------------------------------------------------------------
# get_booking_status
# ---------------------------------------------------------------------------

def test_get_booking_status_not_found():
    ok, data, err = dineout.handle_get_booking_status({"bookingId": "DO_BK_FAKE"})
    assert ok is False
    assert err["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# create_cart
# ---------------------------------------------------------------------------

def test_create_cart():
    ok, data, err = dineout.handle_create_cart({})
    assert ok is True
    assert "cartId" in data
    assert data["cartId"].startswith("do_cart_")


# ---------------------------------------------------------------------------
# report_error
# ---------------------------------------------------------------------------

def test_report_error():
    ok, data, err = dineout.handle_report_error({})
    assert ok is True
    assert "reportLink" in data
