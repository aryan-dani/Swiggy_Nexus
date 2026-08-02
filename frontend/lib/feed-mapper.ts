import type { FeedItem } from "@/lib/api";
import type { NexusCardResult } from "@/components/nexus-result-card";
import { demoImageUrl } from "@/lib/wow-variants";

/** Local SVG fallbacks if remote food images fail offline. */
const FOOD_IMG = "/images/demo/food.svg";
const MART_IMG = "/images/demo/grocery.svg";
const DINE_IMG = "/images/demo/dineout.svg";

type ImageKind = "food" | "grocery" | "dine";

function seedImage(kind: ImageKind, title: string, fallback: string): string {
  const seed = `${kind}-${title || "nexus"}`.slice(0, 64);
  try {
    return demoImageUrl(seed, 480, 320, kind);
  } catch {
    return fallback;
  }
}

export function mapFeedItemToNexusCard(
  item: FeedItem,
  index: number
): NexusCardResult | null {
  const id = `${item.type}-${index}`;

  if (item.type === "restaurant") {
    const rating = item.meta?.rating as number | undefined;
    const eta = item.meta?.eta_mins as number | undefined;
    return {
      id,
      type: "food",
      title: item.title,
      description:
        (item.meta?.cuisine as string) ||
        item.subtitle?.split("·")[0]?.trim() ||
        "Restaurant",
      rating,
      time: eta != null ? `~${eta} min` : undefined,
      price: undefined,
      imageUrl: seedImage("food", item.title, FOOD_IMG),
      meta: item.meta,
    };
  }

  if (item.type === "instamart") {
    const price = item.meta?.price_inr as number | undefined;
    return {
      id,
      type: "grocery",
      title: item.title,
      description: item.subtitle?.split("·")[0]?.trim() || "Instamart",
      rating: 4.5,
      price: price != null ? `₹${price}` : undefined,
      items: undefined,
      imageUrl: seedImage("grocery", item.title, MART_IMG),
      meta: item.meta,
    };
  }

  if (item.type === "dineout") {
    return {
      id,
      type: "dineout",
      title: item.title,
      description: item.subtitle || "Reservation",
      rating: 4.7,
      distance: (item.meta?.restaurant_id as string) || "Nearby",
      offer: item.subtitle?.includes("Available")
        ? "Slots open"
        : undefined,
      imageUrl: seedImage("dine", item.title, DINE_IMG),
      meta: item.meta,
    };
  }

  if (item.type === "dineout_slot") {
    return {
      id,
      type: "dineout",
      title: item.title,
      description: item.subtitle || "Table window",
      rating: undefined,
      time: (item.meta?.time as string) || undefined,
      imageUrl: seedImage("dine", item.title, DINE_IMG),
    };
  }

  if (item.type === "deal_strip") {
    return {
      id,
      type: "food",
      title: item.title,
      description: item.subtitle || "Promo / cross-vertical cue",
      rating: undefined,
      offer: "Agent-suggested route (demo)",
      imageUrl: seedImage("food", item.title, FOOD_IMG),
    };
  }

  if (item.type === "join_strip") {
    return {
      id,
      type: "dineout",
      title: item.title,
      description: item.subtitle || "Join link",
      rating: undefined,
      offer: "One-tap RSVP (mock)",
      imageUrl: seedImage("dine", item.title, DINE_IMG),
    };
  }

  if (item.type === "event_bundle") {
    return {
      id,
      type: "dineout",
      title: item.title,
      description: item.subtitle || "Multi-vertical evening plan",
      rating: undefined,
      offer: "Dineout + Instamart + Food",
      imageUrl: seedImage("dine", item.title, DINE_IMG),
    };
  }

  if (item.type === "error") {
    return null;
  }

  return {
    id,
    type: "food",
    title: item.title,
    description: item.subtitle || "",
    imageUrl: seedImage("food", item.title, FOOD_IMG),
  };
}
