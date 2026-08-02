"""Calendar fetch honesty + webhook channel-token enforcement."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import google_calendar as gcal

client = TestClient(app)


def test_fetch_calendar_event_returns_none_without_service(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gcal, "get_calendar_service", lambda: None)
    assert gcal.fetch_calendar_event("primary", "evt_fake") is None


def test_update_description_and_watch_fail_closed_without_service(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(gcal, "get_calendar_service", lambda: None)
    assert gcal.update_calendar_event_description("evt_x", "new desc") is False
    assert gcal.setup_calendar_watch("https://example.com/hook") is None


def test_calendar_webhook_403_without_channel_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "GOOGLE_PUBSUB_VERIFICATION_TOKEN", "test-secret-token")
    res = client.post(
        "/webhooks/calendar",
        json={"id": "evt_no_token"},
        headers={"X-Goog-Resource-State": "exists"},
    )
    assert res.status_code == 403
    assert "token" in res.json()["detail"].lower()


def test_calendar_webhook_403_wrong_channel_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "GOOGLE_PUBSUB_VERIFICATION_TOKEN", "test-secret-token")
    res = client.post(
        "/webhooks/calendar",
        json={"id": "evt_bad_token"},
        headers={
            "X-Goog-Resource-State": "exists",
            "X-Goog-Channel-Token": "wrong",
        },
    )
    assert res.status_code == 403


def test_calendar_webhook_allows_when_token_matches(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "GOOGLE_PUBSUB_VERIFICATION_TOKEN", "test-secret-token")
    monkeypatch.setattr("app.api.webhooks.fetch_calendar_event", lambda *_a, **_k: None)
    res = client.post(
        "/webhooks/calendar",
        json={"id": "evt_ok"},
        headers={
            "X-Goog-Resource-State": "exists",
            "X-Goog-Channel-Token": "test-secret-token",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ignored"
    assert res.json()["reason"] == "event not found"


def test_calendar_webhook_skips_token_when_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "GOOGLE_PUBSUB_VERIFICATION_TOKEN", "")
    monkeypatch.setattr("app.api.webhooks.fetch_calendar_event", lambda *_a, **_k: None)
    res = client.post(
        "/webhooks/calendar",
        json={"id": "evt_open"},
        headers={"X-Goog-Resource-State": "exists"},
    )
    assert res.status_code == 200
