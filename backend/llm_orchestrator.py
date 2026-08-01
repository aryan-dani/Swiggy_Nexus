"""SSE chat orchestrator — Gemini primary, Groq fallback, deterministic last resort.

Telegram uses the async twin in `app/services/llm.py`. Both share `backend/tool_schemas.TOOLS`.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Generator

from backend.mcp_client import call_tool, LocalMCPError
from backend.memory import get_user_preferences

# Tool schemas live in backend/tool_schemas.py — one source of truth shared by
# this SSE orchestrator and the async Telegram agent in app/services/llm.py.
from backend.tool_schemas import TOOLS

log = logging.getLogger(__name__)

_GEMINI_MODEL_CANDIDATES = (
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
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


def _env_keys() -> tuple[str, str, str, str]:
    """Return (gemini_key, gemini_model, groq_key, groq_model) from env + app settings."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_model = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    groq_model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"
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
    except Exception:  # noqa: BLE001
        pass
    return gemini_key, gemini_model, groq_key, groq_model


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
        "You are Swiggy Nexus, an autonomous agentic copilot for Swiggy's three verticals: "
        "Food delivery, Instamart groceries, and Dineout table reservations.\n\n"
        f"User Preferences: {prefs_str}{scenario_hint}\n\n"
        "## Core rules\n"
        "1. ALWAYS start by resolving location: call food_get_addresses (Food/Instamart) or "
        "dineout_get_saved_locations (Dineout) before any search.\n"
        "2. For dish-name food orders prefer food_search_menu first, then food_add_to_cart with "
        "real itemIds, then confirm before food_place_order. For restaurant-name flows: "
        "search_restaurants → get_menu → add_to_cart → get_food_cart → confirm → place_order.\n"
        "3. For grocery orders: search_products → add_to_cart → get_cart → confirm → checkout\n"
        "4. For Dineout: get_saved_locations → search_restaurants → get_restaurant_details → "
        "check_availability → confirm slot + party size → book_table\n"
        "5. NEVER auto-place an order. ALWAYS get explicit user confirmation (yes/confirm/proceed) "
        "before calling place_order or checkout.\n"
        "6. CART CAP: Cart total must be under ₹1000 (beta restriction). If cart >= ₹1000, "
        "tell user to use the Swiggy app instead.\n"
        "7. PAYMENT: COD only in v1. Do NOT mention online payment options.\n"
        "8. CART + RESTAURANT SWITCH: Warn the user that switching restaurants will clear their cart.\n"
        "9. COUPON NOTE: A coupon is only 'applied' if coupon_discount > 0. Never say a coupon "
        "saved money unless the discount amount is > 0.\n"
        "10. AVAILABILITY: Only recommend restaurants with availabilityStatus='OPEN' (Food) or "
        "availability='AVAILABLE' (Dineout).\n"
        "11. Always call food_get_food_cart after every food_add_to_cart — the cart widget is "
        "NOT updated otherwise.\n"
        "12. For multi-vertical requests (e.g. dinner out + dessert delivered), use parallel "
        "tool calls in a single turn.\n"
        "13. CANCELLATION: If user asks to cancel an order, tell them to call Swiggy customer "
        "care at 080-67466729. Do NOT call any cancel tool.\n"
        "14. Stream tool calls visibly. Prefer several MCP tool calls over a brief reply.\n"
        "15. For Instamart quick reorders, offer im_your_go_to_items before search.\n"
        "16. NEVER invent IDs — copy restaurantId / itemId / spinId from tool results only.\n"
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
    parts = name.split("_", 1)
    if len(parts) == 2:
        vertical, method = parts
    else:
        vertical, method = "food", name
    if "requestId" in args:
        args["requestId"] = session_id
    if "request_id" in args:
        args["request_id"] = session_id
    data = call_tool(vertical, method, args)
    return vertical, method, data


def _run_groq_loop(
    *,
    user_message: str,
    system_prompt: str,
    api_key: str,
    model: str,
) -> Generator[dict[str, Any], None, None]:
    from groq import Groq

    client = Groq(api_key=api_key)
    session_id = str(uuid.uuid4())
    yield {
        "type": "thinking",
        "payload": {"text": f"Groq {model} · agentic MCP tool loop (fallback)"},
    }

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

    while True:
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


def _run_gemini_loop(
    *,
    user_message: str,
    system_prompt: str,
    api_key: str,
    model: str,
) -> Generator[dict[str, Any], None, None]:
    from google import genai
    from google.genai import types

    from app.services.llm import _gemini_declarations, _truncate_for_model, _wrap_result

    client = genai.Client(api_key=api_key)
    declarations = _gemini_declarations(types)
    session_id = str(uuid.uuid4())

    yield {
        "type": "thinking",
        "payload": {"text": f"Gemini {model} · agentic MCP tool loop"},
    }

    def _config(with_tools: bool = True, no_thinking: bool = False) -> Any:
        kwargs: dict[str, Any] = {"system_instruction": system_prompt}
        if with_tools:
            kwargs["tools"] = [types.Tool(function_declarations=declarations)]
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )
        if no_thinking:
            try:
                kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="minimal")
            except (TypeError, ValueError):
                kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
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

    max_rounds = 8
    for round_index in range(max_rounds):
        resp = client.models.generate_content(
            model=model, contents=contents, config=_config()
        )
        # Malformed / empty → one retry with minimal thinking
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
                model=model, contents=contents, config=_config(no_thinking=True)
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
    ctx = context or {}
    gemini_key, gemini_model, groq_key, groq_model = _env_keys()

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

        yield from fallback(user_message, context)
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

            yield from fallback(user_message, context)
            return
        yield from _run_groq_loop(
            user_message=user_message,
            system_prompt=system_prompt,
            api_key=groq_key,
            model=groq_model,
        )
        return

    yield {
        "type": "thinking",
        "payload": {"text": "No usable LLM after Gemini failure — deterministic fallback."},
    }
    from backend.agent import run_agent_stream as fallback

    yield from fallback(user_message, context)
