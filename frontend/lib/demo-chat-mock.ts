import type { FeedItem, StreamEvent } from "@/lib/api";

/** Deterministic-ish demo SSE sequence for frontend-only deployments. */
export function buildDemoChatEvents(userMessage: string): StreamEvent[] {
  const q = userMessage.slice(0, 80).toLowerCase();

  let intent = "food discovery";
  if (/\b(team|office|meet)\b/i.test(userMessage)) intent = "group order";
  if (/\bdinner|lunch|biryani\b/i.test(q)) intent = "meal pickup";

  const feedItems: FeedItem[] = [
    {
      type: "restaurant_card",
      title: "Neo Biryani Co. (demo)",
      subtitle: "Koramangala · ~28 min · synth rating 4.6",
      meta: { cuisines: ["Biryani", "Kebab"], note: intent },
    },
    {
      type: "deal_strip",
      title: "SAVE25 · ₹75 off ₹299+",
      subtitle: "Synthetic coupon — shows in live feed.",
    },
  ];

  const reply = [
    `(Demo MCP) Parsed “${intent}” — no backend connected.`,
    "Here’s a mocked Swiggy-style card stack for the Nexus UI smoke test.",
    "Wire `NEXT_PUBLIC_API_URL` later to swap in your FastAPI stream.",
  ].join(" ");

  return [
    { type: "thinking", payload: { text: "Routing user intent (demo heuristic)…" } },
    { type: "thinking", payload: { text: `Classified slice: «${intent}» (mock)` } },
    {
      type: "tool",
      payload: {
        tool: "nexus.catalog.search_demo",
        args: { query: q || "popular picks", locale: "IN-demo" },
        result_preview: ["3 synthetic listings", "1 promo strip"],
      },
    },
    { type: "feed", payload: { items: feedItems } },
    {
      type: "assistant",
      payload: {
        text: reply,
      },
    },
    {
      type: "done",
      payload: {
        assistant_reply: reply,
        feed_items: feedItems,
      },
    },
  ];
}
