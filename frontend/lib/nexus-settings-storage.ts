const KEY = "nexus-demo-settings-v1";

export type NexusDemoSettings = {
  devMode: boolean;
  compactFeed: boolean;
  sessionHints: boolean;
};

const defaults: NexusDemoSettings = {
  devMode: false,
  compactFeed: false,
  sessionHints: true,
};

function parse(raw: string | null): NexusDemoSettings {
  if (!raw) return { ...defaults };
  try {
    const o = JSON.parse(raw) as Partial<NexusDemoSettings>;
    return {
      devMode: typeof o.devMode === "boolean" ? o.devMode : defaults.devMode,
      compactFeed:
        typeof o.compactFeed === "boolean" ? o.compactFeed : defaults.compactFeed,
      sessionHints:
        typeof o.sessionHints === "boolean" ? o.sessionHints : defaults.sessionHints,
    };
  } catch {
    return { ...defaults };
  }
}

export function loadDemoSettings(): NexusDemoSettings {
  if (typeof window === "undefined") return { ...defaults };
  return parse(window.localStorage.getItem(KEY));
}

export function saveDemoSettings(partial: Partial<NexusDemoSettings>): NexusDemoSettings {
  if (typeof window === "undefined") {
    return { ...defaults, ...partial };
  }
  const next = { ...loadDemoSettings(), ...partial };
  window.localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}
