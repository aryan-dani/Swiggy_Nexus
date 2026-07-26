"""HITL notifications — Telegram inline buttons, Discord, Slack, console."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


async def send_approval_request(
    platform: str,
    event_summary: dict[str, Any],
    cost_breakdown: dict[str, Any],
    approve_url: str,
    request_id: str | None = None,
) -> bool:
    platform = (platform or "console").lower().strip()
    req_id = request_id or event_summary.get("request_id", "REQ-UNKNOWN")
    title = event_summary.get("title", "Social Concierge Event")
    loc = event_summary.get("location", "Home")
    mode = cost_breakdown.get("mode", "DINEOUT")
    total_cost = cost_breakdown.get("total_cost_inr") or cost_breakdown.get("total_inr") or 0.0
    summary = event_summary.get("summary") or ""
    reject_url = approve_url.replace("/approve/", "/reject/")

    if platform == "console":
        print("\n" + "=" * 60)
        print(f"[HITL] Request ID: {req_id}")
        print(f"Event: {title} @ {loc}")
        print(f"Mode: {mode} · INR {total_cost}")
        print(summary)
        print(f"Approve: POST {approve_url}")
        print(f"Reject:  POST {reject_url}")
        print("=" * 60 + "\n")
        return True

    if platform == "telegram":
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return await send_approval_request(
                "console", event_summary, cost_breakdown, approve_url, request_id=req_id
            )
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        text = (
            f"🚨 *HITL Approval Required*\n"
            f"ID: `{req_id}`\n"
            f"*Event:* {title}\n"
            f"*Location:* {loc}\n"
            f"*Mode:* `{mode}`\n"
            f"*Cost:* INR {total_cost}\n"
            f"{summary}"
        )
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve", "callback_data": f"approve:{req_id}"},
                        {"text": "❌ Reject", "callback_data": f"reject:{req_id}"},
                    ]
                ]
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200

    if platform == "discord":
        if not settings.DISCORD_WEBHOOK_URL:
            return await send_approval_request(
                "console", event_summary, cost_breakdown, approve_url, request_id=req_id
            )
        embed = {
            "title": f"HITL Approval [{req_id}]",
            "description": f"**{title}** — {summary}",
            "color": 16744192,
            "fields": [
                {"name": "Location", "value": loc, "inline": True},
                {"name": "Mode", "value": mode, "inline": True},
                {"name": "Cost", "value": f"₹{total_cost}", "inline": True},
                {"name": "Approve", "value": approve_url, "inline": False},
                {"name": "Reject", "value": reject_url, "inline": False},
            ],
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
            return resp.status_code in (200, 204)

    if platform == "slack":
        if not settings.SLACK_WEBHOOK_URL:
            return await send_approval_request(
                "console", event_summary, cost_breakdown, approve_url, request_id=req_id
            )
        payload = {
            "text": f"HITL {req_id}: {title} ({mode}) ₹{total_cost}\nApprove: {approve_url}"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.SLACK_WEBHOOK_URL, json=payload)
            return resp.status_code == 200

    return await send_approval_request(
        "console", event_summary, cost_breakdown, approve_url, request_id=req_id
    )


async def send_qol_prompt(
    text: str,
    *,
    buttons: list[tuple[str, str]] | None = None,
) -> bool:
    """Send a free-form QoL prompt (rain / bhajiya / guests / IPL)."""
    if settings.NOTIFICATION_PLATFORM == "telegram" and settings.TELEGRAM_BOT_TOKEN:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        keyboard = None
        if buttons:
            keyboard = {
                "inline_keyboard": [
                    [{"text": label, "callback_data": data} for label, data in buttons]
                ]
            }
        payload: dict[str, Any] = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }
        if keyboard:
            payload["reply_markup"] = keyboard
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200

    print("\n[QoL PROMPT]\n" + text + "\n")
    if buttons:
        print("Buttons:", buttons)
    return True
