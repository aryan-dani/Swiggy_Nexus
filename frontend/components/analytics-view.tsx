"use client";

import { getToolCoverage } from "@/lib/mcp-client";

export function AnalyticsView() {
  const cov = typeof window !== "undefined" ? getToolCoverage() : { used: 0, total: 33, methods: [] };
  const byVertical = { food: 0, im: 0, dineout: 0 };
  for (const m of cov.methods) {
    const [v] = m.split(":");
    if (v === "food") byVertical.food++;
    else if (v === "im") byVertical.im++;
    else if (v === "dineout") byVertical.dineout++;
  }

  return (
    <div className="w-full max-w-3xl space-y-6">
      <div>
        <h2 className="font-display text-2xl font-black uppercase">Analytics</h2>
        <p className="text-sm text-slate-600">Mock MCP usage dashboard for reviewer demos.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {(["food", "im", "dineout"] as const).map((v) => (
          <div key={v} className="border-2 border-black bg-white p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <p className="font-display text-[10px] font-black uppercase text-slate-500">{v}</p>
            <p className="font-mono text-3xl font-bold">{byVertical[v]}</p>
            <p className="text-xs text-slate-500">tool calls</p>
          </div>
        ))}
      </div>
      <div className="border-2 border-black bg-neo-mint/30 p-4">
        <p className="font-display text-xs font-black uppercase">Session MCP coverage</p>
        <div className="mt-2 h-4 border-2 border-black bg-white">
          <div
            className="h-full bg-primary-container"
            style={{ width: `${(cov.used / cov.total) * 100}%` }}
          />
        </div>
        <p className="mt-2 font-mono text-sm">{cov.used} of {cov.total} unique tools exercised</p>
      </div>
    </div>
  );
}

export function McpCoverageMeter({ className }: { className?: string }) {
  const cov = typeof window !== "undefined" ? getToolCoverage() : { used: 0, total: 33 };
  return (
    <span className={className} title="Unique MCP tools called this session">
      MCP {cov.used}/{cov.total}
    </span>
  );
}
