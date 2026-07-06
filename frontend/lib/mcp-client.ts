import { getApiBase } from "@/lib/api";
import type { McpVertical } from "@/lib/mcp-mock/dispatcher";

export type McpResult =
  | { success: true; data: unknown }
  | { success: false; error: { code: string; message: string } };

const TOOL_LOG_KEY = "nexus-mcp-tool-log";

/** Map streamed executor method names → canonical MCP tool ids for coverage meter. */
const STREAM_METHOD_ALIASES: Record<string, [McpVertical, string]> = {
  dineout_get_saved_locations: ["dineout", "get_saved_locations"],
  dineout_search_restaurants_dineout: ["dineout", "search_restaurants"],
  dineout_search_restaurants: ["dineout", "search_restaurants"],
  dineout_get_available_slots: ["dineout", "check_availability"],
  dineout_check_availability: ["dineout", "check_availability"],
  dineout_book_table: ["dineout", "book_table"],
  food_get_addresses: ["food", "get_addresses"],
  food_search_restaurants: ["food", "search_restaurants"],
  food_get_restaurant_menu: ["food", "get_menu"],
  food_get_menu: ["food", "get_menu"],
  food_update_food_cart: ["food", "add_to_cart"],
  food_add_to_cart: ["food", "add_to_cart"],
  food_get_food_cart: ["food", "get_food_cart"],
  food_fetch_food_coupons: ["food", "fetch_food_coupons"],
  food_apply_food_coupon: ["food", "apply_food_coupon"],
  food_place_food_order: ["food", "place_order"],
  food_place_order: ["food", "place_order"],
  food_track_food_order: ["food", "track_food_order"],
  im_search_products: ["im", "search_products"],
  instamart_get_inventory: ["im", "search_products"],
  im_update_cart: ["im", "add_to_cart"],
  im_add_to_cart: ["im", "add_to_cart"],
  im_get_cart: ["im", "get_cart"],
  im_checkout: ["im", "checkout"],
  im_your_go_to_items: ["im", "your_go_to_items"],
  your_go_to_items: ["im", "your_go_to_items"],
  get_addresses: ["food", "get_addresses"],
  get_saved_locations: ["dineout", "get_saved_locations"],
  search_restaurants: ["food", "search_restaurants"],
  book_table: ["dineout", "book_table"],
  checkout: ["im", "checkout"],
  place_order: ["food", "place_order"],
};

function emitCoverageUpdate() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("nexus-mcp-call"));
  }
}

function storeToolKey(vertical: McpVertical, method: string) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.sessionStorage.getItem(TOOL_LOG_KEY);
    const set = new Set<string>(raw ? JSON.parse(raw) : []);
    set.add(`${vertical}:${method}`);
    window.sessionStorage.setItem(TOOL_LOG_KEY, JSON.stringify([...set]));
    emitCoverageUpdate();
  } catch {
    /* ignore */
  }
}

/** Record tools invoked via direct MCP proxy (`callMcp`). */
export function recordToolCall(vertical: McpVertical, method: string) {
  storeToolKey(vertical, method);
}

/** Record tools from chat SSE `tool` events (Planner → Executor stream). */
export function recordToolFromStream(payload: Record<string, unknown>) {
  const rawMethod = String(payload.method ?? "").trim();
  if (!rawMethod) {
    const path = String(payload.server_path ?? "");
    if (path.includes("dineout")) return;
    return;
  }

  const alias = STREAM_METHOD_ALIASES[rawMethod];
  if (alias) {
    storeToolKey(alias[0], alias[1]);
    return;
  }

  const m = rawMethod.toLowerCase();
  if (m.startsWith("dineout_")) {
    storeToolKey("dineout", m.replace(/^dineout_/, ""));
  } else if (m.startsWith("food_")) {
    storeToolKey("food", m.replace(/^food_/, ""));
  } else if (m.startsWith("im_") || m.startsWith("instamart_")) {
    storeToolKey("im", m.replace(/^(im_|instamart_)/, ""));
  }
}

export function getToolCoverage(): { used: number; total: number; methods: string[] } {
  const total = 33;
  if (typeof window === "undefined") return { used: 0, total, methods: [] };
  try {
    const raw = window.sessionStorage.getItem(TOOL_LOG_KEY);
    const methods = raw ? (JSON.parse(raw) as string[]) : [];
    return { used: methods.length, total, methods };
  } catch {
    return { used: 0, total, methods: [] };
  }
}

export function clearToolCoverage() {
  if (typeof window !== "undefined") window.sessionStorage.removeItem(TOOL_LOG_KEY);
}

export function mcpErrorMessage(res: McpResult, fallback = "Request failed"): string {
  if (res.success) return fallback;
  return res.error?.message ?? fallback;
}

export async function callMcp(
  vertical: McpVertical,
  method: string,
  params: Record<string, unknown> = {},
  requestId?: string
): Promise<McpResult> {
  const body = {
    method,
    params: { ...params, ...(requestId ? { requestId } : {}) },
  };

  const base = getApiBase();
  const url = base
    ? `${base}/${vertical === "im" ? "im" : vertical}`
    : `/api/mcp/${vertical}`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const json = (await res.json()) as McpResult;
  recordToolCall(vertical, method);
  return json;
}
