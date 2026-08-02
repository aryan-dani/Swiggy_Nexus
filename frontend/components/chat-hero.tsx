"use client";

import { Calendar, Play, Shield, UtensilsCrossed, Zap } from "lucide-react";
import { motion } from "framer-motion";

import { type NexusReviewerScenario } from "@/lib/nexus-settings-storage";
import { neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { pickWowVariant, type WowVariant } from "@/lib/wow-variants";

export type ChatHeroProps = {
  onRunWow: (scenario: NexusReviewerScenario, prompt: string, variant?: WowVariant) => void;
  onPickScenario: (scenario: NexusReviewerScenario, prompt: string) => void;
  onOpenConcierge: () => void;
  className?: string;
};

const CARDS = [
  {
    id: "wow" as const,
    title: "Run 60s WOW demo",
    desc: "Each click stages a fresh evening — Dineout + Instamart + Food. Watch the Demo Director.",
    icon: Play,
    primary: true,
  },
  {
    id: "deadlock" as const,
    title: "Deadlock breaker",
    desc: "Pick a table when the group can't decide — slot grid + join strip.",
    icon: UtensilsCrossed,
    primary: false,
    scenario: "deadlock" as NexusReviewerScenario,
    prompt: "Break our dinner deadlock for 6 in Pune, budget ₹800 per head",
  },
  {
    id: "flowstate" as const,
    title: "Flow-state fueler",
    desc: "Deep-work snacks via Instamart — coffee + protein, no ceremony.",
    icon: Zap,
    primary: false,
    scenario: "flowstate" as NexusReviewerScenario,
    prompt: "I'm deep in flow — fuel me with coffee and a protein snack on Instamart",
  },
  {
    id: "concierge" as const,
    title: "Concierge Ops",
    desc: "HITL approvals, rain/guest/IPL simulations, and QoL timeline.",
    icon: Shield,
    primary: false,
  },
];

export function ChatHero({ onRunWow, onPickScenario, onOpenConcierge, className }: ChatHeroProps) {
  return (
    <div className={cn("space-y-4", className)}>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-violet-700" aria-hidden />
          <h2 className="font-display text-base font-black uppercase tracking-tight text-black">
            Swiggy Nexus
          </h2>
        </div>
        <p className="max-w-md font-sans text-sm font-medium leading-snug text-slate-600">
          One prompt orchestrates Dineout, Instamart and Food via 35 MCP tools. Pick a path —
          the Activity rail on the right shows staged results.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <motion.button
              key={card.id}
              type="button"
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
              transition={neoSpring}
              onClick={() => {
                if (card.id === "wow") {
                  const variant = pickWowVariant();
                  onRunWow("chrono_host", variant.prompt, variant);
                } else if (card.id === "concierge") onOpenConcierge();
                else if (card.scenario && card.prompt) onPickScenario(card.scenario, card.prompt);
              }}
              className={cn(
                "flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors",
                card.primary
                  ? "border-2 border-black bg-gradient-to-br from-violet-600 via-indigo-600 to-emerald-600 text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                  : "bento-card-soft hover:bg-slate-50"
              )}
            >
              <span
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded border",
                  card.primary ? "border-white/40 bg-white/15" : "border-black/15 bg-white"
                )}
              >
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <span
                className={cn(
                  "font-display text-xs font-black uppercase tracking-wide",
                  card.primary ? "text-white" : "text-black"
                )}
              >
                {card.title}
              </span>
              <span
                className={cn(
                  "font-sans text-[11px] font-medium leading-snug",
                  card.primary ? "text-white/90" : "text-slate-600"
                )}
              >
                {card.desc}
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

export { pickWowVariant };
