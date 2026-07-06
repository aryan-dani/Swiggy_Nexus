"""Map production Swiggy tool names to legacy mock handler names."""

from __future__ import annotations

FOOD_ALIASES: dict[str, str] = {
    "get_restaurant_menu": "get_menu",
    "update_food_cart": "add_to_cart",
    "place_food_order": "place_order",
    # These already match handler names — explicit identity mappings for clarity
    "search_menu": "search_menu",
    "get_food_cart": "get_food_cart",
    "flush_food_cart": "flush_food_cart",
    "fetch_food_coupons": "fetch_food_coupons",
    "apply_food_coupon": "apply_food_coupon",
    "get_food_orders": "get_food_orders",
    "get_food_order_details": "get_food_order_details",
    "track_food_order": "track_food_order",
}

IM_ALIASES: dict[str, str] = {
    "update_cart": "add_to_cart",
    # Identity mappings
    "search_products": "search_products",
    "your_go_to_items": "your_go_to_items",
    "get_cart": "get_cart",
    "clear_cart": "clear_cart",
    "checkout": "checkout",
    "get_orders": "get_orders",
    "get_order_details": "get_order_details",
    "track_order": "track_order",
    "create_address": "create_address",
    "delete_address": "delete_address",
}

DINEOUT_ALIASES: dict[str, str] = {
    "search_restaurants_dineout": "search_restaurants",
    "get_available_slots": "check_availability",
    # Identity mappings
    "get_restaurant_details": "get_restaurant_details",
    "get_saved_locations": "get_saved_locations",
    "book_table": "book_table",
    "get_booking_status": "get_booking_status",
    "create_cart": "create_cart",
}


def resolve_method(vertical: str, method: str) -> str:
    m = method.strip()
    if vertical == "food":
        return FOOD_ALIASES.get(m, m)
    if vertical == "im":
        return IM_ALIASES.get(m, m)
    if vertical == "dineout":
        return DINEOUT_ALIASES.get(m, m)
    return m
