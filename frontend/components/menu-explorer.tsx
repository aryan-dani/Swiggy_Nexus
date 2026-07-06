"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Minus, Plus, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { callMcp, mcpErrorMessage } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";

type MenuItem = {
  item_id: string;
  name: string;
  price_inr: number;
  vegetarian: boolean;
};

export function MenuExplorer({
  open,
  restaurantId,
  restaurantName,
  onClose,
}: {
  open: boolean;
  restaurantId: string;
  restaurantName: string;
  onClose: () => void;
}) {
  const { requestId, selectedAddressId, refreshCarts } = useNexusSession();
  const [items, setItems] = useState<MenuItem[]>([]);
  const [qty, setQty] = useState<Record<string, number>>({});

  const load = useCallback(async () => {
    const res = await callMcp("food", "get_menu", { restaurantId }, requestId);
    if (res.success && res.data) {
      const cats = (res.data as { categories?: { items: MenuItem[] }[] }).categories ?? [];
      setItems(cats.flatMap((c) => c.items));
    }
  }, [restaurantId, requestId]);

  useEffect(() => {
    if (open && restaurantId) void load();
  }, [open, restaurantId, load]);

  const addToCart = async () => {
    const lines = Object.entries(qty)
      .filter(([, q]) => q > 0)
      .map(([item_id, q]) => ({ item_id, qty: q }));
    if (!lines.length) return;
    const res = await callMcp(
      "food",
      "add_to_cart",
      { restaurantId, addressId: selectedAddressId, lines },
      requestId
    );
    if (res.success) {
      nexusToast(`Added to Food cart · ${restaurantName}`);
      void refreshCarts();
      onClose();
    } else {
      nexusToast(mcpErrorMessage(res, "Add failed"));
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[85] flex items-end justify-center bg-black/40 sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ y: 40 }}
            animate={{ y: 0 }}
            exit={{ y: 40 }}
            transition={neoSpring}
            className="max-h-[80vh] w-full max-w-lg overflow-hidden border-4 border-black bg-white shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b-2 border-black p-4">
              <h2 className="font-display font-black uppercase">{restaurantName}</h2>
              <button type="button" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
            </div>
            <ul className="max-h-[50vh] overflow-y-auto p-4 space-y-3">
              {items.map((it) => (
                <li key={it.item_id} className="flex items-center justify-between gap-3 border-2 border-black p-3">
                  <div>
                    <p className="font-bold text-sm">{it.name}</p>
                    <p className="text-xs text-slate-600">₹{it.price_inr} · {it.vegetarian ? "Veg" : "Non-veg"}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" className="border-2 border-black p-1" onClick={() => setQty((q) => ({ ...q, [it.item_id]: Math.max(0, (q[it.item_id] ?? 0) - 1) }))}>
                      <Minus className="h-3 w-3" />
                    </button>
                    <span className="w-6 text-center font-mono text-sm">{qty[it.item_id] ?? 0}</span>
                    <button type="button" className="border-2 border-black p-1" onClick={() => setQty((q) => ({ ...q, [it.item_id]: (q[it.item_id] ?? 0) + 1 }))}>
                      <Plus className="h-3 w-3" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <div className="border-t-2 border-black p-4">
              <button type="button" className="bento-button w-full bg-orange-500 text-white" onClick={() => void addToCart()}>
                Add to cart
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
