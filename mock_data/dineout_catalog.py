"""Dine-out (table booking) mock venues — IDs separate from food delivery."""

DINEOUT_RESTAURANTS: list[dict] = [
    {
        "restaurant_id": "do_bk_801",
        "name": "The Daily All Day · Kalyani Nagar",
        "rating": 4.4,
        "cuisines": ["Continental", "Cafe"],
        "area": "Kalyani Nagar",
        "price_for_two_inr": 1800,
    },
    {
        "restaurant_id": "do_malaka_802",
        "name": "Malaka Spice",
        "rating": 4.6,
        "cuisines": ["Asian", "Thai"],
        "area": "Koregaon Park",
        "price_for_two_inr": 2400,
    },
    {
        "restaurant_id": "do_savya_803",
        "name": "Savya Rasa · Baner",
        "rating": 4.5,
        "cuisines": ["South Indian"],
        "area": "Baner",
        "price_for_two_inr": 950,
    },
]

# Default slots when check_availability is called — slight variation via handler
DEFAULT_SLOTS = ["18:00", "18:30", "19:00", "19:30", "20:00", "20:30"]
