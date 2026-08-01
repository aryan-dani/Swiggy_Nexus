/** Pune addresses for Next.js MCP mock (mirrors mock_data/pune_addresses.py). */
export const ADDRESSES = [
  {
    addressId: "addr_kp_001",
    label: "Home",
    line1: "Rosary School Road, Near German Bakery",
    area: "Koregaon Park",
    city: "Pune",
    pin: "411001",
    fullAddress: "Rosary School Road, Near German Bakery, Koregaon Park, Pune 411001",
    addressCategory: "HOME",
    _latitude: 18.5362,
    _longitude: 73.8958,
  },
  {
    addressId: "addr_baner_002",
    label: "Work",
    line1: "Baner High Street, Opp. HDFC Bank",
    area: "Baner",
    city: "Pune",
    pin: "411045",
    fullAddress: "Baner High Street, Opp. HDFC Bank, Baner, Pune 411045",
    addressCategory: "WORK",
    _latitude: 18.559,
    _longitude: 73.7794,
  },
  {
    addressId: "addr_fcr_003",
    label: "PG",
    line1: "Camp, MG Road junction",
    area: "Pune Cantonment",
    city: "Pune",
    pin: "411001",
    fullAddress: "Camp, MG Road junction, Pune Cantonment, Pune 411001",
    addressCategory: "OTHER",
    _latitude: 18.5244,
    _longitude: 73.8772,
  },
] as const;

export function publicAddress(a: (typeof ADDRESSES)[number]) {
  const { _latitude: _lat, _longitude: _lng, ...rest } = a as Record<string, unknown>;
  return rest;
}

export function getAddressById(id: string) {
  return ADDRESSES.find((a) => a.addressId === id);
}

export const RESTAURANTS = [
  { restaurant_id: "fd_dom_101", name: "Domino's Pizza", rating: 4.2, cuisines: ["Pizza"], tag: "30 min delivery", price_for_two_inr: 500, distance_km: 2.1, availability_status: "OPEN", eta_mins_min: 25, eta_mins_max: 38 },
  { restaurant_id: "fd_gelato_108", name: "Gelato Vivo", rating: 4.6, cuisines: ["Desserts"], tag: "Artisan gelato", price_for_two_inr: 400, distance_km: 1.5, availability_status: "OPEN", eta_mins_min: 22, eta_mins_max: 35 },
  { restaurant_id: "fd_biryani_106", name: "Biryani House", rating: 4.5, cuisines: ["Biryani"], tag: "Hyderabadi dum", price_for_two_inr: 550, distance_km: 2.8, availability_status: "OPEN", eta_mins_min: 30, eta_mins_max: 42 },
  { restaurant_id: "fd_misal_103", name: "Shrimant Misal House", rating: 4.5, cuisines: ["Maharashtrian"], tag: "Local favourite", price_for_two_inr: 260, distance_km: 1.8, availability_status: "OPEN", eta_mins_min: 28, eta_mins_max: 42 },
];

export const MENUS: Record<string, { restaurant_id: string; categories: { name: string; items: { item_id: string; name: string; price_inr: number; vegetarian: boolean }[] }[] }> = {
  fd_dom_101: { restaurant_id: "fd_dom_101", categories: [{ name: "Popular", items: [
    { item_id: "dom_mar_med", name: "Margherita Medium", price_inr: 389, vegetarian: true },
    { item_id: "dom_pep_med", name: "Pepperoni Medium", price_inr: 529, vegetarian: false },
  ]}]},
  fd_gelato_108: { restaurant_id: "fd_gelato_108", categories: [{ name: "Gelato", items: [
    { item_id: "gv_pistachio", name: "Pistachio Gelato (2 scoops)", price_inr: 249, vegetarian: true },
    { item_id: "gv_dark", name: "Dark Chocolate Gelato", price_inr: 229, vegetarian: true },
  ]}]},
  fd_biryani_106: { restaurant_id: "fd_biryani_106", categories: [{ name: "Biryani", items: [
    { item_id: "bh_paneer", name: "Paneer Biryani", price_inr: 299, vegetarian: true },
    { item_id: "bh_chicken", name: "Chicken Biryani", price_inr: 349, vegetarian: false },
    { item_id: "bh_mutton", name: "Mutton Biryani", price_inr: 449, vegetarian: false },
  ]}]},
};

export const FOOD_COUPONS = [
  { code: "WELCOME50", description: "₹50 off on first order", requiresOnlinePayment: false, discount_inr: 50 },
  { code: "FLAT100", description: "₹100 off above ₹499", requiresOnlinePayment: false, discount_inr: 100 },
];

export const PRODUCTS = [
  { product_id: "im_plate_01", name: "Disposable plates (50 pack)", category: "party", variants: [{ spinId: "spin_plate_50", label: "50 pack", price_inr: 189, inStock: true }] },
  { product_id: "im_napkin_02", name: "Party napkins", category: "party", variants: [{ spinId: "spin_napkin_100", label: "100 pcs", price_inr: 99, inStock: true }] },
  { product_id: "im_chips_03", name: "Lays Classic", category: "snacks", variants: [{ spinId: "spin_lays_52", label: "52g", price_inr: 20, inStock: true }] },
  { product_id: "im_choco_04", name: "Dark chocolate bar", category: "snacks", variants: [{ spinId: "spin_choco_70", label: "70g", price_inr: 95, inStock: true }] },
  { product_id: "im_coffee_05", name: "Cold brew Americano", category: "beverages", variants: [{ spinId: "spin_cold_brew", label: "250ml", price_inr: 189, inStock: true }] },
];

export const PRODUCTS_BY_SPIN: Record<string, typeof PRODUCTS[0]> = {};
for (const p of PRODUCTS) {
  for (const v of p.variants) PRODUCTS_BY_SPIN[v.spinId] = p;
}

export const DINEOUT_VENUES = [
  { restaurant_id: "do_italian_804", name: "Spesso · Koregaon Park", rating: 4.5, cuisines: ["Italian"], area: "Koregaon Park", costForTwo: 3200, availability: "AVAILABLE", _lat: 18.5375, _lng: 73.891 },
  { restaurant_id: "do_malaka_802", name: "Malaka Spice", rating: 4.6, cuisines: ["Asian"], area: "Koregaon Park", costForTwo: 2400, availability: "AVAILABLE", _lat: 18.5362, _lng: 73.8958 },
  { restaurant_id: "do_social_805", name: "Social · FC Road", rating: 4.3, cuisines: ["Continental"], area: "FC Road", costForTwo: 1500, availability: "AVAILABLE", _lat: 18.5244, _lng: 73.841 },
];

export const SLOT_LABELS = ["18:00", "18:30", "19:00", "19:30", "20:00", "20:30"];

export const GO_TO_ITEMS = [
  { product_id: "im_choco_04", name: "Dark chocolate bar", spinId: "spin_choco_70", price_inr: 95, category: "comfort" },
  { product_id: "im_coffee_05", name: "Cold brew Americano", spinId: "spin_cold_brew", price_inr: 189, category: "comfort" },
];
