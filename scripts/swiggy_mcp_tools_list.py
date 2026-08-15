"""Fetch live tools/list from all three Swiggy MCP servers.

Writes:
  docs/mcp-live-catalog.json
  docs/mcp-tool-contract.md

Usage (repo root, after OAuth):
  set USE_MOCK_MCP=false
  python scripts/swiggy_mcp_tools_list.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WRITE_TOOLS = frozenset(
    {
        "place_food_order",
        "checkout",
        "book_table",
        "confirm_order",
        "create_address",
        "delete_address",
        "apply_food_coupon",
        "apply_coupon",
        "update_food_cart",
        "update_cart",
        "flush_food_cart",
        "clear_cart",
        "create_cart",
    }
)

MONEY_TOOLS = frozenset(
    {
        "place_food_order",
        "checkout",
        "book_table",
        "confirm_order",
        "create_address",
        "delete_address",
    }
)


def main() -> None:
    os.environ.setdefault("USE_MOCK_MCP", "false")
    from backend.mcp_client import list_tools, use_mock_mcp, _load_bearer_token

    if use_mock_mcp() and not _load_bearer_token():
        print("Need live token. Run: python scripts/swiggy_oauth_login.py")
        print("Then: set USE_MOCK_MCP=false")
        raise SystemExit(2)

    # Force live for tools/list even if env says mock (list against gateway)
    os.environ["USE_MOCK_MCP"] = "false"

    servers = ("food", "im", "dineout")
    catalog: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "live tools/list",
        "servers": {},
        "all_tools": [],
    }

    for server in servers:
        print(f"=== tools/list {server} ===")
        tools = list_tools(server)  # type: ignore[arg-type]
        entries = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            name = t.get("name") or t.get("tool") or ""
            entry = {
                "name": name,
                "description": (t.get("description") or "")[:2000],
                "inputSchema": t.get("inputSchema") or t.get("input_schema") or {},
                "server": server,
                "behaviour": "write" if name in WRITE_TOOLS else "read",
                "money": name in MONEY_TOOLS,
            }
            entries.append(entry)
            catalog["all_tools"].append(entry)
        catalog["servers"][server] = {
            "endpoint": f"https://mcp.swiggy.com/{server if server != 'im' else 'im'}",
            "tool_count": len(entries),
            "tools": entries,
        }
        print(f"  {len(entries)} tools: {', '.join(e['name'] for e in entries)}")

    out_json = ROOT / "docs" / "mcp-live-catalog.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_json}")

    # Human contract handbook
    lines = [
        "# Swiggy MCP — live tool contract",
        "",
        f"> Fetched: `{catalog['fetched_at']}` from live `tools/list`.",
        "> Source of truth for Nexus wiring. Do not invent tool names.",
        "",
        "## Inventory",
        "",
        "| Server | Tools |",
        "| --- | ---: |",
    ]
    for server in servers:
        sc = catalog["servers"][server]
        lines.append(f"| `{server}` | {sc['tool_count']} |")
    lines.append(f"| **Total** | **{len(catalog['all_tools'])}** |")
    lines.extend(["", "## Tools by server", ""])

    for server in servers:
        lines.append(f"### {server}")
        lines.append("")
        for t in catalog["servers"][server]["tools"]:
            schema = t.get("inputSchema") or {}
            props = schema.get("properties") or {}
            required = schema.get("required") or []
            beh = t["behaviour"]
            money = " MONEY" if t.get("money") else ""
            lines.append(f"#### `{t['name']}` ({beh}{money})")
            lines.append("")
            desc = (t.get("description") or "").strip().split("\n")[0][:300]
            if desc:
                lines.append(desc)
                lines.append("")
            if props:
                lines.append("| Param | Required | Type |")
                lines.append("| --- | --- | --- |")
                for pname, pmeta in props.items():
                    if not isinstance(pmeta, dict):
                        pmeta = {}
                    req = "yes" if pname in required else "no"
                    ptype = pmeta.get("type", "?")
                    lines.append(f"| `{pname}` | {req} | `{ptype}` |")
                    lines.append("")
            else:
                lines.append("_No input parameters (or schema empty)._")
                lines.append("")
            if t.get("money"):
                lines.append("**HITL only — never probe without user Approve.**")
                lines.append("")

    lines.extend(
        [
            "## Call shape",
            "",
            "```json",
            '{',
            '  "jsonrpc": "2.0",',
            '  "method": "tools/call",',
            '  "params": { "name": "<canonical>", "arguments": { } },',
            '  "id": 1',
            "}",
            "```",
            "",
            "Prefer `result.structuredContent` over prose `content[].text`.",
            "Address field is often `id` — Nexus normalizes to `addressId`.",
            "",
        ]
    )
    out_md = ROOT / "docs" / "mcp-tool-contract.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
