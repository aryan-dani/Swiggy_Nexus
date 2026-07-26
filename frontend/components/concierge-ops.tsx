"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CloudRain,
  Users,
  Trophy,
  Zap,
  RefreshCw,
  Check,
  X,
  Loader2,
  MessageCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

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

type DemoPhase =
  | "idle"
  | "staging"
  | "awaiting_hitl"
  | "executing"
  | "done"
  | "rejected"
  | "error";

const PHASE_COPY: Record<
  DemoPhase,
  { label: string; blurb: string; tone: string }
> = {
  idle: {
    label: "Ready",
    blurb: "Pick a workflow below. Nothing is charged until you Approve.",
    tone: "bg-slate-100 text-slate-800 border-slate-300",
  },
  staging: {
    label: "1 · Staging carts",
    blurb: "Read-only MCP tools are building carts / slots. No write tools yet.",
    tone: "bg-violet-100 text-violet-950 border-violet-400",
  },
  awaiting_hitl: {
    label: "2 · Waiting for your Approve",
    blurb: "Check Telegram (@SwiggyNexusbot) or use Approve here. Writes are blocked until HITL.",
    tone: "bg-amber-100 text-amber-950 border-amber-500",
  },
  executing: {
    label: "3 · Executing writes",
    blurb: "Running checkout / book_table / place_food_order on the mock MCP…",
    tone: "bg-sky-100 text-sky-950 border-sky-400",
  },
  done: {
    label: "4 · Complete",
    blurb: "Mock orders placed. Watch the timeline below for what ran.",
    tone: "bg-emerald-100 text-emerald-950 border-emerald-500",
  },
  rejected: {
    label: "Rejected",
    blurb: "You declined. Carts flushed — no mock orders.",
    tone: "bg-rose-100 text-rose-950 border-rose-400",
  },
  error: {
    label: "Error",
    blurb: "Something failed — check API is on :8000 and toast message.",
    tone: "bg-red-100 text-red-950 border-red-400",
  },
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
  const [phase, setPhase] = useState<DemoPhase>("idle");
  const [lastAction, setLastAction] = useState<string>("");
  const [lastRequestId, setLastRequestId] = useState<string>("");
  const [lastResult, setLastResult] = useState<string>("");

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
    const id = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(id);
  }, [refresh]);

  // If Telegram approve happens elsewhere, flip phase when our request leaves pending
  useEffect(() => {
    if (phase !== "awaiting_hitl" || !lastRequestId) return;
    const stillPending = approvals.some((a) => a.request_id === lastRequestId);
    if (!stillPending) {
      setPhase("done");
      setLastResult(`Approved elsewhere (Telegram or another tab) · ${lastRequestId}`);
      nexusToast("HITL decided — refresh timeline");
    }
  }, [approvals, phase, lastRequestId]);

  const post = async (path: string, body?: unknown) => {
    setBusy(true);
    try {
      const res = await fetch(apiUrl(path), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail || res.statusText);
      await refresh();
      return json;
    } catch (e) {
      setPhase("error");
      nexusToast(e instanceof Error ? e.message : "Concierge API unreachable");
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const triggerCalendar = async (kind: "host" | "dineout") => {
    const location = kind === "host" ? "Home" : "Italian Spesso";
    const description =
      kind === "host" ? "Hosting #host #swiggy" : "Dinner #dineout #swiggy";
    const label =
      kind === "host" ? "Zero-Touch Host (Instamart + Food)" : "Dineout table booking";

    setLastAction(label);
    setLastResult("");
    setPhase("staging");
    nexusToast(`Staging · ${label}`);

    try {
      const json = await post("/api/concierge/trigger", {
        event_title: kind === "host" ? "Housewarming #host" : "Team Dinner #swiggy",
        event_time: new Date().toISOString(),
        event_location: location,
        attendee_emails: ["dani@nexus.ai", "priya@nexus.ai"],
        description,
      });
      const rid = String(json.approval_request_id || "");
      setLastRequestId(rid);
      setPhase("awaiting_hitl");
      setLastResult(
        `Paused at HITL · ${rid || "no id"} · mode ${json.mode || "?"} · ~₹${json.total_cost ?? "?"} staged`
      );
      nexusToast("Paused for approval — check Telegram or Approve below");
    } catch {
      /* phase already error */
    }
  };

  const decide = async (requestId: string, approved: boolean) => {
    setLastRequestId(requestId);
    setPhase("executing");
    nexusToast(approved ? "Executing writes…" : "Rejecting…");
    try {
      const json = await post(
        approved ? `/api/hitl/approve/${requestId}` : `/api/hitl/reject/${requestId}`,
        approved ? { approved: true } : undefined
      );
      const status = String(json.status || (approved ? "COMPLETED" : "REJECTED"));
      setPhase(approved ? "done" : "rejected");
      setLastResult(`${status} · ${requestId}`);
      nexusToast(approved ? "Done — mock order placed" : "Rejected — nothing charged");
    } catch {
      /* error phase */
    }
  };

  const runSim = async (name: string, path: string, body?: unknown) => {
    setLastAction(name);
    setLastResult("");
    setPhase("staging");
    try {
      const json = await post(path, body);
      const rid =
        json?.approval?.request_id ||
        json?.approval_request_id ||
        json?.trigger?.approval?.request_id ||
        "";
      if (rid) {
        setLastRequestId(String(rid));
        setPhase("awaiting_hitl");
        setLastResult(`HITL pending · ${rid}`);
        nexusToast(`${name} · waiting for Approve`);
      } else if (json?.status === "pending_approval" || json?.approval) {
        const id = json.approval?.request_id || "";
        setLastRequestId(id);
        setPhase("awaiting_hitl");
        setLastResult(`HITL pending · ${id}`);
      } else {
        setPhase("done");
        setLastResult(JSON.stringify(json).slice(0, 120));
        nexusToast(`${name} · OK`);
      }
    } catch {
      /* error */
    }
  };

  const phaseUi = PHASE_COPY[phase];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn("space-y-4", className)}
    >
      <div className="border-2 border-black bg-gradient-to-r from-violet-600 to-emerald-600 p-4 text-white shadow-[4px_4px_0_0_#000]">
        <h2 className="font-display text-xl font-black uppercase tracking-widest">
          Concierge Ops
        </h2>
        <p className="mt-1 font-mono text-xs text-white/85">
          Demo script: Trigger → stage (read tools) → Approve → write tools. Mock MCP only.
        </p>
      </div>

      {/* Live demo banner */}
      <div className={cn("rounded-lg border-2 p-4", phaseUi.tone)}>
        <div className="flex flex-wrap items-center gap-2">
          {(phase === "staging" || phase === "executing") && (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          )}
          <p className="font-display text-sm font-black uppercase tracking-wide">
            {phaseUi.label}
          </p>
          {lastAction && (
            <span className="rounded border border-black/20 bg-white/70 px-2 py-0.5 font-mono text-[10px] font-bold">
              {lastAction}
            </span>
          )}
        </div>
        <p className="mt-1 font-sans text-sm font-medium">{phaseUi.blurb}</p>
        {lastResult && (
          <p className="mt-2 font-mono text-[11px] opacity-90">{lastResult}</p>
        )}
        {phase === "awaiting_hitl" && (
          <p className="mt-2 flex items-center gap-1.5 font-sans text-[12px] font-semibold">
            <MessageCircle className="h-3.5 w-3.5" aria-hidden />
            Open Telegram → tap Approve, or use the green button in Pending approvals →
          </p>
        )}
      </div>

      {/* Step legend */}
      <ol className="grid gap-2 sm:grid-cols-4">
        {[
          "1 Staging",
          "2 HITL pause",
          "3 Writes",
          "4 Done",
        ].map((step, i) => {
          const active =
            (phase === "staging" && i === 0) ||
            (phase === "awaiting_hitl" && i === 1) ||
            (phase === "executing" && i === 2) ||
            (phase === "done" && i === 3);
          return (
            <li
              key={step}
              className={cn(
                "rounded border px-2 py-1.5 text-center font-display text-[10px] font-black uppercase",
                active
                  ? "border-black bg-black text-white"
                  : "border-black/15 bg-white text-slate-500"
              )}
            >
              {step}
            </li>
          );
        })}
      </ol>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void refresh()}
          className="flex items-center gap-1 rounded border border-black/20 bg-white px-3 py-2 font-display text-[10px] font-black uppercase"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void triggerCalendar("host")}
          className="rounded border-2 border-black bg-neo-mint px-3 py-2 font-display text-[10px] font-black uppercase shadow-[3px_3px_0_0_#000] disabled:opacity-50"
        >
          {busy && lastAction.includes("Zero-Touch") ? "Staging…" : "Trigger Zero-Touch Host"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void triggerCalendar("dineout")}
          className="rounded border-2 border-black bg-indigo-100 px-3 py-2 font-display text-[10px] font-black uppercase shadow-[3px_3px_0_0_#000] disabled:opacity-50"
        >
          {busy && lastAction.includes("Dineout") ? "Staging…" : "Trigger Dineout"}
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="bento-card-soft p-3">
          <h3 className="mb-2 font-display text-xs font-black uppercase">Simulate QoL</h3>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void runSim("Rain / Rooftop", "/api/concierge/simulate/weather", {
                  rain_mm: 28,
                  temp_c: 21,
                  is_raining: true,
                  is_heavy_rain: true,
                  condition: "Heavy rain",
                })
              }
              className="flex items-center gap-1 rounded border border-black/20 bg-sky-100 px-2 py-1.5 font-display text-[10px] font-bold"
            >
              <CloudRain className="h-3.5 w-3.5" /> Rain / Rooftop
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void runSim("Guest SOS", "/api/concierge/simulate/guests", {
                  count: guestCount,
                })
              }
              className="flex items-center gap-1 rounded border border-black/20 bg-amber-100 px-2 py-1.5 font-display text-[10px] font-bold"
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
                void runSim("IPL chase", "/api/concierge/simulate/ipl", {
                  required_run_rate: 14,
                  is_timeout: true,
                  is_tense_chase: true,
                })
              }
              className="flex items-center gap-1 rounded border border-black/20 bg-rose-100 px-2 py-1.5 font-display text-[10px] font-bold"
            >
              <Trophy className="h-3.5 w-3.5" /> IPL chase
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void runSim("Fuel guard", "/api/concierge/simulate/fuel")}
              className="flex items-center gap-1 rounded border border-black/20 bg-violet-100 px-2 py-1.5 font-display text-[10px] font-bold"
            >
              <Zap className="h-3.5 w-3.5" /> Fuel guard
            </button>
          </div>
          {weather && (
            <p className="mt-2 font-mono text-[10px] text-slate-600">
              Weather: {String(weather.condition)} · {String(weather.temp_c)}°C · rain{" "}
              {String(weather.rain_mm)}mm
            </p>
          )}
        </div>

        <div className="rounded-lg border-2 border-amber-500 bg-amber-50 p-3">
          <h3 className="mb-2 font-display text-xs font-black uppercase">
            Pending approvals ({approvals.length})
          </h3>
          <AnimatePresence mode="popLayout">
            <div className="max-h-64 space-y-2 overflow-y-auto">
              {approvals.length === 0 && (
                <p className="font-mono text-[10px] text-slate-500">
                  No pending HITL — trigger a workflow above.
                </p>
              )}
              {approvals.map((a) => (
                <motion.div
                  key={a.request_id}
                  layout
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "rounded border-2 bg-white p-2",
                    a.request_id === lastRequestId
                      ? "border-amber-600 shadow-[3px_3px_0_0_#000]"
                      : "border-black/15"
                  )}
                >
                  <p className="font-display text-[11px] font-bold">{a.title}</p>
                  <p className="font-mono text-[10px] text-slate-600 line-clamp-2">{a.summary}</p>
                  <p className="font-mono text-[9px] text-slate-400">
                    {a.request_id} · {a.trigger_type}
                  </p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void decide(a.request_id, true)}
                      className="flex items-center gap-1 rounded border-2 border-black bg-emerald-400 px-2 py-1 font-display text-[10px] font-black disabled:opacity-50"
                    >
                      <Check className="h-3 w-3" /> Approve
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void decide(a.request_id, false)}
                      className="flex items-center gap-1 rounded border border-black/20 bg-white px-2 py-1 font-display text-[10px] font-black"
                    >
                      <X className="h-3 w-3" /> Reject
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          </AnimatePresence>
        </div>
      </div>

      <div className="rounded-lg border border-black/20 bg-slate-900 p-3 text-white">
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
