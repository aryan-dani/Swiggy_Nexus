"""Bill Split — BHIM-style equal shares with mock UPI deep links.

Nexus extension (the real Swiggy MCP has no split tool). Share math is real;
UPI links are demo handles so reviewers can see the intended UX.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from app.config import settings
from app.db.store import record_qol_event
from app.services.notifications import send_qol_prompt

log = logging.getLogger(__name__)

_UPI_HANDLE = "nexus.demo@upi"

# Friendly names for the demo Taste Vault users
_KNOWN_NAMES = {
    "aryan@nexus.ai": "Aryan",
    "himali@nexus.ai": "Himali",
    "siya@nexus.ai": "Siya",
    "swayam@nexus.ai": "Swayam",
    "priya@nexus.ai": "Priya",
    "kabir@nexus.ai": "Kabir",
    "ananya@nexus.ai": "Ananya",
    "rohan@nexus.ai": "Rohan",
    "meera@nexus.ai": "Meera",
    # legacy
    "dani@nexus.ai": "Aryan",
    "sobaan@nexus.ai": "Siya",
    "alex@nexus.ai": "Alex",
}


def _display_name(email: str) -> str:
    known = _KNOWN_NAMES.get(email.lower().strip())
    if known:
        return known
    local = email.split("@", 1)[0]
    return local.replace(".", " ").title() or email


def compute_split(total_inr: float, attendees: list[str], note: str = "") -> dict[str, Any]:
    """Equal split in whole rupees; the remainder lands on the host (first attendee)."""
    people = [a.strip() for a in attendees if a and a.strip()]
    if not people:
        raise ValueError("attendees must not be empty")
    total = round(float(total_inr))
    if total <= 0:
        raise ValueError("total_inr must be positive")

    n = len(people)
    base = total // n
    remainder = total - base * n

    shares: list[dict[str, Any]] = []
    for i, email in enumerate(people):
        amount = base + (remainder if i == 0 else 0)
        name = _display_name(email)
        upi_note = quote(note or "Swiggy Nexus split")
        shares.append(
            {
                "email": email,
                "name": name,
                "amount_inr": amount,
                "is_host": i == 0,
                "upi_link": (
                    f"upi://pay?pa={_UPI_HANDLE}&pn={quote(name)}"
                    f"&am={amount}&cu=INR&tn={upi_note}"
                ),
            }
        )
    return {
        "total_inr": total,
        "per_head_inr": base,
        "attendee_count": n,
        "shares": shares,
        "note": note or "Swiggy Nexus split",
        "extension": "nexus_split_bill (not in official Swiggy MCP v1)",
    }


async def split_and_notify(
    total_inr: float,
    attendees: list[str],
    *,
    order_id: str | None = None,
    title: str = "Bill split",
    notify: bool = True,
) -> dict[str, Any]:
    result = compute_split(total_inr, attendees, note=title)

    lines = [f"🧾 *{title}* — ₹{result['total_inr']} across {result['attendee_count']}"]
    for s in result["shares"]:
        host = " (host)" if s["is_host"] else ""
        lines.append(f"• {s['name']}{host}: ₹{s['amount_inr']}")
    lines.append("Tap-to-pay links are demo UPI handles — no real collection.")
    # Chrono-Host / WOW web surface passes notify=False so Beat 1 stays phone-silent.
    if notify:
        await send_qol_prompt("\n".join(lines))
    else:
        print("\n[QoL PROMPT · telegram suppressed]\n" + "\n".join(lines) + "\n")

    record_qol_event(
        kind="bill_split",
        title=f"{title} · ₹{result['total_inr']} / {result['attendee_count']}",
        detail=order_id or "",
        severity="info",
        meta={
            "shares": [
                {"name": s["name"], "amount_inr": s["amount_inr"]} for s in result["shares"]
            ],
            "telegram_notified": bool(notify),
        },
    )
    return result
