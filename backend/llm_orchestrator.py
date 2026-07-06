import json
import os
import uuid
from typing import Any, Generator

from backend.mcp_client import call_tool, LocalMCPError
from backend.memory import get_user_preferences, set_user_preference

# Define OpenAI tools schema
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "food_get_addresses",
            "description": "Get user's saved addresses for food delivery.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "food_search_restaurants",
            "description": "Search for food delivery restaurants near an address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "addressId": {"type": "string", "description": "The ID of the address to search near."}
                },
                "required": ["addressId"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "food_get_menu",
            "description": "Get the menu for a specific food delivery restaurant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string", "description": "The ID of the restaurant."}
                },
                "required": ["restaurantId"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "food_add_to_cart",
            "description": "Add items to a food delivery cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requestId": {"type": "string", "description": "Session UUID for the cart."},
                    "restaurantId": {"type": "string", "description": "The ID of the restaurant."},
                    "lines": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_id": {"type": "string"},
                                "qty": {"type": "integer"}
                            },
                            "required": ["item_id", "qty"]
                        }
                    }
                },
                "required": ["requestId", "restaurantId", "lines"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "food_place_order",
            "description": "Place a food delivery order from a cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cartId": {"type": "string", "description": "The cart ID from add_to_cart."},
                    "paymentMode": {"type": "string", "enum": ["COD", "ONLINE"], "default": "COD"}
                },
                "required": ["cartId"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "im_search_products",
            "description": "Search for Instamart grocery products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for groceries."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "im_add_to_cart",
            "description": "Add items to an Instamart grocery cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requestId": {"type": "string", "description": "Session UUID for the cart."},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "qty": {"type": "integer"}
                            },
                            "required": ["product_id", "qty"]
                        }
                    }
                },
                "required": ["requestId", "items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "im_checkout",
            "description": "Checkout an Instamart grocery cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cartId": {"type": "string", "description": "The cart ID from im_add_to_cart."}
                },
                "required": ["cartId"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_search_restaurants",
            "description": "Search for Dineout restaurant reservations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "Optional area/city hint."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_check_availability",
            "description": "Check table availability slots for Dineout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "partySize": {"type": "integer"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"}
                },
                "required": ["restaurantId", "partySize", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dineout_book_table",
            "description": "Book a table for a specific Dineout slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurantId": {"type": "string"},
                    "partySize": {"type": "integer"},
                    "slot": {"type": "string", "description": "time slot (e.g. 19:00)"}
                },
                "required": ["restaurantId", "partySize", "slot"]
            }
        }
    }
]

def _sse_tool(server_key: str, http_path: str, method: str, params: dict[str, Any], data: Any) -> dict[str, Any]:
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


def run_llm_agent(user_message: str, context: dict[str, Any] | None) -> Generator[dict[str, Any], None, None]:
    ctx = context or {}
    api_key = os.environ.get("GROQ_API_KEY", "").strip()

    # Rich scripted demos only when no LLM is configured.
    if not api_key and ctx.get("scenario") in REVIEWER_SCENARIOS:
        from backend.agent import run_agent_stream as deterministic

        yield from deterministic(user_message, ctx)
        return

    if not api_key:
        yield {"type": "thinking", "payload": {"text": "GROQ_API_KEY missing. Falling back to deterministic mode."}}
        from backend.agent import run_agent_stream as fallback

        yield from fallback(user_message, context)
        return

    # Import Groq SDK lazily so the module can be imported even if the SDK
    # isn't installed in the running Python environment. If import fails,
    # gracefully fall back to deterministic agent.
    try:
        from groq import Groq
    except Exception:
        yield {"type": "thinking", "payload": {"text": "Groq SDK not available. Falling back to deterministic mode."}}
        from backend.agent import run_agent_stream as fallback
        yield from fallback(user_message, context)
        return

    client = Groq(api_key=api_key)
    session_id = str(uuid.uuid4())

    yield {
        "type": "thinking",
        "payload": {"text": f"Groq {os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')} · agentic MCP tool loop"},
    }

    prefs = get_user_preferences()
    prefs_str = json.dumps(prefs) if prefs else "None"

    scenario = ctx.get("scenario")
    scenario_hint = ""
    if isinstance(scenario, str) and scenario in SCENARIO_PROMPTS:
        scenario_hint = f"\nActive reviewer scenario ({scenario}): {SCENARIO_PROMPTS[scenario]}"

    party = ctx.get("partySize")
    event = ctx.get("event")
    if not party and isinstance(event, dict):
        party = event.get("guests")
    if party:
        scenario_hint += f"\nParty size: {party}."

    system_prompt = (
        "You are Swiggy Nexus, an autonomous agentic copilot. "
        "You handle cross-vertical commerce requests (Food delivery, Instamart groceries, and Dineout reservations).\n"
        f"User Preferences: {prefs_str}{scenario_hint}\n"
        "1. Start by getting context, e.g., 'food_get_addresses' if you need a delivery location.\n"
        "2. To order food, you MUST: find restaurants -> get menu -> add_to_cart -> place_order.\n"
        "3. To order groceries, you MUST: search products -> add_to_cart -> checkout.\n"
        "4. To book Dineout, you MUST: search restaurants -> check_availability -> book_table.\n"
        "5. Parallel execution: invoke multiple tools in one turn when planning events (table + groceries + dessert).\n"
        "6. Stream tool calls visibly — prefer several MCP tools over a short reply."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    feed_items = []
    
    while True:
        try:
            resp = client.chat.completions.create(
                model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            yield {"type": "assistant", "payload": {"text": f"LLM error: {str(e)}"}}
            yield {"type": "done", "payload": {"assistant_reply": f"LLM error: {str(e)}", "feed_items": feed_items}}
            break

        msg = resp.choices[0].message
        
        if not msg.tool_calls:
            assistant_reply = msg.content or "Done."
            yield {"type": "assistant", "payload": {"text": assistant_reply}}
            yield {"type": "done", "payload": {"assistant_reply": assistant_reply, "feed_items": feed_items}}
            break
            
        # Append the assistant message with tool calls
        messages.append(msg)
        
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            
            # Map legacy prefixes
            vertical = name.split("_")[0] # food, im, dineout
            method = name.replace(f"{vertical}_", "", 1)
            
            if "requestId" in args:
                args["requestId"] = session_id
            if "request_id" in args:
                args["request_id"] = session_id
                
            yield {"type": "thinking", "payload": {"text": f"Executor · {name}"}}

            try:
                data = call_tool(vertical, method, args)
                tool_payload = _sse_tool(vertical, f"/{vertical}", method, args, data)
                tool_payload["method"] = name
                tool_payload["phase"] = "Executor"
                yield {"type": "tool", "payload": tool_payload}
                
                # Render logic (feed mapping)
                if method == "search_restaurants" and "restaurants" in data:
                    for r in data["restaurants"]:
                        feed_items.append({
                            "type": "restaurant" if vertical == "food" else "dineout",
                            "title": r.get("name", "Venue"),
                            "subtitle": f"★ {r.get('rating')} · {', '.join(r.get('cuisines') or [])}",
                            "meta": {f"restaurant_id": r.get("restaurant_id")}
                        })
                elif method == "search_products" and "products" in data:
                    for p in data["products"]:
                        feed_items.append({
                            "type": "instamart",
                            "title": p.get("name"),
                            "subtitle": f"₹{p.get('price_inr')}",
                            "meta": {"product_id": p.get("product_id")}
                        })
                elif method in ["place_order", "checkout"]:
                    feed_items.append({
                        "type": f"{vertical}_order",
                        "title": data.get("message", "Order placed"),
                        "subtitle": f"ETA ~{data.get('eta_mins')} mins",
                        "meta": data
                    })
                elif method == "book_table":
                    feed_items.append({
                        "type": "booking",
                        "title": data.get("confirmation_message", "Table Booked"),
                        "subtitle": data.get("booking_id"),
                        "meta": data
                    })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(data)
                })
            except LocalMCPError as e:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": e.payload})
                })

        if feed_items:
            yield {"type": "feed", "payload": {"items": list(feed_items)}}
