"""Instamart grocery catalog with spinId variants."""

from __future__ import annotations

_RAW: list[dict] = [
    ("im_milk_f", "Amul Taaza Milk", "Dairy", 28, [("spin_milk_500", "500ml", 28), ("spin_milk_1l", "1L", 52)]),
    ("im_bread", "Britannia Wheat Bread", "Bakery", 45, [("spin_bread", "400g loaf", 45)]),
    ("im_eggs", "Farm Fresh Eggs", "Dairy", 54, [("spin_eggs_6", "6 pcs", 54), ("spin_eggs_12", "12 pcs", 98)]),
    ("im_banana", "Robusta Bananas", "Fruits & Veggies", 48, [("spin_banana", "~6 pcs", 48)]),
    ("im_maggi", "Maggi 2-Minute Masala", "Staples", 14, [("spin_maggi", "70g", 14), ("spin_maggi_4p", "4-pack", 52)]),
    ("im_butter", "Amul Salted Butter", "Dairy", 55, [("spin_butter", "100g", 55)]),
    ("im_chips", "Lay's Classic Salted", "Snacks", 20, [("spin_chips_lays", "52g", 20), ("spin_chips_lays_f", "150g family", 55)]),
    ("im_popcorn", "Act II Butter Popcorn", "Snacks", 35, [("spin_popcorn", "microwave 3-pack", 35)]),
    ("im_cola", "Coca-Cola", "Beverages", 40, [("spin_cola_500", "500ml", 40), ("spin_cola_2l", "2L", 90)]),
    ("im_water", "Bisleri Water", "Beverages", 20, [("spin_water_1l", "1L", 20), ("spin_water_2l", "2L", 35)]),
    ("im_americano", "Nescafe Gold Instant", "Beverages", 449, [("spin_americano", "50g jar", 449)]),
    ("im_protein", "Yoga Bar Protein Bar", "Snacks", 99, [("spin_protein_bar", "70g", 99)]),
    ("im_plates", "Disposable Paper Plates", "Party", 89, [("spin_paper_plates", "50 pcs", 89)]),
    ("im_napkins", "Soft Napkins Pack", "Party", 65, [("spin_napkins", "100 pcs", 65)]),
    ("im_cups", "Paper Cups", "Party", 75, [("spin_paper_cups", "50 pcs", 75)]),
    ("im_dark_choc", "Amul Dark Chocolate", "Snacks", 120, [("spin_dark_choc", "150g", 120)]),
    ("im_tea", "Tetley Green Tea", "Beverages", 180, [("spin_tea_green", "25 bags", 180)]),
    ("im_energy", "Red Bull Energy Drink", "Beverages", 125, [("spin_energy_drink", "250ml", 125)]),
    ("im_noodles", "Ching's Hakka Noodles", "Staples", 45, [("spin_instant_noodles", "150g", 45)]),
    ("im_cheese", "Amul Cheese Cubes", "Dairy", 125, [("spin_cheese_cubes", "200g", 125)]),
    ("im_wine_snack", "Pringles Original", "Snacks", 110, [("spin_wine_snack", "107g", 110)]),
    ("im_trail", "Happilo Trail Mix", "Snacks", 199, [("spin_trail_mix", "200g", 199)]),
    ("im_juice", "Real Fruit Juice", "Beverages", 110, [("spin_juice_1l", "1L orange", 110)]),
    ("im_onion", "Onion", "Fruits & Veggies", 35, [("spin_onion_1kg", "1 kg", 35)]),
    ("im_tomato", "Tomato", "Fruits & Veggies", 42, [("spin_tomato_1kg", "1 kg", 42)]),
    ("im_potato", "Potato", "Fruits & Veggies", 38, [("spin_potato_1kg", "1 kg", 38)]),
    ("im_paneer", "Amul Paneer", "Dairy", 90, [("spin_paneer_200", "200g", 90)]),
    ("im_curd", "Mother Dairy Curd", "Dairy", 35, [("spin_curd_400", "400g", 35)]),
    ("im_rice", "India Gate Basmati", "Staples", 220, [("spin_rice_1kg", "1 kg", 220)]),
    ("im_dal", "Toor Dal", "Staples", 145, [("spin_dal_1kg", "1 kg", 145)]),
    ("im_oil", "Fortune Sunflower Oil", "Staples", 185, [("spin_oil_1l", "1L", 185)]),
    ("im_salt", "Tata Salt", "Staples", 28, [("spin_salt_1kg", "1 kg", 28)]),
    ("im_sugar", "Madhur Sugar", "Staples", 52, [("spin_sugar_1kg", "1 kg", 52)]),
    ("im_biscuit", "Parle-G Gold", "Snacks", 30, [("spin_biscuit", "600g", 30)]),
    ("im_icecream", "Kwality Walls Tub", "Frozen", 180, [("spin_icecream_vanilla", "700ml", 180)]),
    ("im_frozen_peas", "Safal Green Peas", "Frozen", 65, [("spin_peas_500", "500g", 65)]),
    ("im_handwash", "Dettol Handwash", "Personal Care", 99, [("spin_handwash", "200ml", 99)]),
    ("im_tissue", "Kleenex Tissues", "Personal Care", 85, [("spin_tissue", "100 pulls", 85)]),
    ("im_detergent", "Surf Excel Matic", "Home", 220, [("spin_detergent_1kg", "1 kg", 220)]),
    ("im_matcha", "Society Tea Premium", "Beverages", 165, [("spin_matcha_tea", "250g", 165)]),
    ("im_honey", "Dabur Honey", "Staples", 199, [("spin_honey_250", "250g", 199)]),
    ("im_garlic", "Garlic", "Fruits & Veggies", 55, [("spin_garlic_250", "250g", 55)]),
    ("im_ginger", "Ginger", "Fruits & Veggies", 40, [("spin_ginger_200", "200g", 40)]),
    ("im_coriander", "Coriander Bunch", "Fruits & Veggies", 15, [("spin_coriander", "1 bunch", 15)]),
]


def _build() -> tuple[list[dict], dict[str, dict]]:
    products: list[dict] = []
    by_spin: dict[str, dict] = {}
    for pid, name, cat, base, variants in _RAW:
        var_list = [
            {"spinId": sid, "label": lbl, "price_inr": price, "inStock": True}
            for sid, lbl, price in variants
        ]
        p = {
            "product_id": pid,
            "name": name,
            "category": cat,
            "price_inr": base,
            "unit": variants[0][1],
            "variants": var_list,
        }
        products.append(p)
        for v in var_list:
            by_spin[v["spinId"]] = {**p, "spinId": v["spinId"], "variant_label": v["label"], "price_inr": v["price_inr"]}
    return products, by_spin


PRODUCTS, PRODUCTS_BY_SPIN = _build()

# Legacy flat list for old handlers
LEGACY_PRODUCTS = [
    {"product_id": p["product_id"], "name": p["name"], "category": p["category"], "price_inr": p["price_inr"], "unit": p["unit"]}
    for p in PRODUCTS
]
