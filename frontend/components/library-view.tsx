"use client";

import { getToolCoverage } from "@/lib/mcp-client";

const SESSIONS_KEY = "nexus-library-sessions";

type SavedSession = {
  id: string;
  title: string;
  scenario: string;
  ts: number;
  toolCount: number;
};

function loadSessions(): SavedSession[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(SESSIONS_KEY) ?? "[]") as SavedSession[];
  } catch {
    return [];
  }
}

export function saveLibrarySession(title: string, scenario: string) {
  if (typeof window === "undefined") return;
  const cov = getToolCoverage();
  const row: SavedSession = {
    id: crypto.randomUUID(),
    title,
    scenario,
    ts: Date.now(),
    toolCount: cov.used,
  };
  const next = [row, ...loadSessions()].slice(0, 20);
  window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(next));
}

export function LibraryView() {
  const sessions = typeof window !== "undefined" ? loadSessions() : [];
  const cov = typeof window !== "undefined" ? getToolCoverage() : { used: 0, total: 33, methods: [] };

  return (
    <div className="w-full max-w-3xl space-y-6">
      <div>
        <h2 className="font-display text-2xl font-black uppercase">Library</h2>
        <p className="text-sm text-slate-600">Saved demo sessions and MCP tool traces.</p>
      </div>
      <div className="border-2 border-black bg-indigo-50 p-4">
        <p className="font-display text-xs font-black uppercase">Current session coverage</p>
        <p className="mt-1 font-mono text-2xl font-bold">{cov.used}/{cov.total} tools</p>
        {cov.methods.length > 0 && (
          <ul className="mt-2 max-h-32 overflow-y-auto font-mono text-[10px] text-slate-600">
            {cov.methods.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        )}
      </div>
      <ul className="space-y-3">
        {sessions.length === 0 ? (
          <li className="border-2 border-dashed border-black p-8 text-center text-sm text-slate-500">
            No saved sessions yet — run a story preset and chat to record one automatically.
          </li>
        ) : (
          sessions.map((s) => (
            <li key={s.id} className="border-2 border-black bg-white p-4 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              <p className="font-display font-black">{s.title}</p>
              <p className="text-xs text-slate-500">
                {s.scenario || "general"} · {s.toolCount} tools · {new Date(s.ts).toLocaleString()}
              </p>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
