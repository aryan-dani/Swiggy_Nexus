"use client";

import { ChevronDown, MapPin, ShoppingBag, ShoppingCart, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";

import { getToolCoverage } from "@/lib/mcp-client";
import { getOrchestratorInfo } from "@/lib/orchestrator-info";
import { useNexusSession } from "@/lib/nexus-session-context";
import { neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function NexusCommandCenter({
  onOpenFoodCart,
  onOpenImCart,
  className,
}: {
  onOpenFoodCart?: () => void;
  onOpenImCart?: () => void;
  className?: string;
}) {
  const { addresses, selectedAddressId, setSelectedAddressId, refreshCarts, carts, bookingsCount } =
    useNexusSession();
  const [coverage, setCoverage] = useState({ used: 0, total: 33 });
  const [addrOpen, setAddrOpen] = useState(false);
  const orch = getOrchestratorInfo();
  const pct = Math.min(100, Math.round((coverage.used / Math.max(1, coverage.total)) * 100));

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
      className={cn("relative flex flex-wrap items-center gap-2", className)}
    >
      <span
        className="flex items-center gap-1.5 rounded border border-black/20 bg-slate-900 px-2.5 py-1 font-mono text-[10px] font-bold text-emerald-300"
        title={orch.detail}
      >
        <Sparkles className="h-3 w-3" aria-hidden />
        {orch.label}
        {orch.llmModel ? ` · ${orch.llmModel}` : ""}
      </span>

      <div className="relative">
        <button
          type="button"
          onClick={() => setAddrOpen((o) => !o)}
          className="flex items-center gap-1.5 rounded border border-black/20 bg-slate-50 px-2.5 py-1 font-mono text-[10px] font-bold text-slate-700 hover:bg-white"
        >
          <MapPin className="h-3 w-3" aria-hidden />
          {addr?.label ?? "Home"}
          <ChevronDown className={cn("h-3 w-3 transition-transform", addrOpen && "rotate-180")} />
        </button>
        <AnimatePresence>
          {addrOpen && addresses.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="absolute left-0 top-full z-50 mt-1 min-w-[10rem] rounded border border-black/20 bg-white p-1 shadow-md"
            >
              {addresses.map((a) => (
                <button
                  key={a.addressId}
                  type="button"
                  onClick={() => {
                    setSelectedAddressId(a.addressId);
                    void refreshCarts();
                    setAddrOpen(false);
                  }}
                  className={cn(
                    "block w-full rounded px-2.5 py-1.5 text-left font-mono text-[10px] font-bold",
                    a.addressId === selectedAddressId
                      ? "bg-indigo-50 text-indigo-900"
                      : "text-slate-600 hover:bg-slate-50"
                  )}
                >
                  {a.label}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <button
        type="button"
        onClick={onOpenFoodCart}
        className="flex items-center gap-1.5 rounded border-2 border-black bg-orange-50 px-2.5 py-1 font-mono text-[10px] font-bold text-orange-900 shadow-[2px_2px_0_0_#000] hover:translate-x-px hover:translate-y-px hover:shadow-none"
      >
        <ShoppingCart className="h-3 w-3" aria-hidden />
        Food cart
        {carts.foodItems > 0 ? ` · ${carts.foodItems}` : ""}
        {carts.foodTotal > 0 ? ` · ₹${carts.foodTotal}` : ""}
      </button>
      <button
        type="button"
        onClick={onOpenImCart}
        className="flex items-center gap-1.5 rounded border-2 border-black bg-emerald-50 px-2.5 py-1 font-mono text-[10px] font-bold text-emerald-900 shadow-[2px_2px_0_0_#000] hover:translate-x-px hover:translate-y-px hover:shadow-none"
      >
        <ShoppingBag className="h-3 w-3" aria-hidden />
        IM cart
        {carts.imItems > 0 ? ` · ${carts.imItems}` : ""}
        {carts.imTotal > 0 ? ` · ₹${carts.imTotal}` : ""}
      </button>
      {bookingsCount > 0 && (
        <span className="flex items-center gap-1.5 rounded border border-black/20 bg-indigo-50 px-2.5 py-1 font-mono text-[10px] font-bold text-indigo-900">
          <ShoppingCart className="h-3 w-3" aria-hidden />
          {bookingsCount} booking
        </span>
      )}
      <span
        className="relative min-w-[7.5rem] overflow-hidden rounded border border-black/20 bg-white px-2.5 py-1 font-mono text-[10px] font-bold text-slate-700"
        title="MCP tools exercised this session"
      >
        <span className="relative z-10">
          MCP {coverage.used}/{coverage.total}
        </span>
        <motion.span
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-violet-400/40 to-emerald-400/40"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={neoSpring}
          aria-hidden
        />
      </span>
    </motion.div>
  );
}
