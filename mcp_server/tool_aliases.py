"""Map production Swiggy tool names to legacy mock handler names.

Delegates to ``backend.mcp_aliases.to_legacy_handler`` so live + mock share one table.
"""

from __future__ import annotations

from typing import Literal

from backend.mcp_aliases import to_legacy_handler

Vertical = Literal["food", "im", "dineout"]


def resolve_method(vertical: str, method: str) -> str:
    m = (method or "").strip()
    if vertical not in ("food", "im", "dineout"):
        return m
    return to_legacy_handler(vertical, m)  # type: ignore[arg-type]
