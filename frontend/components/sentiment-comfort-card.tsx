"use client";

import { Heart } from "lucide-react";
import { motion } from "framer-motion";

import { neoSpring } from "@/lib/motion";
import type { FeedItem } from "@/lib/api";

export function SentimentComfortCard({ item }: { item: FeedItem }) {
  const meta = (item.meta ?? {}) as Record<string, unknown>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className="border-2 border-black bg-rose-50 p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
    >
      <div className="mb-2 flex items-center gap-2">
        <Heart className="h-4 w-4 text-rose-600" />
        <span className="rounded border-2 border-rose-700 bg-rose-700 px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-white">
          Staged · not placed
        </span>
      </div>
      <p className="font-display font-black">{item.title}</p>
      <p className="mt-1 text-sm text-slate-700">{item.subtitle}</p>
      {meta.imTotal != null && (
        <p className="mt-2 text-xs font-bold">Instamart comfort · ₹{String(meta.imTotal)}</p>
      )}
      {meta.foodTotal != null && (
        <p className="text-xs font-bold">Food dessert option · ₹{String(meta.foodTotal)}</p>
      )}
    </motion.div>
  );
}
