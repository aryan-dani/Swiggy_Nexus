"use client";

import { Calendar, Heart, MessageSquare, Sparkles, Trash2, Umbrella, Users, UtensilsCrossed } from "lucide-react";
import { motion } from "framer-motion";
import { useCallback } from "react";

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
  "border-black bg-indigo-50 text-indigo-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]";
const chipOff =
  "border-black/20 bg-white text-slate-600 hover:bg-slate-50 border-2";

export function NexusSignalsBar({
  settings,
  onSettingsChange,
  onReset,
  onSuggestPrompt,
  className,
}: NexusSignalsBarProps) {
  const patch = useCallback(
    (partial: Partial<NexusDemoSettings>, toast?: string) => {
      const next = saveDemoSettings(partial);
      onSettingsChange(next);
      if (toast) nexusToast(toast);
    },
    [onSettingsChange]
  );

const SCENARIO_PROMPTS: Partial<Record<NexusReviewerScenario, string>> = {
  deadlock: "Break our dinner deadlock for 6 in Pune, budget ₹800 per head",
  flowstate: "I'm deep in flow — fuel me with coffee and a protein snack on Instamart",
  zerowaste: "Cook paneer tikka masala — only order missing pantry ingredients",
  chrono_host: "Plan my evening for 12 guests",
  sentiment: "Rough day — suggest comfort food without ordering yet",
  dialectic: "Debate AI ethics — winner picks dinner cuisine",
};

  const applyScenario = useCallback(
    (id: NexusReviewerScenario, label: string) => {
      patch(
        { reviewerScenario: id },
        id ? `Scenario: ${label}` : "Cleared scenario preset"
      );
      const prompt = SCENARIO_PROMPTS[id];
      if (prompt) onSuggestPrompt?.(prompt);
      if (!id) {
        onReset?.();
      }
    },
    [patch, onReset, onSuggestPrompt]
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn(
        "space-y-3 border-2 border-black bg-neo-mint/30 p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]",
        className
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Sparkles className="h-4 w-4 shrink-0 text-black" aria-hidden />
        <h2 className="font-display text-xs font-black uppercase tracking-widest text-black">
          Reviewer · Signals & scenarios
        </h2>
      </div>
      <p className="font-sans text-[11px] font-medium leading-snug text-slate-700">
        Synthetic context for the Swiggy Nexus pitch (no real calendar or weather).
        Toggles feed into <strong>Planner</strong> traces; scenarios bias vertical routing
        (Dineout / Instamart / Food).
      </p>

      <div className="flex flex-wrap gap-2">
        <motion.button
          type="button"
          whileTap={{ scale: 0.98 }}
          className={cn(
            "rounded border-2 px-3 py-1.5 font-display text-[10px] font-black uppercase tracking-wide",
            settings.signalDeepWorkBlock ? chipOn : chipOff
          )}
          onClick={() =>
            patch(
              { signalDeepWorkBlock: !settings.signalDeepWorkBlock },
              settings.signalDeepWorkBlock
                ? "Deep-work signal off"
                : "Deep-work block (synthetic) on"
            )
          }
        >
          Deep-work block
        </motion.button>
        <motion.button
          type="button"
          whileTap={{ scale: 0.98 }}
          className={cn(
            "flex items-center gap-1.5 rounded border-2 px-3 py-1.5 font-display text-[10px] font-black uppercase tracking-wide",
            settings.signalRainInPune ? chipOn : chipOff
          )}
          onClick={() =>
            patch(
              { signalRainInPune: !settings.signalRainInPune },
              settings.signalRainInPune ? "Rain cue off" : "Rain in Pune (synthetic) on"
            )
          }
        >
          <Umbrella className="h-3.5 w-3.5" aria-hidden />
          Rain · Pune
        </motion.button>
        <motion.button
          type="button"
          whileTap={{ scale: 0.98 }}
          className={cn(
            "flex items-center gap-1.5 rounded border-2 px-3 py-1.5 font-display text-[10px] font-black uppercase tracking-wide",
            settings.signalWatchParty ? chipOn : chipOff
          )}
          onClick={() =>
            patch(
              { signalWatchParty: !settings.signalWatchParty },
              settings.signalWatchParty ? "Watch party off" : "Watch party (synthetic) on"
            )
          }
        >
          <Users className="h-3.5 w-3.5" aria-hidden />
          Watch party
        </motion.button>
      </div>

      <div className="space-y-2">
        <label className="flex items-center gap-2 font-display text-[10px] font-black uppercase text-slate-500">
          <Heart className="h-3.5 w-3.5" aria-hidden />
          Mood score · {settings.signalMoodScore.toFixed(2)}
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(settings.signalMoodScore * 100)}
          onChange={(e) =>
            patch({ signalMoodScore: Number(e.target.value) / 100 }, "Mood signal updated")
          }
          className="w-full accent-rose-600"
        />
      </div>

      <div className="border-t-2 border-dashed border-black/15 pt-3">
        <p className="mb-2 font-display text-[10px] font-black uppercase tracking-widest text-slate-500">
          Story presets
        </p>
        <div className="flex flex-wrap gap-2">
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            className={cn(
              "flex items-center gap-1.5 rounded border-2 px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide",
              settings.reviewerScenario === "deadlock" ? chipOn : chipOff
            )}
            onClick={() =>
              applyScenario(
                settings.reviewerScenario === "deadlock" ? "" : "deadlock",
                "Social Deadlock Breaker"
              )
            }
          >
            <UtensilsCrossed className="h-3.5 w-3.5" aria-hidden />
            Deadlock breaker
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            className={cn(
              "flex items-center gap-1.5 rounded border-2 px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide",
              settings.reviewerScenario === "flowstate" ? chipOn : chipOff
            )}
            onClick={() =>
              applyScenario(
                settings.reviewerScenario === "flowstate" ? "" : "flowstate",
                "Flow-state fueler"
              )
            }
          >
            Flow-state fueler
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            className={cn(
              "flex items-center gap-1.5 rounded border-2 px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide",
              settings.reviewerScenario === "zerowaste" ? chipOn : chipOff
            )}
            onClick={() =>
              applyScenario(
                settings.reviewerScenario === "zerowaste" ? "" : "zerowaste",
                "Zero-waste meal"
              )
            }
          >
            Zero-waste meal
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            className={cn(
              "flex items-center gap-1.5 rounded border-2 px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide",
              settings.reviewerScenario === "chrono_host" ? chipOn : chipOff
            )}
            onClick={() =>
              applyScenario(
                settings.reviewerScenario === "chrono_host" ? "" : "chrono_host",
                "Chrono-Host evening"
              )
            }
          >
            <Calendar className="h-3.5 w-3.5" aria-hidden />
            Chrono-Host
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            className={cn(
              "flex items-center gap-1.5 rounded border-2 px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide",
              settings.reviewerScenario === "sentiment" ? chipOn : chipOff
            )}
            onClick={() =>
              applyScenario(
                settings.reviewerScenario === "sentiment" ? "" : "sentiment",
                "Sentiment Thermostat"
              )
            }
          >
            <Heart className="h-3.5 w-3.5" aria-hidden />
            Sentiment
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            className={cn(
              "flex items-center gap-1.5 rounded border-2 px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide",
              settings.reviewerScenario === "dialectic" ? chipOn : chipOff
            )}
            onClick={() =>
              applyScenario(
                settings.reviewerScenario === "dialectic" ? "" : "dialectic",
                "Dialectic Dinner"
              )
            }
          >
            <MessageSquare className="h-3.5 w-3.5" aria-hidden />
            Dialectic
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            className={cn("rounded border-2 px-2 py-2", chipOff)}
            title="Reset scenario"
            onClick={() => applyScenario("", "cleared")}
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden />
          </motion.button>
        </div>
        <p className="mt-2 min-h-8 font-mono text-[10px] text-slate-500">
          {settings.reviewerScenario === "deadlock" && (
            <>Deadlock demo uses party {settings.deadlockPartySize} · ₹{settings.deadlockBudgetInr}/head cap · {settings.deadlockCity}. Adjust in Settings.</>
          )}
          {settings.reviewerScenario === "flowstate" && (
            <>Flow-state fueler assumes deep work block. Biases towards quick delivery.</>
          )}
          {settings.reviewerScenario === "zerowaste" && (
            <>Zero-waste focuses on Instamart leftovers or healthy meal substitutions.</>
          )}
          {settings.reviewerScenario === "chrono_host" && (
            <>Chrono-Host plans dinner out + party supplies + dessert. Try: &quot;Plan my evening for 12&quot;.</>
          )}
          {settings.reviewerScenario === "sentiment" && (
            <>Sentiment Thermostat stages comfort carts — never auto-places. Mood at {settings.signalMoodScore.toFixed(2)}.</>
          )}
          {settings.reviewerScenario === "dialectic" && (
            <>Dialectic Dinner triggers commerce on debate rounds — use Arena buttons or chat.</>
          )}
          {!settings.reviewerScenario && (
            <>Select a story preset to inject mock context.</>
          )}
        </p>
      </div>
    </motion.div>
  );
}
