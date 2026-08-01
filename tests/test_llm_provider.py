"""LLM provider layer — schema conversion, provider selection, Groq fallback."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services import llm as llm_mod
from backend.tool_schemas import TOOLS, TOOLS_FOR_LLM, get_tool_names


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_shared_tool_list_is_single_source():
    """Orchestrator and async agent both use compact LLM schemas with the same 23 names."""
    from backend.llm_orchestrator import TOOLS as ORCH_TOOLS

    assert ORCH_TOOLS is TOOLS_FOR_LLM
    assert len(get_tool_names()) == 23
    assert "im_get_orders" in get_tool_names()
    full_names = {t["function"]["name"] for t in TOOLS}
    llm_names = {t["function"]["name"] for t in TOOLS_FOR_LLM}
    assert full_names == llm_names
    # Compact descriptions are shorter than the full schemas.
    full_desc = TOOLS[0]["function"]["description"]
    compact_desc = TOOLS_FOR_LLM[0]["function"]["description"]
    assert len(compact_desc) <= len(full_desc)

def test_provider_resolution(monkeypatch: pytest.MonkeyPatch):
    s = llm_mod.settings

    monkeypatch.setattr(s, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(s, "GEMINI_API_KEY", "gem")
    monkeypatch.setattr(s, "GROQ_API_KEY", "grq")
    assert llm_mod._resolve_provider()[0] == "gemini"

    monkeypatch.setattr(s, "GEMINI_API_KEY", "")
    assert llm_mod._resolve_provider()[0] == "groq"

    monkeypatch.setattr(s, "GROQ_API_KEY", "")
    assert llm_mod._resolve_provider()[0] == "none"
    assert "No LLM" in llm_mod.active_provider_label()

    monkeypatch.setattr(s, "GEMINI_API_KEY", "gem")
    monkeypatch.setattr(s, "LLM_PROVIDER", "groq")
    assert llm_mod._resolve_provider()[0] == "none"  # groq forced but unavailable


def test_no_provider_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(llm_mod.settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_mod.settings, "GROQ_API_KEY", "")

    async def never(name, args):  # pragma: no cover
        raise AssertionError("tool should not run")

    with pytest.raises(llm_mod.LLMUnavailable):
        _run(
            llm_mod.run_tool_conversation(
                system_prompt="x", user_message="hi", execute_tool=never
            )
        )


def test_gemini_declarations_cover_every_tool():
    """Every OpenAI-style schema converts to a Gemini FunctionDeclaration."""
    types = pytest.importorskip("google.genai.types")
    decls = llm_mod._gemini_declarations(types)
    assert len(decls) == len(TOOLS_FOR_LLM)
    names = {d.name for d in decls}
    assert names == set(get_tool_names())


def test_gemini_model_chain_dedupes_preferred():
    assert llm_mod._gemini_model_chain("gemini-3.6-flash")[0] == "gemini-3.6-flash"
    assert llm_mod._gemini_model_chain("gemini-3.5-flash-lite")[0] == "gemini-3.5-flash-lite"
    assert "gemini-3.1-flash-lite" in llm_mod._gemini_model_chain("gemini-3.5-flash-lite")
    assert llm_mod._is_model_unavailable(
        RuntimeError("404 NOT_FOUND. This model models/gemini-2.5-flash is no longer available")
    )


def test_gemini_model_404_tries_next_before_groq(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(llm_mod.settings, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(llm_mod.settings, "GEMINI_API_KEY", "gem")
    monkeypatch.setattr(llm_mod.settings, "GROQ_API_KEY", "grq")
    monkeypatch.setattr(llm_mod.settings, "GEMINI_MODEL", "gemini-2.5-flash")

    tried: list[str] = []

    async def fake_gemini(**kwargs):
        model = kwargs["model"]
        tried.append(model)
        if model == "gemini-2.5-flash":
            raise RuntimeError("404 NOT_FOUND. This model is no longer available to new users.")
        return llm_mod.LLMResult(text="ok", provider="gemini", model=model)

    async def never_groq(**kwargs):  # pragma: no cover
        raise AssertionError("should not hit Groq when a Gemini candidate works")

    monkeypatch.setattr(llm_mod, "_run_gemini", fake_gemini)
    monkeypatch.setattr(llm_mod, "_run_groq", never_groq)

    async def never(name, args):  # pragma: no cover
        raise AssertionError("tool should not run")

    result = _run(
        llm_mod.run_tool_conversation(
            system_prompt="x", user_message="hi", execute_tool=never
        )
    )
    assert tried[0] == "gemini-2.5-flash"
    assert result.provider == "gemini"
    assert result.model == "gemini-3.5-flash-lite"


def test_gemini_failure_falls_back_to_groq(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(llm_mod.settings, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(llm_mod.settings, "GEMINI_API_KEY", "gem")
    monkeypatch.setattr(llm_mod.settings, "GROQ_API_KEY", "grq")

    async def boom(**kwargs):
        raise RuntimeError("429 rate_limit_exceeded")

    async def fake_groq(**kwargs):
        return llm_mod.LLMResult(text="from groq", provider="groq", model="fake")

    monkeypatch.setattr(llm_mod, "_run_gemini", boom)
    monkeypatch.setattr(llm_mod, "_run_groq", fake_groq)

    async def never(name, args):  # pragma: no cover
        raise AssertionError("tool should not run")

    result = _run(
        llm_mod.run_tool_conversation(
            system_prompt="x", user_message="hi", execute_tool=never
        )
    )
    assert result.provider == "groq"
    assert result.text == "from groq"


def test_gemini_only_mode_does_not_fall_back(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(llm_mod.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm_mod.settings, "GEMINI_API_KEY", "gem")
    monkeypatch.setattr(llm_mod.settings, "GROQ_API_KEY", "grq")

    async def boom(**kwargs):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(llm_mod, "_run_gemini", boom)

    async def never(name, args):  # pragma: no cover
        raise AssertionError("tool should not run")

    with pytest.raises(RuntimeError, match="gemini down"):
        _run(
            llm_mod.run_tool_conversation(
                system_prompt="x", user_message="hi", execute_tool=never
            )
        )


def test_truncate_keeps_payloads_small():
    big = {"rows": ["x" * 100 for _ in range(500)]}
    out = llm_mod._truncate_for_model(big, limit=1000)
    assert out["truncated"] is True
    assert len(out["preview"]) == 1000

    small = {"ok": True}
    assert llm_mod._truncate_for_model(small) == small


def test_truncate_caps_search_lists():
    payload = {
        "items": [
            {
                "itemId": f"i{i}",
                "name": f"Dish {i}",
                "price_inr": 100 + i,
                "extra_blob": "z" * 200,
            }
            for i in range(20)
        ]
    }
    out = llm_mod._truncate_for_model(payload)
    assert len(out["items"]) == 5
    assert out["items_truncated"] == 15
    assert "extra_blob" not in out["items"][0]
    assert "itemId" in out["items"][0]

def test_wrap_result_always_object():
    assert llm_mod._wrap_result({"a": 1}) == {"a": 1}
    assert llm_mod._wrap_result([1, 2]) == {"result": [1, 2]}


def test_is_malformed_detects_empty_and_malformed():
    class Cand:
        def __init__(self, reason):
            self.finish_reason = reason

    class Resp:
        def __init__(self, reason, text="", calls=None):
            self.candidates = [Cand(reason)]
            self.text = text
            self.function_calls = calls or []

    assert llm_mod._is_malformed(Resp("MALFORMED_FUNCTION_CALL")) is True
    assert llm_mod._is_malformed(Resp("STOP", text="")) is True
    assert llm_mod._is_malformed(Resp("STOP", text="hello")) is False

    class NoCands:
        candidates: list[Any] = []
        text = ""
        function_calls: list[Any] = []

    assert llm_mod._is_malformed(NoCands()) is True
