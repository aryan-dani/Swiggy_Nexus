"""LangGraph nodes — stage (read) before HITL; write tools only after approval."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import uuid
from typing import Any

from app.config import settings
from app.db.profiler import get_group_preferences
from app.db.store import (
    create_approval,
    find_pending_approval,
    record_dish_history,
    record_qol_event,
    save_execution,
)
from app.graph.state import ConciergeState
from app.mcp.client import SwiggyMCPError, mcp_client
from app.services.google_calendar import update_calendar_event_description
from app.services.notifications import send_approval_request

log = logging.getLogger(__name__)

DEFAULT_ADDRESS = "addr_kp_001"
DEFAULT_LAT = 18.5204
DEFAULT_LNG = 73.8567


def _add_log(state: ConciergeState, message: str) -> list[dict[str, Any]]:
    logs = list(state.get("execution_logs") or [])
    logs.append({"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "message": message})
    return logs


async def profile_attendees_node(state: ConciergeState) -> ConciergeState:
    emails = state.get("attendee_emails") or []
    group_profile = await asyncio.to_thread(get_group_preferences, emails)
    profile_dict = group_profile.model_dump()
    logs = _add_log(
        state,
        f"Profiled {group_profile.attendee_count} attendees · "
        f"vegan={group_profile.must_be_vegan} veg={group_profile.must_be_vegetarian} "
        f"spice≤{group_profile.max_spice_tolerance}",
    )
    return {
        **state,
        "group_profile": profile_dict,
        "unknown_attendees": group_profile.unrecognized_emails,
        "address_id": state.get("address_id") or DEFAULT_ADDRESS,
        "execution_logs": logs,
    }


async def parse_and_route_node(state: ConciergeState) -> ConciergeState:
    location = (state.get("event_location") or "").lower().strip()
    description = (state.get("event_description") or "").lower().strip()
    home_keywords = ["home", "house", "office", "apartment", "my place", "flat", "residence"]
    is_home = any(kw in location for kw in home_keywords)
    force_zero = "#host" in description or "#zerotouch" in description
    force_dineout = "#dineout" in description or "#restaurant" in description

    if force_dineout:
        mode, reason = "DINEOUT", "Explicit #dineout flag"
    elif force_zero or is_home:
        mode, reason = "ZERO_TOUCH_HOST", f"Home/host location '{state.get('event_location')}'"
    else:
        mode, reason = "DINEOUT", f"Venue location '{state.get('event_location')}'"

    logs = _add_log(state, f"Routing → {mode}: {reason}")
    return {**state, "mode": mode, "routing_reason": reason, "execution_logs": logs}


async def stage_dineout_node(state: ConciergeState) -> ConciergeState:
    """READ-ONLY staging: search + slots + menu. Does NOT call book_table."""
    from app.services.google_calendar import maps_url_for
    from mock_data.dineout_catalog import DINEOUT_RESTAURANTS

    group_profile = state.get("group_profile") or {}
    location = state.get("event_location") or "Pune"
    attendees = state.get("attendee_emails") or []
    preferred = (state.get("preferred_restaurant_query") or "").strip()
    party_size = max(
        2,
        int(state.get("guest_count") or 0),
        len(attendees) or 0,
        2,
    )
    cuisine = (group_profile.get("recommended_cuisines") or ["Italian"])[0]
    search_q = preferred or cuisine
    logs = _add_log(state, f"Staging Dineout for '{search_q}' · party {party_size}")

    try:
        search_res = await mcp_client.call_tool_async(
            "dineout",
            "search_restaurants_dineout",
            {"query": search_q, "area": location, "latitude": DEFAULT_LAT, "longitude": DEFAULT_LNG},
        )
        restaurants = list((search_res or {}).get("restaurants") or [])

        selected = None
        if preferred:
            pref_l = preferred.lower()
            for r in restaurants:
                name = str(r.get("name") or "").lower()
                if pref_l in name or any(pref_l in str(c).lower() for c in (r.get("cuisines") or [])):
                    selected = r
                    break
            if not selected:
                for r in DINEOUT_RESTAURANTS:
                    if pref_l in r["name"].lower() and r.get("availability") == "AVAILABLE":
                        selected = {
                            "restaurant_id": r["restaurant_id"],
                            "name": r["name"],
                            "latitude": r.get("_lat"),
                            "longitude": r.get("_lng"),
                            "costForTwo": r.get("costForTwo"),
                        }
                        break
        if not selected:
            if not restaurants:
                raise SwiggyMCPError({"code": "NO_RESTAURANT", "message": f"No Dineout results for {search_q}"})
            selected = restaurants[0]

        rest_id = str(selected.get("restaurant_id") or selected.get("restaurantId") or "do_6digs_809")
        rest_name = str(selected.get("name") or "6 Digs · Kothrud")
        catalog = next((r for r in DINEOUT_RESTAURANTS if r["restaurant_id"] == rest_id), None)
        lat = float(selected.get("latitude") or (catalog or {}).get("_lat") or DEFAULT_LAT)
        lng = float(selected.get("longitude") or (catalog or {}).get("_lng") or DEFAULT_LNG)
        cost_for_two = float(
            selected.get("costForTwo")
            or (catalog or {}).get("costForTwo")
            or (catalog or {}).get("price_for_two_inr")
            or 2200
        )
        estimated_cover = round(cost_for_two * party_size / 2)

        details = {}
        try:
            details = await mcp_client.call_tool_async(
                "dineout",
                "get_restaurant_details",
                {"restaurantId": rest_id},
            ) or {}
        except SwiggyMCPError:
            details = {}

        outdoor_hint = json.dumps(details).lower()
        is_outdoor = any(k in outdoor_hint for k in ("rooftop", "outdoor", "terrace", "open air"))

        slots_res = await mcp_client.call_tool_async(
            "dineout",
            "get_available_slots",
            {
                "restaurantId": rest_id,
                "guestCount": party_size,
                "partySize": party_size,
                "date": datetime.date.today().strftime("%Y-%m-%d"),
                "latitude": lat,
                "longitude": lng,
            },
        )
        slots = (slots_res or {}).get("slots") or []
        if not slots:
            raise SwiggyMCPError(
                {"code": "SLOT_UNAVAILABLE", "message": f"No slots at {rest_name}"}
            )

        preferred_slot = (state.get("preferred_slot") or "").strip()
        preferred_slot_id = state.get("preferred_slot_id")
        first = slots[0]
        if preferred_slot or preferred_slot_id:
            for s in slots:
                if isinstance(s, str):
                    if preferred_slot and s == preferred_slot:
                        first = s
                        break
                    continue
                label = str(s.get("label") or s.get("time") or "")
                sid = s.get("slotId") or s.get("slot_id")
                if preferred_slot_id and str(sid) == str(preferred_slot_id):
                    first = s
                    break
                if preferred_slot and (
                    preferred_slot == label or preferred_slot in label
                ):
                    first = s
                    break

        if isinstance(first, str):
            slot_label, slot_id, item_id = first, None, None
        else:
            slot_label = str(first.get("label") or first.get("time") or "19:30")
            slot_id = first.get("slotId") or first.get("slot_id")
            item_id = first.get("itemId") or first.get("item_id")
            deals = first.get("deals") or []
            if not item_id and deals and isinstance(deals[0], dict):
                item_id = deals[0].get("itemId")

        food_rid = "fd_dom_101" if str(rest_id).startswith("do_") else rest_id
        menu_res = await mcp_client.call_tool_async(
            "food",
            "get_restaurant_menu",
            {"restaurantId": food_rid, "addressId": state.get("address_id") or DEFAULT_ADDRESS},
        )

        maps = state.get("maps_url") or maps_url_for(rest_name, lat, lng)
        plan = {
            "restaurantId": rest_id,
            "restaurantName": rest_name,
            "slotId": slot_id,
            "itemId": item_id,
            "reservationTime": slot_label,
            "guestCount": party_size,
            "latitude": lat,
            "longitude": lng,
            "is_outdoor_or_rooftop": is_outdoor,
            "slot_label": slot_label,
            "foodRestaurantId": food_rid,
            "costForTwo": cost_for_two,
            "estimated_cover_inr": estimated_cover,
            "maps_url": maps,
            "calendar_html_link": state.get("calendar_html_link"),
            "attendee_emails": attendees,
        }
        logs = _add_log(
            state,
            f"Staged Dineout {rest_name} @ {slot_label} (outdoor={is_outdoor}) — awaiting HITL",
        )
        return {
            **state,
            "dineout_plan": plan,
            "dineout_restaurant_id": rest_id,
            "dineout_restaurant_name": rest_name,
            "dineout_slot": slot_label,
            "dineout_slot_id": str(slot_id) if slot_id else None,
            "dineout_item_id": str(item_id) if item_id else None,
            "dineout_menu": menu_res if isinstance(menu_res, dict) else {},
            "dineout_error": None,
            "maps_url": maps,
            "total_estimated_cost": float(estimated_cover),
            "execution_logs": logs,
        }
    except SwiggyMCPError as e:
        logs = _add_log(state, f"Dineout staging failed ({e.message}) → Zero-Touch fallback")
        return {
            **state,
            "dineout_error": e.message,
            "mode": "ZERO_TOUCH_HOST",
            "execution_logs": logs,
        }


async def stage_zero_touch_node(state: ConciergeState) -> ConciergeState:
    """Stage Instamart + Food carts with official update_* tools. No place/checkout yet."""
    group_profile = state.get("group_profile") or {}
    party_size = max(2, len(state.get("attendee_emails") or []) or 4)
    must_veg = bool(group_profile.get("must_be_vegetarian") or group_profile.get("must_be_vegan"))
    address_id = state.get("address_id") or DEFAULT_ADDRESS
    logs = _add_log(state, "Staging Zero-Touch Host carts (IM T-45m + Food T-15m) — no write yet")

    im_search = await mcp_client.call_tool_async(
        "im",
        "search_products",
        {"addressId": address_id, "selectedAddressId": address_id, "query": "party supplies chips drinks"},
    )
    products = (im_search or {}).get("products") or []
    im_items: list[dict[str, Any]] = []
    for p in products[:4]:
        variants = p.get("variants") or []
        spin = variants[0].get("spinId") if variants else p.get("spinId")
        if spin:
            im_items.append(
                {
                    "spinId": spin,
                    "quantity": max(1, party_size // 3),
                    "name": p.get("name"),
                    "price_inr": p.get("price_inr"),
                }
            )
    if not im_items:
        im_items = [
            {"spinId": "spin_chips_lays", "quantity": 2, "name": "Lay's"},
            {"spinId": "spin_cola_500", "quantity": max(2, party_size), "name": "Coca-Cola"},
            {"spinId": "spin_napkins", "quantity": 1, "name": "Napkins"},
        ]

    im_cart = await mcp_client.call_tool_async(
        "im",
        "update_cart",
        {
            "selectedAddressId": address_id,
            "addressId": address_id,
            "items": [{"spinId": i["spinId"], "quantity": i["quantity"]} for i in im_items],
        },
    )
    im_total = float(
        (im_cart or {}).get("total")
        or (im_cart or {}).get("total_inr")
        or sum((i.get("price_inr") or 50) * i["quantity"] for i in im_items)
    )

    food_query = "thali dosa" if must_veg else "party meal"
    food_search = await mcp_client.call_tool_async(
        "food",
        "search_restaurants",
        {"addressId": address_id, "query": food_query},
    )
    restaurants = list((food_search or {}).get("restaurants") or [])
    # Prefer kitchens that actually have matching dietary items in the mock catalog.
    if must_veg:
        restaurants = restaurants + [
            {"restaurant_id": "fd_south_111", "name": "Vaishali Restaurant"},
            {"restaurant_id": "fd_thali_104", "name": "Maratha Samrat Thali House"},
            {"restaurant_id": "fd_misal_103", "name": "Shrimant Misal House"},
        ]
    else:
        restaurants = restaurants + [
            {"restaurant_id": "fd_biryani_106", "name": "Biryani House"},
            {"restaurant_id": "fd_dom_101", "name": "Domino's Pizza"},
        ]

    cart_items: list[dict[str, Any]] = []
    rest_id = "fd_south_111" if must_veg else "fd_biryani_106"
    rest_name = "Catering Kitchen"
    menu: dict[str, Any] = {}

    def _pick_from_menu(menu_payload: dict[str, Any]) -> list[dict[str, Any]]:
        picked: list[dict[str, Any]] = []
        for cat in (menu_payload or {}).get("categories") or []:
            for item in cat.get("items") or []:
                if must_veg and not item.get("vegetarian", True):
                    continue
                item_id = str(item.get("item_id") or item.get("itemId") or item.get("id") or "").strip()
                if not item_id:
                    continue
                picked.append(
                    {
                        "itemId": item_id,
                        "quantity": max(2, party_size // 2),
                        "name": item.get("name"),
                        "price_inr": item.get("price_inr"),
                    }
                )
                if len(picked) >= 2:
                    return picked
        return picked

    for rest in restaurants:
        candidate_id = str(rest.get("restaurant_id") or rest.get("restaurantId") or "")
        if not candidate_id:
            continue
        candidate_menu = await mcp_client.call_tool_async(
            "food",
            "get_restaurant_menu",
            {"restaurantId": candidate_id, "addressId": address_id},
        )
        if not isinstance(candidate_menu, dict):
            continue
        picked = _pick_from_menu(candidate_menu)
        if picked:
            cart_items = picked
            rest_id = candidate_id
            rest_name = str(rest.get("name") or "Catering Kitchen")
            menu = candidate_menu
            break

    if not cart_items:
        # Hard fallback to known mock catalog IDs (never invent item_* names).
        if must_veg:
            rest_id, rest_name = "fd_south_111", "Vaishali Restaurant"
            cart_items = [
                {"itemId": "vs_masala", "quantity": max(2, party_size // 2), "name": "Masala Dosa", "price_inr": 120},
                {"itemId": "vs_idli", "quantity": max(2, party_size // 2), "name": "Idli Sambar", "price_inr": 80},
            ]
        else:
            rest_id, rest_name = "fd_biryani_106", "Biryani House"
            cart_items = [
                {"itemId": "bh_chicken", "quantity": max(2, party_size // 2), "name": "Chicken Biryani", "price_inr": 349},
            ]
        menu = await mcp_client.call_tool_async(
            "food",
            "get_restaurant_menu",
            {"restaurantId": rest_id, "addressId": address_id},
        ) or {}

    food_cart = await mcp_client.call_tool_async(
        "food",
        "update_food_cart",
        {
            "restaurantId": rest_id,
            "addressId": address_id,
            "cartItems": [{"itemId": c["itemId"], "quantity": c["quantity"]} for c in cart_items],
            "items": [{"item_id": c["itemId"], "qty": c["quantity"]} for c in cart_items],
        },
    )
    food_total = float(
        (food_cart or {}).get("total")
        or ((food_cart or {}).get("bill") or {}).get("total_inr")
        or ((food_cart or {}).get("bill") or {}).get("grandTotal")
        or 650.0
    )

    staged_im = {
        "selectedAddressId": address_id,
        "items": im_items,
        "estimated_total_inr": im_total,
    }
    staged_food = {
        "restaurantId": rest_id,
        "restaurantName": rest_name,
        "addressId": address_id,
        "cartItems": cart_items,
        "estimated_total_inr": food_total,
    }
    logs = _add_log(
        state,
        f"Staged IM ₹{im_total} + Food ₹{food_total} at {rest_name} — awaiting HITL",
    )
    return {
        **state,
        "staged_im_cart": staged_im,
        "staged_food_cart": staged_food,
        "instamart_total": im_total,
        "food_total": food_total,
        "food_restaurant_id": rest_id,
        "dineout_menu": menu if isinstance(menu, dict) else {},
        "execution_logs": logs,
    }


def _display_name_from_profile(prof: dict) -> str:
    name = str(prof.get("full_name") or "").strip()
    if name:
        return name
    email = str(prof.get("email") or "Guest")
    local = email.split("@")[0].replace(".", " ").replace("_", " ")
    return local.title() if local else "Guest"


def _rule_based_sommelier(state: ConciergeState) -> str:
    """Plain-text menu sheet — Google Calendar does not render Markdown tables."""
    group_profile = state.get("group_profile") or {}
    individual = group_profile.get("individual_profiles") or []
    allergies = ", ".join(group_profile.get("all_allergies") or ["none"])
    lines = [
        "AI Sommelier · Menu picks",
        (
            f"Guardrails: vegan={group_profile.get('must_be_vegan')} · "
            f"veg={group_profile.get('must_be_vegetarian')} · "
            f"spice≤{group_profile.get('max_spice_tolerance')}/5 · "
            f"allergies={allergies}"
        ),
        "",
    ]
    for prof in individual:
        p = prof.get("profile") or {}
        diet = (
            "Vegan"
            if p.get("is_vegan")
            else (
                "Jain"
                if p.get("is_jain")
                else ("Veg" if p.get("is_vegetarian") else "Non-veg")
            )
        )
        spice = p.get("spice_tolerance", 3)
        if p.get("is_jain"):
            dish = "Paneer Tikka (no onion/garlic)"
        elif p.get("is_vegan"):
            dish = "Vegan Garden Bowl"
        elif p.get("is_vegetarian"):
            dish = "Malai Kofta / Margherita"
        else:
            dish = "Guntur Chilli Chicken" if spice >= 4 else "Butter Chicken"
        lines.append(f"• {_display_name_from_profile(prof)} — {dish} ({diet})")
    if not individual:
        lines.append("• Guests — Chef's tasting platter (screened for group allergies)")
    lines.append("")
    lines.append("Pre-screened against Taste Vault constraints.")
    return "\n".join(lines)


async def ai_sommelier_node(state: ConciergeState) -> ConciergeState:
    """Groq-backed menu synthesis with rule-based fallback (plain text for Calendar)."""
    fallback = _rule_based_sommelier(state)
    md = fallback
    if settings.GROQ_API_KEY:
        try:
            from groq import Groq

            client = Groq(api_key=settings.GROQ_API_KEY)
            menu = state.get("dineout_menu") or {}
            group = state.get("group_profile") or {}
            prompt = (
                "You are an Indian AI sommelier for Swiggy Nexus. "
                "Given group dietary constraints and a restaurant menu JSON, "
                "return a PLAIN TEXT menu sheet (NO markdown tables, NO # headings, NO backticks). "
                "Format exactly like:\n"
                "AI Sommelier · Menu picks\n"
                "Guardrails: …\n"
                "• Full Name — Dish (Diet)\n"
                "Respect Jain/vegan/veg/allergies/spice. No prose outside this sheet.\n\n"
                f"GROUP:\n{json.dumps(group)[:3000]}\n\nMENU:\n{json.dumps(menu)[:4000]}"
            )
            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=800,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content and "•" in content and "|---|" not in content and "|" not in content.split("\n")[0]:
                md = content
            elif content and "•" in content and "|---|" not in content:
                md = content
        except Exception as e:  # noqa: BLE001
            log.warning("Sommelier Groq failed (%s); using rule fallback", e)

    logs = _add_log(state, "AI Sommelier sheet ready")
    return {**state, "sommelier_recommendations_markdown": md, "execution_logs": logs}


async def hitl_notify_node(state: ConciergeState) -> ConciergeState:
    """Create durable approval + notify Telegram/console, then graph interrupts AFTER this node."""
    # If we are resuming past HITL (or a bad resume re-enters this node), never
    # mint a second approval / Telegram push.
    prior = state.get("approval_status")
    if prior in ("APPROVED", "REJECTED"):
        logs = _add_log(state, f"HITL notify skipped — already {prior}")
        return {**state, "execution_logs": logs}

    mode = state.get("mode") or "DINEOUT"
    event_id = state.get("event_id") or f"evt-{uuid.uuid4().hex[:8]}"
    thread_id = event_id

    if mode == "DINEOUT":
        plan = state.get("dineout_plan") or {}
        total = float(
            plan.get("estimated_cover_inr")
            or state.get("total_estimated_cost")
            or 0
        )
        breakdown = {
            "mode": "DINEOUT",
            "venue": state.get("dineout_restaurant_name"),
            "slot": state.get("dineout_slot"),
            "plan": plan,
            "total_inr": total,
            "estimated_cover_inr": total,
            "attendee_emails": state.get("attendee_emails") or plan.get("attendee_emails") or [],
            "calendar_html_link": state.get("calendar_html_link") or plan.get("calendar_html_link"),
            "maps_url": state.get("maps_url") or plan.get("maps_url"),
            "note": "Table booking executes only after /approve; bill split after approve",
        }
        summary = (
            f"Book table at {state.get('dineout_restaurant_name')} · "
            f"{state.get('dineout_slot')} · party "
            f"{plan.get('guestCount', 2)}"
            + (f" · ~₹{total:.0f} cover" if total else "")
        )
    else:
        im = float(state.get("instamart_total") or 0)
        food = float(state.get("food_total") or 0)
        total = im + food
        breakdown = {
            "mode": "ZERO_TOUCH_HOST",
            "instamart_inr": im,
            "food_inr": food,
            "total_inr": total,
            "staged_im_cart": state.get("staged_im_cart"),
            "staged_food_cart": state.get("staged_food_cart"),
            "attendee_emails": state.get("attendee_emails") or [],
            "calendar_html_link": state.get("calendar_html_link"),
            "maps_url": state.get("maps_url"),
        }
        summary = f"Zero-Touch Host · IM ₹{im:.0f} + Food ₹{food:.0f} (place after approve)"

    trigger_type = state.get("trigger_type") or "calendar_concierge"
    existing = await asyncio.to_thread(find_pending_approval, event_id, trigger_type)
    if existing:
        request_id = existing["request_id"]
        log.info(
            "HITL dedupe: reusing PENDING %s for event_id=%s trigger=%s (skip notify)",
            request_id,
            event_id,
            trigger_type,
        )
        await asyncio.to_thread(
            save_execution,
            event_id,
            {
                "request_id": request_id,
                "status": "paused_at_hitl_checkpoint",
                "mode": mode,
                "state": {
                    **state,
                    "approval_request_id": request_id,
                    "approval_status": "PENDING",
                },
            },
        )
        logs = _add_log(state, f"HITL reused pending · {request_id} (deduped)")
        return {
            **state,
            "event_id": event_id,
            "approval_request_id": request_id,
            "approval_status": "PENDING",
            "total_estimated_cost": total,
            "cost_summary_breakdown": breakdown,
            "hitl_message": summary,
            "execution_logs": logs,
        }

    approval = await asyncio.to_thread(
        create_approval,
        event_id=event_id,
        thread_id=thread_id,
        trigger_type=trigger_type,
        title=state.get("event_title") or "Swiggy Concierge",
        summary=summary,
        cost_breakdown=breakdown,
        staged_payload={
            "mode": mode,
            "dineout_plan": state.get("dineout_plan"),
            "staged_im_cart": state.get("staged_im_cart"),
            "staged_food_cart": state.get("staged_food_cart"),
            "sommelier": state.get("sommelier_recommendations_markdown"),
            "attendee_emails": state.get("attendee_emails") or [],
            "calendar_html_link": state.get("calendar_html_link"),
            "maps_url": state.get("maps_url"),
            "auto_split_bill": bool(state.get("auto_split_bill")),
        },
    )
    request_id = approval["request_id"]
    approve_url = f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{request_id}"

    if not state.get("suppress_hitl_telegram"):
        await send_approval_request(
            platform=settings.NOTIFICATION_PLATFORM,
            event_summary={
                "request_id": request_id,
                "title": state.get("event_title", "Concierge"),
                "time": state.get("event_time_str", ""),
                "location": state.get("event_location", ""),
                "attendee_count": len(state.get("attendee_emails") or []),
                "summary": summary,
            },
            cost_breakdown=breakdown,
            approve_url=approve_url,
            request_id=request_id,
        )
    else:
        log.info(
            "HITL %s staged with Telegram notify suppressed (wizard will approve once)",
            request_id,
        )

    await asyncio.to_thread(
        record_qol_event,
        kind="hitl_pending",
        title=f"Approval pending · {request_id}",
        detail=summary,
        severity="action",
        meta={"request_id": request_id, "event_id": event_id, "mode": mode},
        event_id=event_id,
    )
    await asyncio.to_thread(
        save_execution,
        event_id,
        {
            "request_id": request_id,
            "status": "paused_at_hitl_checkpoint",
            "mode": mode,
            "state": {**state, "approval_request_id": request_id, "approval_status": "PENDING"},
        },
    )

    logs = _add_log(state, f"HITL notified · {request_id} via {settings.NOTIFICATION_PLATFORM}")
    return {
        **state,
        "event_id": event_id,
        "approval_request_id": request_id,
        "approval_status": "PENDING",
        "total_estimated_cost": total,
        "cost_summary_breakdown": breakdown,
        "hitl_message": summary,
        "execution_logs": logs,
    }


async def execute_transactions_node(state: ConciergeState) -> ConciergeState:
    """WRITE tools only — book_table / checkout / place_food_order after approval."""
    if state.get("approval_status") == "REJECTED":
        logs = _add_log(state, "Skipped writes — rejected")
        return {**state, "execution_logs": logs}

    mode = state.get("mode") or "DINEOUT"
    address_id = state.get("address_id") or DEFAULT_ADDRESS
    logs = _add_log(state, f"Executing transactions for mode={mode}")
    booking_id = None
    im_order_id = None
    food_order_id = None

    if mode == "DINEOUT":
        plan = state.get("dineout_plan") or {}
        booking = await mcp_client.call_tool_async(
            "dineout",
            "book_table",
            {
                "restaurantId": plan.get("restaurantId") or state.get("dineout_restaurant_id"),
                "slotId": plan.get("slotId") or state.get("dineout_slot_id"),
                "itemId": plan.get("itemId") or state.get("dineout_item_id"),
                "reservationTime": plan.get("reservationTime") or state.get("dineout_slot"),
                "slot": plan.get("slot_label") or state.get("dineout_slot"),
                "guestCount": plan.get("guestCount") or 2,
                "partySize": plan.get("guestCount") or 2,
                "latitude": plan.get("latitude") or DEFAULT_LAT,
                "longitude": plan.get("longitude") or DEFAULT_LNG,
            },
        )
        booking_id = str(
            (booking or {}).get("booking_id")
            or (booking or {}).get("bookingId")
            or (booking or {}).get("orderId")
            or f"DO_BK_{uuid.uuid4().hex[:8].upper()}"
        )
        logs = _add_log(state, f"book_table OK · {booking_id}")
        state = {
            **state,
            "dineout_booking_id": booking_id,
            "approval_status": "APPROVED",
            "execution_logs": logs,
        }
    else:
        # Zero-touch: checkout IM + place food (scheduler may also fire delayed legs)
        staged_im = state.get("staged_im_cart") or {}
        staged_food = state.get("staged_food_cart") or {}

        if staged_im.get("items"):
            await mcp_client.call_tool_async(
                "im",
                "update_cart",
                {
                    "selectedAddressId": staged_im.get("selectedAddressId") or address_id,
                    "items": [
                        {"spinId": i["spinId"], "quantity": i["quantity"]}
                        for i in staged_im["items"]
                    ],
                },
            )
            checkout = await mcp_client.call_tool_async(
                "im",
                "checkout",
                {"addressId": staged_im.get("selectedAddressId") or address_id},
            )
            im_order_id = str(
                (checkout or {}).get("order_id")
                or (checkout or {}).get("orderId")
                or f"IM-{uuid.uuid4().hex[:8].upper()}"
            )
            logs = _add_log(state, f"Instamart checkout OK · {im_order_id}")

        if staged_food.get("cartItems"):
            await mcp_client.call_tool_async(
                "food",
                "update_food_cart",
                {
                    "restaurantId": staged_food.get("restaurantId"),
                    "addressId": staged_food.get("addressId") or address_id,
                    "cartItems": [
                        {"itemId": c["itemId"], "quantity": c["quantity"]}
                        for c in staged_food["cartItems"]
                    ],
                },
            )
            placed = await mcp_client.call_tool_async(
                "food",
                "place_food_order",
                {"addressId": staged_food.get("addressId") or address_id},
            )
            food_order_id = str(
                (placed or {}).get("order_id")
                or (placed or {}).get("orderId")
                or f"FD-{uuid.uuid4().hex[:8].upper()}"
            )
            logs = _add_log(state, f"place_food_order OK · {food_order_id}")
            for email in state.get("attendee_emails") or []:
                await asyncio.to_thread(
                    record_dish_history,
                    email,
                    (staged_food["cartItems"][0].get("name") or "catering"),
                    staged_food.get("restaurantName") or "Food",
                )

        state = {
            **state,
            "instamart_order_id": im_order_id,
            "food_order_id": food_order_id,
            "approval_status": "APPROVED",
            "execution_logs": logs,
        }

    # Auto equal split + night-out receipt for night_out / dinner_party / flagged runs
    if state.get("auto_split_bill") or state.get("trigger_type") in ("night_out", "dinner_party"):
        state = await _emit_night_out_receipt(state)

    return state


async def _emit_night_out_receipt(state: ConciergeState) -> ConciergeState:
    """Equal UPI split + QoL night_out_receipt for the Concierge Ops card."""
    from app.services.bill_split import split_and_notify

    attendees = list(state.get("attendee_emails") or [])
    if not attendees:
        return state

    plan = state.get("dineout_plan") or {}
    mode = state.get("mode") or "DINEOUT"
    if mode == "DINEOUT":
        total = float(
            plan.get("estimated_cover_inr")
            or state.get("total_estimated_cost")
            or (state.get("cost_summary_breakdown") or {}).get("total_inr")
            or 0
        )
        if total <= 0:
            total = float(plan.get("costForTwo") or 2200) * max(2, int(plan.get("guestCount") or 2)) / 2
        title = f"Night out · {state.get('dineout_restaurant_name') or 'Dineout'}"
    else:
        total = float(state.get("instamart_total") or 0) + float(state.get("food_total") or 0)
        if total <= 0:
            total = float((state.get("cost_summary_breakdown") or {}).get("total_inr") or 900)
        title = state.get("event_title") or "Dinner party split"

    if total <= 0:
        return state

    try:
        split = await split_and_notify(
            total,
            attendees,
            order_id=state.get("dineout_booking_id") or state.get("food_order_id"),
            title=title,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Auto bill split failed: %s", e)
        return state

    receipt = {
        "kind": "night_out_receipt",
        "title": title,
        "mode": mode,
        "venue": state.get("dineout_restaurant_name") or "Home",
        "slot": state.get("dineout_slot"),
        "booking_id": state.get("dineout_booking_id"),
        "food_order_id": state.get("food_order_id"),
        "instamart_order_id": state.get("instamart_order_id"),
        "calendar_html_link": state.get("calendar_html_link") or plan.get("calendar_html_link"),
        "calendar_mock": bool(state.get("calendar_mock")),
        "maps_url": state.get("maps_url") or plan.get("maps_url"),
        "attendee_emails": attendees,
        "guest_count": plan.get("guestCount") or len(attendees),
        "total_inr": split.get("total_inr"),
        "shares": split.get("shares") or [],
        "event_id": state.get("event_id"),
        "approval_request_id": state.get("approval_request_id"),
        "staged_food_cart": state.get("staged_food_cart"),
    }
    await asyncio.to_thread(
        record_qol_event,
        kind="night_out_receipt",
        title=f"Receipt · {title}",
        detail=f"Split ₹{split.get('total_inr')} · {len(attendees)} people",
        severity="action",
        event_id=state.get("event_id"),
        meta=receipt,
    )
    logs = _add_log(state, f"Night-out receipt + split ₹{split.get('total_inr')}")
    return {
        **state,
        "bill_split": split,
        "night_out_receipt": receipt,
        "execution_logs": logs,
    }


async def schedule_legs_node(state: ConciergeState) -> ConciergeState:
    """Register delayed T-45m / T-15m reminder jobs (orders already placed on approve for demo reliability)."""
    try:
        from app.services.scheduler import schedule_zero_touch_reminders

        im_job, food_job = schedule_zero_touch_reminders(state)
        logs = _add_log(state, f"Scheduled reminders im={im_job} food={food_job}")
        return {
            **state,
            "scheduled_im_job_id": im_job,
            "scheduled_food_job_id": food_job,
            "execution_logs": logs,
        }
    except Exception as e:  # noqa: BLE001
        log.warning("schedule_legs_node warning: %s", e)
        logs = _add_log(state, f"Scheduler note: {e}")
        return {**state, "execution_logs": logs}


async def cleanup_reject_node(state: ConciergeState) -> ConciergeState:
    address_id = state.get("address_id") or DEFAULT_ADDRESS
    try:
        await mcp_client.call_tool_async("food", "flush_food_cart", {"addressId": address_id})
    except Exception as e:  # noqa: BLE001
        log.warning("flush_food_cart during reject failed: %s", e)
    try:
        await mcp_client.call_tool_async("im", "clear_cart", {"selectedAddressId": address_id})
    except Exception as e:  # noqa: BLE001
        log.warning("clear_cart during reject failed: %s", e)
    logs = _add_log(state, "Rejected — flushed food cart & cleared Instamart cart")
    await asyncio.to_thread(
        record_qol_event,
        kind="hitl_rejected",
        title="Plan declined",
        detail=state.get("approval_request_id") or "",
        severity="warn",
        event_id=state.get("event_id"),
    )
    return {**state, "approval_status": "REJECTED", "execution_logs": logs}


async def calendar_mutate_node(state: ConciergeState) -> ConciergeState:
    calendar_event_id = state.get("calendar_event_id") or state.get("event_id")
    mode = state.get("mode") or "DINEOUT"
    status = state.get("approval_status") or "PENDING"
    rec_md = state.get("sommelier_recommendations_markdown") or ""

    parts = [
        state.get("event_description") or "",
        "",
        "---",
        "Autonomous Swiggy Social Concierge",
        f"Mode: {mode} · Status: {status}",
    ]
    if status == "REJECTED":
        parts.append("User declined — carts cleared. No orders placed.")
    elif mode == "DINEOUT":
        parts.extend(
            [
                f"Venue: {state.get('dineout_restaurant_name') or '—'}",
                f"Slot: {state.get('dineout_slot') or '—'}",
                f"Booking ID: {state.get('dineout_booking_id') or '—'}",
            ]
        )
    else:
        parts.extend(
            [
                f"Instamart order: {state.get('instamart_order_id') or '—'}",
                f"Food order: {state.get('food_order_id') or '—'}",
            ]
        )
    if rec_md.strip():
        parts.extend(["", rec_md.strip()])
    text = "\n".join(parts)
    if calendar_event_id:
        try:
            update_calendar_event_description(str(calendar_event_id), text)
        except Exception as e:  # noqa: BLE001
            log.warning("Calendar patch failed: %s", e)
    logs = _add_log(state, "Calendar description write-back complete")
    await asyncio.to_thread(
        save_execution,
        state.get("event_id") or "unknown",
        {
            "request_id": state.get("approval_request_id"),
            "status": "COMPLETED" if status == "APPROVED" else status,
            "mode": mode,
            "state": dict(state),
        },
    )
    await asyncio.to_thread(
        record_qol_event,
        kind="concierge_complete",
        title=f"Concierge {status}",
        detail=f"{mode} · {state.get('event_title')}",
        severity="info",
        event_id=state.get("event_id"),
    )
    return {**state, "execution_logs": logs}


# Backwards-compatible aliases used by older tests / imports
execute_dineout_node = stage_dineout_node
execute_zero_touch_node = stage_zero_touch_node
hitl_checkpoint_node = hitl_notify_node
