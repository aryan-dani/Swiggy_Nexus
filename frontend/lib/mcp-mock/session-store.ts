type FoodCart = {
  restaurant_id: string;
  restaurant_name: string;
  address_id: string;
  lines: { item_id: string; name: string; qty: number; unit_price_inr: number; line_total_inr: number }[];
  coupon_code?: string;
  coupon_discount?: number;
};

type ImCart = {
  address_id: string;
  lines: { spinId: string; product_id: string; name: string; qty: number; unit_price_inr: number; line_total_inr: number }[];
};

type Session = {
  food: FoodCart;
  im: ImCart;
  food_orders: Record<string, unknown>[];
  im_orders: Record<string, unknown>[];
  bookings: Record<string, unknown>[];
  last_food_order_id?: string;
  last_im_order_id?: string;
  last_booking_id?: string;
};

const sessions = new Map<string, Session>();

function emptySession(): Session {
  return {
    food: { restaurant_id: "", restaurant_name: "", address_id: "", lines: [] },
    im: { address_id: "", lines: [] },
    food_orders: [],
    im_orders: [],
    bookings: [],
  };
}

export function getSession(sid: string): Session {
  if (!sessions.has(sid)) sessions.set(sid, emptySession());
  return sessions.get(sid)!;
}

export function resolveSessionId(params: Record<string, unknown>): string {
  const raw = params.requestId ?? params.request_id ?? params.sessionId ?? params.session_id;
  return typeof raw === "string" && raw.trim() ? raw.trim() : "default-session";
}
