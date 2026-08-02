/** Rotating Chrono-Host / 60s WOW variants — each click feels like a fresh night. */

export type WowVariant = {
  id: string;
  prompt: string;
  title: string;
  guests: number;
  cuisineHint: string;
  dessertQuery: string;
  imQuery: string;
  playlistKey: "housewarming" | "team_dinner" | "date_night" | "festival";
  blurb: string;
};

export const WOW_VARIANTS: WowVariant[] = [
  {
    id: "housewarming-12",
    prompt: "Plan my housewarming evening for 12 guests — Italian vibes",
    title: "Housewarming Saturday",
    guests: 12,
    cuisineHint: "italian",
    dessertQuery: "gelato",
    imQuery: "party plates napkins drinks",
    playlistKey: "housewarming",
    blurb: "Table + party supplies + dessert",
  },
  {
    id: "team-8-asian",
    prompt: "Plan a team dinner for 8 in Koregaon Park — Asian cuisine",
    title: "Team dinner · KP",
    guests: 8,
    cuisineHint: "asian",
    dessertQuery: "mochi dessert",
    imQuery: "party snacks cola napkins",
    playlistKey: "team_dinner",
    blurb: "Asian table + snacks + sweet finish",
  },
  {
    id: "date-2-continental",
    prompt: "Plan a date-night for 2 — rooftop continental dinner",
    title: "Date night",
    guests: 2,
    cuisineHint: "continental",
    dessertQuery: "tiramisu",
    imQuery: "flowers wine glasses candles",
    playlistKey: "date_night",
    blurb: "Intimate table + ambience + dessert",
  },
  {
    id: "festival-10-north",
    prompt: "Plan my evening — festive dinner for 10, North Indian thali energy",
    title: "Festival feast",
    guests: 10,
    cuisineHint: "north indian",
    dessertQuery: "kulfi",
    imQuery: "diyas sweets paper plates",
    playlistKey: "festival",
    blurb: "Big table + festive haul + kulfi",
  },
  {
    id: "baner-6-south",
    prompt: "Plan my evening for 6 in Baner — South Indian dinner",
    title: "Baner hangout",
    guests: 6,
    cuisineHint: "south indian",
    dessertQuery: "filter coffee sweets",
    imQuery: "banana leaves paper cups",
    playlistKey: "team_dinner",
    blurb: "South Indian table + supplies",
  },
];

const STORAGE_KEY = "nexus_wow_variant_v1";

export function pickWowVariant(): WowVariant {
  let lastId: string | null = null;
  if (typeof window !== "undefined") {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (raw) lastId = (JSON.parse(raw) as WowVariant).id;
    } catch {
      /* ignore */
    }
  }
  const pool = lastId
    ? WOW_VARIANTS.filter((v) => v.id !== lastId)
    : WOW_VARIANTS;
  const idx = Math.floor(Math.random() * pool.length);
  const variant = pool[idx] ?? WOW_VARIANTS[0]!;
  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(variant));
    } catch {
      /* ignore */
    }
  }
  return variant;
}

export function loadWowVariant(): WowVariant | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as WowVariant;
  } catch {
    return null;
  }
}

export function wowEventFromVariant(v: WowVariant): Record<string, unknown> {
  return {
    title: v.title,
    start: "2026-08-02T19:00:00+05:30",
    end: "2026-08-02T23:00:00+05:30",
    guests: v.guests,
    cuisineHint: v.cuisineHint,
    dessertQuery: v.dessertQuery,
    imQuery: v.imQuery,
    playlistKey: v.playlistKey,
  };
}

export type PlaylistTrack = { t: string; vibe: string; bpm?: number };

export const PLAYLISTS: Record<WowVariant["playlistKey"], PlaylistTrack[]> = {
  housewarming: [
    { t: "Khuloos · Talwiinder", vibe: "doors open · friends pouring in", bpm: 96 },
    { t: "Jee Le Zaraa · Vishal Dadlani", vibe: "house filled · lights low", bpm: 108 },
    { t: "Blinding Lights · The Weeknd", vibe: "dance floor by the sofa", bpm: 171 },
    { t: "Pasoori · Ali Sethi", vibe: "kitchen chaos energy", bpm: 118 },
  ],
  team_dinner: [
    { t: "Starboy · The Weeknd", vibe: "team walks into the venue", bpm: 186 },
    { t: "Levitating · Dua Lipa", vibe: "first round of toasts", bpm: 103 },
    { t: "Naatu Naatu · Rahul Sipligunj", vibe: "celebration mode", bpm: 157 },
    { t: "As It Was · Harry Styles", vibe: "walk home after dinner", bpm: 174 },
  ],
  date_night: [
    { t: "Die For You · The Weeknd", vibe: "candlelight · soft talk", bpm: 133 },
    { t: "Night Changes · One Direction", vibe: "city lights from the table", bpm: 118 },
    { t: "Tum Se Hi · Mohit Chauhan", vibe: "slow dessert course", bpm: 92 },
    { t: "Golden · Harry Styles", vibe: "cab ride home", bpm: 140 },
  ],
  festival: [
    { t: "Nagada Sang Dhol · Shreya Ghoshal", vibe: "festive entry", bpm: 140 },
    { t: "Kesariya · Arijit Singh", vibe: "thali mid-course glow", bpm: 90 },
    { t: "Magenta Riddim · DJ Snake", vibe: "after-dinner energy", bpm: 128 },
    { t: "Apna Time Aayega · Ranveer Singh", vibe: "group photo chaos", bpm: 100 },
  ],
};

export function playlistForScenario(
  scenario?: string,
  playlistKey?: string
): PlaylistTrack[] {
  if (playlistKey && playlistKey in PLAYLISTS) {
    return PLAYLISTS[playlistKey as WowVariant["playlistKey"]];
  }
  if (scenario === "chrono_host") {
    const v = loadWowVariant();
    if (v) return PLAYLISTS[v.playlistKey];
  }
  // Shuffle a cross-cut so Playlist never feels frozen across demos
  const pool = [
    ...PLAYLISTS.housewarming,
    ...PLAYLISTS.team_dinner,
    ...PLAYLISTS.date_night,
  ];
  const seed = Date.now() % pool.length;
  return [...pool.slice(seed), ...pool.slice(0, seed)].slice(0, 4);
}

/** Distinct alternate listings for More options (not clones of the same card). */
export const ALT_LISTINGS: Record<
  "dineout" | "grocery" | "food",
  Array<{ title: string; description: string; price?: string; offer?: string; imageSeed: string }>
> = {
  dineout: [
    {
      title: "Malaka Spice · terrace",
      description: "Thai · open table · KP",
      offer: "20:30 free reservation",
      imageSeed: "malaka-terrace",
    },
    {
      title: "Social FC Road",
      description: "Continental · group booth",
      offer: "Happy hour mocktails",
      imageSeed: "social-fc",
    },
    {
      title: "6 Digs · Kothrud",
      description: "Asian bar · 6–10 guests",
      offer: "Slots open tonight",
      imageSeed: "six-digs",
    },
  ],
  grocery: [
    {
      title: "Paper lanterns pack",
      description: "Instamart · décor",
      price: "₹199",
      offer: "Party aisle pick",
      imageSeed: "lanterns",
    },
    {
      title: "Sparkling juice 750ml",
      description: "Instamart · drinks",
      price: "₹149",
      offer: "Chill in 15 min",
      imageSeed: "sparkling",
    },
    {
      title: "Fairy lights USB",
      description: "Instamart · ambience",
      price: "₹299",
      offer: "Demo ₹40 off",
      imageSeed: "fairy-lights",
    },
  ],
  food: [
    {
      title: "Pistachio gelato tub",
      description: "Dessert · late drop",
      price: "₹320",
      offer: "Stage for 10 PM",
      imageSeed: "pistachio",
    },
    {
      title: "Belgian waffle stack",
      description: "Dessert · shareable",
      price: "₹280",
      offer: "Add chocolate drizzle",
      imageSeed: "waffle",
    },
    {
      title: "Kulfi stick box (6)",
      description: "Dessert · festive",
      price: "₹240",
      offer: "Cold pack included",
      imageSeed: "kulfi",
    },
  ],
};

export function demoImageUrl(
  seed: string,
  w = 480,
  h = 320,
  kind: "food" | "grocery" | "dine" = "food"
): string {
  const lower = seed.toLowerCase();
  const lock = [...lower].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7) % 2400;

  // Keyword → food/grocery/dining Flickr tags (loremflickr, not random landscapes).
  const hit = (
    [
      ["gelato", "gelato,icecream,dessert"],
      ["pistachio", "pistachio,dessert,icecream"],
      ["domino", "pizza,italian,food"],
      ["pizza", "pizza,food,italian"],
      ["malaka", "asian,restaurant,noodles"],
      ["spice", "indian,curry,food"],
      ["lantern", "party,celebration,decor"],
      ["biryani", "biryani,indian,food"],
      ["waffle", "waffle,dessert,breakfast"],
      ["kulfi", "kulfi,icecream,dessert"],
      ["chips", "chips,snacks,potato"],
      ["cola", "soda,drink,beverage"],
      ["paneer", "paneer,indian,food"],
      ["burger", "burger,fastfood,food"],
      ["sushi", "sushi,japanese,food"],
      ["coffee", "coffee,cafe,drink"],
      ["cake", "cake,dessert,bakery"],
      ["thali", "indian,thali,food"],
      ["noodles", "noodles,asian,food"],
      ["salad", "salad,healthy,food"],
    ] as const
  ).find(([k]) => lower.includes(k));

  const fallback =
    kind === "grocery"
      ? "grocery,snacks,supermarket"
      : kind === "dine"
        ? "restaurant,dining,plate"
        : "food,restaurant,cuisine";
  const tags = hit?.[1] ?? fallback;
  return `https://loremflickr.com/${w}/${h}/${tags}?lock=${lock}`;
}
