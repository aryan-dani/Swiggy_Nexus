"""Shared pytest fixtures for Swiggy Nexus tests."""
from __future__ import annotations

import os
import pytest

# Ensure we can import from the project root
# (pytest.ini / pyproject.toml should set rootdir correctly)


@pytest.fixture(autouse=True)
def fresh_session(monkeypatch):
    """Reset the in-process session store before each test."""
    from mcp_server import session_store
    session_store._sessions.clear()
    yield
    session_store._sessions.clear()


@pytest.fixture(autouse=True)
def fresh_orders(monkeypatch):
    """Reset in-process order/booking stores before each test."""
    from mock_data import active_orders
    active_orders._food_orders.clear()
    active_orders._im_orders.clear()
    active_orders._bookings.clear()
    yield


@pytest.fixture()
def test_client():
    """FastAPI TestClient for API endpoint tests."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.fixture()
def mock_env(monkeypatch):
    """Remove GROQ_API_KEY to force deterministic mode."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    yield


@pytest.fixture()
def sample_address_id():
    return "addr_kp_001"


@pytest.fixture()
def sample_restaurant_id():
    """A restaurant ID that exists in the mock food catalog."""
    from mock_data.food_catalog import RESTAURANTS
    return RESTAURANTS[0]["restaurant_id"]


@pytest.fixture()
def sample_menu_item(sample_restaurant_id):
    """First item in the first category of the sample restaurant's menu."""
    from mock_data.food_catalog import MENU_BY_RESTAURANT
    menu = MENU_BY_RESTAURANT.get(sample_restaurant_id, {})
    cats = menu.get("categories", [])
    if not cats or not cats[0].get("items"):
        pytest.skip("No menu items available for test restaurant")
    return cats[0]["items"][0]
