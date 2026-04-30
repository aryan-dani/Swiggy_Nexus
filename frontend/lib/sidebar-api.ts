import { getApiBase } from "@/lib/api";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type SidebarNewChatResponse = {
  ok: boolean;
  message: string;
  session_number: number;
  id: string;
  label: string;
  created_at: number;
};

export type SidebarAnalytics = {
  sessions_started: number;
  mock_tool_calls_24h: number;
  avg_latency_ms: number;
  top_intent: string;
  note: string;
};

export type SidebarArchive = { items: Array<Record<string, unknown>> };

export type SidebarLibrary = {
  pins: Array<{ id: string; title: string; type: string }>;
};

export type SidebarPro = {
  headline: string;
  bullets: string[];
};

export type SidebarSummary = {
  analytics: SidebarAnalytics;
  library: Array<{ id: string; title: string; type: string }>;
  archive_preview: Array<Record<string, unknown>>;
};

export function fetchSidebarSummary() {
  return jsonFetch<SidebarSummary>("/api/sidebar/summary");
}

export function postSidebarNewChat() {
  return jsonFetch<SidebarNewChatResponse>("/api/sidebar/new-chat", {
    method: "POST",
  });
}

export function fetchSidebarAnalytics() {
  return jsonFetch<SidebarAnalytics>("/api/sidebar/analytics");
}

export function fetchSidebarArchive() {
  return jsonFetch<SidebarArchive>("/api/sidebar/archive");
}

export function fetchSidebarLibrary() {
  return jsonFetch<SidebarLibrary>("/api/sidebar/library");
}

export function fetchSidebarPro() {
  return jsonFetch<SidebarPro>("/api/sidebar/pro");
}

export function postSidebarDevMode(enabled: boolean) {
  return jsonFetch<{ received: boolean; dev_mode: boolean; logged_at: number }>(
    "/api/sidebar/dev-mode",
    { method: "POST", body: JSON.stringify({ enabled }) }
  );
}
