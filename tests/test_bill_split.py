"""Bill Split share math + API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.store import init_durable_tables
from app.main import app
from app.services.bill_split import compute_split

client = TestClient(app)


def setup_function():
    init_durable_tables()


def test_equal_split_sums_to_total():
    result = compute_split(1000, ["a@x.com", "b@x.com", "c@x.com"])
    amounts = [s["amount_inr"] for s in result["shares"]]
    assert sum(amounts) == 1000
    assert amounts == [334, 333, 333]  # remainder to host


def test_split_rounding_remainder_goes_to_host():
    result = compute_split(1001, ["dani@nexus.ai", "priya@nexus.ai", "alex@nexus.ai"])
    shares = result["shares"]
    assert shares[0]["is_host"] is True
    assert shares[0]["amount_inr"] == 335
    assert shares[1]["amount_inr"] == shares[2]["amount_inr"] == 333
    assert sum(s["amount_inr"] for s in shares) == 1001
    assert shares[0]["name"] == "Dani"  # Taste Vault name mapping


def test_split_upi_links_contain_amount():
    result = compute_split(600, ["a@x.com", "b@x.com"])
    for s in result["shares"]:
        assert s["upi_link"].startswith("upi://pay?")
        assert f"am={s['amount_inr']}" in s["upi_link"]


def test_split_rejects_bad_input():
    with pytest.raises(ValueError):
        compute_split(0, ["a@x.com"])
    with pytest.raises(ValueError):
        compute_split(500, [])


def test_split_endpoint():
    res = client.post(
        "/api/concierge/split",
        json={"total_inr": 900, "attendees": ["dani@nexus.ai", "priya@nexus.ai"], "title": "Test dinner"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_inr"] == 900
    assert len(body["shares"]) == 2
    assert sum(s["amount_inr"] for s in body["shares"]) == 900

    bad = client.post("/api/concierge/split", json={"total_inr": -5, "attendees": ["a@x.com"]})
    assert bad.status_code == 422
