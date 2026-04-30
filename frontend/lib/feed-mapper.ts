import type { FeedItem } from "@/lib/api";
import type { NexusCardResult } from "@/components/nexus-result-card";

/** Bundled under `public/images/demo` — works offline / no hotlink blocks. */
const FOOD_IMG = "/images/demo/food.jpg";
const MART_IMG = "/images/demo/grocery.jpg";
const DINE_IMG = "/images/demo/dineout.jpg";

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
      imageUrl: FOOD_IMG,
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
      imageUrl: MART_IMG,
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
      imageUrl: DINE_IMG,
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
      imageUrl: DINE_IMG,
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
      imageUrl: FOOD_IMG,
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
      imageUrl: DINE_IMG,
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
    imageUrl: FOOD_IMG,
  };
}
