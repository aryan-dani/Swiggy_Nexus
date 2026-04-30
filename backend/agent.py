"""LangGraph workflow: analyze intent → mock MCP tools → normalized feed cards."""

from __future__ import annotations

import json
import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from backend.mcp_server import dispatch


class AgentState(TypedDict, total=False):
    user_message: str
    context: dict[str, Any]
    thinking_steps: Annotated[list[str], operator.add]
    vertical: Literal["food", "instamart", "dineout"]
    mcp_method: str
    mcp_params: dict[str, Any]
    raw_tool_results: dict[str, Any]
    rpc_logs: Annotated[list[dict[str, Any]], operator.add]
    feed_items: list[dict[str, Any]]
    assistant_reply: str


def _infer_cuisine(message: str) -> str:
    m = message.lower()
    if "italian" in m:
        return "italian"
    if "chinese" in m:
        return "chinese"
    if "south indian" in m or "dosa" in m:
        return "south indian"
    if "biryani" in m:
        return "biryani"
    return "comfort food"


def _infer_instamart_category(message: str, ctx: dict[str, Any]) -> str:
    m = message.lower()
    if "snack" in m or "chips" in m:
        return "snacks"
    if "drink" in m or "beverage" in m or "coffee" in m:
        return "beverages"
    if ctx.get("category"):
        return str(ctx["category"])
    return "groceries"


def _default_coords(ctx: dict[str, Any]) -> tuple[float, float]:
    lat = float(ctx.get("lat", 12.9716))
    long = float(ctx.get("long", 77.5946))
    return lat, long


def analyze_context(state: AgentState) -> dict[str, Any]:
    msg = state.get("user_message") or ""
    ctx = state.get("context") or {}
    steps: list[str] = ["Analyzing user context and natural-language intent…"]

    mlow = msg.lower()
    vertical: Literal["food", "instamart", "dineout"] = "food"

    if any(
        k in mlow
        for k in (
            "dineout",
            "reservation",
            "book a table",
            "team dinner",
            "party of",
            "table for",
            "restaurant night",
        )
    ):
        vertical = "dineout"
    elif any(
        k in mlow
        for k in (
            "instamart",
            "grocery",
            "groceries",
            "snacks",
            "stock up",
            "coding for",
            "ingredient",
            "supplies",
        )
    ):
        vertical = "instamart"

    if ctx.get("scenario") == "team_dinner" or ctx.get("vertical") == "dineout":
        vertical = "dineout"
    if ctx.get("vertical") == "instamart":
        vertical = "instamart"

    method_map = {
        "food": "food_search_restaurants",
        "instamart": "instamart_get_inventory",
        "dineout": "dineout_check_availability",
    }
    method = method_map[vertical]

    params: dict[str, Any]
    if vertical == "food":
        lat, long = _default_coords(ctx)
        params = {
            "cuisine": _infer_cuisine(msg),
            "lat": lat,
            "long": long,
        }
    elif vertical == "instamart":
        params = {"category": _infer_instamart_category(msg, ctx)}
    else:
        params = {
            "restaurant_id": str(ctx.get("restaurant_id", "demo-bistro-001")),
            "party_size": int(ctx.get("party_size", 4)),
            "time": str(ctx.get("time", "19:00")),
        }

    steps.append(f"Selected vertical `{vertical}` → will call `{method}` (mock MCP).")

    return {
        "thinking_steps": steps,
        "vertical": vertical,
        "mcp_method": method,
        "mcp_params": params,
    }


def call_tools(state: AgentState) -> dict[str, Any]:
    method = state["mcp_method"]
    params = state["mcp_params"]
    preview = json.dumps(params, default=str)
    steps = [f"Invoking Swiggy MCP tool `{method}` with params: {preview}"]

    try:
        result, log = dispatch(method, params)
    except Exception as e:  # noqa: BLE001
        err = str(e)
        steps.append(f"Tool error: {err}")
        return {
            "thinking_steps": steps,
            "raw_tool_results": {"method": method, "error": err},
            "rpc_logs": [
                {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "error": err,
                }
            ],
        }

    steps.append(f"Received mock result from `{method}` — synthesizing cards…")
    return {
        "thinking_steps": steps,
        "raw_tool_results": {"method": method, "result": result},
        "rpc_logs": [log],
    }


def synthesize(state: AgentState) -> dict[str, Any]:
    vertical = state.get("vertical", "food")
    raw = state.get("raw_tool_results") or {}
    result = raw.get("result")
    steps: list[str] = ["Building Nexus Live Feed cards for the UI…"]

    feed_items: list[dict[str, Any]] = []
    reply_parts: list[str] = []

    if raw.get("error"):
        feed_items.append(
            {
                "type": "error",
                "title": "Tool error",
                "subtitle": str(raw.get("error")),
                "meta": {},
            }
        )
        return {
            "thinking_steps": steps,
            "feed_items": feed_items,
            "assistant_reply": "Something went wrong calling the mock MCP tool. Toggle Developer Mode to inspect logs.",
        }

    if vertical == "food" and isinstance(result, list):
        for r in result:
            feed_items.append(
                {
                    "type": "restaurant",
                    "title": r.get("name", "Restaurant"),
                    "subtitle": f"★ {r.get('rating', '—')} · ETA ~{r.get('eta_mins', '?')} min · {r.get('tag', '')}",
                    "meta": {
                        "id": r.get("id"),
                        "cuisine": r.get("cuisine"),
                        "eta_mins": r.get("eta_mins"),
                    },
                }
            )
        reply_parts.append(f"Here are {len(feed_items)} demo restaurants for your run.")
    elif vertical == "instamart" and isinstance(result, list):
        for item in result:
            stock = "In stock" if item.get("in_stock") else "Out of stock (demo)"
            feed_items.append(
                {
                    "type": "instamart",
                    "title": item.get("name", "SKU"),
                    "subtitle": f"₹{item.get('price_inr', '—')} · {stock}",
                    "meta": {"sku": item.get("sku"), "in_stock": item.get("in_stock")},
                }
            )
        reply_parts.append("Instamart-style inventory (synthetic) is ready on the right.")
    elif vertical == "dineout" and isinstance(result, dict):
        slots = result.get("slots") or []
        feed_items.append(
            {
                "type": "dineout",
                "title": f"Dineout · Party of {result.get('party_size', '?')}",
                "subtitle": f"Slot {result.get('time_slot')} · Available: {result.get('available')}",
                "meta": {"slots": slots, "restaurant_id": result.get("restaurant_id")},
            }
        )
        for s in slots[:5]:
            feed_items.append(
                {
                    "type": "dineout_slot",
                    "title": f"Table window · {s}",
                    "subtitle": "Synthetic availability — demo only",
                    "meta": {"time": s},
                }
            )
        reply_parts.append("Dineout availability (mock) — see suggested slots in the feed.")

    assistant_reply = " ".join(reply_parts) if reply_parts else "Processed your request with the mock Swiggy MCP layer."
    steps.append("Done — stream closed after this turn.")

    return {
        "thinking_steps": steps,
        "feed_items": feed_items,
        "assistant_reply": assistant_reply,
    }


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("analyze", analyze_context)
    g.add_node("call_tools", call_tools)
    g.add_node("synthesize", synthesize)
    g.set_entry_point("analyze")
    g.add_edge("analyze", "call_tools")
    g.add_edge("call_tools", "synthesize")
    g.add_edge("synthesize", END)
    return g


_compiled = None


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile()
    return _compiled


def _merge_agent_state(base: AgentState, patch: dict[str, Any]) -> AgentState:
    out = dict(base)
    for k, v in patch.items():
        if k == "thinking_steps" and isinstance(v, list):
            out["thinking_steps"] = list(out.get("thinking_steps") or []) + v
        elif k == "rpc_logs" and isinstance(v, list):
            out["rpc_logs"] = list(out.get("rpc_logs") or []) + v
        else:
            out[k] = v  # type: ignore[assignment]
    return out  # type: ignore[return-value]


def run_agent_stream(user_message: str, context: dict[str, Any] | None):
    """Yield event dicts: thinking | tool | feed | assistant | done.

    Executed sequentially (same edges as LangGraph) for reliable SSE without
    relying on graph.stream() callback internals across langchain versions.
    """
    state: AgentState = {
        "user_message": user_message,
        "context": context or {},
        "thinking_steps": [],
        "rpc_logs": [],
    }

    a = analyze_context(state)
    state = _merge_agent_state(state, a)
    for text in a.get("thinking_steps", []):
        yield {"type": "thinking", "payload": {"text": text}}

    b = call_tools(state)
    state = _merge_agent_state(state, b)
    for text in b.get("thinking_steps", []):
        yield {"type": "thinking", "payload": {"text": text}}
    for log_entry in b.get("rpc_logs", []):
        yield {"type": "tool", "payload": log_entry}

    c = synthesize(state)
    state = _merge_agent_state(state, c)
    for text in c.get("thinking_steps", []):
        yield {"type": "thinking", "payload": {"text": text}}
    if "feed_items" in c:
        yield {"type": "feed", "payload": {"items": c["feed_items"]}}
    if "assistant_reply" in c:
        yield {"type": "assistant", "payload": {"text": c["assistant_reply"]}}

    yield {
        "type": "done",
        "payload": {
            "assistant_reply": state.get("assistant_reply"),
            "feed_items": state.get("feed_items") or [],
        },
    }
