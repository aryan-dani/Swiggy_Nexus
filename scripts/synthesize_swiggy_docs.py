"""Synthesize swiggy_mcp_docs.md from cached Swiggy Builders Club documentation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "docs" / "_swiggy_cache"
OUT = ROOT / "swiggy_mcp_docs.md"

FOOD_TOOLS = [
    "search_restaurants", "get_restaurant_menu", "search_menu", "update_food_cart",
    "get_food_cart", "flush_food_cart", "fetch_food_coupons", "apply_food_coupon",
    "place_food_order", "get_food_orders", "get_food_order_details", "track_food_order",
    "get_addresses", "report_error",
]
INSTAMART_TOOLS = [
    "search_products", "your_go_to_items", "update_cart", "get_cart", "clear_cart",
    "checkout", "get_orders", "get_order_details", "track_order", "get_addresses",
    "create_address", "delete_address", "report_error",
]
DINEOUT_TOOLS = [
    "search_restaurants_dineout", "get_restaurant_details", "get_available_slots",
    "create_cart", "book_table", "get_booking_status", "get_saved_locations", "report_error",
]

SERVER_ENDPOINT = {
    "food": "https://mcp.swiggy.com/food",
    "instamart": "https://mcp.swiggy.com/im",
    "dineout": "https://mcp.swiggy.com/dineout",
}


@dataclass
class Param:
    name: str
    type_str: str
    required: bool
    description: str


@dataclass
class ToolDoc:
    name: str
    server: str
    title: str
    summary: str
    params: list[Param] = field(default_factory=list)
    stage: str = ""
    behaviour: str = ""
    endpoint: str = ""
    agent_guidance: str = ""
    next_tool: str = ""
    response_notes: str = ""


def read_cached(name: str) -> str:
    p = CACHE / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def extract_block(text: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_params_table(text: str) -> list[Param]:
    section = extract_block(text, "Parameters")
    if not section:
        return []
    rows = []
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        cols = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cols) < 4:
            continue
        name = cols[0].strip("`")
        type_str = cols[1].strip("`").replace("\\|", "|")
        required = "yes" in cols[2].lower()
        desc = cols[3]
        rows.append(Param(name, type_str, required, desc))
    return rows


def parse_details(text: str) -> dict[str, str]:
    section = extract_block(text, "Details")
    out: dict[str, str] = {}
    for line in section.splitlines():
        m = re.match(r"\| \*\*(.+?)\*\* \| `?(.+?)`? \|", line)
        if m:
            out[m.group(1)] = m.group(2).strip("`")
    return out


def ts_type(raw: str) -> str:
    raw = raw.strip().replace("\\|", "|")
    if raw == "string":
        return "string"
    if raw == "number":
        return "number"
    if raw == "boolean":
        return "boolean"
    if raw == "object[]":
        return "Record<string, unknown>[]"
    if raw == "object":
        return "Record<string, unknown>"
    if "|" in raw:
        parts = []
        for p in raw.split("|"):
            p = p.strip().strip('"').strip("'")
            if p:
                parts.append(f'"{p}"')
        if parts:
            return " | ".join(parts)
    return raw


def iface_name(tool: str) -> str:
    parts = tool.split("_")
    return "".join(p.capitalize() for p in parts) + "Input"


def gen_ts_interface(tool: ToolDoc) -> str:
    if not tool.params:
        return f"// {tool.name}: no arguments\nexport type {iface_name(tool.name)} = Record<string, never>;"
    lines = [f"export interface {iface_name(tool.name)} {{"]
    for p in tool.params:
        opt = "" if p.required else "?"
        lines.append(f"  {p.name}{opt}: {ts_type(p.type_str)};  // {p.description}")
    lines.append("}")
    return "\n".join(lines)


def parse_tool(path: Path, server: str) -> ToolDoc:
    text = path.read_text(encoding="utf-8")
    title_m = re.match(r"# (.+)", text)
    title = title_m.group(1) if title_m else path.stem
    quote_m = re.search(r"^> (.+)$", text, re.MULTILINE)
    summary_line = quote_m.group(1) if quote_m else ""
    body_m = re.search(r"^> .+\n\n(.+?)\n\n## ", text, re.DOTALL)
    summary = body_m.group(1).strip() if body_m else summary_line
    details = parse_details(text)
    guidance = extract_block(text, "Agent guidance")
    next_m = re.search(r"Continue with \[`([^`]+)`\]", text)
    return ToolDoc(
        name=path.stem,
        server=server,
        title=title,
        summary=summary,
        params=parse_params_table(text),
        stage=details.get("Stage", ""),
        behaviour=details.get("Behaviour", ""),
        endpoint=details.get("Endpoint", SERVER_ENDPOINT[server]),
        agent_guidance=guidance,
        next_tool=next_m.group(1) if next_m else "",
    )


def render_tool_section(tool: ToolDoc) -> str:
    ep = SERVER_ENDPOINT[tool.server]
    lines = [
        f"#### `{tool.name}`",
        "",
        f"**Server:** {tool.server.title()} | **Endpoint:** `POST {ep}` | **Stage:** {tool.stage} | **Behaviour:** {tool.behaviour}",
        "",
        tool.summary,
        "",
        "**Input (TypeScript):**",
        "```typescript",
        gen_ts_interface(tool),
        "```",
        "",
    ]
    if tool.params:
        lines += ["**Parameters:**", "", "| Parameter | Type | Required | Description |", "| --- | --- | --- | --- |"]
        for p in tool.params:
            req = "yes" if p.required else "no"
            type_cell = p.type_str.replace("|", "\\|")
            lines.append(f"| `{p.name}` | `{type_cell}` | {req} | {p.description} |")
        lines.append("")
    else:
        lines += ["**Parameters:** none (session auth handled automatically)", ""]

    lines += [
        "**Response envelope:**",
        "```json",
        '{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }',
        "```",
        "",
        "*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.",
        "",
        "**JSON-RPC example:**",
        "```json",
        "{",
        '  "jsonrpc": "2.0",',
        '  "method": "tools/call",',
        '  "params": {',
        f'    "name": "{tool.name}",',
        '    "arguments": { /* see TypeScript interface */ }',
        "  },",
        '  "id": 1',
        "}",
        "```",
        "",
    ]
    if tool.agent_guidance:
        lines += ["**Agent guidance:**", "", tool.agent_guidance, ""]
    if tool.next_tool:
        lines += [f"**Next in journey:** `{tool.next_tool}`", ""]
    return "\n".join(lines)


def response_field_notes() -> str:
    return """### Documented response fields (from official agent guidance)

These fields are explicitly referenced in Swiggy docs but not fully specified in response schemas:

| Tool / context | Fields |
| --- | --- |
| `search_restaurants` | `availabilityStatus` (`OPEN` \| `CLOSED` \| `UNAVAILABLE`), `distanceKm`, `nextOffset` |
| `search_products` | `products[].variants[].spinId` (SKU identifier for cart) |
| `get_food_cart` | `valid_addons`, `availablePaymentMethods`, `total`, `offers.coupon_applied`, `coupon_discount` |
| `update_food_cart` | `offers.coupon_applied` (coupon_discount=0 means suggested, not applied) |
| `place_food_order` | `orderId`, branded success `message` |
| `track_food_order` / `track_order` | ETA, delivery status timeline |
| `get_addresses` | `addressId`, `label`, display text — **no** lat/lng |
| `get_saved_locations` (Dineout) | `lat`, `lng`, address IDs |
| `get_available_slots` | `slots[].slotId`, `slots[].deals[].itemId`, `slot.reservationTime` |
| `book_table` | `bookingId` / order ID in `data` |

*Label: partial schema — inferred from agent guidance.*"""


def gap_matrix() -> str:
    return """| Area | Current mock ([`mcp_server/`](mcp_server/)) | Production Swiggy MCP |
| --- | --- | --- |
| Protocol | `{ "method", "params" }` on `/food`, `/im`, `/dineout` | JSON-RPC 2.0 `tools/call` on streamable HTTP |
| Auth | None | OAuth 2.1 + PKCE Bearer token |
| Food tools | 5: `get_addresses`, `search_restaurants`, `get_menu`, `add_to_cart`, `place_order` | 14 tools (see Section 6.1) |
| Instamart tools | 3: `search_products`, `add_to_cart`, `checkout` | 13 tools (see Section 6.2) |
| Dineout tools | 3: `search_restaurants`, `check_availability`, `book_table` | 8 tools incl. `get_available_slots`, `create_cart` |
| Cart model | Client `requestId` + `cartId` in [`mcp_server/food/dispatcher.py`](mcp_server/food/dispatcher.py) | Server-side session cart; no client cart ID |
| Address shape | `line1`, `area`, `pin` in [`mock_data/pune_addresses.py`](mock_data/pune_addresses.py) | `fullAddress`, `addressCategory`; coords omitted from `get_addresses` |
| LLM tools | Prefixed names in [`backend/llm_orchestrator.py`](backend/llm_orchestrator.py) (`food_*`, `im_*`) | Canonical tool names from MCP `tools/list` |

**Phase 3 goal:** Mock server must expose all 35 tools with production input/output schemas so agent core logic requires zero changes when swapping `LOCAL_MCP_BASE` for `mcp.swiggy.com`."""


def main() -> None:
    food = [parse_tool(CACHE / "reference" / "food" / f"{t}.md", "food") for t in FOOD_TOOLS]
    im = [parse_tool(CACHE / "reference" / "instamart" / f"{t}.md", "instamart") for t in INSTAMART_TOOLS]
    dine = [parse_tool(CACHE / "reference" / "dineout" / f"{t}.md", "dineout") for t in DINEOUT_TOOLS]
    all_tools = food + im + dine

  # Include key pattern/recipe pages verbatim (trimmed headers)
    multi_turn = read_cached("docs__build__agent-patterns__multi-turn-state.md")
    voice_chat = read_cached("docs__build__agent-patterns__voice-vs-chat.md")
    order_food = read_cached("docs__build__recipes__order-food.md")
    order_groceries = read_cached("docs__build__recipes__order-groceries.md")
    book_table_recipe = read_cached("docs__build__recipes__book-a-table.md")
    combined = read_cached("docs__build__recipes__combined.md")
    auth = read_cached("docs__start__authenticate.md")
    rate_limits = read_cached("docs__operate__rate-limits.md")
    errors = read_cached("docs__reference__errors.md")
    build_agent = read_cached("docs__start__developer__build-an-agent.md")

    today = date.today().isoformat()
    parts: list[str] = [
        "# Swiggy Builders Club MCP — Local Knowledge Base",
        "",
        f"> **Source:** [mcp.swiggy.com/builders](https://mcp.swiggy.com/builders) (fetched {today}). ",
        "> Synthesized for Swiggy Nexus local development. Not affiliated with Swiggy.",
        "",
        "**Machine-readable upstream:**",
        "- Index: `https://mcp.swiggy.com/builders/llms.txt`",
        "- Full dump: `https://mcp.swiggy.com/builders/llms-full.txt`",
        "- Per-page: append `.md` to any `/builders/docs/...` URL",
        "",
        "---",
        "",
        "## Table of Contents",
        "",
        "1. [Architecture Overview](#1-architecture-overview)",
        "2. [Authentication & Transport](#2-authentication--transport)",
        "3. [Rate Limits & Error Handling](#3-rate-limits--error-handling)",
        "4. [Agent Patterns](#4-agent-patterns)",
        "5. [End-to-End Recipes](#5-end-to-end-recipes)",
        "6. [Complete Tool Reference (35 tools)](#6-complete-tool-reference-35-tools)",
        "7. [TypeScript Schema Appendix](#7-typescript-schema-appendix)",
        "8. [Mock-vs-Production Gap Matrix](#8-mock-vs-production-gap-matrix)",
        "",
        "---",
        "",
        "## 1. Architecture Overview",
        "",
        "Swiggy Builders Club exposes **35 MCP tools** across **3 independent streamable-HTTP servers**:",
        "",
        "| Server | Endpoint | Tools | Domain |",
        "| --- | --- | --- | --- |",
        "| Food | `POST https://mcp.swiggy.com/food` | 14 | Restaurant delivery, menus, cart, coupons, orders |",
        "| Instamart | `POST https://mcp.swiggy.com/im` | 13 | Grocery quick-commerce |",
        "| Dineout | `POST https://mcp.swiggy.com/dineout` | 8 | Table booking / reservations |",
        "",
        "**Key architectural facts:**",
        "",
        "- **Transport:** MCP streamable HTTP with JSON-RPC 2.0 (`tools/call`, `tools/list`).",
        "- **Auth:** OAuth 2.1 + PKCE (S256). One Bearer token works across all three servers.",
        "- **Sessions:** Per-server carts and orders; carts do **not** cross Food / Instamart / Dineout.",
        "- **Region:** India-only (AWS Mumbai primary, Singapore failover).",
        "- **Widgets:** Food server has `hasWidgets: true` (iframe layer; v1.1).",
        "- **Payment (v1):** COD only for Builders Club orders; Food cart cap **₹1000**; Instamart minimum **₹99**.",
        "",
        "### Standard response envelope",
        "",
        "```json",
        "{",
        '  "success": true,',
        '  "data": { /* tool-specific payload */ },',
        '  "message": "optional human-readable message"',
        "}",
        "```",
        "",
        "Failure:",
        "",
        "```json",
        "{",
        '  "success": false,',
        '  "error": {',
        '    "message": "human-readable description",',
        '    "reportLink": "https://... (optional)",',
        '    "reportHint": "Run report_error to share diagnostics (optional)"',
        "  }",
        "}",
        "```",
        "",
        "### JSON-RPC call shape",
        "",
        "```json",
        "{",
        '  "jsonrpc": "2.0",',
        '  "method": "tools/call",',
        '  "params": {',
        '    "name": "search_restaurants",',
        '    "arguments": { "addressId": "addr_01HXYZ", "query": "biryani" }',
        "  },",
        '  "id": 1',
        "}",
        "```",
        "",
        "---",
        "",
        "## 2. Authentication & Transport",
        "",
        auth.replace("# Authenticate", "### OAuth 2.1 + PKCE (from official docs)"),
        "",
        "---",
        "",
        "## 3. Rate Limits & Error Handling",
        "",
        rate_limits.replace("# Rate limits", "### Rate limits"),
        "",
        errors.replace("# Error codes", "### Error codes"),
        "",
        response_field_notes(),
        "",
        "---",
        "",
        "## 4. Agent Patterns",
        "",
        "### Multi-turn cart state",
        "",
        multi_turn.replace("# Multi-turn cart state", "").strip(),
        "",
        "### Voice vs chat",
        "",
        voice_chat.replace("# Voice vs chat", "").strip(),
        "",
        "### Framework integration (LangGraph / others)",
        "",
        build_agent.replace("# Build an agent", "").strip(),
        "",
        "---",
        "",
        "## 5. End-to-End Recipes",
        "",
        "### Order food",
        "",
        order_food.replace("# Order food end-to-end", "").strip(),
        "",
        "### Order groceries (Instamart)",
        "",
        order_groceries.replace("# Order groceries end-to-end", "").strip(),
        "",
        "### Book a table (Dineout)",
        "",
        book_table_recipe.replace("# Book a table", "").strip(),
        "",
        "### Combined evening planner",
        "",
        combined.replace("# Plan my evening (combined)", "").strip(),
        "",
        "---",
        "",
        "## 6. Complete Tool Reference (35 tools)",
        "",
        "### 6.1 Food (14 tools)",
        "",
    ]
    for t in food:
        parts.append(render_tool_section(t))

    parts += ["### 6.2 Instamart (13 tools)", ""]
    for t in im:
        parts.append(render_tool_section(t))

    parts += ["### 6.3 Dineout (8 tools)", ""]
    for t in dine:
        parts.append(render_tool_section(t))

    parts += [
        "---",
        "",
        "## 7. TypeScript Schema Appendix",
        "",
        "### Shared types",
        "",
        "```typescript",
        "export interface SwiggySuccess<T> {",
        "  success: true;",
        "  data: T;",
        "  message?: string;",
        "}",
        "",
        "export interface SwiggyError {",
        "  success: false;",
        "  error: {",
        "    message: string;",
        "    reportLink?: string;",
        "    reportHint?: string;",
        "  };",
        "}",
        "",
        "export type SwiggyResponse<T> = SwiggySuccess<T> | SwiggyError;",
        "",
        'export type AddressCategory = "HOME" | "WORK" | "OFFICE" | "FRIENDS_AND_FAMILY" | "OTHER";',
        "",
        "export type PaymentMethod = string; // from get_food_cart / get_cart availablePaymentMethods",
        "```",
        "",
        "### Per-tool input interfaces",
        "",
        "```typescript",
    ]
    for t in all_tools:
        parts.append(gen_ts_interface(t))
        parts.append("")
    parts += ["```", "", "---", "", "## 8. Mock-vs-Production Gap Matrix", "", gap_matrix(), ""]

    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(parts)} sections)")


if __name__ == "__main__":
    main()
