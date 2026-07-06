"""Map production Swiggy tool names to legacy mock handler names."""

from __future__ import annotations

FOOD_ALIASES: dict[str, str] = {
    "get_restaurant_menu": "get_menu",
    "update_food_cart": "add_to_cart",
    "place_food_order": "place_order",
}

IM_ALIASES: dict[str, str] = {
    "update_cart": "add_to_cart",
}

DINEOUT_ALIASES: dict[str, str] = {
    "search_restaurants_dineout": "search_restaurants",
    "get_available_slots": "check_availability",
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
