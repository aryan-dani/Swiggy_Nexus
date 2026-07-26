"""India-first QoL triggers — rain pivot, bhajiya, guests, fuel, IPL."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from app.db.store import (
    create_approval,
    get_approval,
    list_approvals,
    record_qol_event,
)
from app.mcp.client import mcp_client
from app.schemas import WeatherAlert
from app.services.match import match_provider
from app.services.notifications import send_approval_request, send_qol_prompt
from app.services.weather import get_weather_provider

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# In-memory cooldowns (also gated by qol_events for demos)
_cooldowns: dict[str, datetime] = {}

# Staged outdoor bookings for rooftop rescue demos
_outdoor_bookings: list[dict[str, Any]] = []


def register_outdoor_booking(booking: dict[str, Any]) -> None:
    _outdoor_bookings.append(booking)


def _cooled(key: str, minutes: int = 90) -> bool:
    last = _cooldowns.get(key)
    if last and datetime.utcnow() - last < timedelta(minutes=minutes):
        return True
    return False


def _mark(key: str) -> None:
    _cooldowns[key] = datetime.utcnow()


async def run_all_qol_checks() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    weather = await get_weather_provider().get_current()
    results.append(await check_rooftop_rescue(weather))
    results.append(await check_bhajiya_chai(weather))
    results.append(await check_fuel_guard())
    results.append(await check_ipl_timeout())
    return [r for r in results if r]


async def check_rooftop_rescue(weather: WeatherAlert | None = None) -> dict[str, Any] | None:
    weather = weather or await get_weather_provider().get_current()
    if not weather.is_heavy_rain and not (weather.is_raining and weather.rain_mm >= 5):
        return None
    if _cooled("rooftop_rescue"):
        return None

    # Prefer registered outdoor bookings; else demo synthetic
    bookings = [b for b in _outdoor_bookings if b.get("is_outdoor_or_rooftop")]
    if not bookings:
        bookings = [
            {
                "restaurantId": "do_italian_804",
                "restaurantName": "Italian Spesso Rooftop",
                "slot_label": "20:00",
                "is_outdoor_or_rooftop": True,
                "foodRestaurantId": "fd_dom_101",
                "minutes_until": 60,
            }
        ]

    booking = bookings[0]
    mins = int(booking.get("minutes_until") or 60)
    if mins < 45 or mins > 90:
        # Still allow demo when synthetic
        if booking.get("restaurantName") != "Italian Spesso Rooftop":
            return None

    _mark("rooftop_rescue")
    text = (
        f"Bahot tez barish shuru ho gayi hai! 🌧\n"
        f"Your *{booking.get('restaurantName')}* table (~{mins}m) looks outdoor/rooftop.\n\n"
        f"*Options:*\n"
        f"1. Order the same kitchen home (Food MCP + coupons)\n"
        f"2. Try an indoor slot at the same venue\n"
        f"3. Keep the table\n\n"
        f"_Note: Swiggy MCP has no cancel_reservation tool — "
        f"please cancel the old table in the Swiggy app / customer care if you pivot._"
    )
    await send_qol_prompt(
        text,
        buttons=[
            ("🏠 Order Home", "qol:rooftop:home"),
            ("🪑 Indoor slot", "qol:rooftop:indoor"),
            ("✅ Keep table", "qol:rooftop:keep"),
        ],
    )
    ev = record_qol_event(
        kind="rooftop_rescue",
        title="Rooftop Rescue prompted",
        detail=booking.get("restaurantName") or "",
        severity="action",
        meta={"weather": weather.model_dump(mode="json"), "booking": booking},
    )
    return ev


async def handle_rooftop_choice(choice: str) -> dict[str, Any]:
    address_id = settings.DEFAULT_ADDRESS_ID
    if choice == "keep":
        record_qol_event(kind="rooftop_keep", title="User kept rooftop table", severity="info")
        return {"status": "kept"}

    if choice == "indoor":
        slots = await mcp_client.call_tool_async(
            "dineout",
            "get_available_slots",
            {
                "restaurantId": "do_italian_804",
                "guestCount": 4,
                "date": datetime.now(IST).strftime("%Y-%m-%d"),
                "latitude": settings.HOME_LAT,
                "longitude": settings.HOME_LNG,
            },
        )
        approval = create_approval(
            event_id=f"rooftop-indoor-{uuid.uuid4().hex[:6]}",
            thread_id=f"rooftop-indoor-{uuid.uuid4().hex[:6]}",
            trigger_type="rooftop_rescue",
            title="Rooftop Rescue · Indoor rebook",
            summary="Re-book indoor slot after rain pivot",
            cost_breakdown={"mode": "DINEOUT", "slots": slots},
            staged_payload={
                "mode": "DINEOUT",
                "dineout_plan": {
                    "restaurantId": "do_italian_804",
                    "restaurantName": "Italian Spesso",
                    "guestCount": 4,
                    "slot_label": "19:30",
                    "latitude": settings.HOME_LAT,
                    "longitude": settings.HOME_LNG,
                },
                "action": "book_indoor",
            },
        )
        await send_approval_request(
            settings.NOTIFICATION_PLATFORM,
            {
                "request_id": approval["request_id"],
                "title": approval["title"],
                "location": "Indoor",
                "summary": approval["summary"],
            },
            approval["cost_breakdown"],
            f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{approval['request_id']}",
            request_id=approval["request_id"],
        )
        return {"status": "pending_approval", "approval": approval}

    # Order home — stage food cart from twin kitchen
    menu = await mcp_client.call_tool_async(
        "food",
        "get_restaurant_menu",
        {"restaurantId": "fd_dom_101", "addressId": address_id},
    )
    items = []
    for cat in (menu or {}).get("categories") or []:
        for item in (cat.get("items") or [])[:2]:
            items.append(
                {
                    "itemId": str(item.get("item_id") or item.get("itemId") or "item_1"),
                    "quantity": 1,
                    "name": item.get("name"),
                }
            )
    if not items:
        items = [{"itemId": "item_pasta", "quantity": 2, "name": "Rainy day pasta"}]

    await mcp_client.call_tool_async(
        "food",
        "update_food_cart",
        {
            "restaurantId": "fd_dom_101",
            "addressId": address_id,
            "cartItems": [{"itemId": i["itemId"], "quantity": i["quantity"]} for i in items],
        },
    )
    coupons = {}
    try:
        coupons = await mcp_client.call_tool_async(
            "food", "fetch_food_coupons", {"addressId": address_id}
        )
        codes = (coupons or {}).get("coupons") or (coupons or {}).get("offers") or []
        if codes:
            code = codes[0].get("code") if isinstance(codes[0], dict) else str(codes[0])
            await mcp_client.call_tool_async(
                "food", "apply_food_coupon", {"couponCode": code, "addressId": address_id}
            )
    except Exception:  # noqa: BLE001
        pass

    approval = create_approval(
        event_id=f"rooftop-home-{uuid.uuid4().hex[:6]}",
        thread_id=f"rooftop-home-{uuid.uuid4().hex[:6]}",
        trigger_type="rooftop_rescue",
        title="Rooftop Rescue · Order home",
        summary="Same kitchen delivery · cancel old table manually in Swiggy app",
        cost_breakdown={"mode": "FOOD_PIVOT", "items": items},
        staged_payload={
            "mode": "ZERO_TOUCH_HOST",
            "staged_food_cart": {
                "restaurantId": "fd_dom_101",
                "restaurantName": "Italian Spesso (delivery)",
                "addressId": address_id,
                "cartItems": items,
                "estimated_total_inr": 499,
            },
            "staged_im_cart": {"items": [], "selectedAddressId": address_id},
        },
    )
    await send_approval_request(
        settings.NOTIFICATION_PLATFORM,
        {
            "request_id": approval["request_id"],
            "title": approval["title"],
            "location": "Home",
            "summary": approval["summary"],
        },
        approval["cost_breakdown"],
        f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{approval['request_id']}",
        request_id=approval["request_id"],
    )
    record_qol_event(
        kind="rooftop_home_staged",
        title="Rain pivot cart staged",
        detail=approval["request_id"],
        severity="action",
    )
    return {"status": "pending_approval", "approval": approval}


async def check_bhajiya_chai(weather: WeatherAlert | None = None) -> dict[str, Any] | None:
    weather = weather or await get_weather_provider().get_current()
    now = datetime.now(IST)
    if not (16 <= now.hour < 19):
        return None
    if not (weather.is_raining and weather.temp_c <= 24):
        return None
    if _cooled("bhajiya_chai", minutes=180):
        return None
    _mark("bhajiya_chai")

    go_to = {}
    try:
        go_to = await mcp_client.call_tool_async("im", "your_go_to_items", {})
    except Exception:  # noqa: BLE001
        go_to = {}

    text = (
        "Barish + Chai weather detected! ☕🍟\n"
        "Want me to order *Kanda Bhajiya / Samosas* from your go-to kitchen, "
        "or dispatch a 10-min Instamart bag (Adrak, Chai Patti, Maggi)?"
    )
    await send_qol_prompt(
        text,
        buttons=[
            ("🍟 Food bhajiya", "qol:bhajiya:food"),
            ("🛒 Instamart chai kit", "qol:bhajiya:im"),
        ],
    )
    return record_qol_event(
        kind="bhajiya_chai",
        title="Bhajiya & Chai prompt",
        detail=f"temp={weather.temp_c} rain={weather.rain_mm}",
        severity="action",
        meta={"go_to": go_to, "weather": weather.model_dump(mode="json")},
    )


async def handle_bhajiya_choice(choice: str) -> dict[str, Any]:
    address_id = settings.DEFAULT_ADDRESS_ID
    if choice == "im":
        search = await mcp_client.call_tool_async(
            "im",
            "search_products",
            {"query": "ginger tea maggi", "selectedAddressId": address_id},
        )
        products = (search or {}).get("products") or []
        items = []
        for p in products[:4]:
            variants = p.get("variants") or []
            spin = variants[0].get("spinId") if variants else p.get("spinId")
            if spin:
                items.append({"spinId": spin, "quantity": 1, "name": p.get("name")})
        if not items:
            items = [
                {"spinId": "spin_tea_green", "quantity": 1, "name": "Tea"},
                {"spinId": "spin_maggi", "quantity": 2, "name": "Maggi"},
                {"spinId": "spin_onion_1kg", "quantity": 1, "name": "Onion"},
            ]
        await mcp_client.call_tool_async(
            "im",
            "update_cart",
            {
                "selectedAddressId": address_id,
                "items": [{"spinId": i["spinId"], "quantity": i["quantity"]} for i in items],
            },
        )
        approval = create_approval(
            event_id=f"bhajiya-im-{uuid.uuid4().hex[:6]}",
            thread_id=f"bhajiya-im-{uuid.uuid4().hex[:6]}",
            trigger_type="bhajiya_chai",
            title="Bhajiya & Chai · Instamart kit",
            summary="Adrak + chai + Maggi 10-min bag",
            cost_breakdown={"mode": "IM", "items": items},
            staged_payload={
                "mode": "ZERO_TOUCH_HOST",
                "staged_im_cart": {
                    "selectedAddressId": address_id,
                    "items": items,
                    "estimated_total_inr": 199,
                },
                "staged_food_cart": {"cartItems": [], "addressId": address_id},
            },
        )
    else:
        await mcp_client.call_tool_async(
            "food",
            "search_restaurants",
            {"addressId": address_id, "query": "bhajiya samosa"},
        )
        items = [{"itemId": "item_bhajiya", "quantity": 2, "name": "Kanda Bhajiya"}]
        await mcp_client.call_tool_async(
            "food",
            "update_food_cart",
            {
                "restaurantId": "fd_snacks_01",
                "addressId": address_id,
                "cartItems": items,
            },
        )
        approval = create_approval(
            event_id=f"bhajiya-fd-{uuid.uuid4().hex[:6]}",
            thread_id=f"bhajiya-fd-{uuid.uuid4().hex[:6]}",
            trigger_type="bhajiya_chai",
            title="Bhajiya & Chai · Food",
            summary="Kanda Bhajiya from go-to kitchen",
            cost_breakdown={"mode": "FOOD", "items": items},
            staged_payload={
                "mode": "ZERO_TOUCH_HOST",
                "staged_food_cart": {
                    "restaurantId": "fd_snacks_01",
                    "addressId": address_id,
                    "cartItems": items,
                    "estimated_total_inr": 180,
                },
                "staged_im_cart": {"items": [], "selectedAddressId": address_id},
            },
        )

    await send_approval_request(
        settings.NOTIFICATION_PLATFORM,
        {
            "request_id": approval["request_id"],
            "title": approval["title"],
            "location": "Home",
            "summary": approval["summary"],
        },
        approval["cost_breakdown"],
        f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{approval['request_id']}",
        request_id=approval["request_id"],
    )
    return {"status": "pending_approval", "approval": approval}


async def guest_sos(count: int = 6) -> dict[str, Any]:
    address_id = settings.DEFAULT_ADDRESS_ID
    qty = max(1, count // 3)
    search = await mcp_client.call_tool_async(
        "im",
        "search_products",
        {"query": "namkeen biscuits cold drinks napkins", "selectedAddressId": address_id},
    )
    products = (search or {}).get("products") or []
    items = []
    for p in products[:5]:
        variants = p.get("variants") or []
        spin = variants[0].get("spinId") if variants else p.get("spinId")
        if spin:
            items.append({"spinId": spin, "quantity": qty, "name": p.get("name")})
    if not items:
        items = [
            {"spinId": "spin_chips_lays", "quantity": qty, "name": "Namkeen/Chips"},
            {"spinId": "spin_biscuit", "quantity": qty, "name": "Biscuits"},
            {"spinId": "spin_cola_500", "quantity": count, "name": "Cold drinks"},
            {"spinId": "spin_napkins", "quantity": 1, "name": "Napkins"},
        ]
    await mcp_client.call_tool_async(
        "im",
        "update_cart",
        {
            "selectedAddressId": address_id,
            "items": [{"spinId": i["spinId"], "quantity": i["quantity"]} for i in items],
        },
    )
    approval = create_approval(
        event_id=f"guests-{uuid.uuid4().hex[:6]}",
        thread_id=f"guests-{uuid.uuid4().hex[:6]}",
        trigger_type="guest_sos",
        title=f"Bin Bulaye Mehmaan · {count} guests",
        summary="Namkeen + biscuits + drinks + napkins (10-min Instamart)",
        cost_breakdown={"mode": "IM", "guest_count": count, "items": items},
        staged_payload={
            "mode": "ZERO_TOUCH_HOST",
            "staged_im_cart": {
                "selectedAddressId": address_id,
                "items": items,
                "estimated_total_inr": 40 * count,
            },
            "staged_food_cart": {"cartItems": [], "addressId": address_id},
        },
    )
    await send_approval_request(
        settings.NOTIFICATION_PLATFORM,
        {
            "request_id": approval["request_id"],
            "title": approval["title"],
            "location": "Home",
            "summary": approval["summary"],
        },
        approval["cost_breakdown"],
        f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{approval['request_id']}",
        request_id=approval["request_id"],
    )
    record_qol_event(
        kind="guest_sos",
        title=f"Guest SOS · {count}",
        detail=approval["request_id"],
        severity="action",
    )
    return {"status": "pending_approval", "approval": approval}


_fuel_force = False


def force_fuel_guard(enabled: bool = True) -> None:
    global _fuel_force
    _fuel_force = enabled


async def check_fuel_guard() -> dict[str, Any] | None:
    now = datetime.now(IST)
    hour = now.hour
    in_window = hour >= 23 or hour < 3 or _fuel_force
    if not in_window:
        return None
    if _cooled("fuel_guard", minutes=240) and not _fuel_force:
        return None
    if not (_fuel_force or settings.FORCE_FUEL_GUARD):
        return None
    _mark("fuel_guard")
    force_fuel_guard(False)
    text = (
        "Late-night study/coding fuel check 💻\n"
        "Red Bull / cold coffee / munchies via Instamart?"
    )
    await send_qol_prompt(text, buttons=[("⚡ Fuel me", "qol:fuel:go"), ("Skip", "qol:fuel:skip")])
    return record_qol_event(
        kind="fuel_guard",
        title="Late-Night Fuel Guard",
        detail=now.isoformat(),
        severity="action",
    )


async def handle_fuel_choice(choice: str) -> dict[str, Any]:
    if choice == "skip":
        return {"status": "skipped"}
    address_id = settings.DEFAULT_ADDRESS_ID
    items = [
        {"spinId": "spin_energy_drink", "quantity": 2, "name": "Red Bull"},
        {"spinId": "spin_americano", "quantity": 1, "name": "Coffee"},
        {"spinId": "spin_chips_lays", "quantity": 2, "name": "Munchies"},
    ]
    await mcp_client.call_tool_async(
        "im",
        "update_cart",
        {
            "selectedAddressId": address_id,
            "items": [{"spinId": i["spinId"], "quantity": i["quantity"]} for i in items],
        },
    )
    approval = create_approval(
        event_id=f"fuel-{uuid.uuid4().hex[:6]}",
        thread_id=f"fuel-{uuid.uuid4().hex[:6]}",
        trigger_type="fuel_guard",
        title="Late-Night Fuel Guard",
        summary="Energy + munchies Instamart cart",
        cost_breakdown={"mode": "IM", "items": items},
        staged_payload={
            "mode": "ZERO_TOUCH_HOST",
            "staged_im_cart": {
                "selectedAddressId": address_id,
                "items": items,
                "estimated_total_inr": 320,
            },
            "staged_food_cart": {"cartItems": [], "addressId": address_id},
        },
    )
    await send_approval_request(
        settings.NOTIFICATION_PLATFORM,
        {
            "request_id": approval["request_id"],
            "title": approval["title"],
            "location": "Desk",
            "summary": approval["summary"],
        },
        approval["cost_breakdown"],
        f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{approval['request_id']}",
        request_id=approval["request_id"],
    )
    return {"status": "pending_approval", "approval": approval}


async def check_ipl_timeout() -> dict[str, Any] | None:
    state = match_provider.get_state()
    if not (state.is_timeout and state.is_tense_chase and state.required_run_rate >= 10):
        return None
    if _cooled("ipl_timeout", minutes=30):
        return None
    _mark("ipl_timeout")
    text = (
        f"IPL Timeout Sprint 🏏\n"
        f"*{state.teams}* · RRR {state.required_run_rate} @ {state.overs} overs\n"
        f"Finger foods for the chase?"
    )
    await send_qol_prompt(
        text,
        buttons=[("🍟 Order snacks", "qol:ipl:go"), ("Not now", "qol:ipl:skip")],
    )
    return record_qol_event(
        kind="ipl_timeout",
        title="IPL Timeout Sprint",
        detail=state.teams,
        severity="action",
        meta=state.model_dump(),
    )


async def handle_ipl_choice(choice: str) -> dict[str, Any]:
    if choice == "skip":
        return {"status": "skipped"}
    address_id = settings.DEFAULT_ADDRESS_ID
    items = [
        {"itemId": "item_fries", "quantity": 2, "name": "Fries"},
        {"itemId": "item_wings", "quantity": 1, "name": "Wings"},
    ]
    await mcp_client.call_tool_async(
        "food",
        "update_food_cart",
        {
            "restaurantId": "fd_snacks_01",
            "addressId": address_id,
            "cartItems": items,
        },
    )
    approval = create_approval(
        event_id=f"ipl-{uuid.uuid4().hex[:6]}",
        thread_id=f"ipl-{uuid.uuid4().hex[:6]}",
        trigger_type="ipl_timeout",
        title="IPL Timeout Sprint",
        summary="Finger foods during tense chase",
        cost_breakdown={"mode": "FOOD", "items": items},
        staged_payload={
            "mode": "ZERO_TOUCH_HOST",
            "staged_food_cart": {
                "restaurantId": "fd_snacks_01",
                "addressId": address_id,
                "cartItems": items,
                "estimated_total_inr": 450,
            },
            "staged_im_cart": {"items": [], "selectedAddressId": address_id},
        },
    )
    await send_approval_request(
        settings.NOTIFICATION_PLATFORM,
        {
            "request_id": approval["request_id"],
            "title": approval["title"],
            "location": "Couch",
            "summary": approval["summary"],
        },
        approval["cost_breakdown"],
        f"{settings.BASE_URL.rstrip('/')}/api/hitl/approve/{approval['request_id']}",
        request_id=approval["request_id"],
    )
    return {"status": "pending_approval", "approval": approval}


async def execute_staged_approval(approval: dict[str, Any]) -> dict[str, Any]:
    """Execute write tools for QoL approvals that are not full LangGraph threads."""
    payload = approval.get("staged_payload") or {}
    mode = payload.get("mode")
    address_id = settings.DEFAULT_ADDRESS_ID
    result: dict[str, Any] = {"mode": mode}

    if mode == "DINEOUT" or payload.get("action") == "book_indoor":
        plan = payload.get("dineout_plan") or {}
        booking = await mcp_client.call_tool_async(
            "dineout",
            "book_table",
            {
                "restaurantId": plan.get("restaurantId"),
                "slot": plan.get("slot_label") or "19:30",
                "guestCount": plan.get("guestCount") or 4,
                "latitude": plan.get("latitude") or settings.HOME_LAT,
                "longitude": plan.get("longitude") or settings.HOME_LNG,
            },
        )
        result["booking"] = booking
        return result

    staged_im = payload.get("staged_im_cart") or {}
    staged_food = payload.get("staged_food_cart") or {}
    if staged_im.get("items"):
        await mcp_client.call_tool_async(
            "im",
            "update_cart",
            {
                "selectedAddressId": staged_im.get("selectedAddressId") or address_id,
                "items": [
                    {"spinId": i["spinId"], "quantity": i["quantity"]} for i in staged_im["items"]
                ],
            },
        )
        result["im_checkout"] = await mcp_client.call_tool_async(
            "im", "checkout", {"addressId": staged_im.get("selectedAddressId") or address_id}
        )
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
        result["food_order"] = await mcp_client.call_tool_async(
            "food",
            "place_food_order",
            {"addressId": staged_food.get("addressId") or address_id},
        )
    return result
