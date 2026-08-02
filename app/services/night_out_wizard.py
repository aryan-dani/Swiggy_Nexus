"""Night-out guided wizard — shared draft state for Ops UI + Telegram."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from app.db.models import ensure_night_out_guests
from app.services.night_out import HOST_ID, plan_night_out, resolve_guest_emails

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
TTL_SECONDS = 30 * 60

# wizard_id → draft dict
_DRAFTS: dict[str, dict[str, Any]] = {}
# telegram chat_id → wizard_id
_CHAT_WIZARDS: dict[str, str] = {}

GUEST_CHIPS = [
    {"id": "aryan", "label": "Aryan", "email": "aryan@nexus.ai", "host": True},
    {"id": "himali", "label": "Himali", "email": "himali@nexus.ai", "host": False},
    {"id": "siya", "label": "Siya", "email": "siya@nexus.ai", "host": False},
    {"id": "swayam", "label": "Swayam", "email": "swayam@nexus.ai", "host": False},
    {"id": "priya", "label": "Priya", "email": "priya@nexus.ai", "host": False},
    {"id": "kabir", "label": "Kabir", "email": "kabir@nexus.ai", "host": False},
    {"id": "ananya", "label": "Ananya", "email": "ananya@nexus.ai", "host": False},
    {"id": "rohan", "label": "Rohan", "email": "rohan@nexus.ai", "host": False},
    {"id": "meera", "label": "Meera", "email": "meera@nexus.ai", "host": False},
]


def _purge_expired() -> None:
    now = time.time()
    dead = [k for k, v in _DRAFTS.items() if now - float(v.get("created_at") or 0) > TTL_SECONDS]
    for k in dead:
        _DRAFTS.pop(k, None)
    for chat, wid in list(_CHAT_WIZARDS.items()):
        if wid not in _DRAFTS:
            _CHAT_WIZARDS.pop(chat, None)


def _get(wizard_id: str) -> dict[str, Any]:
    _purge_expired()
    draft = _DRAFTS.get(wizard_id)
    if not draft:
        raise KeyError(wizard_id)
    return draft


def _public(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "wizard_id": draft["wizard_id"],
        "step": draft["step"],
        "guests": draft.get("guests") or [],
        "guest_chips": GUEST_CHIPS,
        "venue": draft.get("venue"),
        "venue_query": draft.get("venue_query"),
        "restaurant_id": draft.get("restaurant_id"),
        "slot": draft.get("slot"),
        "slot_id": draft.get("slot_id"),
        "start_iso": draft.get("start_iso"),
        "slots": draft.get("slots") or [],
        "venues": draft.get("venues") or [],
    }


def start_wizard(*, chat_id: str | None = None) -> dict[str, Any]:
    ensure_night_out_guests()
    _purge_expired()
    wizard_id = f"now_{uuid.uuid4().hex[:10]}"
    draft = {
        "wizard_id": wizard_id,
        "step": "guests",
        "created_at": time.time(),
        "guests": ["aryan", "himali", "siya", "swayam"],
        "venue": None,
        "venue_query": None,
        "restaurant_id": None,
        "slot": None,
        "slot_id": None,
        "start_iso": None,
        "slots": [],
        "venues": [],
        "chat_id": chat_id,
        "tg_message_id": None,
    }
    _DRAFTS[wizard_id] = draft
    if chat_id:
        _CHAT_WIZARDS[str(chat_id)] = wizard_id
    return _public(draft)


def get_wizard(wizard_id: str) -> dict[str, Any]:
    return _public(_get(wizard_id))


def wizard_for_chat(chat_id: str | int) -> dict[str, Any] | None:
    _purge_expired()
    wid = _CHAT_WIZARDS.get(str(chat_id))
    if not wid or wid not in _DRAFTS:
        return None
    return _public(_DRAFTS[wid])


def clear_chat_wizard(chat_id: str | int) -> None:
    wid = _CHAT_WIZARDS.pop(str(chat_id), None)
    if wid:
        _DRAFTS.pop(wid, None)


def set_guests(wizard_id: str, guests: list[str]) -> dict[str, Any]:
    draft = _get(wizard_id)
    cleaned = []
    seen: set[str] = set()
    for g in guests:
        key = "".join(ch for ch in str(g).lower() if ch.isalnum())
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(key)
    if HOST_ID not in cleaned and "aryan" not in cleaned:
        cleaned.insert(0, HOST_ID)
    if len(cleaned) < 2:
        raise ValueError("Pick at least one guest besides the host (or 2 people total).")
    draft["guests"] = cleaned
    draft["step"] = "venue"
    return _public(draft)


def toggle_guest(wizard_id: str, guest_id: str) -> dict[str, Any]:
    draft = _get(wizard_id)
    gid = "".join(ch for ch in guest_id.lower() if ch.isalnum())
    if gid == HOST_ID:
        return _public(draft)  # host always on
    current = list(draft.get("guests") or [])
    if gid in current:
        current = [g for g in current if g != gid]
    else:
        current.append(gid)
    if HOST_ID not in current:
        current.insert(0, HOST_ID)
    draft["guests"] = current
    return _public(draft)


async def search_venues(wizard_id: str, query: str = "") -> dict[str, Any]:
    from app.mcp.client import mcp_client

    draft = _get(wizard_id)
    q = (query or "Pune").strip() or "Pune"
    try:
        res = await mcp_client.call_tool_async(
            "dineout",
            "search_restaurants_dineout",
            {
                "query": q,
                "area": "Pune",
                "latitude": settings.HOME_LAT,
                "longitude": settings.HOME_LNG,
            },
        )
        restaurants = list((res or {}).get("restaurants") or [])
    except Exception as e:  # noqa: BLE001
        log.warning("Venue search failed: %s", e)
        restaurants = []

    if not restaurants:
        from mock_data.dineout_catalog import DINEOUT_RESTAURANTS

        ql = q.lower()
        restaurants = [
            {
                "restaurant_id": r["restaurant_id"],
                "name": r["name"],
                "cuisines": r.get("cuisines"),
                "area": r.get("area"),
                "costForTwo": r.get("costForTwo"),
                "rating": r.get("rating"),
            }
            for r in DINEOUT_RESTAURANTS
            if r.get("availability") == "AVAILABLE"
            and (
                not ql
                or ql in r["name"].lower()
                or any(ql in str(c).lower() for c in (r.get("cuisines") or []))
                or ql in str(r.get("area") or "").lower()
            )
        ][:8]

    venues = []
    for r in restaurants[:8]:
        venues.append(
            {
                "restaurant_id": str(r.get("restaurant_id") or r.get("restaurantId") or ""),
                "name": str(r.get("name") or "Restaurant"),
                "area": r.get("area"),
                "cuisines": r.get("cuisines") or [],
                "costForTwo": r.get("costForTwo") or r.get("price_for_two_inr"),
                "rating": r.get("rating"),
            }
        )
    draft["venues"] = venues
    draft["step"] = "venue"
    out = _public(draft)
    out["venues"] = venues
    return out


async def set_venue(
    wizard_id: str,
    *,
    restaurant_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    from app.mcp.client import mcp_client
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS

    draft = _get(wizard_id)
    rid = (restaurant_id or "").strip()
    vname = (name or "").strip()
    catalog = None
    if rid:
        catalog = next((r for r in DINEOUT_RESTAURANTS if r["restaurant_id"] == rid), None)
    if not catalog and vname:
        vl = vname.lower()
        catalog = next(
            (r for r in DINEOUT_RESTAURANTS if vl in r["name"].lower()),
            None,
        )
        if catalog:
            rid = catalog["restaurant_id"]
            vname = catalog["name"]
    if not vname and catalog:
        vname = catalog["name"]
    if not vname:
        raise ValueError("Pick a restaurant.")

    draft["restaurant_id"] = rid or None
    draft["venue"] = vname
    draft["venue_query"] = vname.split("·")[0].strip() if vname else vname

    party = max(len(resolve_guest_emails(draft.get("guests"))), 2)
    lat = float((catalog or {}).get("_lat") or settings.HOME_LAT)
    lng = float((catalog or {}).get("_lng") or settings.HOME_LNG)
    slots_out: list[dict[str, Any]] = []
    try:
        slots_res = await mcp_client.call_tool_async(
            "dineout",
            "get_available_slots",
            {
                "restaurantId": rid or "do_6digs_809",
                "guestCount": party,
                "partySize": party,
                "date": datetime.now(IST).strftime("%Y-%m-%d"),
                "latitude": lat,
                "longitude": lng,
            },
        )
        raw = (slots_res or {}).get("slots") or []
        for s in raw[:8]:
            if isinstance(s, str):
                slots_out.append({"label": s, "slot_id": None})
            else:
                slots_out.append(
                    {
                        "label": str(s.get("label") or s.get("time") or "19:30"),
                        "slot_id": s.get("slotId") or s.get("slot_id"),
                    }
                )
    except Exception as e:  # noqa: BLE001
        log.warning("Slots fetch failed: %s", e)
        slots_out = [
            {"label": "19:00", "slot_id": None},
            {"label": "19:30", "slot_id": None},
            {"label": "20:00", "slot_id": None},
            {"label": "20:30", "slot_id": None},
        ]

    draft["slots"] = slots_out
    draft["step"] = "slot"
    return _public(draft)


def set_slot(
    wizard_id: str,
    *,
    slot: str,
    slot_id: str | int | None = None,
    start_iso: str | None = None,
) -> dict[str, Any]:
    draft = _get(wizard_id)
    label = (slot or "").strip()
    if not label:
        raise ValueError("Pick a time slot.")
    draft["slot"] = label
    draft["slot_id"] = str(slot_id) if slot_id is not None else None
    if start_iso:
        draft["start_iso"] = start_iso
    else:
        # Build today's IST datetime from HH:MM label
        try:
            hh, mm = label.split(":")[:2]
            now = datetime.now(IST)
            start = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if start < now:
                start = start + timedelta(days=1)
            draft["start_iso"] = start.isoformat()
        except Exception:  # noqa: BLE001
            draft["start_iso"] = (datetime.now(IST) + timedelta(hours=3)).isoformat()
    draft["step"] = "confirm"
    return _public(draft)


async def confirm_wizard(wizard_id: str, *, suppress_hitl_telegram: bool = False) -> dict[str, Any]:
    draft = _get(wizard_id)
    if not draft.get("venue"):
        raise ValueError("Venue missing — pick a restaurant first.")
    if not draft.get("slot"):
        raise ValueError("Slot missing — pick a time first.")
    guests = draft.get("guests") or []
    result = await plan_night_out(
        guest_names=list(guests),
        venue=str(draft["venue"]),
        venue_query=str(draft.get("venue_query") or draft["venue"]),
        guest_count=len(resolve_guest_emails(guests)),
        start_iso=draft.get("start_iso"),
        preferred_slot=draft.get("slot"),
        preferred_slot_id=str(draft["slot_id"]) if draft.get("slot_id") else None,
        restaurant_id=draft.get("restaurant_id"),
        suppress_hitl_telegram=suppress_hitl_telegram,
    )
    result["wizard_id"] = wizard_id
    result["slot"] = draft.get("slot")
    chat_id = draft.get("chat_id")
    _DRAFTS.pop(wizard_id, None)
    if chat_id:
        _CHAT_WIZARDS.pop(str(chat_id), None)
    return result


def set_tg_message_id(wizard_id: str, message_id: int | str | None) -> None:
    try:
        draft = _get(wizard_id)
        draft["tg_message_id"] = message_id
    except KeyError:
        pass


def get_tg_message_id(wizard_id: str) -> int | None:
    try:
        mid = _get(wizard_id).get("tg_message_id")
        return int(mid) if mid is not None else None
    except (KeyError, TypeError, ValueError):
        return None


def summary_text(draft: dict[str, Any]) -> str:
    guests = draft.get("guests") or []
    labels = []
    chip_map = {c["id"]: c["label"] for c in GUEST_CHIPS}
    for g in guests:
        labels.append(chip_map.get(g, g.title()))
    return (
        f"Night out summary\n"
        f"Guests: {', '.join(labels)}\n"
        f"Venue: {draft.get('venue') or '—'}\n"
        f"Time: {draft.get('slot') or '—'}\n"
        f"Split: equal after Approve"
    )
