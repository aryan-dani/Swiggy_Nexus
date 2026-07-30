"""Pydantic schemas for the Indian QoL Concierge."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class AttendeeProfile(BaseModel):
    email: str
    full_name: str = ""
    is_vegetarian: bool = False
    is_vegan: bool = False
    is_eggetarian: bool = False
    is_jain: bool = False
    is_halal: bool = False
    is_gluten_free: bool = False
    spice_tolerance: int = Field(default=3, ge=1, le=5)
    allergies: list[str] = Field(default_factory=list)
    fav_cuisines: list[str] = Field(default_factory=list)
    disliked_ingredients: list[str] = Field(default_factory=list)


class GroupTasteProfile(BaseModel):
    attendee_count: int = 0
    recognized_emails: list[str] = Field(default_factory=list)
    unrecognized_emails: list[str] = Field(default_factory=list)
    must_be_vegetarian: bool = False
    must_be_vegan: bool = False
    must_be_jain: bool = False
    must_be_halal: bool = False
    max_spice_tolerance: int = 5
    all_allergies: list[str] = Field(default_factory=list)
    recommended_cuisines: list[str] = Field(default_factory=list)
    individual_profiles: list[dict[str, Any]] = Field(default_factory=list)


class WeatherAlert(BaseModel):
    source: Literal["openweather", "scenario", "imd"] = "scenario"
    city: str = "Pune"
    lat: float = 18.5204
    lng: float = 73.8567
    temp_c: float = 28.0
    humidity: int = 60
    rain_mm: float = 0.0
    is_raining: bool = False
    is_heavy_rain: bool = False
    condition: str = "Clear"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MatchState(BaseModel):
    match_id: str = "ipl-sim-1"
    teams: str = "MI vs CSK"
    overs: float = 16.2
    required_run_rate: float = 12.5
    is_timeout: bool = False
    is_tense_chase: bool = False
    status: str = "in_play"
    note: str = ""


class FoodCartItem(BaseModel):
    itemId: str
    quantity: int = 1
    name: str | None = None
    price_inr: float | None = None


class StagedFoodCart(BaseModel):
    restaurantId: str
    restaurantName: str | None = None
    addressId: str = "addr_kp_001"
    cartItems: list[FoodCartItem] = Field(default_factory=list)
    estimated_total_inr: float = 0.0
    coupon_code: str | None = None


class InstamartCartItem(BaseModel):
    spinId: str
    quantity: int = 1
    name: str | None = None
    price_inr: float | None = None


class StagedInstamartCart(BaseModel):
    selectedAddressId: str = "addr_kp_001"
    items: list[InstamartCartItem] = Field(default_factory=list)
    estimated_total_inr: float = 0.0


class DineoutBookingPlan(BaseModel):
    """Staged (not yet booked) Dineout reservation — write happens post-HITL."""

    restaurantId: str
    restaurantName: str | None = None
    slotId: str | None = None
    itemId: str | None = None
    reservationTime: str | None = None
    guestCount: int = 2
    latitude: float = 18.5204
    longitude: float = 73.8567
    is_outdoor_or_rooftop: bool = False
    slot_label: str | None = None


class ApprovalRequest(BaseModel):
    request_id: str
    event_id: str
    thread_id: str
    trigger_type: Literal[
        "calendar_concierge",
        "rooftop_rescue",
        "bhajiya_chai",
        "guest_sos",
        "fuel_guard",
        "ipl_timeout",
        "pantry_refill",
        "voice_order",
    ] = "calendar_concierge"
    status: Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED"] = "PENDING"
    title: str = ""
    summary: str = ""
    cost_breakdown: dict[str, Any] = Field(default_factory=dict)
    staged_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None


class QoLEvent(BaseModel):
    event_id: str
    kind: str
    title: str
    detail: str = ""
    severity: Literal["info", "warn", "action"] = "info"
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramCallback(BaseModel):
    callback_query_id: str
    chat_id: str
    data: str
    from_user: str | None = None


class ManualTriggerBody(BaseModel):
    event_title: str = Field(..., examples=["Housewarming & Dinner"])
    event_time: str = Field(default="2026-07-26T19:00:00+05:30")
    event_location: str = Field(default="Home", examples=["Home or Bistro"])
    attendee_emails: list[str] = Field(
        default_factory=lambda: ["dani@nexus.ai", "priya@nexus.ai"]
    )
    description: str = Field(
        default="Social outing #swiggy",
        examples=["Hosting at home #swiggy"],
    )


class ApprovalBody(BaseModel):
    approved: bool = True
    comments: str | None = None


class SimulateWeatherBody(BaseModel):
    rain_mm: float = 25.0
    temp_c: float = 22.0
    is_raining: bool = True
    is_heavy_rain: bool = True
    condition: str = "Heavy rain"


class SimulateGuestsBody(BaseModel):
    count: int = Field(default=6, ge=1, le=20)


class SimulateIplBody(BaseModel):
    required_run_rate: float = 14.0
    is_timeout: bool = True
    is_tense_chase: bool = True
    overs: float = 17.3
    teams: str = "MI vs CSK"
