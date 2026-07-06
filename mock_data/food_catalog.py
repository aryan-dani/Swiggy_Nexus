"""Food delivery mock restaurants + menus keyed by restaurantId."""

RESTAURANTS: list[dict] = [
    {"restaurant_id": "fd_dom_101", "name": "Domino's Pizza", "rating": 4.2, "eta_mins_min": 25, "eta_mins_max": 38, "cuisines": ["Pizza", "Italian"], "tag": "30 min delivery", "price_for_two_inr": 500, "distance_km": 2.1, "availability_status": "OPEN"},
    {"restaurant_id": "fd_bk_102", "name": "Burger King", "rating": 4.1, "eta_mins_min": 26, "eta_mins_max": 40, "cuisines": ["Burger", "Fast Food"], "tag": "Flame grilled", "price_for_two_inr": 420, "distance_km": 3.4, "availability_status": "OPEN"},
    {"restaurant_id": "fd_misal_103", "name": "Shrimant Misal House", "rating": 4.5, "eta_mins_min": 28, "eta_mins_max": 42, "cuisines": ["Maharashtrian", "Street Food"], "tag": "Local favourite", "price_for_two_inr": 260, "distance_km": 1.8, "availability_status": "OPEN"},
    {"restaurant_id": "fd_thali_104", "name": "Maratha Samrat Thali House", "rating": 4.3, "eta_mins_min": 30, "eta_mins_max": 45, "cuisines": ["North Indian", "Thali"], "tag": "Unlimited thali sundays", "price_for_two_inr": 650, "distance_km": 4.2, "availability_status": "OPEN"},
    {"restaurant_id": "fd_ck_105", "name": "Mainland China · FC Road", "rating": 4.4, "eta_mins_min": 32, "eta_mins_max": 48, "cuisines": ["Chinese", "Asian"], "tag": "Sichuan-style", "price_for_two_inr": 1100, "distance_km": 5.1, "availability_status": "OPEN"},
    {"restaurant_id": "fd_biryani_106", "name": "Biryani House", "rating": 4.5, "eta_mins_min": 30, "eta_mins_max": 42, "cuisines": ["Biryani", "North Indian"], "tag": "Hyderabadi dum", "price_for_two_inr": 550, "distance_km": 2.8, "availability_status": "OPEN"},
    {"restaurant_id": "fd_paradise_107", "name": "Paradise Biryani", "rating": 4.3, "eta_mins_min": 35, "eta_mins_max": 48, "cuisines": ["Biryani"], "tag": "Since 1953 style", "price_for_two_inr": 620, "distance_km": 6.2, "availability_status": "OPEN"},
    {"restaurant_id": "fd_gelato_108", "name": "Gelato Vivo", "rating": 4.6, "eta_mins_min": 22, "eta_mins_max": 35, "cuisines": ["Desserts", "Italian"], "tag": "Artisan gelato", "price_for_two_inr": 400, "distance_km": 1.5, "availability_status": "OPEN"},
    {"restaurant_id": "fd_natural_109", "name": "Natural Ice Cream", "rating": 4.7, "eta_mins_min": 20, "eta_mins_max": 32, "cuisines": ["Desserts", "Ice Cream"], "tag": "Fruit flavours", "price_for_two_inr": 350, "distance_km": 2.0, "availability_status": "OPEN"},
    {"restaurant_id": "fd_punjab_110", "name": "Punjab Grill Delivery", "rating": 4.4, "eta_mins_min": 38, "eta_mins_max": 52, "cuisines": ["North Indian", "Mughlai"], "tag": "Premium gravies", "price_for_two_inr": 900, "distance_km": 7.5, "availability_status": "OPEN"},
    {"restaurant_id": "fd_south_111", "name": "Vaishali Restaurant", "rating": 4.2, "eta_mins_min": 28, "eta_mins_max": 40, "cuisines": ["South Indian"], "tag": "FC Road classic", "price_for_two_inr": 320, "distance_km": 3.0, "availability_status": "OPEN"},
    {"restaurant_id": "fd_closed_112", "name": "Midnight Wok (Closed)", "rating": 4.0, "eta_mins_min": 40, "eta_mins_max": 55, "cuisines": ["Chinese"], "tag": "Opens 6 PM", "price_for_two_inr": 480, "distance_km": 4.0, "availability_status": "CLOSED"},
]

FOOD_COUPONS: list[dict] = [
    {"code": "WELCOME50", "description": "₹50 off on first order", "requiresOnlinePayment": False, "discount_inr": 50},
    {"code": "FLAT100", "description": "₹100 off above ₹499", "requiresOnlinePayment": False, "discount_inr": 100},
    {"code": "PAYTM200", "description": "₹200 off with online pay", "requiresOnlinePayment": True, "discount_inr": 200},
]

MENU_BY_RESTAURANT: dict[str, dict] = {
    "fd_dom_101": {
        "restaurant_id": "fd_dom_101",
        "categories": [{"name": "Popular", "items": [
            {"item_id": "dom_mar_med", "name": "Margherita Medium", "description": "Classic tomato & mozzarella", "price_inr": 389, "vegetarian": True, "hasVariants": False, "hasAddons": True},
            {"item_id": "dom_pep_med", "name": "Pepperoni Medium", "description": "Pepperoni & cheese", "price_inr": 529, "vegetarian": False, "hasVariants": False, "hasAddons": True},
            {"item_id": "dom_ff", "name": "Garlic Breadsticks", "description": "Side — serves 2", "price_inr": 149, "vegetarian": True, "hasVariants": False, "hasAddons": False},
        ]}],
    },
    "fd_bk_102": {"restaurant_id": "fd_bk_102", "categories": [{"name": "Burgers", "items": [
        {"item_id": "bk_whooper", "name": "Whopper Meal", "price_inr": 329, "vegetarian": False, "hasVariants": True, "hasAddons": False},
        {"item_id": "bk_veg_whooper", "name": "Veggie Whopper", "price_inr": 259, "vegetarian": True, "hasVariants": False, "hasAddons": False},
    ]}]},
    "fd_misal_103": {"restaurant_id": "fd_misal_103", "categories": [{"name": "Specials", "items": [
        {"item_id": "mh_misal", "name": "Misal Pav", "price_inr": 140, "vegetarian": True, "hasVariants": False, "hasAddons": False},
        {"item_id": "mh_td", "name": "Tarri Poha", "price_inr": 90, "vegetarian": True, "hasVariants": False, "hasAddons": False},
    ]}]},
    "fd_thali_104": {"restaurant_id": "fd_thali_104", "categories": [{"name": "Thali", "items": [
        {"item_id": "th_std", "name": "Rajasthani Mini Thali", "price_inr": 280, "vegetarian": True, "hasVariants": False, "hasAddons": False},
        {"item_id": "th_nl", "name": "Non-veg Frontier Thali", "price_inr": 420, "vegetarian": False, "hasVariants": False, "hasAddons": False},
    ]}]},
    "fd_ck_105": {"restaurant_id": "fd_ck_105", "categories": [{"name": "Mains", "items": [
        {"item_id": "ck_kung", "name": "Kung Pao Chicken", "price_inr": 365, "vegetarian": False, "hasVariants": False, "hasAddons": True},
        {"item_id": "ck_dumplings", "name": "Vegetable Dumplings (8 pcs)", "price_inr": 245, "vegetarian": True, "hasVariants": False, "hasAddons": False},
    ]}]},
    "fd_biryani_106": {"restaurant_id": "fd_biryani_106", "categories": [{"name": "Biryani", "items": [
        {"item_id": "bh_chicken", "name": "Chicken Biryani", "price_inr": 349, "vegetarian": False, "hasVariants": True, "hasAddons": True},
        {"item_id": "bh_mutton", "name": "Mutton Biryani", "price_inr": 449, "vegetarian": False, "hasVariants": True, "hasAddons": True},
    ]}]},
    "fd_paradise_107": {"restaurant_id": "fd_paradise_107", "categories": [{"name": "Signature", "items": [
        {"item_id": "pb_biryani", "name": "Paradise Special Biryani", "price_inr": 399, "vegetarian": False, "hasVariants": False, "hasAddons": True},
    ]}]},
    "fd_gelato_108": {"restaurant_id": "fd_gelato_108", "categories": [{"name": "Gelato", "items": [
        {"item_id": "gv_pistachio", "name": "Pistachio Gelato (2 scoops)", "price_inr": 249, "vegetarian": True, "hasVariants": False, "hasAddons": False},
        {"item_id": "gv_dark", "name": "Dark Chocolate Gelato", "price_inr": 229, "vegetarian": True, "hasVariants": False, "hasAddons": False},
        {"item_id": "gv_mango", "name": "Alphonso Mango Sorbet", "price_inr": 219, "vegetarian": True, "hasVariants": False, "hasAddons": False},
    ]}]},
    "fd_natural_109": {"restaurant_id": "fd_natural_109", "categories": [{"name": "Ice Cream", "items": [
        {"item_id": "ni_tender", "name": "Tender Coconut", "price_inr": 180, "vegetarian": True, "hasVariants": False, "hasAddons": False},
        {"item_id": "ni_jack", "name": "Jackfruit", "price_inr": 190, "vegetarian": True, "hasVariants": False, "hasAddons": False},
    ]}]},
    "fd_punjab_110": {"restaurant_id": "fd_punjab_110", "categories": [{"name": "Curries", "items": [
        {"item_id": "pg_butter", "name": "Butter Chicken", "price_inr": 425, "vegetarian": False, "hasVariants": False, "hasAddons": True},
    ]}]},
    "fd_south_111": {"restaurant_id": "fd_south_111", "categories": [{"name": "Breakfast", "items": [
        {"item_id": "vs_masala", "name": "Masala Dosa", "price_inr": 120, "vegetarian": True, "hasVariants": False, "hasAddons": False},
        {"item_id": "vs_idli", "name": "Idli Sambar (2 pcs)", "price_inr": 80, "vegetarian": True, "hasVariants": False, "hasAddons": False},
    ]}]},
    "fd_closed_112": {"restaurant_id": "fd_closed_112", "categories": [{"name": "Mains", "items": [
        {"item_id": "mw_noodles", "name": "Hakka Noodles", "price_inr": 220, "vegetarian": True, "hasVariants": False, "hasAddons": False},
    ]}]},
}
