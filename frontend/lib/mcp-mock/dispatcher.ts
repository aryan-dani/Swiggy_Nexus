import {
  ADDRESSES,
  DINEOUT_VENUES,
  FOOD_COUPONS,
  GO_TO_ITEMS,
  MENUS,
  PRODUCTS,
  PRODUCTS_BY_SPIN,
  RESTAURANTS,
  SLOT_LABELS,
  getAddressById,
  publicAddress,
} from "./data";
import { getSession, resolveSessionId } from "./session-store";

export type McpVertical = "food" | "im" | "dineout";

const ALIASES: Record<string, string> = {
  get_restaurant_menu: "get_menu",
  update_food_cart: "add_to_cart",
  place_food_order: "place_order",
  update_cart: "add_to_cart",
  search_restaurants_dineout: "search_restaurants",
  get_available_slots: "check_availability",
};

function resolveMethod(method: string): string {
  return ALIASES[method] ?? method;
}

function err(code: string, message: string) {
  return { success: false as const, error: { code, message } };
}

function ok(data: unknown) {
  return { success: true as const, data };
}

function pickEta(r: (typeof RESTAURANTS)[0]) {
  return Math.floor((r.eta_mins_min + r.eta_mins_max) / 2);
}

function foodCartView(sid: string, addressId?: string) {
  const s = getSession(sid);
  const subtotal = s.food.lines.reduce((n, l) => n + l.line_total_inr, 0);
  const discount = s.food.coupon_discount ?? 0;
  const delivery = subtotal > 0 ? 40 : 0;
  const total = Math.max(0, subtotal + delivery - discount);
  const rest = RESTAURANTS.find((r) => r.restaurant_id === s.food.restaurant_id);
  return {
    restaurantId: s.food.restaurant_id || undefined,
    restaurantName: s.food.restaurant_name || rest?.name,
    addressId: addressId || s.food.address_id || undefined,
    items: s.food.lines,
    subtotal_inr: subtotal,
    deliveryCharge: delivery,
    total,
    availablePaymentMethods: ["COD"],
    offers: { coupon_applied: s.food.coupon_code ?? null },
  };
}

function imCartView(sid: string) {
  const s = getSession(sid);
  const subtotal = s.im.lines.reduce((n, l) => n + l.line_total_inr, 0);
  const delivery = subtotal > 0 ? 25 : 0;
  const grand = subtotal + delivery;
  return {
    cart_id: `cart_im_${sid}`,
    items: s.im.lines,
    selectedAddressId: s.im.address_id || undefined,
    subtotal_inr: subtotal,
    total: grand,
    bill: { itemTotal: subtotal, delivery, grandTotal: grand },
    availablePaymentMethods: ["COD"],
  };
}

function invokeFood(method: string, params: Record<string, unknown>) {
  const m = resolveMethod(method);
  const sid = resolveSessionId(params);

  if (m === "get_addresses") {
    return ok({ addresses: ADDRESSES.map(publicAddress) });
  }
  if (m === "search_restaurants") {
    const addressId = String(params.addressId ?? params.address_id ?? "");
    if (!addressId) return err("VALIDATION", "addressId is required");
    const addr = getAddressById(addressId);
    if (!addr) return err("NOT_FOUND", `Unknown addressId: ${addressId}`);
    const q = String(params.query ?? params.q ?? "").toLowerCase();
    let rows = [...RESTAURANTS];
    if (q) {
      rows = rows.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          r.cuisines.some((c) => c.toLowerCase().includes(q))
      );
    }
    return ok({
      addressId,
      area: addr.area,
      restaurants: rows.map((r) => ({
        restaurant_id: r.restaurant_id,
        name: r.name,
        rating: r.rating,
        eta_mins: pickEta(r),
        distanceKm: r.distance_km,
        availabilityStatus: r.availability_status,
        cuisines: r.cuisines,
        tag: r.tag,
      })),
      nextOffset: rows.length,
    });
  }
  if (m === "get_menu") {
    const rid = String(params.restaurantId ?? params.restaurant_id ?? "");
    const menu = MENUS[rid];
    if (!menu) return err("NOT_FOUND", `No menu for ${rid}`);
    return ok(menu);
  }
  if (m === "add_to_cart") {
    const rid = String(params.restaurantId ?? params.restaurant_id ?? "");
    const addressId = String(params.addressId ?? params.address_id ?? "");
    const raw = (params.lines ?? params.items ?? params.cartItems) as unknown[];
    if (!rid || !Array.isArray(raw) || !raw.length) {
      return err("VALIDATION", "restaurantId and lines required");
    }
    const s = getSession(sid);
    if (s.food.restaurant_id && s.food.restaurant_id !== rid && s.food.lines.length) {
      s.food = { restaurant_id: "", restaurant_name: "", address_id: "", lines: [] };
    }
    const menu = MENUS[rid];
    const prices: Record<string, { name: string; price: number }> = {};
    for (const cat of menu?.categories ?? []) {
      for (const it of cat.items) {
        prices[it.item_id] = { name: it.name, price: it.price_inr };
      }
    }
    const rest = RESTAURANTS.find((r) => r.restaurant_id === rid);
    s.food.restaurant_id = rid;
    s.food.restaurant_name = rest?.name ?? rid;
    s.food.address_id = addressId;
    s.food.lines = raw.map((row) => {
      const r = row as Record<string, unknown>;
      const itemId = String(r.item_id ?? r.itemId ?? "");
      const qty = Number(r.qty ?? r.quantity ?? 1);
      const p = prices[itemId]?.price ?? 199;
      return {
        item_id: itemId,
        name: prices[itemId]?.name ?? itemId,
        qty,
        unit_price_inr: p,
        line_total_inr: p * qty,
      };
    });
    return ok({ ...foodCartView(sid, addressId), message: "Cart updated" });
  }
  if (m === "get_food_cart") {
    return ok(foodCartView(sid, String(params.addressId ?? params.address_id ?? "")));
  }
  if (m === "flush_food_cart") {
    getSession(sid).food = { restaurant_id: "", restaurant_name: "", address_id: "", lines: [] };
    return ok({ cleared: true });
  }
  if (m === "fetch_food_coupons") {
    return ok({ coupons: FOOD_COUPONS });
  }
  if (m === "apply_food_coupon") {
    const code = String(params.code ?? params.couponCode ?? "");
    const coupon = FOOD_COUPONS.find((c) => c.code === code);
    if (!coupon) return err("NOT_FOUND", `Unknown coupon ${code}`);
    const s = getSession(sid);
    s.food.coupon_code = code;
    s.food.coupon_discount = coupon.discount_inr;
    return ok({ code, discount_inr: coupon.discount_inr });
  }
  if (m === "place_order") {
    const view = foodCartView(sid);
    if (!view.items?.length) return err("VALIDATION", "Cart is empty");
    if ((view.total ?? 0) >= 1000) return err("LIMIT", "Mock cap: orders above ₹999 need app handoff");
    const orderId = `fd-ord-${Date.now()}`;
    const s = getSession(sid);
    const order = { orderId, status: "ACTIVE", ...view, eta_mins: 32, paymentMethod: "COD" };
    s.food_orders.push(order);
    s.last_food_order_id = orderId;
    s.food = { restaurant_id: "", restaurant_name: "", address_id: "", lines: [] };
    return ok({ ...order, order_id: orderId, orderId, message: "Order placed (mock)" });
  }
  if (m === "get_food_orders") {
    return ok({ orders: getSession(sid).food_orders });
  }
  if (m === "get_food_order_details") {
    const oid = String(params.orderId ?? params.order_id ?? "");
    const o = getSession(sid).food_orders.find((x) => x.orderId === oid);
    if (!o) return err("NOT_FOUND", "Order not found");
    return ok(o);
  }
  if (m === "track_food_order") {
    const oid = String(params.orderId ?? params.order_id ?? getSession(sid).last_food_order_id ?? "");
    return ok({ orderId: oid, status: "OUT_FOR_DELIVERY", eta_mins: 18, deliveryTimeSpoken: "about 18 minutes" });
  }
  if (m === "report_error") {
    return ok({ reportLink: "https://example.com/report", summary: "Mock error report filed" });
  }
  return err("UNKNOWN", `Unknown food method: ${method}`);
}

function invokeIm(method: string, params: Record<string, unknown>) {
  const m = resolveMethod(method);
  const sid = resolveSessionId(params);

  if (m === "get_addresses") return invokeFood("get_addresses", params);
  if (m === "search_products") {
    const q = String(params.query ?? params.q ?? "").toLowerCase();
    let rows = PRODUCTS;
    if (q) rows = rows.filter((p) => p.name.toLowerCase().includes(q) || p.category.includes(q));
    return ok({
      products: rows.map((p) => ({ product_id: p.product_id, name: p.name, category: p.category, variants: p.variants })),
      query: q || null,
      addressId: params.addressId,
    });
  }
  if (m === "your_go_to_items") {
    const party = Boolean(params.party ?? params.partyMode);
    const items = party
      ? [...GO_TO_ITEMS, { product_id: "im_plate_01", name: "Party plates", spinId: "spin_plate_50", price_inr: 189, category: "party" }]
      : GO_TO_ITEMS;
    return ok({
      products: items.map((g) => ({
        product_id: g.product_id,
        name: g.name,
        variants: [{ spinId: g.spinId, label: "default", price_inr: g.price_inr, inStock: true }],
      })),
      addressId: params.addressId ?? "addr_kp_001",
    });
  }
  if (m === "add_to_cart") {
    const addr = String(params.selectedAddressId ?? params.addressId ?? "");
    const raw = (params.items ?? params.lines) as unknown[];
    if (!Array.isArray(raw) || !raw.length) return err("VALIDATION", "items required");
    const s = getSession(sid);
    if (s.im.address_id && addr && s.im.address_id !== addr && s.im.lines.length) {
      s.im = { address_id: "", lines: [] };
    }
    s.im.address_id = addr;
    s.im.lines = raw.map((row) => {
      const r = row as Record<string, unknown>;
      const spinId = String(r.spinId ?? r.spin_id ?? "");
      const qty = Number(r.qty ?? r.quantity ?? 1);
      const sku = PRODUCTS_BY_SPIN[spinId];
      const price = sku?.variants[0]?.price_inr ?? 99;
      return {
        spinId,
        product_id: sku?.product_id ?? spinId,
        name: sku?.name ?? spinId,
        qty,
        unit_price_inr: price,
        line_total_inr: price * qty,
      };
    });
    return ok(imCartView(sid));
  }
  if (m === "get_cart") return ok(imCartView(sid));
  if (m === "clear_cart") {
    getSession(sid).im = { address_id: "", lines: [] };
    return ok({ cleared: true });
  }
  if (m === "checkout") {
    const view = imCartView(sid);
    if (!view.items?.length) return err("VALIDATION", "Cart is empty");
    if ((view.subtotal_inr ?? 0) < 99) return err("MIN_ORDER", "Minimum order ₹99");
    const orderId = `im-ord-${Date.now()}`;
    const s = getSession(sid);
    const order = { orderId, status: "ACTIVE", ...view, eta_mins: 25 };
    s.im_orders.push(order);
    s.last_im_order_id = orderId;
    s.im = { address_id: "", lines: [] };
    return ok({ ...order, order_id: orderId, orderId, message: "Checkout complete (mock)" });
  }
  if (m === "get_orders") return ok({ orders: getSession(sid).im_orders });
  if (m === "get_order_details") {
    const oid = String(params.orderId ?? params.order_id ?? "");
    const o = getSession(sid).im_orders.find((x) => x.orderId === oid);
    if (!o) return err("NOT_FOUND", "Order not found");
    return ok(o);
  }
  if (m === "track_order") {
    const oid = String(params.orderId ?? params.order_id ?? getSession(sid).last_im_order_id ?? "");
    return ok({ orderId: oid, status: "OUT_FOR_DELIVERY", eta_mins: 22 });
  }
  if (m === "create_address") {
    return ok({ addressId: `addr_new_${Date.now()}`, message: "Address created (mock)" });
  }
  if (m === "delete_address") {
    return ok({ deleted: params.addressId });
  }
  if (m === "report_error") {
    return ok({ reportLink: "https://example.com/report", summary: "Mock error report filed" });
  }
  return err("UNKNOWN", `Unknown im method: ${method}`);
}

function invokeDineout(method: string, params: Record<string, unknown>) {
  const m = resolveMethod(method);

  if (m === "get_saved_locations") {
    return ok({
      locations: ADDRESSES.map((a) => ({
        addressId: a.addressId,
        label: a.label,
        lat: a._latitude,
        lng: a._longitude,
        latitude: a._latitude,
        longitude: a._longitude,
      })),
    });
  }
  if (m === "search_restaurants") {
    const q = String(params.query ?? params.q ?? "").toLowerCase();
    let rows = DINEOUT_VENUES.filter((v) => v.availability === "AVAILABLE");
    if (q) {
      rows = rows.filter(
        (v) =>
          v.name.toLowerCase().includes(q) ||
          v.cuisines.some((c) => c.toLowerCase().includes(q))
      );
    }
    return ok({
      restaurants: rows.map((v) => ({
        restaurant_id: v.restaurant_id,
        name: v.name,
        rating: v.rating,
        cuisines: v.cuisines,
        area: v.area,
        costForTwo: v.costForTwo,
        availability: v.availability,
        booking_type: "TABLE",
        latitude: v._lat,
        longitude: v._lng,
      })),
    });
  }
  if (m === "check_availability") {
    const rid = String(params.restaurantId ?? params.restaurant_id ?? "");
    const guests = Number(params.guestCount ?? params.partySize ?? params.party_size ?? 2);
    const venue = DINEOUT_VENUES.find((v) => v.restaurant_id === rid);
    if (!venue) return err("NOT_FOUND", "Venue not found");
    if (venue.availability === "UNAVAILABLE") return err("UNAVAILABLE", "Walk-in only");
    const slots = SLOT_LABELS.map((label, i) => ({
      slotId: 4200 + i,
      label,
      reservationTime: Math.floor(Date.now() / 1000) + (i + 1) * 3600,
      guestCount: guests,
      band: "dinner",
      deals: [{ slotId: 4200 + i, itemId: `${rid}-ticket_${4200 + i}`, isFree: true, bookingPrice: 0, title: "Free table reservation" }],
    }));
    return ok({ restaurant_id: rid, name: venue.name, party_size: guests, guestCount: guests, available: true, slots });
  }
  if (m === "book_table") {
    const rid = String(params.restaurantId ?? params.restaurant_id ?? "");
    const venue = DINEOUT_VENUES.find((v) => v.restaurant_id === rid);
    const bookingId = `bk-${Date.now()}`;
    const booking = {
      booking_id: bookingId,
      bookingId,
      restaurant_id: rid,
      venue_name: venue?.name ?? "Restaurant",
      guests: Number(params.partySize ?? params.guestCount ?? 2),
      slot: params.slot ?? "20:00",
      slotId: params.slotId,
      itemId: params.itemId,
      status: "CONFIRMED",
      confirmation_message: `Table confirmed at ${venue?.name ?? "venue"} (mock).`,
    };
    const sid = resolveSessionId(params);
    const s = getSession(sid);
    s.bookings.push(booking);
    s.last_booking_id = bookingId;
    return ok(booking);
  }
  if (m === "get_booking_status") {
    const bid = String(params.bookingId ?? params.booking_id ?? "");
    const sid = resolveSessionId(params);
    const b = getSession(sid).bookings.find((x) => x.bookingId === bid);
    if (!b) return err("NOT_FOUND", "Booking not found");
    return ok(b);
  }
  if (m === "create_cart") {
    return ok({ cartId: `do-cart-${Date.now()}`, message: "Dineout cart stub" });
  }
  if (m === "report_error") {
    return ok({ reportLink: "https://example.com/report", summary: "Mock error report filed" });
  }
  return err("UNKNOWN", `Unknown dineout method: ${method}`);
}

export function invokeMockMcp(vertical: McpVertical, method: string, params: Record<string, unknown> = {}) {
  if (vertical === "food") return invokeFood(method, params);
  if (vertical === "im") return invokeIm(method, params);
  return invokeDineout(method, params);
}

export const ALL_MCP_METHODS: Record<McpVertical, string[]> = {
  food: ["get_addresses", "search_restaurants", "get_menu", "add_to_cart", "get_food_cart", "flush_food_cart", "fetch_food_coupons", "apply_food_coupon", "place_order", "get_food_orders", "get_food_order_details", "track_food_order", "report_error"],
  im: ["get_addresses", "search_products", "your_go_to_items", "add_to_cart", "get_cart", "clear_cart", "checkout", "get_orders", "get_order_details", "track_order", "create_address", "delete_address", "report_error"],
  dineout: ["get_saved_locations", "search_restaurants", "check_availability", "book_table", "get_booking_status", "create_cart", "report_error"],
};
