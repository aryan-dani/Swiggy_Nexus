"""Per-request mock/live MCP override from chat context."""

from __future__ import annotations

from backend.mcp_client import (
    apply_mock_override_from_context,
    iter_with_mock_override,
    parse_use_mock_from_context,
    reset_mock_mcp_override,
    set_mock_mcp_override,
    use_mock_mcp,
)


def test_override_forces_mock():
    apply_mock_override_from_context({"use_mock_mcp": True})
    try:
        assert use_mock_mcp() is True
    finally:
        reset_mock_mcp_override()


def test_override_forces_live_flag():
    apply_mock_override_from_context({"use_mock_mcp": False})
    try:
        assert use_mock_mcp() is False
    finally:
        reset_mock_mcp_override()


def test_missing_context_key_clears_override():
    set_mock_mcp_override(False)
    apply_mock_override_from_context({})
    try:
        # No override — env/token heuristic (pytest forces USE_MOCK_MCP=true)
        assert use_mock_mcp() is True
    finally:
        reset_mock_mcp_override()


def test_parse_use_mock_from_context():
    assert parse_use_mock_from_context({}) is None
    assert parse_use_mock_from_context({"use_mock_mcp": True}) is True
    assert parse_use_mock_from_context({"use_mock_mcp": False}) is False
    assert parse_use_mock_from_context({"use_mock_mcp": "true"}) is True


def test_iter_with_mock_override_reapplies_across_yields():
    def gen():
        assert use_mock_mcp() is False
        yield 1
        assert use_mock_mcp() is False
        yield 2

    out = list(iter_with_mock_override(gen(), False))
    assert out == [1, 2]
    # Cleared after iteration (pytest env → mock)
    assert use_mock_mcp() is True
