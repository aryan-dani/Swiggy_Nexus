"""Telegram agent — write-tool interception, read passthrough, dispatch wiring."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.api import hitl
from app.db.store import get_approval, init_durable_tables, list_approvals
from app.services import telegram_agent as ta


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _quiet_telegram(monkeypatch: pytest.MonkeyPatch):
    """Capture outbound Telegram traffic instead of hitting the network."""
    sent: list[dict[str, Any]] = []

    async def fake_post(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sent.append({"method": method, **payload})
        return {"result": {"message_id": len(sent)}}

    monkeypatch.setattr(ta, "_post", fake_post)
    init_durable_tables()
    return sent


def test_write_tools_are_the_three_money_tools():
    assert ta.WRITE_TOOLS == {"food_place_order", "im_checkout", "dineout_book_table"}


def test_split_tool_and_address_defaults():
    assert ta._split_tool("food_search_restaurants") == ("food", "search_restaurants")
    assert ta._split_tool("im_get_cart") == ("im", "get_cart")
    assert ta._split_tool("dineout_book_table") == ("dineout", "book_table")

    filled = ta._with_defaults("im", "search_products", {"query": "milk"})
    assert filled["selectedAddressId"]
    assert filled["addressId"]

    # Explicit address wins
    kept = ta._with_defaults("food", "search_restaurants", {"addressId": "addr_x"})
    assert kept["addressId"] == "addr_x"

    geo = ta._with_defaults("dineout", "search_restaurants", {})
    assert geo["latitude"] and geo["longitude"]


def test_dineout_booking_is_staged_not_booked(_quiet_telegram):
    """dineout_book_table must produce a PENDING approval, never a live booking."""
    before = {a["request_id"] for a in list_approvals("PENDING")}

    result = _run(
        ta._stage_write_tool(
            123,
            "dineout_book_table",
            {"restaurantId": "do_italian_804", "guestCount": 4, "slot": "20:00"},
        )
    )

    assert result[ta.HALT_KEY] is True
    assert result["status"] == "awaiting_human_approval"

    request_id = result["request_id"]
    assert request_id not in before
    approval = get_approval(request_id)
    assert approval["status"] == "PENDING"
    assert approval["trigger_type"] == "voice_order"
    payload = approval["staged_payload"]
    assert payload["mode"] == "DINEOUT"
    assert payload["source"] == "telegram_agent"
    assert payload["dineout_plan"]["restaurantId"] == "do_italian_804"
    assert payload["dineout_plan"]["guestCount"] == 4

    # Approve/Reject buttons were offered with the shared callback contract
    buttons = [m for m in _quiet_telegram if m.get("reply_markup")]
    assert buttons, "expected an inline keyboard"
    rows = buttons[-1]["reply_markup"]["inline_keyboard"][0]
    assert rows[0]["callback_data"] == f"approve:{request_id}"
    assert rows[1]["callback_data"] == f"reject:{request_id}"


def test_empty_cart_checkout_errors_without_staging(_quiet_telegram):
    """No cart means no approval — the model gets a plain error to recover from."""
    from mcp_server.session_store import reset_all_sessions

    reset_all_sessions()
    before = len(list_approvals("PENDING"))

    result = _run(ta._stage_write_tool(123, "im_checkout", {}))

    assert result["status"] == "error"
    assert ta.HALT_KEY not in result
    assert len(list_approvals("PENDING")) == before


def test_instamart_checkout_stages_real_cart_lines(_quiet_telegram):
    """Stage from the live MCP cart so Approve checks out exactly what was shown."""
    from app.mcp.client import mcp_client
    from mcp_server.session_store import reset_all_sessions

    reset_all_sessions()
    _run(
        mcp_client.call_tool_async(
            "im",
            "update_cart",
            {
                "selectedAddressId": "addr_kp_001",
                "items": [{"spinId": "spin_cola_2l", "quantity": 2}],
            },
        )
    )

    result = _run(ta._stage_write_tool(123, "im_checkout", {}))
    assert result[ta.HALT_KEY] is True

    payload = get_approval(result["request_id"])["staged_payload"]
    items = payload["staged_im_cart"]["items"]
    assert [i["spinId"] for i in items] == ["spin_cola_2l"]
    assert items[0]["quantity"] == 2
    assert items[0]["name"]  # Instamart lines carry product names
    assert payload["staged_im_cart"]["estimated_total_inr"] > 0


def test_food_cart_lines_expose_dish_names():
    """The approval card renders names, so the mock cart must return them."""
    from app.mcp.client import mcp_client
    from mcp_server.session_store import reset_all_sessions

    reset_all_sessions()
    cart = _run(
        mcp_client.call_tool_async(
            "food",
            "add_to_cart",
            {
                "restaurantId": "fd_biryani_106",
                "addressId": "addr_kp_001",
                "lines": [{"item_id": "bh_chicken", "qty": 1}],
            },
        )
    )
    names = [line.get("name") for line in cart["items"]]
    assert names == ["Chicken Biryani"]


def test_free_text_routes_to_agent(monkeypatch: pytest.MonkeyPatch):
    """A non-command message must reach the LLM agent, not fall through silently."""
    seen: dict[str, Any] = {}

    async def fake_agent(chat_id, text, source="text"):
        seen["chat_id"] = chat_id
        seen["text"] = text
        seen["source"] = source
        return {"ok": True}

    monkeypatch.setattr(ta, "run_telegram_agent", fake_agent)

    out = _run(
        hitl.process_telegram_update(
            {"message": {"chat": {"id": 42}, "text": "order paneer biryani"}}
        )
    )
    assert out == {"ok": "agent"}
    assert seen == {"chat_id": 42, "text": "order paneer biryani", "source": "text"}


def test_greetings_no_longer_shadow_the_agent(monkeypatch: pytest.MonkeyPatch):
    """'hi' used to be swallowed as help text; it should now reach the agent."""
    calls: list[str] = []

    async def fake_agent(chat_id, text, source="text"):
        calls.append(text)
        return {"ok": True}

    monkeypatch.setattr(ta, "run_telegram_agent", fake_agent)

    out = _run(hitl.process_telegram_update({"message": {"chat": {"id": 7}, "text": "hi"}}))
    assert out == {"ok": "agent"}
    assert calls == ["hi"]


def test_slash_help_still_handled(monkeypatch: pytest.MonkeyPatch):
    async def fake_reply(chat_id, text):
        return None

    monkeypatch.setattr(hitl, "_telegram_reply", fake_reply)
    out = _run(hitl.process_telegram_update({"message": {"chat": {"id": 7}, "text": "/help"}}))
    assert out == {"ok": "help"}


def test_voice_note_transcribes_then_runs_agent(monkeypatch: pytest.MonkeyPatch):
    import app.services.voice as voice_mod

    async def fake_transcribe(file_id: str) -> str:
        assert file_id == "voice-abc"
        return "get me milk and bread"

    async def fake_reply(chat_id, text):
        return None

    seen: dict[str, Any] = {}

    async def fake_agent(chat_id, text, source="text"):
        seen["text"] = text
        seen["source"] = source
        return {"ok": True}

    monkeypatch.setattr(voice_mod, "transcribe_telegram_voice", fake_transcribe)
    monkeypatch.setattr(hitl, "_telegram_reply", fake_reply)
    monkeypatch.setattr(ta, "run_telegram_agent", fake_agent)

    out = _run(
        hitl.process_telegram_update(
            {"message": {"chat": {"id": 9}, "voice": {"file_id": "voice-abc"}}}
        )
    )
    assert out == {"ok": "voice"}
    assert seen == {"text": "get me milk and bread", "source": "voice"}


def test_night_out_intent_matches_demo_sentence():
    assert ta.looks_like_night_out_intent(ta.DEMO_NIGHT_OUT_SENTENCE)
    assert ta.looks_like_night_out_intent(
        "plan a night out with friends this saturday dinner then drinks then split the bill"
    )
    assert ta.looks_like_night_out_intent("Can we plan a night out with friends?")
    assert not ta.looks_like_night_out_intent("order a paneer biryani for dinner")
    assert not ta.looks_like_night_out_intent("get me milk and bread")


def test_memory_helpers_importable_from_telegram_agent():
    """Regression: NameError on get_conversation_history left Thinking forever."""
    from backend.memory import get_conversation_history, save_turn

    assert callable(get_conversation_history)
    assert callable(save_turn)
    # Module must bind the same helpers (not leave them unbound locals).
    assert ta.get_conversation_history is get_conversation_history
    assert ta.save_turn is save_turn


def test_night_out_short_circuit_skips_llm(monkeypatch: pytest.MonkeyPatch, _quiet_telegram):
    """Demo NL sentence must stage Night Out without run_tool_conversation."""
    called_llm = {"n": 0}

    async def boom(*_a, **_k):
        called_llm["n"] += 1
        raise AssertionError("LLM must not run for night-out short-circuit")

    async def fake_plan(**kwargs):
        return {
            "status": "awaiting_approval",
            "venue": "6 Digs · Kothrud",
            "guest_count": 4,
            "approval_request_id": "REQ-TEST-NO",
        }

    monkeypatch.setattr(ta, "run_tool_conversation", boom)
    monkeypatch.setattr(ta, "plan_night_out", fake_plan)

    out = _run(ta.run_telegram_agent(99, ta.DEMO_NIGHT_OUT_SENTENCE, source="voice"))
    assert out["ok"] is True
    assert out["short_circuit"] == "night_out"
    assert out["provider"] == "deterministic"
    assert called_llm["n"] == 0

    edits = [m for m in _quiet_telegram if m.get("method") == "editMessageText"]
    assert edits, "Thinking bubble must be edited away"
    assert not any("Thinking" in str(m.get("text") or "") for m in edits[-1:])
    assert any(m.get("reply_markup") for m in _quiet_telegram)


def test_thinking_cleared_on_crash_before_llm(monkeypatch: pytest.MonkeyPatch, _quiet_telegram):
    """Any crash after Thinking is sent must edit the status bubble."""

    def boom_history(*_a, **_k):
        raise RuntimeError("simulated history failure")

    monkeypatch.setattr(ta, "get_conversation_history", boom_history)
    monkeypatch.setattr(ta, "looks_like_night_out_intent", lambda _t: False)

    out = _run(ta.run_telegram_agent(55, "order paneer biryani"))
    assert out["ok"] is False
    edits = [m for m in _quiet_telegram if m.get("method") == "editMessageText"]
    assert edits
    last = edits[-1].get("text") or ""
    assert "Thinking" not in last
    assert "⚠️" in last or "broke" in last.lower() or "Interrupted" in last
