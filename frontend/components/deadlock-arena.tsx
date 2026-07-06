"use client";

import { Copy, Users } from "lucide-react";
import { motion } from "framer-motion";

import { DineoutSlotGrid } from "@/components/dineout-slot-grid";
import { neoSpring } from "@/lib/motion";
import type { FeedItem } from "@/lib/api";
import { nexusToast } from "@/lib/nexus-toast-bus";

export function JoinStripCard({ item }: { item: FeedItem }) {
  const url = String(item.meta?.joinUrl ?? item.meta?.url ?? "https://nexus.demo/join/deadlock-abc123");

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className="border-2 border-black bg-yellow-50 p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
    >
      <div className="mb-2 flex items-center gap-2">
        <Users className="h-4 w-4" />
        <span className="font-display text-xs font-black uppercase">{item.title}</span>
      </div>
      <p className="text-sm text-slate-700">{item.subtitle}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <code className="flex-1 truncate border-2 border-black bg-white px-2 py-1 font-mono text-[10px]">
          {url}
        </code>
        <button
          type="button"
          className="flex items-center gap-1 border-2 border-black bg-black px-3 py-1 text-[10px] font-bold uppercase text-white"
          onClick={() => {
            void navigator.clipboard.writeText(url).then(() => nexusToast("Join link copied"));
          }}
        >
          <Copy className="h-3 w-3" /> Copy
        </button>
      </div>
      <p className="mt-2 font-mono text-[10px] text-slate-500">
        RSVP {String(item.meta?.rsvpCount ?? 4)}/{String(item.meta?.partySize ?? 6)} (mock)
      </p>
    </motion.div>
  );
}

export function DeadlockArena({
  partySize,
  budgetInr,
  restaurantId = "do_italian_804",
}: {
  partySize: number;
  budgetInr: number;
  restaurantId?: string;
}) {
  return (
    <div className="space-y-4">
      <div className="border-2 border-black bg-white p-3">
        <p className="font-display text-[10px] font-black uppercase text-slate-500">Party budget</p>
        <div className="mt-1 h-2 border-2 border-black bg-slate-100">
          <div className="h-full w-2/3 bg-indigo-500" />
        </div>
        <p className="mt-1 text-xs font-bold">₹{budgetInr}/head · {partySize} guests · Pune</p>
      </div>
      <DineoutSlotGrid restaurantId={restaurantId} partySize={partySize} />
    </div>
  );
}
