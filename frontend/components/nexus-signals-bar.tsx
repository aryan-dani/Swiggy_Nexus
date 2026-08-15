"use client";

import {
  Calendar,
  ChevronDown,
  Heart,
  MessageSquare,
  Sparkles,
  Trash2,
  Umbrella,
  Users,
  UtensilsCrossed,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useState } from "react";

import {
  type NexusDemoSettings,
  type NexusReviewerScenario,
  saveDemoSettings,
} from "@/lib/nexus-settings-storage";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";

export type NexusSignalsBarProps = {
  settings: NexusDemoSettings;
  onSettingsChange: (next: NexusDemoSettings) => void;
  onReset?: () => void;
  onSuggestPrompt?: (text: string) => void;
  className?: string;
};

const chipOn =
  "border-black bg-indigo-50 text-indigo-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]";
const chipOff = "border-black/20 bg-white text-slate-600 hover:bg-slate-50 border";

const SCENARIO_LABELS: Record<string, string> = {
  deadlock: "Deadlock",
  flowstate: "Flow-state",
  zerowaste: "Zero-waste",
  chrono_host: "Chrono-Host",
  sentiment: "Sentiment",
  dialectic: "Dialectic",
};

const SCENARIO_PROMPTS: Partial<Record<NexusReviewerScenario, string>> = {
  deadlock: "Break our dinner deadlock for 6 in Pune, budget ₹800 per head",
  flowstate: "I'm deep in flow — fuel me with coffee and a protein snack on Instamart",
  zerowaste: "Cook paneer tikka masala — only order missing pantry ingredients",
  chrono_host: "Plan my evening for 12 guests",
  sentiment: "Rough day — suggest comfort food without ordering yet",
  dialectic: "Debate AI ethics — winner picks dinner cuisine",
};

export function NexusSignalsBar({
  settings,
  onSettingsChange,
  onReset,
  onSuggestPrompt,
  className,
}: NexusSignalsBarProps) {
  const [open, setOpen] = useState(false);

  const patch = useCallback(
    (partial: Partial<NexusDemoSettings>, toast?: string) => {
      const next = saveDemoSettings(partial);
      onSettingsChange(next);
      if (toast) nexusToast(toast);
    },
    [onSettingsChange]
  );

  const applyScenario = useCallback(
    (id: NexusReviewerScenario, label: string) => {
      patch({ reviewerScenario: id }, id ? `Scenario: ${label}` : "Cleared scenario preset");
      const prompt = SCENARIO_PROMPTS[id];
      if (prompt) onSuggestPrompt?.(prompt);
      if (!id) onReset?.();
    },
    [patch, onReset, onSuggestPrompt]
  );

  const signalsOn = [
    settings.signalDeepWorkBlock,
    settings.signalRainInPune,
    settings.signalWatchParty,
  ].filter(Boolean).length;

  const scenarioLabel = settings.reviewerScenario
    ? SCENARIO_LABELS[settings.reviewerScenario] ?? settings.reviewerScenario
    : "None";

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn("rounded border border-black/15 bg-slate-50/80", className)}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left"
      >
        <Sparkles className="h-3.5 w-3.5 shrink-0 text-violet-700" aria-hidden />
        <span className="min-w-0 flex-1 truncate font-sans text-[11px] font-medium text-slate-700">
          Scenario:{" "}
          <strong className="text-black">{scenarioLabel}</strong>
          {" · "}
          MCP:{" "}
          <strong className="text-black">{settings.useMockMcp ? "Mock" : "Live"}</strong>
          {" · "}
          Signals ({signalsOn} on)
        </span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform", open && "rotate-180")}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-black/10"
          >
            <div className="space-y-3 p-3">
              <p className="font-display text-[10px] font-black uppercase tracking-widest text-slate-500">
                Story presets
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(
                  [
                    ["deadlock", "Deadlock", UtensilsCrossed],
                    ["flowstate", "Flow-state", null],
                    ["zerowaste", "Zero-waste", null],
                    ["chrono_host", "Chrono-Host", Calendar],
                    ["sentiment", "Sentiment", Heart],
                    ["dialectic", "Dialectic", MessageSquare],
                  ] as const
                ).map(([id, label, Icon]) => (
                  <button
                    key={id}
                    type="button"
                    className={cn(
                      "inline-flex items-center gap-1 rounded px-2.5 py-1.5 font-display text-[10px] font-black uppercase tracking-wide",
                      settings.reviewerScenario === id ? chipOn : chipOff
                    )}
                    onClick={() =>
                      applyScenario(
                        settings.reviewerScenario === id ? ("" as NexusReviewerScenario) : id,
                        label
                      )
                    }
                  >
                    {Icon ? <Icon className="h-3 w-3" aria-hidden /> : null}
                    {label}
                  </button>
                ))}
                <button
                  type="button"
                  className={cn("rounded px-2 py-1.5", chipOff)}
                  title="Reset scenario"
                  onClick={() => applyScenario("" as NexusReviewerScenario, "cleared")}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>

              <p className="font-display text-[10px] font-black uppercase tracking-widest text-slate-500">
                Swiggy MCP
              </p>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  className={cn(
                    "rounded px-2.5 py-1.5 font-display text-[10px] font-black uppercase",
                    settings.useMockMcp ? chipOn : chipOff
                  )}
                  onClick={() =>
                    patch({ useMockMcp: true }, "MCP · Mock (offline catalog)")
                  }
                >
                  Mock
                </button>
                <button
                  type="button"
                  className={cn(
                    "rounded px-2.5 py-1.5 font-display text-[10px] font-black uppercase",
                    !settings.useMockMcp ? chipOn : chipOff
                  )}
                  onClick={() =>
                    patch(
                      { useMockMcp: false },
                      "MCP · Live (needs SWIGGY_OAUTH_TOKEN on API)"
                    )
                  }
                >
                  Live
                </button>
              </div>

              <p className="font-display text-[10px] font-black uppercase tracking-widest text-slate-500">
                Synthetic signals
              </p>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  className={cn(
                    "rounded px-2.5 py-1.5 font-display text-[10px] font-black uppercase",
                    settings.signalDeepWorkBlock ? chipOn : chipOff
                  )}
                  onClick={() =>
                    patch(
                      { signalDeepWorkBlock: !settings.signalDeepWorkBlock },
                      settings.signalDeepWorkBlock ? "Deep-work off" : "Deep-work on"
                    )
                  }
                >
                  Deep-work
                </button>
                <button
                  type="button"
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-2.5 py-1.5 font-display text-[10px] font-black uppercase",
                    settings.signalRainInPune ? chipOn : chipOff
                  )}
                  onClick={() =>
                    patch(
                      { signalRainInPune: !settings.signalRainInPune },
                      settings.signalRainInPune ? "Rain off" : "Rain · Pune on"
                    )
                  }
                >
                  <Umbrella className="h-3 w-3" aria-hidden />
                  Rain
                </button>
                <button
                  type="button"
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-2.5 py-1.5 font-display text-[10px] font-black uppercase",
                    settings.signalWatchParty ? chipOn : chipOff
                  )}
                  onClick={() =>
                    patch(
                      { signalWatchParty: !settings.signalWatchParty },
                      settings.signalWatchParty ? "Watch party off" : "Watch party on"
                    )
                  }
                >
                  <Users className="h-3 w-3" aria-hidden />
                  Watch party
                </button>
              </div>

              <label className="block space-y-1">
                <span className="flex items-center gap-1.5 font-display text-[10px] font-black uppercase text-slate-500">
                  <Heart className="h-3 w-3" aria-hidden />
                  Mood · {settings.signalMoodScore.toFixed(2)}
                </span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={Math.round(settings.signalMoodScore * 100)}
                  onChange={(e) =>
                    patch({ signalMoodScore: Number(e.target.value) / 100 })
                  }
                  className="w-full accent-rose-600"
                />
              </label>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
