"""Food delivery mock restaurants + menus keyed by restaurantId."""

RESTAURANTS: list[dict] = [
    {
        "restaurant_id": "fd_dom_101",
        "name": "Domino's Pizza",
        "rating": 4.2,
        "eta_mins_min": 25,
        "eta_mins_max": 38,
        "cuisines": ["Pizza", "Italian"],
        "tag": "30 min delivery • Pure veg options",
        "price_for_two_inr": 500,
    },
    {
        "restaurant_id": "fd_bk_102",
        "name": "Burger King",
        "rating": 4.1,
        "eta_mins_min": 26,
        "eta_mins_max": 40,
        "cuisines": ["Burger", "Fast Food"],
        "tag": "Flame grilled",
        "price_for_two_inr": 420,
    },
    {
        "restaurant_id": "fd_misal_103",
        "name": "Shrimant Misal House",
        "rating": 4.5,
        "eta_mins_min": 28,
        "eta_mins_max": 42,
        "cuisines": ["Maharashtrian", "Street Food"],
        "tag": "Local favourite",
        "price_for_two_inr": 260,
    },
    {
        "restaurant_id": "fd_thali_104",
        "name": "Maratha Samrat Thali House",
        "rating": 4.3,
        "eta_mins_min": 30,
        "eta_mins_max": 45,
        "cuisines": ["North Indian", "Thali"],
        "tag": "Unlimited thali sundays",
        "price_for_two_inr": 650,
    },
    {
        "restaurant_id": "fd_ck_105",
        "name": "Mainland China · FC Road",
        "rating": 4.4,
        "eta_mins_min": 32,
        "eta_mins_max": 48,
        "cuisines": ["Chinese", "Asian"],
        "tag": "Sichuan-style gravies",
        "price_for_two_inr": 1100,
    },
]

MENU_BY_RESTAURANT: dict[str, dict] = {
    "fd_dom_101": {
        "restaurant_id": "fd_dom_101",
        "categories": [
            {
                "name": "Popular",
                "items": [
                    {
                        "item_id": "dom_mar_med",
                        "name": "Margherita Medium",
                        "description": "Classic tomato & mozzarella",
                        "price_inr": 389,
                        "vegetarian": True,
                    },
                    {
                        "item_id": "dom_pep_med",
                        "name": "Pepperoni Medium",
                        "description": "Pepperoni & cheese melt",
                        "price_inr": 529,
                        "vegetarian": False,
                    },
                    {
                        "item_id": "dom_ff",
                        "name": "Garlic Breadsticks",
                        "description": "Side — serves 2",
                        "price_inr": 149,
                        "vegetarian": True,
                    },
                ],
            },
        ],
    },
    "fd_bk_102": {
        "restaurant_id": "fd_bk_102",
        "categories": [
            {
                "name": "Burgers",
                "items": [
                    {"item_id": "bk_whooper", "name": "Whopper Meal", "description": "", "price_inr": 329, "vegetarian": False},
                    {"item_id": "bk_veg_whooper", "name": "Veggie Whopper", "description": "", "price_inr": 259, "vegetarian": True},
                ],
            }
        ],
    },
    "fd_misal_103": {"restaurant_id": "fd_misal_103", "categories": [{"name": "Specials", "items": [{"item_id": "mh_misal", "name": "Misal Pav", "price_inr": 140, "vegetarian": True}, {"item_id": "mh_td", "name": "Tarri Poha", "price_inr": 90, "vegetarian": True}]}]},
    "fd_thali_104": {"restaurant_id": "fd_thali_104", "categories": [{"name": "Thali", "items": [{"item_id": "th_std", "name": "Rajasthani Mini Thali", "price_inr": 280, "vegetarian": True}, {"item_id": "th_nl", "name": "Non-veg Frontier Thali", "price_inr": 420, "vegetarian": False}]}]},
    "fd_ck_105": {"restaurant_id": "fd_ck_105", "categories": [{"name": "Mains", "items": [{"item_id": "ck_kung", "name": "Kung Pao Chicken", "price_inr": 365, "vegetarian": False}, {"item_id": "ck_dumplings", "name": "Vegetable Dumplings (8 pcs)", "price_inr": 245, "vegetarian": True}]}]},
}
