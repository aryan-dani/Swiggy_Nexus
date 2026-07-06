"use client";

import { motion } from "framer-motion";
import { useState } from "react";

import { neoSpring } from "@/lib/motion";

const ROUNDS = [
  { pro: "AI augments human creativity rather than replacing it.", con: "Automation erodes entry-level jobs faster than we retrain.", score: "Pro +1" },
  { pro: "Open models democratize innovation.", con: "Unchecked models amplify bias at scale.", score: "Stalemate" },
];

export function DialecticArena({
  onTriggerCommerce,
}: {
  onTriggerCommerce?: (action: string) => void;
}) {
  const [round, setRound] = useState(0);
  const r = ROUNDS[round] ?? ROUNDS[0];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={neoSpring}
      className="grid gap-3 border-4 border-black bg-slate-50 p-4"
    >
      <p className="text-center font-display text-xs font-black uppercase tracking-widest">
        Dialectic Dinner · Round {round + 1}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="border-2 border-black bg-blue-50 p-3">
          <p className="mb-1 font-display text-[10px] font-black uppercase text-blue-800">Pro</p>
          <p className="text-sm font-medium">{r.pro}</p>
        </div>
        <div className="border-2 border-black bg-red-50 p-3">
          <p className="mb-1 font-display text-[10px] font-black uppercase text-red-800">Con</p>
          <p className="text-sm font-medium">{r.con}</p>
        </div>
      </div>
      <div className="border-2 border-dashed border-black bg-white p-2 text-center font-mono text-xs font-bold">
        Referee · {r.score}
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="border-2 border-black bg-emerald-600 px-3 py-2 text-[10px] font-black uppercase text-white"
          onClick={() => {
            onTriggerCommerce?.("loser snacks checkout");
            setRound((x) => Math.min(x + 1, ROUNDS.length - 1));
          }}
        >
          Round win → IM checkout
        </button>
        <button
          type="button"
          className="border-2 border-black bg-orange-500 px-3 py-2 text-[10px] font-black uppercase text-white"
          onClick={() => onTriggerCommerce?.("winner cuisine food order")}
        >
          Winner picks dinner
        </button>
      </div>
    </motion.div>
  );
}
