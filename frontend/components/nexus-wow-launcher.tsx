"use client";

import { Play } from "lucide-react";
import { motion } from "framer-motion";

import { type NexusReviewerScenario } from "@/lib/nexus-settings-storage";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";
import { pickWowVariant, type WowVariant } from "@/lib/wow-variants";

export function NexusWowLauncher({
  onRunDemo,
  className,
}: {
  onRunDemo: (scenario: NexusReviewerScenario, prompt: string, variant?: WowVariant) => void;
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
          const variant = pickWowVariant();
          onRunDemo("chrono_host", variant.prompt, variant);
          nexusToast(`WOW · ${variant.title} — fresh plan each click`);
        }}
        className="group flex w-full items-center justify-center gap-2 border-4 border-black bg-gradient-to-r from-violet-600 via-indigo-600 to-emerald-600 px-4 py-3 font-display text-sm font-black uppercase tracking-widest text-white shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] transition-transform hover:translate-y-[-2px] hover:shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]"
      >
        <Play className="h-4 w-4 fill-white" aria-hidden />
        Run 60s WOW demo
      </button>
      <p className="mt-2 text-center font-mono text-[10px] text-slate-600">
        Rotating nights · Dineout + Instamart + Food — never the same script twice
      </p>
    </motion.div>
  );
}
