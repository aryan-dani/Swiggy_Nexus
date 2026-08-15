"""SSE chat orchestrator — Gemini primary, Groq fallback, Ollama local, deterministic last resort.

Telegram uses the async twin in `app/services/llm.py`. Both share `backend/tool_schemas.TOOLS`.
When `LLM_PROVIDER=ollama`, neither Gemini nor Groq is touched.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Generator

from backend.mcp_client import call_tool, LocalMCPError
from backend.memory import get_user_preferences

# Tool schemas live in backend/tool_schemas.py — one source of truth shared by
# this SSE orchestrator and the async Telegram agent in app/services/llm.py.
from backend.tool_schemas import TOOLS_FOR_LLM as TOOLS

log = logging.getLogger(__name__)

_GEMINI_MODEL_CANDIDATES = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
)


def _sse_tool(
    server_key: str, http_path: str, method: str, params: dict[str, Any], data: Any
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "vertical": server_key,
        "server_path": http_path,
        "method": method,
        "params": params,
        "result": {"success": True, "data": data},
        "demo_note": "local_mock_mcp",
    }


REVIEWER_SCENARIOS = ("chrono_host", "deadlock", "flowstate", "zerowaste", "sentiment", "dialectic")

SCENARIO_PROMPTS: dict[str, str] = {
    "chrono_host": (
        "Chrono-Host: plan a multi-vertical evening (Dineout table + Instamart party supplies + Food dessert). "
        "Use parallel tool calls across food, im, and dineout. Stage carts; do not auto-place without user confirm."
    ),
    "deadlock": "Social deadlock breaker: find a dinner compromise for a picky group using Dineout search and availability.",
    "flowstate": "Flow-state fueler: quick Instamart delivery for deep-work snacks and coffee.",
    "zerowaste": "Zero-waste meal: search pantry gaps on Instamart for a recipe, minimize waste.",
    "sentiment": "Sentiment thermostat: suggest comfort food options; stage carts but never auto-checkout.",
    "dialectic": "Dialectic dinner: search restaurants for a debate-night meal pick.",
}


def _env_keys() -> tuple[str, str, str, str, str, str, str]:
    """Return (gemini_key, gemini_model, groq_key, groq_model, ollama_base, ollama_model, provider)."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_model = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite"
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    groq_model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "").strip() or "http://127.0.0.1:11434"
    ollama_model = os.environ.get("OLLAMA_MODEL", "").strip() or "qwen2.5:7b-instruct"
    provider = os.environ.get("LLM_PROVIDER", "").strip() or "auto"
    try:
        from app.config import settings

        gemini_key = gemini_key or settings.GEMINI_API_KEY.strip()
        gemini_model = (
            os.environ.get("GEMINI_MODEL", "").strip()
            or settings.GEMINI_MODEL.strip()
            or gemini_model
        )
        groq_key = groq_key or settings.GROQ_API_KEY.strip()
        groq_model = (
            os.environ.get("GROQ_MODEL", "").strip()
            or settings.GROQ_MODEL.strip()
            or groq_model
        )
        ollama_base = (
            os.environ.get("OLLAMA_BASE_URL", "").strip()
            or settings.OLLAMA_BASE_URL.strip()
            or ollama_base
        )
        ollama_model = (
            os.environ.get("OLLAMA_MODEL", "").strip()
            or settings.OLLAMA_MODEL.strip()
            or ollama_model
        )
        provider = os.environ.get("LLM_PROVIDER", "").strip() or settings.LLM_PROVIDER or provider
    except Exception:  # noqa: BLE001
        pass
    return gemini_key, gemini_model, groq_key, groq_model, ollama_base, ollama_model, provider


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


def _build_system_prompt(prefs_str: str, scenario_hint: str) -> str:
    return (
        "You are Swiggy Nexus — Food, Instamart, and Dineout via MCP tools.\n"
        f"Prefs: {prefs_str}{scenario_hint}\n"
        "Rules: never invent IDs; copy restaurantId/itemId/spinId from tool results. "
        "Dish orders → food_search_menu then add_to_cart. "
        "Never place_order/checkout/book_table without explicit user confirm. "
        "Food cart < ₹1000; Instamart min ₹99; COD only. "
        "OPEN/AVAILABLE venues only. After food_add_to_cart call food_get_food_cart once. "
        "Cancel → tell user to call 080-67466729. Prefer tool calls over chatter."
    )


def _scenario_hint(ctx: dict[str, Any]) -> str:
    scenario = ctx.get("scenario")
    hint = ""
    if isinstance(scenario, str) and scenario in SCENARIO_PROMPTS:
        hint = f"\nActive reviewer scenario ({scenario}): {SCENARIO_PROMPTS[scenario]}"
    party = ctx.get("partySize")
    event = ctx.get("event")
    if not party and isinstance(event, dict):
        party = event.get("guests")
    if party:
        hint += f"\nParty size: {party}."
    return hint


def _add_feed_from_tool(
    *,
    vertical: str,
    method: str,
    data: Any,
    add_feed: Any,
) -> None:
    if method == "search_restaurants" and isinstance(data, dict) and "restaurants" in data:
        for r in data.get("restaurants") or []:
            add_feed({
                "type": "restaurant" if vertical == "food" else "dineout",
                "title": r.get("name", "Venue"),
                "subtitle": f"★ {r.get('rating')} · {', '.join(r.get('cuisines') or [])}",
                "meta": {"restaurant_id": r.get("restaurant_id") or r.get("id")},
            })
    elif method == "search_menu" and isinstance(data, dict) and "items" in data:
        for item in data.get("items") or []:
            veg_badge = "🟢" if item.get("vegetarian") else "🔴"
            add_feed({
                "type": "food",
                "title": item.get("name", "Dish"),
                "subtitle": (
                    f"{veg_badge} ₹{item.get('price_inr')} · "
                    f"{item.get('restaurantName', '')} · ★{item.get('restaurantRating', '')}"
                ),
                "meta": {
                    "item_id": item.get("item_id"),
                    "restaurant_id": item.get("restaurantId"),
                    "price_inr": item.get("price_inr"),
                },
            })
    elif method in ("get_menu", "get_restaurant_menu") and isinstance(data, dict):
        for cat in data.get("categories") or []:
            for item in cat.get("items") or []:
                veg_badge = "🟢" if item.get("vegetarian") else "🔴"
                add_feed({
                    "type": "food",
                    "title": item.get("name", "Item"),
                    "subtitle": f"{veg_badge} ₹{item.get('price_inr')} · {cat.get('name', '')}",
                    "meta": {
                        "item_id": item.get("item_id"),
                        "price_inr": item.get("price_inr"),
                    },
                })
    elif method == "search_products" and isinstance(data, dict) and "products" in data:
        for p in data.get("products") or []:
            add_feed({
                "type": "grocery",
                "title": p.get("name", "Product"),
                "subtitle": f"₹{p.get('price_inr', '?')} · {p.get('category', '')}",
                "meta": {
                    "product_id": p.get("product_id"),
                    "price_inr": p.get("price_inr"),
                    "spinId": (p.get("variants") or [{}])[0].get("spinId"),
                },
            })
    elif method == "your_go_to_items" and isinstance(data, dict) and "products" in data:
        for p in data.get("products") or []:
            add_feed({
                "type": "grocery",
                "title": f"⚡ {p.get('name', 'Item')}",
                "subtitle": f"₹{p.get('price_inr', '?')} · Quick reorder",
                "meta": {
                    "product_id": p.get("product_id"),
                    "price_inr": p.get("price_inr"),
                },
            })
    elif method == "get_restaurant_details" and isinstance(data, dict):
        add_feed({
            "type": "dineout",
            "title": data.get("name", "Restaurant"),
            "subtitle": (
                f"★ {data.get('rating')} · "
                f"{', '.join(data.get('cuisines', []))} · "
                f"₹{data.get('costForTwo')}/2"
            ),
            "meta": {"restaurant_id": data.get("restaurantId")},
        })
    elif method in ("get_food_cart", "get_cart") and isinstance(data, dict):
        total = data.get("bill", {}).get("total_inr") or data.get("total_inr")
        items_count = len(data.get("items", []))
        add_feed({
            "type": "cart_summary",
            "title": "Cart Summary",
            "subtitle": f"{items_count} item(s) · ₹{total or '?'} total",
            "meta": data,
        })
    elif method in ("fetch_food_coupons",) and isinstance(data, dict) and data.get("coupons"):
        for c in (data.get("coupons") or [])[:3]:
            add_feed({
                "type": "coupon",
                "title": f"🏷️ {c.get('code', 'COUPON')}",
                "subtitle": c.get("description", ""),
                "meta": c,
            })
    elif method in ("place_order", "checkout") and isinstance(data, dict):
        add_feed({
            "type": f"{vertical}_order",
            "title": data.get("message", "Order placed ✓"),
            "subtitle": f"ETA ~{data.get('eta_mins', '?')} mins",
            "meta": data,
        })
    elif method == "book_table" and isinstance(data, dict):
        add_feed({
            "type": "booking",
            "title": "Table Reserved ✓",
            "subtitle": data.get("confirmation_message", data.get("booking_id", "")),
            "meta": data,
        })
    elif method in ("track_food_order", "track_order") and isinstance(data, dict):
        status = data.get("status", "In Progress")
        add_feed({
            "type": "tracking",
            "title": f"Order Tracking · {status}",
            "subtitle": f"ETA ~{data.get('eta_mins', '?')} mins",
            "meta": data,
        })


def _dispatch_named_tool(
    name: str,
    args: dict[str, Any],
    session_id: str,
) -> tuple[str, str, Any]:
    from backend.mcp_aliases import resolve_llm_tool

    vertical, method = resolve_llm_tool(name)
    if "requestId" in args:
        args["requestId"] = session_id
    if "request_id" in args:
        args["request_id"] = session_id
    # Always pin cart mutations to the UI session (stage → confirm) for mock/replay.
    if "requestId" not in args and "request_id" not in args:
        args["requestId"] = session_id
    data = call_tool(vertical, method, args)
    return vertical, method, data


def _resolve_mcp_session_id(ctx: dict[str, Any] | None) -> str:
    """Align LLM tool carts with the frontend Nexus requestId."""
    ctx = ctx or {}
    for key in ("requestId", "request_id", "sessionId", "session_id"):
        val = ctx.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return "default_mock_session"


def _run_openai_compat_loop(
    *,
    client: Any,
    user_message: str,
    system_prompt: str,
    model: str,
    banner: str,
    session_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Shared sync tool loop for Groq and Ollama (OpenAI-compatible chat API)."""
    session_id = session_id or "default_mock_session"
    yield {"type": "thinking", "payload": {"text": banner}}

    messages: list[Any] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    feed_items: list[dict[str, Any]] = []
    seen_feed_keys: set[str] = set()

    def _add_feed(item: dict[str, Any]) -> None:
        key = f"{item.get('type')}|{item.get('title')}"
        if key not in seen_feed_keys:
            seen_feed_keys.add(key)
            feed_items.append(item)

    max_rounds = 8
    for _ in range(max_rounds):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            yield {"type": "assistant", "payload": {"text": f"LLM error: {str(e)}"}}
            yield {
                "type": "done",
                "payload": {"assistant_reply": f"LLM error: {str(e)}", "feed_items": feed_items},
            }
            return

        msg = resp.choices[0].message
        if not msg.tool_calls:
            assistant_reply = msg.content or "Done."
            yield {"type": "assistant", "payload": {"text": assistant_reply}}
            if feed_items:
                yield {"type": "feed", "payload": {"items": list(feed_items)}}
            yield {
                "type": "done",
                "payload": {"assistant_reply": assistant_reply, "feed_items": feed_items},
            }
            return

        messages.append(msg)
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}

            yield {"type": "thinking", "payload": {"text": f"Executor · {name}"}}
            try:
                vertical, method, data = _dispatch_named_tool(name, args, session_id)
                tool_payload = _sse_tool(vertical, f"/{vertical}", method, args, data)
                tool_payload["method"] = name
                tool_payload["phase"] = "Executor"
                yield {"type": "tool", "payload": tool_payload}
                _add_feed_from_tool(vertical=vertical, method=method, data=data, add_feed=_add_feed)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(data),
                })
            except LocalMCPError as e:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": e.payload}),
                })
            except Exception as e:  # noqa: BLE001
                yield {
                    "type": "thinking",
                    "payload": {"text": f"Executor recovered from {name}: {e}"},
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": {"code": "EXECUTOR_ERROR", "message": str(e)}}),
                })

    assistant_reply = "I ran out of tool steps — try narrowing the request."
    yield {"type": "assistant", "payload": {"text": assistant_reply}}
    if feed_items:
        yield {"type": "feed", "payload": {"items": list(feed_items)}}
    yield {
        "type": "done",
        "payload": {"assistant_reply": assistant_reply, "feed_items": feed_items},
    }


def _run_groq_loop(
    *,
    user_message: str,
    system_prompt: str,
    api_key: str,
    model: str,
    session_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    from groq import Groq

    client = Groq(api_key=api_key)
    yield from _run_openai_compat_loop(
        client=client,
        user_message=user_message,
        system_prompt=system_prompt,
        model=model,
        banner=f"Groq {model} · agentic MCP tool loop (fallback)",
        session_id=session_id,
    )


def _run_ollama_loop(
    *,
    user_message: str,
    system_prompt: str,
    base_url: str,
    model: str,
    session_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    from openai import OpenAI

    base = base_url.rstrip("/")
    client = OpenAI(base_url=f"{base}/v1", api_key="ollama")
    yield from _run_openai_compat_loop(
        client=client,
        user_message=user_message,
        system_prompt=system_prompt,
        model=model,
        banner=f"Ollama {model} · agentic MCP tool loop",
        session_id=session_id,
    )


def _run_gemini_loop(
    *,
    user_message: str,
    system_prompt: str,
    api_key: str,
    model: str,
    session_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    from google import genai
    from google.genai import types

    from app.services.llm import (
        _gemini_declarations,
        _thinking_config,
        _truncate_for_model,
        _wrap_result,
    )

    client = genai.Client(api_key=api_key)
    declarations = _gemini_declarations(types)
    session_id = session_id or "default_mock_session"

    yield {
        "type": "thinking",
        "payload": {"text": f"Gemini {model} · agentic MCP tool loop"},
    }

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

    contents: list[Any] = [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]
    feed_items: list[dict[str, Any]] = []
    seen_feed_keys: set[str] = set()

    def _add_feed(item: dict[str, Any]) -> None:
        key = f"{item.get('type')}|{item.get('title')}"
        if key not in seen_feed_keys:
            seen_feed_keys.add(key)
            feed_items.append(item)

    max_rounds = 6
    for round_index in range(max_rounds):
        resp = client.models.generate_content(
            model=model, contents=contents, config=_config()
        )
        try:
            candidates = resp.candidates or []
            reason = str(getattr(candidates[0], "finish_reason", "") or "") if candidates else ""
            empty = not candidates or (
                not (resp.text or "").strip() and not resp.function_calls
            )
            malformed = "MALFORMED" in reason.upper() or empty
        except Exception:  # noqa: BLE001
            malformed = True
        if malformed:
            resp = client.models.generate_content(
                model=model, contents=contents, config=_config()
            )

        calls = list(resp.function_calls or [])
        if not calls:
            assistant_reply = (resp.text or "").strip() or "Done."
            yield {"type": "assistant", "payload": {"text": assistant_reply}}
            if feed_items:
                yield {"type": "feed", "payload": {"items": list(feed_items)}}
            yield {
                "type": "done",
                "payload": {"assistant_reply": assistant_reply, "feed_items": feed_items},
            }
            return

        contents.append(resp.candidates[0].content)
        response_parts: list[Any] = []
        for call in calls:
            name = call.name
            args = dict(call.args or {})
            if not isinstance(args, dict):
                args = {}
            yield {"type": "thinking", "payload": {"text": f"Executor · {name}"}}
            try:
                vertical, method, data = _dispatch_named_tool(name, args, session_id)
                tool_payload = _sse_tool(vertical, f"/{vertical}", method, args, data)
                tool_payload["method"] = name
                tool_payload["phase"] = "Executor"
                yield {"type": "tool", "payload": tool_payload}
                _add_feed_from_tool(vertical=vertical, method=method, data=data, add_feed=_add_feed)
                payload = _truncate_for_model(_wrap_result(data))
            except LocalMCPError as e:
                payload = {"error": e.payload}
            except Exception as e:  # noqa: BLE001
                yield {
                    "type": "thinking",
                    "payload": {"text": f"Executor recovered from {name}: {e}"},
                }
                payload = {"error": {"code": "EXECUTOR_ERROR", "message": str(e)}}
            try:
                part = types.Part.from_function_response(
                    name=name, response=payload, id=call.id
                )
            except TypeError:
                part = types.Part.from_function_response(name=name, response=payload)
            response_parts.append(part)

        contents.append(types.Content(role="user", parts=response_parts))
        _ = round_index  # silence unused in some linters

    assistant_reply = "I ran out of tool steps — try narrowing the request."
    yield {"type": "assistant", "payload": {"text": assistant_reply}}
    if feed_items:
        yield {"type": "feed", "payload": {"items": list(feed_items)}}
    yield {
        "type": "done",
        "payload": {"assistant_reply": assistant_reply, "feed_items": feed_items},
    }


def run_llm_agent(user_message: str, context: dict[str, Any] | None) -> Generator[dict[str, Any], None, None]:
    from backend.mcp_client import (
        apply_mock_override_from_context,
        reset_mock_mcp_override,
    )

    ctx = dict(context or {})
    override_tok = apply_mock_override_from_context(ctx)
    try:
        yield from _run_llm_agent_inner(user_message, ctx)
    finally:
        reset_mock_mcp_override(override_tok)


def _run_llm_agent_inner(
    user_message: str, ctx: dict[str, Any]
) -> Generator[dict[str, Any], None, None]:
    from backend.mcp_client import live_token_configured, use_mock_mcp

    mcp_session = _resolve_mcp_session_id(ctx)
    # Ensure deterministic Chrono confirm legs see the same session key.
    ctx.setdefault("requestId", mcp_session)
    gemini_key, gemini_model, groq_key, groq_model, ollama_base, ollama_model, provider = _env_keys()

    mode = "MOCK" if use_mock_mcp() else "LIVE"
    live_ok = live_token_configured()
    if not use_mock_mcp() and not live_ok:
        yield {
            "type": "thinking",
            "payload": {
                "text": (
                    "Live MCP requested but no SWIGGY_OAUTH_TOKEN on this server. "
                    "Falling back to mock — set the token on Render/local, or flip Mock MCP on."
                ),
            },
        }
        from backend.mcp_client import set_mock_mcp_override

        set_mock_mcp_override(True)
        mode = "MOCK"
    else:
        yield {
            "type": "thinking",
            "payload": {"text": f"MCP mode · {mode}" + (" · token ok" if live_ok and mode == "LIVE" else "")},
        }

    # 60s WOW / Chrono-Host must stay on the deterministic multi-vertical script.
    # Free-form LLM tool loops burn rounds on search_restaurants/search_menu and
    # end with "ran out of tool steps" — which breaks the Demo Director recording.
    # Confirm legs also stay here: web Beat 1 must never stage Telegram HITL.
    msg_low = (user_message or "").lower()
    is_chrono_confirm = any(
        k in msg_low
        for k in (
            "confirm table",
            "confirm groceries",
            "confirm grocery",
            "confirm dessert",
        )
    )
    force_chrono = (
        ctx.get("scenario") == "chrono_host"
        or is_chrono_confirm
        or any(
            k in msg_low
            for k in (
                "plan my evening",
                "plan my housewarming",
                "plan a festive",
                "plan a team dinner",
                "plan a date-night",
                "plan a date night",
                "chrono host",
                "dinner out and dessert",
                "thali energy",
                "for 12 guests",
                "housewarming evening",
            )
        )
    )
    if force_chrono:
        from backend.agent import run_agent_stream as deterministic

        if not is_chrono_confirm:
            ctx["scenario"] = "chrono_host"
        yield {
            "type": "thinking",
            "payload": {
                "text": (
                    "Chrono-Host · confirm leg (browser-only — no Telegram)"
                    if is_chrono_confirm
                    else "Chrono-Host · deterministic 3-vertical orchestrator (Dineout + Instamart + Food)"
                )
            },
        }
        yield from deterministic(user_message, ctx)
        return

    # Local rehearsal: never touch Gemini/Groq when LLM_PROVIDER=ollama.
    if provider == "ollama":
        prefs = get_user_preferences()
        prefs_str = json.dumps(prefs) if prefs else "None"
        system_prompt = _build_system_prompt(prefs_str, _scenario_hint(ctx))
        try:
            from openai import OpenAI  # noqa: F401
        except Exception as e:  # noqa: BLE001
            msg = f"Ollama path needs the openai package: {e}"
            yield {"type": "assistant", "payload": {"text": msg}}
            yield {"type": "done", "payload": {"assistant_reply": msg, "feed_items": []}}
            return
        try:
            yield from _run_ollama_loop(
                user_message=user_message,
                system_prompt=system_prompt,
                base_url=ollama_base,
                model=ollama_model,
                session_id=mcp_session,
            )
        except Exception as e:  # noqa: BLE001
            msg = (
                f"Ollama failed ({e}). Is `ollama serve` running at {ollama_base}? "
                "Not falling back to Gemini."
            )
            yield {"type": "assistant", "payload": {"text": msg}}
            yield {"type": "done", "payload": {"assistant_reply": msg, "feed_items": []}}
        return

    # Rich scripted demos only when no LLM is configured.
    if not gemini_key and not groq_key and ctx.get("scenario") in REVIEWER_SCENARIOS:
        from backend.agent import run_agent_stream as deterministic

        yield from deterministic(user_message, ctx)
        return

    if not gemini_key and not groq_key:
        yield {
            "type": "thinking",
            "payload": {
                "text": "No GEMINI_API_KEY or GROQ_API_KEY — falling back to deterministic mode."
            },
        }
        from backend.agent import run_agent_stream as fallback

        yield from fallback(user_message, ctx)
        return

    prefs = get_user_preferences()
    prefs_str = json.dumps(prefs) if prefs else "None"
    system_prompt = _build_system_prompt(prefs_str, _scenario_hint(ctx))

    if gemini_key:
        last_err: Exception | None = None
        for candidate in _gemini_model_chain(gemini_model):
            try:
                yield from _run_gemini_loop(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    api_key=gemini_key,
                    model=candidate,
                    session_id=mcp_session,
                )
                return
            except Exception as e:  # noqa: BLE001
                last_err = e
                if _is_model_unavailable(e):
                    log.warning("Gemini model %s unavailable (%s) — trying next", candidate, e)
                    yield {
                        "type": "thinking",
                        "payload": {"text": f"Gemini {candidate} unavailable — trying next model"},
                    }
                    continue
                log.warning("Gemini failed (%s) — will try Groq if configured", e)
                yield {
                    "type": "thinking",
                    "payload": {"text": f"Gemini failed ({e}) — falling back to Groq"},
                }
                break
        if last_err and not groq_key:
            msg = f"LLM error: Gemini failed and no Groq fallback: {last_err}"
            yield {"type": "assistant", "payload": {"text": msg}}
            yield {"type": "done", "payload": {"assistant_reply": msg, "feed_items": []}}
            return

    if groq_key:
        try:
            # Import check so missing SDK falls through cleanly
            from groq import Groq  # noqa: F401
        except Exception:
            yield {
                "type": "thinking",
                "payload": {"text": "Groq SDK not available. Falling back to deterministic mode."},
            }
            from backend.agent import run_agent_stream as fallback

            yield from fallback(user_message, ctx)
            return
        yield from _run_groq_loop(
            user_message=user_message,
            system_prompt=system_prompt,
            api_key=groq_key,
            model=groq_model,
            session_id=mcp_session,
        )
        return

    yield {
        "type": "thinking",
        "payload": {"text": "No usable LLM after Gemini failure — deterministic fallback."},
    }
    from backend.agent import run_agent_stream as fallback

    yield from fallback(user_message, ctx)
