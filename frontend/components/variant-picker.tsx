"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useState } from "react";

import { callMcp, mcpErrorMessage } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";

type Variant = { spinId: string; label: string; price_inr: number; inStock?: boolean };

export function VariantPicker({
  open,
  productName,
  variants,
  productId,
  onClose,
}: {
  open: boolean;
  productName: string;
  variants: Variant[];
  productId: string;
  onClose: () => void;
}) {
  const { requestId, selectedAddressId, refreshCarts } = useNexusSession();
  const [selected, setSelected] = useState(variants[0]?.spinId ?? "");

  const add = async () => {
    if (!selected) return;
    const res = await callMcp(
      "im",
      "add_to_cart",
      {
        selectedAddressId,
        items: [{ spinId: selected, product_id: productId, quantity: 1 }],
      },
      requestId
    );
    if (res.success) {
      nexusToast(`Added ${productName} (${selected})`);
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
          className="fixed inset-0 z-[85] flex items-center justify-center bg-black/40 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95 }}
            animate={{ scale: 1 }}
            transition={neoSpring}
            className="w-full max-w-sm border-4 border-black bg-white p-5 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex justify-between">
              <h3 className="font-display font-black uppercase">Pick variant</h3>
              <button type="button" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
            </div>
            <p className="mb-3 text-sm font-bold">{productName}</p>
            <div className="space-y-2">
              {variants.map((v) => (
                <label key={v.spinId} className="flex cursor-pointer items-center gap-2 border-2 border-black p-2">
                  <input type="radio" name="spin" checked={selected === v.spinId} onChange={() => setSelected(v.spinId)} />
                  <span className="text-sm">{v.label} — ₹{v.price_inr}</span>
                  <span className="ml-auto font-mono text-[10px] text-slate-500">{v.spinId}</span>
                </label>
              ))}
            </div>
            <button type="button" className="bento-button mt-4 w-full bg-emerald-600 text-white" onClick={() => void add()}>
              Add to Instamart cart
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
