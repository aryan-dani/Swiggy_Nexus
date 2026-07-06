"use client";

import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

import { callMcp, mcpErrorMessage } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Slot = {
  slotId: number;
  label: string;
  deals?: { itemId: string; bookingPrice: number; title: string }[];
};

export function DineoutSlotGrid({
  restaurantId,
  partySize,
  onBooked,
  className,
}: {
  restaurantId: string;
  partySize: number;
  onBooked?: (bookingId: string) => void;
  className?: string;
}) {
  const { requestId } = useNexusSession();
  const [slots, setSlots] = useState<Slot[]>([]);
  const [venueName, setVenueName] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    const res = await callMcp(
      "dineout",
      "check_availability",
      { restaurantId, guestCount: partySize, partySize, date: "2026-07-12" },
      requestId
    );
    if (res.success && res.data) {
      const d = res.data as { slots?: Slot[]; name?: string };
      setSlots(d.slots ?? []);
      setVenueName(d.name ?? "");
    }
  }, [restaurantId, partySize, requestId]);

  useEffect(() => {
    if (restaurantId) void load();
  }, [restaurantId, load]);

  const book = async (slot: Slot) => {
    setBusy(slot.slotId);
    const deal = slot.deals?.[0];
    const res = await callMcp(
      "dineout",
      "book_table",
      {
        restaurantId,
        partySize,
        slot: slot.label,
        slotId: slot.slotId,
        itemId: deal?.itemId,
      },
      requestId
    );
    setBusy(null);
    if (res.success && res.data) {
      const bid = (res.data as { bookingId?: string }).bookingId ?? "";
      nexusToast(`Table booked · ${slot.label}`);
      onBooked?.(bid);
    } else {
      nexusToast(mcpErrorMessage(res, "Booking failed"));
    }
  };

  if (!slots.length) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn("border-2 border-black bg-indigo-50 p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]", className)}
    >
      <p className="mb-2 font-display text-xs font-black uppercase text-indigo-900">
        {venueName || "Dineout"} · slots for {partySize}
      </p>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {slots.map((s) => (
          <button
            key={s.slotId}
            type="button"
            disabled={busy !== null}
            onClick={() => void book(s)}
            className="border-2 border-black bg-white px-2 py-3 text-center font-mono text-sm font-bold hover:bg-indigo-100 disabled:opacity-50"
          >
            {s.label}
            {s.deals?.[0]?.bookingPrice === 0 && (
              <span className="mt-1 block text-[9px] font-sans font-bold uppercase text-emerald-700">Free</span>
            )}
          </button>
        ))}
      </div>
    </motion.div>
  );
}
