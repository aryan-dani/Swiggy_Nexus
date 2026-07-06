"use client";

import { MapPin, ShoppingBag, ShoppingCart, Sparkles, UtensilsCrossed } from "lucide-react";
import { motion } from "framer-motion";

import { getToolCoverage } from "@/lib/mcp-client";
import { getOrchestratorInfo } from "@/lib/orchestrator-info";
import { useNexusSession } from "@/lib/nexus-session-context";
import { neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

export function NexusCommandCenter({
  onOpenFoodCart,
  onOpenImCart,
  className,
}: {
  onOpenFoodCart?: () => void;
  onOpenImCart?: () => void;
  className?: string;
}) {
  const { addresses, selectedAddressId, carts, bookingsCount } = useNexusSession();
  const [coverage, setCoverage] = useState({ used: 0, total: 33 });
  const orch = getOrchestratorInfo();
  const pct = Math.min(100, Math.round((coverage.used / coverage.total) * 100));

  useEffect(() => {
    const sync = () => setCoverage(getToolCoverage());
    sync();
    window.addEventListener("nexus-mcp-call", sync);
    return () => window.removeEventListener("nexus-mcp-call", sync);
  }, []);

  const addr = addresses.find((a) => a.addressId === selectedAddressId);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={neoSpring}
      className={cn("flex flex-wrap items-center gap-2", className)}
    >
      <span
        className="flex items-center gap-1.5 border-2 border-black bg-slate-900 px-2.5 py-1 font-mono text-[10px] font-bold text-emerald-300"
        title={orch.detail}
      >
        <Sparkles className="h-3 w-3" aria-hidden />
        {orch.label}
        {orch.llmModel ? ` · ${orch.llmModel}` : ""}
      </span>
      <span className="flex items-center gap-1.5 border-2 border-black bg-slate-50 px-2.5 py-1 font-mono text-[10px] font-bold text-slate-700">
        <MapPin className="h-3 w-3" aria-hidden />
        {addr?.label ?? "Home"}
      </span>
      <button
        type="button"
        onClick={onOpenFoodCart}
        className="flex items-center gap-1.5 border-2 border-black bg-orange-50 px-2.5 py-1 font-mono text-[10px] font-bold text-orange-900 hover:bg-orange-100"
      >
        <UtensilsCrossed className="h-3 w-3" aria-hidden />
        Food ₹{carts.foodTotal || 0}
        {carts.foodItems > 0 ? ` · ${carts.foodItems}` : ""}
      </button>
      <button
        type="button"
        onClick={onOpenImCart}
        className="flex items-center gap-1.5 border-2 border-black bg-emerald-50 px-2.5 py-1 font-mono text-[10px] font-bold text-emerald-900 hover:bg-emerald-100"
      >
        <ShoppingBag className="h-3 w-3" aria-hidden />
        IM ₹{carts.imTotal || 0}
        {carts.imItems > 0 ? ` · ${carts.imItems}` : ""}
      </button>
      {bookingsCount > 0 && (
        <span className="flex items-center gap-1.5 border-2 border-black bg-indigo-50 px-2.5 py-1 font-mono text-[10px] font-bold text-indigo-900">
          <ShoppingCart className="h-3 w-3" aria-hidden />
          {bookingsCount} booking
        </span>
      )}
      <span
        className="relative min-w-[7.5rem] overflow-hidden border-2 border-black bg-white px-2.5 py-1 font-mono text-[10px] font-bold text-slate-700"
        title="MCP tools exercised this session"
      >
        <span className="relative z-10">MCP {coverage.used}/{coverage.total}</span>
        <motion.span
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-violet-400/50 to-emerald-400/50"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={neoSpring}
          aria-hidden
        />
      </span>
    </motion.div>
  );
}
