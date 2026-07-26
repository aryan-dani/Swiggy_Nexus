"use client";

import { useCallback, useEffect, useState } from "react";
import { CloudRain, Users, Trophy, Zap, RefreshCw, Check, X } from "lucide-react";
import { motion } from "framer-motion";

import { getApiBase } from "@/lib/api";
import { neoSpring } from "@/lib/motion";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { cn } from "@/lib/utils";

type Approval = {
  request_id: string;
  title: string;
  summary: string;
  status: string;
  trigger_type: string;
  cost_breakdown: Record<string, unknown>;
  created_at: string;
};

type TimelineItem = {
  event_id: string;
  kind: string;
  title: string;
  detail: string;
  severity: string;
  created_at: string;
};

function apiUrl(path: string) {
  const base = getApiBase();
  return `${base}${path}`;
}

export function ConciergeOps({ className }: { className?: string }) {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [weather, setWeather] = useState<Record<string, unknown> | null>(null);
  const [guestCount, setGuestCount] = useState(6);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [a, t, w] = await Promise.all([
        fetch(apiUrl("/api/concierge/approvals")).then((r) => r.json()),
        fetch(apiUrl("/api/concierge/timeline")).then((r) => r.json()),
        fetch(apiUrl("/api/concierge/weather")).then((r) => r.json()),
      ]);
      setApprovals(a.items || []);
      setTimeline(t.items || []);
      setWeather(w);
    } catch {
      /* backend offline — keep last */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const post = async (path: string, body?: unknown) => {
    setBusy(true);
    try {
      const res = await fetch(apiUrl(path), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || res.statusText);
      nexusToast("Concierge action OK");
      await refresh();
      return json;
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Concierge API unreachable");
    } finally {
      setBusy(false);
    }
  };

  const triggerCalendar = async (location: string, description: string) => {
    await post("/api/concierge/trigger", {
      event_title: location === "Home" ? "Housewarming #host" : "Team Dinner #swiggy",
      event_time: new Date().toISOString(),
      event_location: location,
      attendee_emails: ["dani@nexus.ai", "priya@nexus.ai"],
      description,
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn("space-y-4", className)}
    >
      <div className="border-4 border-black bg-gradient-to-r from-violet-600 to-emerald-600 p-4 text-white shadow-[6px_6px_0_0_#000]">
        <h2 className="font-display text-xl font-black uppercase tracking-widest">
          Concierge Ops
        </h2>
        <p className="mt-1 font-mono text-xs text-white/80">
          India-first QoL · LangGraph HITL · Swiggy MCP (35 tools) · not a chatbot
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void refresh()}
          className="flex items-center gap-1 border-2 border-black bg-white px-3 py-2 font-display text-[10px] font-black uppercase shadow-[3px_3px_0_0_#000]"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void triggerCalendar("Home", "Hosting #host #swiggy")}
          className="border-2 border-black bg-neo-mint px-3 py-2 font-display text-[10px] font-black uppercase shadow-[3px_3px_0_0_#000]"
        >
          Trigger Zero-Touch Host
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void triggerCalendar("Italian Spesso", "Dinner #dineout #swiggy")}
          className="border-2 border-black bg-indigo-100 px-3 py-2 font-display text-[10px] font-black uppercase shadow-[3px_3px_0_0_#000]"
        >
          Trigger Dineout
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="border-2 border-black bg-slate-50 p-3 shadow-[4px_4px_0_0_#000]">
          <h3 className="mb-2 font-display text-xs font-black uppercase">Simulate QoL</h3>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void post("/api/concierge/simulate/weather", {
                  rain_mm: 28,
                  temp_c: 21,
                  is_raining: true,
                  is_heavy_rain: true,
                  condition: "Heavy rain",
                })
              }
              className="flex items-center gap-1 border-2 border-black bg-sky-100 px-2 py-1.5 font-display text-[10px] font-bold"
            >
              <CloudRain className="h-3.5 w-3.5" /> Rain / Rooftop
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void post("/api/concierge/simulate/guests", { count: guestCount })}
              className="flex items-center gap-1 border-2 border-black bg-amber-100 px-2 py-1.5 font-display text-[10px] font-bold"
            >
              <Users className="h-3.5 w-3.5" /> Guests {guestCount}
            </button>
            <input
              type="range"
              min={2}
              max={12}
              value={guestCount}
              onChange={(e) => setGuestCount(Number(e.target.value))}
              className="w-24 accent-black"
            />
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void post("/api/concierge/simulate/ipl", {
                  required_run_rate: 14,
                  is_timeout: true,
                  is_tense_chase: true,
                })
              }
              className="flex items-center gap-1 border-2 border-black bg-rose-100 px-2 py-1.5 font-display text-[10px] font-bold"
            >
              <Trophy className="h-3.5 w-3.5" /> IPL chase
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void post("/api/concierge/simulate/fuel")}
              className="flex items-center gap-1 border-2 border-black bg-violet-100 px-2 py-1.5 font-display text-[10px] font-bold"
            >
              <Zap className="h-3.5 w-3.5" /> Fuel guard
            </button>
          </div>
          {weather && (
            <p className="mt-2 font-mono text-[10px] text-slate-600">
              Weather: {String(weather.condition)} · {String(weather.temp_c)}°C · rain{" "}
              {String(weather.rain_mm)}mm · raining={String(weather.is_raining)}
            </p>
          )}
        </div>

        <div className="border-2 border-black bg-white p-3 shadow-[4px_4px_0_0_#000]">
          <h3 className="mb-2 font-display text-xs font-black uppercase">
            Pending approvals ({approvals.length})
          </h3>
          <div className="max-h-56 space-y-2 overflow-y-auto">
            {approvals.length === 0 && (
              <p className="font-mono text-[10px] text-slate-500">No pending HITL items.</p>
            )}
            {approvals.map((a) => (
              <div
                key={a.request_id}
                className="border-2 border-black/20 bg-amber-50 p-2"
              >
                <p className="font-display text-[11px] font-bold">{a.title}</p>
                <p className="font-mono text-[10px] text-slate-600">{a.summary}</p>
                <p className="font-mono text-[9px] text-slate-400">
                  {a.request_id} · {a.trigger_type}
                </p>
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void post(`/api/hitl/approve/${a.request_id}`, { approved: true })}
                    className="flex items-center gap-1 border-2 border-black bg-emerald-400 px-2 py-1 font-display text-[10px] font-black"
                  >
                    <Check className="h-3 w-3" /> Approve
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void post(`/api/hitl/reject/${a.request_id}`)}
                    className="flex items-center gap-1 border-2 border-black bg-white px-2 py-1 font-display text-[10px] font-black"
                  >
                    <X className="h-3 w-3" /> Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="border-2 border-black bg-slate-900 p-3 text-white shadow-[4px_4px_0_0_#000]">
        <h3 className="mb-2 font-display text-xs font-black uppercase tracking-widest text-emerald-300">
          QoL timeline
        </h3>
        <ul className="max-h-48 space-y-1 overflow-y-auto font-mono text-[10px]">
          {timeline.length === 0 && <li className="text-slate-500">No events yet.</li>}
          {timeline.map((t) => (
            <li key={`${t.event_id}-${t.created_at}`} className="border-l-2 border-emerald-500/40 pl-2">
              <span className="text-amber-300">[{t.kind}]</span> {t.title}
              {t.detail ? <span className="text-slate-400"> — {t.detail}</span> : null}
            </li>
          ))}
        </ul>
      </div>
    </motion.div>
  );
}
