"""Spot-check parameter parity between cache and swiggy_mcp_docs.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "docs" / "_swiggy_cache"
OUT = ROOT / "swiggy_mcp_docs.md"

CHECKS = [
    ("food", "get_addresses"),
    ("instamart", "create_address"),
    ("instamart", "delete_address"),
    ("dineout", "get_restaurant_details"),
    ("food", "search_restaurants"),
]


def parse_params_from_md(text: str) -> list[str]:
    in_params = False
    names: list[str] = []
    for line in text.splitlines():
        if line.startswith("## Parameters"):
            in_params = True
            continue
        if in_params and line.startswith("## "):
            break
        if in_params and line.startswith("| `"):
            cols = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
            if len(cols) >= 4 and cols[0] != "Parameter":
                names.append(cols[0].strip("`"))
    return names


def parse_params_from_synth(block: str) -> list[str]:
    names: list[str] = []
    in_table = False
    for line in block.splitlines():
        if line.strip() == "**Parameters:**":
            in_table = True
            continue
        if in_table and line.startswith("**") and "Parameters" not in line:
            break
        if in_table and line.startswith("| `"):
            cols = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
            if len(cols) >= 4 and cols[0] != "Parameter":
                names.append(cols[0].strip("`"))
    return names


def main() -> int:
    out = OUT.read_text(encoding="utf-8")
    passed = 0
    for server, name in CHECKS:
        cached = (CACHE / "reference" / server / f"{name}.md").read_text(encoding="utf-8")
        cp = parse_params_from_md(cached)
        m = re.search(rf"#### `{re.escape(name)}`.*?(?=\n#### `|\Z)", out, re.DOTALL)
        block = m.group(0) if m else ""
        sp = parse_params_from_synth(block)
        ok = cp == sp
        status = "PASS" if ok else "FAIL"
        print(f"{name}: cache={cp} synth={sp} -> {status}")
        if ok:
            passed += 1
    print(f"\nSpot-check: {passed}/{len(CHECKS)} passed")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
