"use client";

import { Play } from "lucide-react";
import { motion } from "framer-motion";

import { type NexusReviewerScenario } from "@/lib/nexus-settings-storage";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";

const WOW_PROMPT = "Plan my evening for 12 guests";

export function NexusWowLauncher({
  onRunDemo,
  className,
}: {
  onRunDemo: (scenario: NexusReviewerScenario, prompt: string) => void;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={neoSpring}
      className={className}
    >
      <button
        type="button"
        onClick={() => {
          onRunDemo("chrono_host", WOW_PROMPT);
          nexusToast("WOW demo · Chrono-Host across 3 Swiggy verticals…");
        }}
        className="group flex w-full items-center justify-center gap-2 border-4 border-black bg-gradient-to-r from-violet-600 via-indigo-600 to-emerald-600 px-4 py-3 font-display text-sm font-black uppercase tracking-widest text-white shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] transition-transform hover:translate-y-[-2px] hover:shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]"
      >
        <Play className="h-4 w-4 fill-white" aria-hidden />
        Run 60s WOW demo
      </button>
      <p className="mt-2 text-center font-mono text-[10px] text-slate-600">
        One click → 12+ MCP tools · Dineout + Instamart + Food bundle
      </p>
    </motion.div>
  );
}

export { WOW_PROMPT };
