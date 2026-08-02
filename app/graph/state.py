"""LangGraph ConciergeState for the Indian QoL Concierge."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class ConciergeState(TypedDict, total=False):
    # Event ingestion
    event_id: str
    event_title: str
    event_time_str: str
    event_location: str
    event_description: str
    attendee_emails: list[str]
    calendar_event_id: str
    calendar_html_link: str
    calendar_mock: bool
    maps_url: str
    suppress_hitl_telegram: bool
    preferred_restaurant_query: str
    preferred_slot: str
    preferred_slot_id: str | None
    preferred_food_query: str
    guest_count: int
    auto_split_bill: bool
    trigger_type: str
    bill_split: dict[str, Any]
    night_out_receipt: dict[str, Any]

    # Taste vault
    group_profile: dict[str, Any]
    unknown_attendees: list[str]

    # Routing
    mode: Literal["DINEOUT", "ZERO_TOUCH_HOST"]
    routing_reason: str

    # Staged Dineout (read-only until execute_transactions)
    dineout_plan: dict[str, Any]
    dineout_restaurant_id: str | None
    dineout_restaurant_name: str | None
    dineout_slot: str | None
    dineout_slot_id: str | None
    dineout_item_id: str | None
    dineout_booking_id: str | None
    dineout_menu: dict[str, Any] | None
    dineout_error: str | None

    # Staged carts
    staged_food_cart: dict[str, Any]
    staged_im_cart: dict[str, Any]
    instamart_query: str | None
    instamart_cart_id: str | None
    instamart_order_id: str | None
    instamart_total: float | None
    food_restaurant_id: str | None
    food_cart_id: str | None
    food_order_id: str | None
    food_total: float | None

    # Sommelier
    sommelier_recommendations_markdown: str | None
    menu_items_analyzed: list[dict[str, Any]]

    # HITL
    approval_request_id: str
    approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
    total_estimated_cost: float
    cost_summary_breakdown: dict[str, Any]
    hitl_message: str

    # Post-approval scheduling
    scheduled_im_job_id: str | None
    scheduled_food_job_id: str | None

    # Diagnostics
    execution_logs: list[dict[str, Any]]
    errors: list[str]
    address_id: str
