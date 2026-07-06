"use client";

import { useMemo, useState } from "react";

import { cn } from "@/lib/utils";

export function renderSimpleMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const lines = text.split("\n");
  lines.forEach((line, li) => {
    const chunks = line.split(/(\*\*[^*]+\*\*)/g);
    const inline = chunks.map((c, i) => {
      if (c.startsWith("**") && c.endsWith("**")) {
        return <strong key={`${li}-${i}`}>{c.slice(2, -2)}</strong>;
      }
      return <span key={`${li}-${i}`}>{c}</span>;
    });
    parts.push(
      <span key={li}>
        {inline}
        {li < lines.length - 1 ? <br /> : null}
      </span>
    );
  });
  return parts;
}

export function ToolTraceTheater({
  logs,
  className,
}: {
  logs: string[];
  className?: string;
}) {
  const [filter, setFilter] = useState<"all" | "food" | "im" | "dineout">("all");
  const [expanded, setExpanded] = useState<number | null>(null);

  const parsed = useMemo(() => {
    return logs.map((raw, i) => {
      try {
        const o = JSON.parse(raw) as Record<string, unknown>;
        const method = String(o.method ?? "");
        const vertical =
          method.includes("food") || o.server_path === "/food"
            ? "food"
            : method.includes("dineout") || o.server_path === "/dineout"
              ? "dineout"
              : method.includes("im") || o.server_path === "/im"
                ? "im"
                : "food";
        return { i, raw, o, vertical, method };
      } catch {
        return { i, raw, o: {}, vertical: "food" as const, method: "?" };
      }
    });
  }, [logs]);

  const rows = parsed.filter((p) => filter === "all" || p.vertical === filter);

  return (
    <div className={cn("border-2 border-black bg-slate-950 text-emerald-400", className)}>
      <div className="flex flex-wrap gap-1 border-b border-emerald-900 p-2">
        {(["all", "food", "im", "dineout"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn(
              "px-2 py-0.5 font-mono text-[10px] uppercase",
              filter === f ? "bg-emerald-900 text-white" : "text-emerald-600"
            )}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto font-mono text-[10px] text-emerald-700">{rows.length} traces</span>
      </div>
      <ul className="max-h-48 overflow-y-auto p-2 font-mono text-[10px]">
        {rows.map((row) => (
          <li key={row.i} className="mb-1">
            <button
              type="button"
              className="w-full text-left hover:bg-emerald-950"
              onClick={() => setExpanded(expanded === row.i ? null : row.i)}
            >
              [{row.vertical}] {row.method || "tool"}
            </button>
            {expanded === row.i && (
              <pre className="mt-1 whitespace-pre-wrap break-all text-emerald-300">{row.raw}</pre>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
