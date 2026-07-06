"use client";

import { motion } from "framer-motion";
import { Truck } from "lucide-react";
import { useEffect, useState } from "react";

import { callMcp } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { neoSpring } from "@/lib/motion";

export function LiveTrackCard({
  vertical,
  orderId,
}: {
  vertical: "food" | "im";
  orderId: string;
}) {
  const { requestId } = useNexusSession();
  const [eta, setEta] = useState(30);
  const [spoken, setSpoken] = useState("");

  useEffect(() => {
    void (async () => {
      const method = vertical === "food" ? "track_food_order" : "track_order";
      const res = await callMcp(vertical === "food" ? "food" : "im", method, { orderId }, requestId);
      if (res.success && res.data) {
        const d = res.data as { eta_mins?: number; deliveryTimeSpoken?: string };
        setEta(d.eta_mins ?? 25);
        setSpoken(d.deliveryTimeSpoken ?? `about ${d.eta_mins} minutes`);
      }
    })();
  }, [vertical, orderId, requestId]);

  const pct = Math.max(8, Math.min(92, 100 - eta * 2));

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className="border-2 border-black bg-sky-50 p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
    >
      <div className="mb-2 flex items-center gap-2">
        <Truck className="h-4 w-4" />
        <span className="font-display text-xs font-black uppercase">Live track · {orderId}</span>
      </div>
      <p className="mb-2 text-sm font-medium">{spoken || `ETA ~${eta} min`}</p>
      <div className="h-3 border-2 border-black bg-white">
        <motion.div
          className="h-full bg-sky-500"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
      </div>
    </motion.div>
  );
}
