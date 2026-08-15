import { loadWowVariant, wowEventFromVariant } from "@/lib/wow-variants";

const KEY = "nexus-demo-settings-v1";

/** Reviewer presets for Swiggy credential pitch demos (frontend-only mocks). */
export type NexusReviewerScenario =
  | ""
  | "deadlock"
  | "flowstate"
  | "zerowaste"
  | "chrono_host"
  | "sentiment"
  | "dialectic";

export type NexusDemoSettings = {
  devMode: boolean;
  compactFeed: boolean;
  sessionHints: boolean;
  /** When true, chat uses local mock MCP. When false, live mcp.swiggy.com (needs server token). */
  useMockMcp: boolean;
  signalDeepWorkBlock: boolean;
  signalRainInPune: boolean;
  signalWatchParty: boolean;
  signalMoodScore: number;
  reviewerScenario: NexusReviewerScenario;
  deadlockPartySize: number;
  deadlockBudgetInr: number;
  deadlockCity: string;
  zerowasteRecipeHint: string;
};

export const DEMO_SETTINGS_DEFAULTS: NexusDemoSettings = {
  devMode: false,
  compactFeed: false,
  sessionHints: true,
  useMockMcp: true,
  signalDeepWorkBlock: false,
  signalRainInPune: false,
  signalWatchParty: false,
  signalMoodScore: 0.35,
  reviewerScenario: "",
  deadlockPartySize: 5,
  deadlockBudgetInr: 800,
  deadlockCity: "Pune",
  zerowasteRecipeHint: "Paneer tikka masala",
};

function parse(raw: string | null): NexusDemoSettings {
  if (!raw) return { ...DEMO_SETTINGS_DEFAULTS };
  try {
    const o = JSON.parse(raw) as Partial<NexusDemoSettings>;
    const d = DEMO_SETTINGS_DEFAULTS;
    const scenario =
      o.reviewerScenario === "deadlock" ||
      o.reviewerScenario === "flowstate" ||
      o.reviewerScenario === "zerowaste" ||
      o.reviewerScenario === "chrono_host" ||
      o.reviewerScenario === "sentiment" ||
      o.reviewerScenario === "dialectic"
        ? o.reviewerScenario
        : "";

    return {
      devMode: typeof o.devMode === "boolean" ? o.devMode : d.devMode,
      compactFeed:
        typeof o.compactFeed === "boolean" ? o.compactFeed : d.compactFeed,
      sessionHints:
        typeof o.sessionHints === "boolean" ? o.sessionHints : d.sessionHints,
      useMockMcp:
        typeof o.useMockMcp === "boolean" ? o.useMockMcp : d.useMockMcp,
      signalDeepWorkBlock:
        typeof o.signalDeepWorkBlock === "boolean"
          ? o.signalDeepWorkBlock
          : d.signalDeepWorkBlock,
      signalRainInPune:
        typeof o.signalRainInPune === "boolean"
          ? o.signalRainInPune
          : d.signalRainInPune,
      signalWatchParty:
        typeof o.signalWatchParty === "boolean"
          ? o.signalWatchParty
          : d.signalWatchParty,
      signalMoodScore:
        typeof o.signalMoodScore === "number" && Number.isFinite(o.signalMoodScore)
          ? Math.min(1, Math.max(0, o.signalMoodScore))
          : d.signalMoodScore,
      reviewerScenario: scenario,
      deadlockPartySize:
        typeof o.deadlockPartySize === "number" && Number.isFinite(o.deadlockPartySize)
          ? Math.min(20, Math.max(2, Math.floor(o.deadlockPartySize)))
          : d.deadlockPartySize,
      deadlockBudgetInr:
        typeof o.deadlockBudgetInr === "number" &&
        Number.isFinite(o.deadlockBudgetInr)
          ? Math.min(5000, Math.max(200, Math.floor(o.deadlockBudgetInr)))
          : d.deadlockBudgetInr,
      deadlockCity:
        typeof o.deadlockCity === "string" && o.deadlockCity.trim()
          ? o.deadlockCity.trim()
          : d.deadlockCity,
      zerowasteRecipeHint:
        typeof o.zerowasteRecipeHint === "string" && o.zerowasteRecipeHint.trim()
          ? o.zerowasteRecipeHint.trim()
          : d.zerowasteRecipeHint,
    };
  } catch {
    return { ...DEMO_SETTINGS_DEFAULTS };
  }
}

/** Shape passed to `POST /api/chat/stream` for mock orchestration. */
export function orchestrationContextFromSettings(
  s: NexusDemoSettings
): Record<string, unknown> {
  let chronoEvent: Record<string, unknown> | undefined;
  if (s.reviewerScenario === "chrono_host") {
    const variant = loadWowVariant();
    chronoEvent = variant
      ? wowEventFromVariant(variant)
      : {
          title: "Housewarming Saturday",
          start: "2026-08-02T19:00:00+05:30",
          end: "2026-08-02T23:00:00+05:30",
          guests: 12,
          cuisineHint: "italian",
          dessertQuery: "gelato",
          imQuery: "party plates napkins drinks",
          playlistKey: "housewarming",
        };
  }

  return {
    signals: {
      deepWorkBlock: s.signalDeepWorkBlock,
      rainInPune: s.signalRainInPune,
      watchParty: s.signalWatchParty,
      moodScore: s.signalMoodScore,
    },
    scenario: s.reviewerScenario || undefined,
    partySize: s.deadlockPartySize,
    budgetInr: s.deadlockBudgetInr,
    city: s.deadlockCity,
    recipeHint: s.zerowasteRecipeHint,
    event: chronoEvent,
    use_mock_mcp: s.useMockMcp,
  };
}

export function loadDemoSettings(): NexusDemoSettings {
  if (typeof window === "undefined") return { ...DEMO_SETTINGS_DEFAULTS };
  return parse(window.localStorage.getItem(KEY));
}

export function saveDemoSettings(partial: Partial<NexusDemoSettings>): NexusDemoSettings {
  if (typeof window === "undefined") {
    return { ...DEMO_SETTINGS_DEFAULTS, ...partial };
  }
  const next = { ...loadDemoSettings(), ...partial };
  window.localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}
