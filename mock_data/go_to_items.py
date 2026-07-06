"""Per-address frequently ordered Instamart SKUs (your_go_to_items mock)."""

from mock_data.instamart_catalog import PRODUCTS_BY_SPIN

GO_TO_BY_ADDRESS: dict[str, list[str]] = {
    "addr_kp_001": [
        "spin_milk_500",
        "spin_chips_lays",
        "spin_dark_choc",
        "spin_tea_green",
    ],
    "addr_baner_002": ["spin_americano", "spin_protein_bar", "spin_water_1l"],
    "addr_fcr_003": ["spin_maggi", "spin_eggs_6", "spin_bread"],
    "addr_kalyani_004": ["spin_wine_snack", "spin_cheese_cubes"],
    "addr_hinj_005": ["spin_energy_drink", "spin_instant_noodles"],
    "addr_viman_006": ["spin_trail_mix", "spin_juice_1l"],
}

PARTY_GO_TO = [
    "spin_chips_lays",
    "spin_popcorn",
    "spin_cola_2l",
    "spin_paper_plates",
    "spin_napkins",
]


def items_for_address(address_id: str, party: bool = False) -> list[dict]:
    spins = PARTY_GO_TO if party else GO_TO_BY_ADDRESS.get(address_id, GO_TO_BY_ADDRESS["addr_kp_001"])
    out: list[dict] = []
    for spin in spins:
        p = PRODUCTS_BY_SPIN.get(spin)
        if p:
            out.append(p)
    return out
