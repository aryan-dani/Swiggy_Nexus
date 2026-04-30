const KEY = "nexus-demo-settings-v1";

/** Reviewer presets for Swiggy credential pitch demos (frontend-only mocks). */
export type NexusReviewerScenario = "" | "deadlock" | "flowstate" | "zerowaste";

export type NexusDemoSettings = {
  devMode: boolean;
  compactFeed: boolean;
  sessionHints: boolean;
  signalDeepWorkBlock: boolean;
  signalRainInPune: boolean;
  signalWatchParty: boolean;
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
  signalDeepWorkBlock: false,
  signalRainInPune: false,
  signalWatchParty: false,
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
      o.reviewerScenario === "zerowaste"
        ? o.reviewerScenario
        : "";

    return {
      devMode: typeof o.devMode === "boolean" ? o.devMode : d.devMode,
      compactFeed:
        typeof o.compactFeed === "boolean" ? o.compactFeed : d.compactFeed,
      sessionHints:
        typeof o.sessionHints === "boolean" ? o.sessionHints : d.sessionHints,
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
  return {
    signals: {
      deepWorkBlock: s.signalDeepWorkBlock,
      rainInPune: s.signalRainInPune,
      watchParty: s.signalWatchParty,
    },
    scenario: s.reviewerScenario || undefined,
    partySize: s.deadlockPartySize,
    budgetInr: s.deadlockBudgetInr,
    city: s.deadlockCity,
    recipeHint: s.zerowasteRecipeHint,
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
