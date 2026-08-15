"""Per-request mock/live MCP override from chat context."""

from __future__ import annotations

from backend.mcp_client import (
    apply_mock_override_from_context,
    reset_mock_mcp_override,
    use_mock_mcp,
)


def test_override_forces_mock():
    tok = apply_mock_override_from_context({"use_mock_mcp": True})
    try:
        assert use_mock_mcp() is True
    finally:
        reset_mock_mcp_override(tok)


def test_override_forces_live_flag():
    tok = apply_mock_override_from_context({"use_mock_mcp": False})
    try:
        assert use_mock_mcp() is False
    finally:
        reset_mock_mcp_override(tok)


def test_missing_context_key_clears_override():
    tok = apply_mock_override_from_context({"use_mock_mcp": False})
    reset_mock_mcp_override(tok)
    tok2 = apply_mock_override_from_context({})
    try:
        # No override — env/token heuristic (pytest forces USE_MOCK_MCP=true)
        assert use_mock_mcp() is True
    finally:
        reset_mock_mcp_override(tok2)
