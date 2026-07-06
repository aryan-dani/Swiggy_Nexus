"use client";

import { CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

import { neoSpring } from "@/lib/motion";

export function BookingTicket({
  venueName,
  slot,
  guests,
  bookingId,
}: {
  venueName: string;
  slot: string;
  guests: number;
  bookingId: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={neoSpring}
      className="border-4 border-black bg-white p-5 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
    >
      <div className="mb-3 flex items-center gap-2 text-emerald-700">
        <CheckCircle2 className="h-5 w-5" />
        <span className="font-display text-sm font-black uppercase">Booking confirmed</span>
      </div>
      <p className="font-display text-lg font-black">{venueName}</p>
      <p className="mt-1 text-sm text-slate-700">
        Table for {guests} · {slot}
      </p>
      <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-slate-500">
        ID {bookingId}
      </p>
      <div className="mt-4 flex h-16 items-center justify-center border-2 border-dashed border-black bg-slate-100 font-mono text-xs text-slate-400">
        QR · mock
      </div>
    </motion.div>
  );
}
