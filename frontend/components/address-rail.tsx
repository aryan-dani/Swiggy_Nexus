"use client";

import { MapPin } from "lucide-react";
import { motion } from "framer-motion";

import { useNexusSession } from "@/lib/nexus-session-context";
import { neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function AddressRail({ className }: { className?: string }) {
  const { addresses, selectedAddressId, setSelectedAddressId, refreshCarts } = useNexusSession();

  if (!addresses.length) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn(
        "flex flex-wrap items-center gap-2 border-2 border-black bg-white p-3 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]",
        className
      )}
    >
      <MapPin className="h-4 w-4 shrink-0 text-indigo-600" aria-hidden />
      <span className="font-display text-[10px] font-black uppercase tracking-widest text-slate-500">
        Deliver to
      </span>
      {addresses.map((a) => {
        const on = a.addressId === selectedAddressId;
        return (
          <button
            key={a.addressId}
            type="button"
            onClick={() => {
              setSelectedAddressId(a.addressId);
              void refreshCarts();
            }}
            className={cn(
              "rounded border-2 px-3 py-1.5 font-display text-[10px] font-black uppercase tracking-wide transition-colors",
              on
                ? "border-black bg-indigo-50 text-indigo-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                : "border-black/20 bg-slate-50 text-slate-600 hover:bg-white"
            )}
          >
            {a.label}
          </button>
        );
      })}
    </motion.div>
  );
}
