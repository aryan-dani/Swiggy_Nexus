"""Unified async tool-calling LLM layer — Gemini primary, Groq fallback, Ollama local.

The SSE chat path in `backend/llm_orchestrator.py` stays a sync generator for
streaming. This module is the async equivalent used by the Telegram agent, so
nothing blocks the long-poll event loop.

Both providers share the tool schemas in `backend/tool_schemas.py`, so the
Telegram brain and the web chat brain can never drift apart. Set
`LLM_PROVIDER=ollama` for local rehearsal without burning Gemini quota.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.config import settings
from backend.tool_schemas import TOOLS_FOR_LLM

log = logging.getLogger(__name__)

# Executor contract: (tool_name, args) -> result dict.
# A result containing "__halt__": True means "stop calling tools, just narrate".
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
ToolObserver = Callable[[str, dict[str, Any]], Awaitable[None]]

HALT_KEY = "__halt__"

# Prefer cheap Flash-Lite; escalate only if a model is unavailable to this key.
_GEMINI_MODEL_CANDIDATES = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
)

_LIST_KEYS = ("restaurants", "items", "products", "coupons", "addresses", "venues")
_SLIM_FIELDS = (
    "id",
    "itemId",
    "item_id",
    "restaurantId",
    "restaurant_id",
    "product_id",
    "name",
    "price_inr",
    "rating",
    "vegetarian",
    "spinId",
    "availabilityStatus",
    "availability",
    "eta_mins",
)


def _gemini_model_chain(preferred: str) -> list[str]:
    ordered = [preferred, *_GEMINI_MODEL_CANDIDATES]
    seen: set[str] = set()
    out: list[str] = []
    for m in ordered:
        m = (m or "").strip()
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _is_model_unavailable(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "404" in text or "not_found" in text or "no longer available" in text


class LLMUnavailable(RuntimeError):
    """No usable provider (no keys, or every provider failed)."""


@dataclass
class LLMResult:
    text: str = ""
    provider: str = ""
    model: str = ""
    tool_names: list[str] = field(default_factory=list)
    rounds: int = 0
    halted: bool = False


def active_provider_label() -> str:
    """Human-readable brain name for the UI / bot footer."""
    provider, model = _resolve_provider()
    if provider == "gemini":
        return f"Gemini · {model}"
    if provider == "groq":
        return f"Groq · {model}"
    if provider == "ollama":
        return f"Ollama · {model}"
    return "No LLM configured"


def _resolve_provider() -> tuple[str, str]:
    choice = settings.LLM_PROVIDER
    has_gemini = bool(settings.GEMINI_API_KEY.strip())
    has_groq = bool(settings.GROQ_API_KEY.strip())
    has_ollama = bool(settings.OLLAMA_BASE_URL.strip())

    if choice == "ollama" and has_ollama:
        return "ollama", settings.OLLAMA_MODEL
    if choice == "gemini" and has_gemini:
        return "gemini", settings.GEMINI_MODEL
    if choice == "groq" and has_groq:
        return "groq", settings.GROQ_MODEL
    if choice == "auto":
        if has_gemini:
            return "gemini", settings.GEMINI_MODEL
        if has_groq:
            return "groq", settings.GROQ_MODEL
    return "none", ""


def _wrap_result(result: Any) -> dict[str, Any]:
    """Gemini requires function responses to be JSON objects."""
    if isinstance(result, dict):
        return result
    return {"result": result}


def _slim_row(row: Any) -> Any:
    if not isinstance(row, dict):
        return row
    return {k: row[k] for k in _SLIM_FIELDS if k in row} or {
        k: row[k] for k in list(row)[:6]
    }


def _shape_for_model(payload: dict[str, Any], list_cap: int = 5) -> dict[str, Any]:
    """Drop bulky list rows before JSON truncate — biggest win on search/menu tools."""
    out = dict(payload)
    for key in _LIST_KEYS:
        rows = out.get(key)
        if isinstance(rows, list) and rows:
            out[key] = [_slim_row(r) for r in rows[:list_cap]]
            if len(rows) > list_cap:
                out[f"{key}_truncated"] = len(rows) - list_cap
    cats = out.get("categories")
    if isinstance(cats, list):
        slim_cats = []
        for cat in cats[:4]:
            if not isinstance(cat, dict):
                continue
            items = cat.get("items") or []
            slim_cats.append(
                {
                    "name": cat.get("name"),
                    "items": [_slim_row(i) for i in items[:list_cap]],
                }
            )
        out["categories"] = slim_cats
    return out


def _truncate_for_model(payload: dict[str, Any], limit: int = 1800) -> dict[str, Any]:
    """Keep tool results small so multi-round conversations stay within budget."""
    shaped = _shape_for_model(payload if isinstance(payload, dict) else {"result": payload})
    blob = json.dumps(shaped, default=str)
    if len(blob) <= limit:
        return shaped
    return {"truncated": True, "preview": blob[:limit]}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_tool_conversation(
    *,
    system_prompt: str,
    user_message: str,
    execute_tool: ToolExecutor,
    history: list[dict[str, str]] | None = None,
    on_tool_start: ToolObserver | None = None,
    max_rounds: int = 6,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResult:
    """Run a tool-calling conversation to completion and return the final text."""
    provider, model = _resolve_provider()
    if provider == "none":
        raise LLMUnavailable(
            "Set LLM_PROVIDER=ollama (local) or GEMINI_API_KEY / GROQ_API_KEY."
        )

    history = history or []
    tool_schemas = tools or TOOLS_FOR_LLM

    if provider == "ollama":
        try:
            return await _run_ollama(
                system_prompt=system_prompt,
                user_message=user_message,
                execute_tool=execute_tool,
                history=history,
                on_tool_start=on_tool_start,
                max_rounds=max_rounds,
                model=model,
                tools=tool_schemas,
            )
        except LLMUnavailable:
            raise
        except Exception as e:  # noqa: BLE001 — never fall through to Gemini
            raise LLMUnavailable(
                f"Ollama failed ({e}). Is `ollama serve` running at {settings.OLLAMA_BASE_URL}?"
            ) from e

    if provider == "gemini":
        last_err: Exception | None = None
        for candidate in _gemini_model_chain(model):
            try:
                return await _run_gemini(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    execute_tool=execute_tool,
                    history=history,
                    on_tool_start=on_tool_start,
                    max_rounds=max_rounds,
                    model=candidate,
                    tools=tool_schemas,
                )
            except Exception as e:  # noqa: BLE001 — try next model / Groq
                last_err = e
                if _is_model_unavailable(e):
                    log.warning("Gemini model %s unavailable (%s) — trying next", candidate, e)
                    continue
                break
        assert last_err is not None
        if settings.LLM_PROVIDER == "gemini":
            raise last_err  # explicit gemini-only choice: fail loudly
        if not settings.GROQ_API_KEY.strip():
            raise LLMUnavailable(f"Gemini failed and no Groq fallback: {last_err}") from last_err
        log.warning("Gemini failed (%s) — falling back to Groq", last_err)
        return await _run_groq(
            system_prompt=system_prompt,
            user_message=user_message,
            execute_tool=execute_tool,
            history=history,
            on_tool_start=on_tool_start,
            max_rounds=max_rounds,
            model=settings.GROQ_MODEL,
            tools=tool_schemas,
        )

    return await _run_groq(
        system_prompt=system_prompt,
        user_message=user_message,
        execute_tool=execute_tool,
        history=history,
        on_tool_start=on_tool_start,
        max_rounds=max_rounds,
        model=model,
        tools=tool_schemas,
    )


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


def _gemini_declarations(types_mod: Any, tools: list[dict[str, Any]] | None = None) -> list[Any]:
    """Convert OpenAI-style tool schemas to Gemini FunctionDeclarations."""
    decls = []
    for tool in tools or TOOLS_FOR_LLM:
        fn = tool.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        params = fn.get("parameters") or {"type": "object", "properties": {}}
        decls.append(
            types_mod.FunctionDeclaration(
                name=name,
                description=fn.get("description", ""),
                parameters_json_schema=params,
            )
        )
    return decls


def _thinking_config(types_mod: Any) -> Any:
    """Always minimal thinking — Gemini 3.x medium thinking burns tokens on tool loops."""
    try:
        return types_mod.ThinkingConfig(thinking_level="minimal")
    except (TypeError, ValueError):
        return types_mod.ThinkingConfig(thinking_budget=0)


def _is_malformed(resp: Any) -> bool:
    """Detect empty / MALFORMED_FUNCTION_CALL turns that need one retry."""
    try:
        candidates = resp.candidates or []
        if not candidates:
            return True
        reason = str(getattr(candidates[0], "finish_reason", "") or "")
        if "MALFORMED" in reason.upper():
            return True
        has_text = bool((resp.text or "").strip())
        has_calls = bool(resp.function_calls)
        return not has_text and not has_calls
    except Exception:  # noqa: BLE001
        return False


async def _run_gemini(
    *,
    system_prompt: str,
    user_message: str,
    execute_tool: ToolExecutor,
    history: list[dict[str, str]],
    on_tool_start: ToolObserver | None,
    max_rounds: int,
    model: str,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResult:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    declarations = _gemini_declarations(types, tools)

    def _config(with_tools: bool = True) -> Any:
        kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "thinking_config": _thinking_config(types),
        }
        if with_tools:
            kwargs["tools"] = [types.Tool(function_declarations=declarations)]
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )
        return types.GenerateContentConfig(**kwargs)

    contents: list[Any] = []
    for turn in history:
        role = "model" if turn.get("role") in ("assistant", "model") else "user"
        text = (turn.get("content") or "").strip()
        if text:
            contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    result = LLMResult(provider="gemini", model=model)

    for round_index in range(max_rounds):
        resp = await client.aio.models.generate_content(
            model=model, contents=contents, config=_config()
        )
        if _is_malformed(resp):
            log.info("Gemini malformed/empty turn — one retry")
            resp = await client.aio.models.generate_content(
                model=model, contents=contents, config=_config()
            )

        calls = list(resp.function_calls or [])
        if not calls:
            result.text = (resp.text or "").strip()
            result.rounds = round_index
            return result

        # Append the model turn verbatim so thought signatures survive.
        contents.append(resp.candidates[0].content)

        response_parts: list[Any] = []
        halted = False
        for call in calls:
            args = dict(call.args or {})
            result.tool_names.append(call.name)
            if on_tool_start:
                await on_tool_start(call.name, args)
            tool_result = _truncate_for_model(_wrap_result(await execute_tool(call.name, args)))
            if tool_result.get(HALT_KEY):
                halted = True
            try:
                part = types.Part.from_function_response(
                    name=call.name, response=tool_result, id=call.id
                )
            except TypeError:
                part = types.Part.from_function_response(
                    name=call.name, response=tool_result
                )
            response_parts.append(part)

        contents.append(types.Content(role="user", parts=response_parts))
        result.rounds = round_index + 1

        if halted:
            # Ask for narration only — no more tool calls after a HITL pause.
            final = await client.aio.models.generate_content(
                model=model, contents=contents, config=_config(with_tools=False)
            )
            result.text = (final.text or "").strip()
            result.halted = True
            return result

    result.text = result.text or "I ran out of tool steps — try narrowing the request."
    return result


# ---------------------------------------------------------------------------
# OpenAI-compatible (Groq + Ollama)
# ---------------------------------------------------------------------------


async def _openai_compat_create(
    client: Any,
    model: str,
    messages: list[Any],
    *,
    with_tools: bool,
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    """Create with one retry on malformed tool calls (Groq / some Ollama models)."""
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if with_tools:
        kwargs["tools"] = tools or TOOLS_FOR_LLM
        kwargs["tool_choice"] = "auto"
    try:
        return await client.chat.completions.create(**kwargs)
    except Exception as e:  # noqa: BLE001
        if "tool_use_failed" not in str(e) and "tool call validation" not in str(e):
            raise
        log.warning("Malformed tool call — retrying once with a corrective nudge")
        nudged = list(messages) + [
            {
                "role": "system",
                "content": (
                    "Your previous tool call was malformed. Emit exactly one well-formed "
                    "tool call using the documented JSON arguments, or reply with plain text."
                ),
            }
        ]
        retry_kwargs = dict(kwargs)
        retry_kwargs["messages"] = nudged
        return await client.chat.completions.create(**retry_kwargs)


async def _run_openai_compatible(
    *,
    client: Any,
    provider: str,
    system_prompt: str,
    user_message: str,
    execute_tool: ToolExecutor,
    history: list[dict[str, str]],
    on_tool_start: ToolObserver | None,
    max_rounds: int,
    model: str,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResult:
    messages: list[Any] = [{"role": "system", "content": system_prompt}]
    for turn in history:
        role = "assistant" if turn.get("role") in ("assistant", "model") else "user"
        text = (turn.get("content") or "").strip()
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": user_message})

    result = LLMResult(provider=provider, model=model)
    tool_schemas = tools or TOOLS_FOR_LLM

    for round_index in range(max_rounds):
        resp = await _openai_compat_create(
            client, model, messages, with_tools=True, tools=tool_schemas
        )
        msg = resp.choices[0].message
        calls = list(msg.tool_calls or [])
        if not calls:
            result.text = (msg.content or "").strip()
            result.rounds = round_index
            return result

        messages.append(msg)
        halted = False
        for call in calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            result.tool_names.append(call.function.name)
            if on_tool_start:
                await on_tool_start(call.function.name, args)
            tool_result = _truncate_for_model(
                _wrap_result(await execute_tool(call.function.name, args))
            )
            if tool_result.get(HALT_KEY):
                halted = True
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(tool_result, default=str),
                }
            )

        result.rounds = round_index + 1

        if halted:
            final = await _openai_compat_create(
                client, model, messages, with_tools=False, tools=tool_schemas
            )
            result.text = (final.choices[0].message.content or "").strip()
            result.halted = True
            return result

    result.text = result.text or "I ran out of tool steps — try narrowing the request."
    return result


async def _run_groq(
    *,
    system_prompt: str,
    user_message: str,
    execute_tool: ToolExecutor,
    history: list[dict[str, str]],
    on_tool_start: ToolObserver | None,
    max_rounds: int,
    model: str,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResult:
    from groq import AsyncGroq

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return await _run_openai_compatible(
        client=client,
        provider="groq",
        system_prompt=system_prompt,
        user_message=user_message,
        execute_tool=execute_tool,
        history=history,
        on_tool_start=on_tool_start,
        max_rounds=max_rounds,
        model=model,
        tools=tools,
    )


async def _run_ollama(
    *,
    system_prompt: str,
    user_message: str,
    execute_tool: ToolExecutor,
    history: list[dict[str, str]],
    on_tool_start: ToolObserver | None,
    max_rounds: int,
    model: str,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResult:
    from openai import AsyncOpenAI

    base = settings.OLLAMA_BASE_URL.rstrip("/")
    client = AsyncOpenAI(base_url=f"{base}/v1", api_key="ollama")
    return await _run_openai_compatible(
        client=client,
        provider="ollama",
        system_prompt=system_prompt,
        user_message=user_message,
        execute_tool=execute_tool,
        history=history,
        on_tool_start=on_tool_start,
        max_rounds=max_rounds,
        model=model,
        tools=tools,
    )
