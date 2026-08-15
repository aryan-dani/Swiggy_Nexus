import type { FeedItem, StreamEvent } from "@/lib/api";

type Vertical = "food" | "instamart" | "dineout" | "chrono";

type NormalizedCtx = {
  deepWork: boolean;
  rainPune: boolean;
  watchParty: boolean;
  moodScore: number;
  scenario: string;
  partySize: number;
  budgetInr: number;
  city: string;
  recipeHint: string;
  eventTitle: string;
  cuisineHint: string;
  dessertQuery: string;
  imQuery: string;
};

function normalizeContext(raw: Record<string, unknown> | undefined): NormalizedCtx {
  const sig = (raw?.signals as Record<string, unknown> | undefined) ?? {};
  const event = (raw?.event as Record<string, unknown> | undefined) ?? {};
  const guestsFromEvent =
    typeof event.guests === "number" ? event.guests : undefined;
  return {
    deepWork: Boolean(sig.deepWorkBlock),
    rainPune: Boolean(sig.rainInPune),
    watchParty: Boolean(sig.watchParty),
    moodScore: typeof sig.moodScore === "number" ? sig.moodScore : 0.35,
    scenario: typeof raw?.scenario === "string" ? raw.scenario : "",
    partySize:
      guestsFromEvent ??
      (typeof raw?.partySize === "number" ? raw.partySize : 4),
    budgetInr: typeof raw?.budgetInr === "number" ? raw.budgetInr : 800,
    city: typeof raw?.city === "string" ? raw.city : "Pune",
    recipeHint:
      typeof raw?.recipeHint === "string"
        ? raw.recipeHint
        : "Paneer tikka masala",
    eventTitle:
      typeof event.title === "string" ? event.title : "Housewarming Saturday",
    cuisineHint:
      typeof event.cuisineHint === "string" ? event.cuisineHint : "italian",
    dessertQuery:
      typeof event.dessertQuery === "string" ? event.dessertQuery : "gelato",
    imQuery:
      typeof event.imQuery === "string"
        ? event.imQuery
        : "party plates napkins drinks",
  };
}

function inferCuisine(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("italian")) return "italian";
  if (m.includes("chinese")) return "chinese";
  if (m.includes("south indian") || m.includes("dosa")) return "south indian";
  if (m.includes("biryani")) return "biryani";
  return "comfort food";
}

function inferInstamartCategory(message: string, ctx: NormalizedCtx): string {
  const m = message.toLowerCase();
  if (m.includes("snack") || m.includes("chips") || m.includes("protein"))
    return "snacks";
  if (
    m.includes("drink") ||
    m.includes("beverage") ||
    m.includes("coffee") ||
    m.includes("americano")
  )
    return "beverages";
  if (ctx.scenario === "flowstate") return "beverages";
  if (ctx.scenario === "zerowaste") return "groceries";
  return "groceries";
}

function isChronoPlanMessage(message: string): boolean {
  const m = (message || "").toLowerCase();
  return [
    "plan my evening",
    "plan my housewarming",
    "plan a festive",
    "plan a team dinner",
    "plan a date-night",
    "plan a date night",
    "chrono host",
    "dinner out and dessert",
    "thali energy",
    "for 12 guests",
    "housewarming evening",
    "evening plan",
    "festive dinner",
  ].some((k) => m.includes(k));
}

function isSavedAddressQuery(message: string): boolean {
  const m = (message || "").toLowerCase();
  return [
    "saved address",
    "saved addresses",
    "saved addreses",
    "my address",
    "my addresses",
    "saved location",
    "saved locations",
  ].some((k) => m.includes(k));
}

function inferVertical(message: string, ctx: NormalizedCtx): Vertical {
  if (isChronoPlanMessage(message)) return "chrono";
  if (ctx.scenario === "sentiment") return "instamart";
  if (ctx.scenario === "dialectic") return "food";
  if (ctx.scenario === "deadlock") return "dineout";
  if (ctx.scenario === "flowstate") return "instamart";
  if (ctx.scenario === "zerowaste") return "instamart";

  const m = message.toLowerCase();
  if (
    [
      "dineout",
      "reservation",
      "book a table",
      "team dinner",
      "party of",
      "table for",
      "restaurant night",
      "group dinner",
      "friends dinner",
    ].some((k) => m.includes(k)) ||
    ctx.watchParty
  ) {
    return "dineout";
  }
  if (
    [
      "instamart",
      "grocery",
      "groceries",
      "snacks",
      "stock up",
      "coding for",
      "ingredient",
      "supplies",
      "americano",
      "recipe",
      "cook",
      "pantry",
    ].some((k) => m.includes(k)) ||
    ctx.deepWork
  ) {
    return "instamart";
  }
  return "food";
}

function foodSearchRestaurants(
  cuisine: string,
  lat: number,
  long: number
): Record<string, unknown>[] {
  const base = cuisine || "any";
  return [
    {
      id: "mock-food-1",
      name: `Nexus Kitchen — ${base} hub`,
      rating: 4.6,
      eta_mins: 28,
      tag: "Fast delivery",
      cuisine: base,
      lat,
      long,
    },
    {
      id: "mock-food-2",
      name: "Demo Diner Express",
      rating: 4.3,
      eta_mins: 35,
      tag: "Budget-friendly",
      cuisine: base,
      lat,
      long,
    },
    {
      id: "mock-food-3",
      name: "Synth Spice Grove",
      rating: 4.8,
      eta_mins: 42,
      tag: "Top rated (demo)",
      cuisine: base,
      lat,
      long,
    },
  ];
}

function instamartInventory(
  category: string,
  ctx: NormalizedCtx
): Record<string, unknown>[] {
  if (ctx.scenario === "flowstate" || ctx.deepWork) {
    return [
      {
        sku: "imx-fuel-01",
        name: "Cold brew Americano (stub)",
        price_inr: 189,
        in_stock: true,
      },
      {
        sku: "imx-fuel-02",
        name: "Roasted chickpea protein pack",
        price_inr: 120,
        in_stock: true,
      },
    ];
  }
  if (ctx.scenario === "zerowaste") {
    return [
      {
        sku: "imx-diff-01",
        name: "Heavy cream — 250ml (pantry gap)",
        price_inr: 95,
        in_stock: true,
      },
      {
        sku: "imx-diff-02",
        name: "Kasuri methi 25g",
        price_inr: 45,
        in_stock: true,
      },
      {
        sku: "imx-diff-03",
        name: "Cherry tomato pack 250g",
        price_inr: 68,
        in_stock: true,
      },
    ];
  }

  const cat = (category || "groceries").toLowerCase();
  const catalog: Record<string, Record<string, unknown>[]> = {
    snacks: [
      { sku: "imx-101", name: "Demo crunch mix 200g", price_inr: 99, in_stock: true },
      { sku: "imx-102", name: "Nexus energy bar (6-pack)", price_inr: 240, in_stock: true },
    ],
    beverages: [
      {
        sku: "imx-201",
        name: "Sparkling demo cola 500ml",
        price_inr: 45,
        in_stock: true,
      },
      {
        sku: "imx-202",
        name: "Cold brew stub (demo)",
        price_inr: 120,
        in_stock: false,
      },
    ],
    groceries: [
      {
        sku: "imx-301",
        name: "Instant noodles (demo)",
        price_inr: 55,
        in_stock: true,
      },
      {
        sku: "imx-302",
        name: "Organic basmati 1kg (synthetic)",
        price_inr: 189,
        in_stock: true,
      },
    ],
  };
  return catalog[cat] ?? catalog.groceries;
}

function dineoutAvailability(
  restaurantId: string,
  partySize: number,
  time: string,
  ctx: NormalizedCtx
): Record<string, unknown> {
  return {
    restaurant_id: restaurantId,
    party_size: partySize,
    time_slot: time,
    city: ctx.city,
    available: true,
    slots: ["18:30", "19:00", "19:30", "20:00", "20:30"],
    note: `${ctx.city} · budget ≤ ₹${ctx.budgetInr}/head (demo arbiter); not live Swiggy data.`,
    join_token: `nexus-join-demo-${partySize}-${Date.now().toString(36).slice(-6)}`,
  };
}

function toFoodFeed(rows: Record<string, unknown>[], ctx: NormalizedCtx): FeedItem[] {
  const items: FeedItem[] = [];
  for (const r of rows) {
    const eta = r.eta_mins as number | undefined;
    const tagRain =
      ctx.rainPune && typeof eta === "number" ? Math.min(eta + 18, 75) : eta;
    items.push({
      type: "restaurant",
      title: String(r.name ?? "Restaurant"),
      subtitle: `★ ${r.rating} · ETA ~${tagRain ?? eta ?? "?"} min · ${r.tag ?? ""}`,
      meta: {
        id: r.id,
        cuisine: r.cuisine,
        eta_mins: tagRain ?? eta,
        rating: r.rating,
      },
    });
  }
  return items;
}

function toMartFeed(rows: Record<string, unknown>[]): FeedItem[] {
  return rows.map((item) => {
    const stock = item.in_stock ? "In stock" : "Out of stock (demo)";
    return {
      type: "instamart",
      title: String(item.name ?? "SKU"),
      subtitle: `₹${item.price_inr} · ${stock}`,
      meta: {
        sku: item.sku,
        price_inr: item.price_inr,
        in_stock: item.in_stock,
      },
    };
  });
}

function toDineoutFeed(
  result: Record<string, unknown>,
  ctx: NormalizedCtx,
  assistantBits: string[]
): FeedItem[] {
  const items: FeedItem[] = [];
  const slots = (result.slots as string[]) || [];
  items.push({
    type: "dineout",
    title: `Dineout arbiter · party of ${result.party_size}`,
    subtitle: `Slot ${result.time_slot} · ${String(result.city ?? ctx.city)}`,
    meta: {
      slots,
      restaurant_id: result.restaurant_id,
      join_token: result.join_token,
    },
  });
  const joinUrl = `https://nexus.demo/join/${String(result.join_token ?? "mock")}`;
  assistantBits.push(
    `Consensus venue window proposed (synthetic). Share join link — one tap RSVP (demo): ${joinUrl}`
  );
  items.push({
    type: "join_strip",
    title: "Tap to Join (demo)",
    subtitle: joinUrl,
    meta: { url: joinUrl, joinUrl, partySize: ctx.partySize, rsvpCount: 4, party_budget_inr: ctx.budgetInr },
  });
  for (const s of slots.slice(0, 5)) {
    items.push({
      type: "dineout_slot",
      title: `Table window · ${s}`,
      subtitle: `${ctx.city} · Nexus arbiter lane (mock MCP)`,
      meta: { time: s },
    });
  }
  return items;
}

/**
 * Deterministic SSE: Planner-labeled steps → Executor tool envelope → Synth feed.
 * Mirrors `backend/agent.py` vertical routing for credential-review demos (no LLM).
 */
export function buildDemoChatEvents(
  userMessage: string,
  rawContext?: Record<string, unknown>
): StreamEvent[] {
  const ctx = normalizeContext(rawContext);
  const mlow = userMessage.toLowerCase();

  if (isSavedAddressQuery(userMessage) && !isChronoPlanMessage(userMessage)) {
    const feed: FeedItem[] = [
      {
        type: "address",
        title: "Home",
        subtitle: "Koregaon Park, Pune (demo)",
        meta: { addressId: "addr_kp_001" },
      },
      {
        type: "address",
        title: "Work",
        subtitle: "Baner, Pune (demo)",
        meta: { addressId: "addr_baner_002" },
      },
    ];
    const reply =
      "Here are your **2** saved address(es) (demo mock). Connect FastAPI for live MCP.";
    return [
      { type: "thinking", payload: { text: "Address lookup · leftover Chrono-Host ignored" } },
      { type: "tool", payload: { method: "get_addresses", vertical: "food" } },
      { type: "feed", payload: { items: feed } },
      { type: "assistant", payload: { text: reply } },
      { type: "done", payload: { assistant_reply: reply, feed_items: feed } },
    ];
  }

  if (mlow.includes("confirm table")) {
    const reply = "**Table confirmed** via `book_table` (mock). Check booking ticket in feed.";
    const feed: FeedItem[] = [{
      type: "booking",
      title: "Spesso · Koregaon Park",
      subtitle: "CONFIRMED · 20:00",
      meta: { bookingId: `bk-${Date.now()}`, guests: ctx.partySize },
    }];
    return [
      { type: "thinking", payload: { text: "Executor • dineout book_table" } },
      { type: "tool", payload: { method: "book_table", vertical: "dineout" } },
      { type: "feed", payload: { items: feed } },
      { type: "assistant", payload: { text: reply } },
      { type: "done", payload: { assistant_reply: reply, feed_items: feed } },
    ];
  }
  if (mlow.includes("confirm groceries") || mlow.includes("checkout")) {
    const reply = "Instamart **checkout** staged — open cart drawer to complete (mock `checkout`).";
    return [
      { type: "thinking", payload: { text: "Executor • im get_cart → checkout" } },
      { type: "tool", payload: { method: "checkout", vertical: "im" } },
      { type: "assistant", payload: { text: reply } },
      { type: "done", payload: { assistant_reply: reply, feed_items: [] } },
    ];
  }
  if (mlow.includes("confirm dessert")) {
    const reply = "**Dessert placed** via `place_food_order` (mock). 10 PM reminder is manual in v1.";
    return [
      { type: "thinking", payload: { text: "Executor • food place_order" } },
      { type: "tool", payload: { method: "place_food_order", vertical: "food" } },
      { type: "assistant", payload: { text: reply } },
      { type: "done", payload: { assistant_reply: reply, feed_items: [] } },
    ];
  }

  const vertical = inferVertical(userMessage, ctx);

  const coords = { lat: 18.5204, long: 73.8567 };
  const cuisine = inferCuisine(userMessage);
  const martCat = inferInstamartCategory(userMessage, ctx);
  const dineRestId =
    typeof rawContext?.restaurant_id === "string"
      ? String(rawContext.restaurant_id)
      : "demo-pune-soc-ledger";

  const plannerLines: string[] = [
    "Planner • Ingest triggers (signals + NL intent) …",
    `Planner • Signals: deep_work=${ctx.deepWork} · rain_${ctx.city}=${ctx.rainPune} · watch_party=${ctx.watchParty}`,
  ];
  if (ctx.scenario) {
    plannerLines.push(`Planner • Active reviewer scenario preset: "${ctx.scenario}"`);
  }
  plannerLines.push(
    `Planner • Route vertical="${vertical}" (mock heuristic — swaps to Swiggy MCP tools with API access)`
  );

  let mcpMethod: string;
  let mcpParams: Record<string, unknown>;

  if (vertical === "food") {
    mcpMethod = "food_search_restaurants";
    mcpParams = {
      cuisine,
      lat: coords.lat,
      long: coords.long,
    };
  } else if (vertical === "instamart") {
    mcpMethod = "instamart_get_inventory";
    mcpParams = { category: martCat };
  } else {
    mcpMethod = "dineout_check_availability";
    mcpParams = {
      restaurant_id: dineRestId,
      party_size: ctx.partySize,
      time: typeof rawContext?.time === "string" ? rawContext.time : "19:00",
      city: ctx.city,
      budget_inr: ctx.budgetInr,
    };
  }

  const thinkingEvents: StreamEvent[] = plannerLines.map((text) => ({
    type: "thinking",
    payload: { text },
  }));

  let toolPayload: Record<string, unknown>;
  let feedItems: FeedItem[] = [];
  const assistantParts: string[] = [];

  if (vertical === "chrono") {
    const guests = ctx.partySize || 12;
    const cuisine = ctx.cuisineHint || "italian";
    const dessert = ctx.dessertQuery || "gelato";
    const imQ = ctx.imQuery || "party";
    const title = ctx.eventTitle || "Your evening";
    const dineRaw = dineoutAvailability("do-italian-spesso", guests, "20:00", ctx);
    const martRows = instamartInventory(imQ.split(/\s+/)[0] || "party", ctx);
    const foodRows = foodSearchRestaurants(dessert, coords.lat, coords.long);

    const toolEvents: StreamEvent[] = [
      { type: "tool", payload: { phase: "Executor", method: "dineout_get_saved_locations", params: {}, result: { locations: [{ label: "Home" }] } } },
      { type: "tool", payload: { phase: "Executor", method: "dineout_search_restaurants_dineout", params: { query: cuisine }, result: dineRaw } },
      { type: "tool", payload: { phase: "Executor", method: "dineout_get_available_slots", params: { guestCount: guests }, result: { slots: [{ slotId: 4204, label: "20:00" }] } } },
      { type: "tool", payload: { phase: "Executor", method: "food_get_addresses", params: {}, result: { addresses: [{ addressId: "addr_kp_001" }] } } },
      { type: "tool", payload: { phase: "Executor", method: "im_search_products", params: { query: imQ }, result: martRows } },
      { type: "tool", payload: { phase: "Executor", method: "im_your_go_to_items", params: { party: true }, result: { products: martRows.slice(0, 2) } } },
      { type: "tool", payload: { phase: "Executor", method: "im_update_cart", params: { items: 4 }, result: { total: 1847 } } },
      { type: "tool", payload: { phase: "Executor", method: "im_get_cart", params: {}, result: { total: 1847, bill: { grandTotal: 1872 } } } },
      { type: "tool", payload: { phase: "Executor", method: "food_search_restaurants", params: { query: dessert }, result: foodRows } },
      { type: "tool", payload: { phase: "Executor", method: "food_get_restaurant_menu", params: { restaurantId: "fd_gelato_108" }, result: { categories: [] } } },
      { type: "tool", payload: { phase: "Executor", method: "food_update_food_cart", params: { lines: 2 }, result: { subtotal_inr: 498 } } },
      { type: "tool", payload: { phase: "Executor", method: "food_get_food_cart", params: {}, result: { total: 649 } } },
    ];

    feedItems = [
      {
        type: "event_bundle",
        title: `Evening plan · ${title}`,
        subtitle: `Dineout + Instamart + ${dessert} (staged)`,
        meta: {
          guests,
          cuisine,
          event: title,
          dineout: { restaurant: `${cuisine} pick`, slot: "20:00" },
          instamart: { total: 1847, items: 6, query: imQ },
          food: { total: 649, item: dessert },
        },
      },
      ...toDineoutFeed(dineRaw, ctx, []),
      ...toMartFeed(martRows).slice(0, 3),
      ...toFoodFeed(foodRows.slice(0, 2), ctx),
    ];

    const assistantReply =
      `Chrono-Host bundle for **${title}** (${guests} guests · ${cuisine}): table ~8 PM (confirm to book), ` +
      `“${imQ}” staged on Instamart, ${dessert} dessert queued for a 10 PM reminder. Nothing auto-placed.`;

    return [
      ...thinkingEvents,
      {
        type: "thinking",
        payload: { text: `Planner · Chrono-Host: ${title} — Dineout → Instamart → ${dessert}` },
      },
      ...toolEvents,
      { type: "feed", payload: { items: feedItems } },
      { type: "assistant", payload: { text: assistantReply } },
      {
        type: "done",
        payload: { assistant_reply: assistantReply, feed_items: feedItems },
      },
    ];
  }

  if (vertical === "food") {
    const rows = foodSearchRestaurants(cuisine, coords.lat, coords.long);
    if (ctx.rainPune && rows[2]) {
      rows[2] = {
        ...rows[2],
        eta_mins:
          typeof rows[2].eta_mins === "number" ? rows[2].eta_mins + 22 : 50,
        tag: `Rain surcharge (demo · ${ctx.city})`,
      };
    }
    toolPayload = {
      phase: "Executor",
      jsonrpc: "2.0",
      method: mcpMethod,
      params: mcpParams,
      result: rows,
    };
    feedItems = toFoodFeed(rows, ctx);
    if (ctx.rainPune) {
      feedItems.unshift({
        type: "deal_strip",
        title: "Cross-vertical cue (demo)",
        subtitle:
          "Rain → delivery ETAs under stress. Swiggy can route users to Instamart or Dineout in one agent turn when APIs are wired.",
        meta: { vertical_hint: "dineout_or_mart_fallback" },
      });
    }
    assistantParts.push(
      `Food vertical (mock MCP: ${mcpMethod}). Showing ${feedItems.filter((x) => x.type === "restaurant").length} synth listings. Live creds unlock real catalog & checkout.`
    );
    if (ctx.scenario === "dialectic" || mlow.includes("debate") || mlow.includes("winner")) {
      assistantParts.unshift(
        `Dialectic Dinner — Referee triggered commerce chain: search_restaurants → get_menu → update_food_cart → fetch_food_coupons (staged). Confirm before place_food_order.`
      );
    }
  } else if (vertical === "instamart") {
    const rows = instamartInventory(martCat, ctx);
    toolPayload = {
      phase: "Executor",
      jsonrpc: "2.0",
      method: mcpMethod,
      params: {
        ...mcpParams,
        recipe: ctx.recipeHint,
      },
      result: rows,
    };
    feedItems = toMartFeed(rows);

    if (ctx.scenario === "sentiment" || ctx.moodScore > 0.7) {
      feedItems.unshift({
        type: "comfort_proposal",
        title: "Comfort bundle staged",
        subtitle: "Dark chocolate + dessert search — I staged, did not place",
        meta: { imTotal: 95, foodTotal: 249, moodScore: ctx.moodScore },
      });
      assistantParts.push(
        `Sentiment Thermostat — mood ${ctx.moodScore.toFixed(2)}. Staged Instamart go-to + Food dessert option. **Nothing auto-placed.** Reply to confirm each leg.`
      );
    } else if (ctx.scenario === "zerowaste") {
      assistantParts.push(
        `Zero-Waste Meal Architecture — recipe "${ctx.recipeHint}" vs virtual pantry stub. Cart below is **diff-only** (missing SKUs); memory layer would hydrate from order history with Instamart APIs.`
      );
    } else if (ctx.scenario === "flowstate" || ctx.deepWork) {
      assistantParts.push(
        `Context-Aware Flow-State Fueler — deep-work block detected (synthetic). Proactive Americano + protein snack stack; confirm to queue (mock cart).`
      );
    } else {
      assistantParts.push(
        `Instamart vertical (mock MCP: ${mcpMethod}). SKUs are synthetic; production tools would validate stock, promos, and slotting.`
      );
    }
  } else {
    const raw = dineoutAvailability(
      dineRestId,
      ctx.partySize,
      String(mcpParams.time ?? "19:00"),
      ctx
    );
    toolPayload = {
      phase: "Executor",
      jsonrpc: "2.0",
      method: mcpMethod,
      params: mcpParams,
      result: raw,
    };
    feedItems = toDineoutFeed(raw, ctx, assistantParts);
    assistantParts.unshift(
      `Social Deadlock Breaker — Arbiter synthesized one booking window under ₹${ctx.budgetInr} / capita (demo maths). MCP would pull live Dineout availability + payer split.`
    );
  }

  const assistantReply = assistantParts.join(" ");

  const synthExtra: StreamEvent[] =
    vertical === "instamart" &&
    (ctx.scenario === "zerowaste" || userMessage.toLowerCase().includes("pantry"))
      ? [
          {
            type: "thinking",
            payload: {
              text: "Synth • Composing pantry-diff SKUs → Instamart cart projections",
            },
          },
        ]
      : [];

  return [
    ...thinkingEvents,
    {
      type: "thinking",
      payload: {
        text: `Executor • Dispatching MCP-shaped call \`${mcpMethod}\``,
      },
    },
    { type: "tool", payload: toolPayload },
    ...synthExtra,
    {
      type: "thinking",
      payload: {
        text: "Synth • Normalizing executor JSON → Nexus Live Feed cards",
      },
    },
    { type: "feed", payload: { items: feedItems } },
    { type: "assistant", payload: { text: assistantReply } },
    {
      type: "done",
      payload: {
        assistant_reply: assistantReply,
        feed_items: feedItems,
      },
    },
  ];
}
