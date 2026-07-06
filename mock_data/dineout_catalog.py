"""Dine-out (table booking) mock venues — separate IDs from food delivery."""

import time
from datetime import datetime, timedelta

DINEOUT_RESTAURANTS: list[dict] = [
    {"restaurant_id": "do_bk_801", "name": "The Daily All Day · Kalyani Nagar", "rating": 4.4, "cuisines": ["Continental", "Cafe"], "area": "Kalyani Nagar", "price_for_two_inr": 1800, "costForTwo": 1800, "availability": "AVAILABLE", "_lat": 18.5489, "_lng": 73.9035},
    {"restaurant_id": "do_malaka_802", "name": "Malaka Spice", "rating": 4.6, "cuisines": ["Asian", "Thai"], "area": "Koregaon Park", "price_for_two_inr": 2400, "costForTwo": 2400, "availability": "AVAILABLE", "_lat": 18.5362, "_lng": 73.8958},
    {"restaurant_id": "do_savya_803", "name": "Savya Rasa · Baner", "rating": 4.5, "cuisines": ["South Indian"], "area": "Baner", "price_for_two_inr": 950, "costForTwo": 950, "availability": "AVAILABLE", "_lat": 18.5590, "_lng": 73.7794},
    {"restaurant_id": "do_italian_804", "name": "Spesso · Koregaon Park", "rating": 4.5, "cuisines": ["Italian", "European"], "area": "Koregaon Park", "price_for_two_inr": 3200, "costForTwo": 3200, "availability": "AVAILABLE", "_lat": 18.5375, "_lng": 73.8910},
    {"restaurant_id": "do_social_805", "name": "Social · FC Road", "rating": 4.3, "cuisines": ["Continental", "Bar"], "area": "FC Road", "price_for_two_inr": 1500, "costForTwo": 1500, "availability": "AVAILABLE", "_lat": 18.5244, "_lng": 73.8410},
    {"restaurant_id": "do_peshwa_806", "name": "Peshwa Pavilion", "rating": 4.7, "cuisines": ["Maharashtrian", "Fine Dining"], "area": "Koregaon Park", "price_for_two_inr": 4500, "costForTwo": 4500, "availability": "AVAILABLE", "_lat": 18.5340, "_lng": 73.8980},
    {"restaurant_id": "do_baoli_807", "name": "Baoli · SB Road", "rating": 4.4, "cuisines": ["North Indian", "Mughlai"], "area": "SB Road", "price_for_two_inr": 2800, "costForTwo": 2800, "availability": "AVAILABLE", "_lat": 18.5280, "_lng": 73.8320},
    {"restaurant_id": "do_unavail_808", "name": "Rooftop Lounge (Walk-in only)", "rating": 4.2, "cuisines": ["Continental"], "area": "Baner", "price_for_two_inr": 2000, "costForTwo": 2000, "availability": "UNAVAILABLE", "_lat": 18.5600, "_lng": 73.7800},
]

DEFAULT_SLOTS = ["18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"]


def structured_slots(restaurant_id: str, date: str, guest_count: int) -> list[dict]:
    """Build production-shaped slot objects for get_available_slots."""
    base_ts = int(datetime.now().timestamp())
    slots: list[dict] = []
    for i, label in enumerate(DEFAULT_SLOTS[:6]):
        hour, minute = label.split(":")
        res_time = base_ts + (i + 1) * 3600
        slot_id = 4200 + i
        slots.append({
            "slotId": slot_id,
            "label": label,
            "reservationTime": res_time,
            "guestCount": guest_count,
            "band": "dinner" if int(hour) >= 18 else "lunch",
            "deals": [{
                "slotId": slot_id,
                "itemId": f"{restaurant_id}-ticket_{slot_id}",
                "isFree": True,
                "bookingPrice": 0,
                "title": "Free table reservation",
            }],
        })
    return slots
