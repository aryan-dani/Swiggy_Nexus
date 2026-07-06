"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Loader2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { callMcp, mcpErrorMessage } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";

type ImLine = {
  spinId?: string;
  name?: string;
  qty?: number;
  line_total_inr?: number;
};

type ImCartData = {
  items?: ImLine[];
  subtotal_inr?: number;
  total?: number;
  bill?: { itemTotal?: number; delivery?: number; grandTotal?: number };
};

export function InstamartCartDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { requestId, selectedAddressId, refreshCarts } = useNexusSession();
  const [cart, setCart] = useState<ImCartData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await callMcp("im", "get_cart", {}, requestId);
    if (res.success) setCart(res.data as ImCartData);
    void refreshCarts();
  }, [requestId, refreshCarts]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const checkout = async () => {
    setBusy(true);
    setError(null);
    const res = await callMcp("im", "checkout", { selectedAddressId }, requestId);
    setBusy(false);
    if (res.success) {
      const oid = (res.data as { orderId?: string })?.orderId;
      nexusToast(`Instamart checkout · ${oid}`);
      onClose();
      void load();
    } else {
      setError(mcpErrorMessage(res, "Checkout failed"));
    }
  };

  const minWarning = (cart?.subtotal_inr ?? 0) > 0 && (cart?.subtotal_inr ?? 0) < 99;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[80] flex justify-end bg-black/40"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.aside
            initial={{ x: 320 }}
            animate={{ x: 0 }}
            exit={{ x: 320 }}
            transition={neoSpring}
            className="flex h-full w-full max-w-md flex-col border-l-4 border-black bg-white"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b-2 border-black p-4">
              <h2 className="font-display text-lg font-black uppercase">Instamart cart</h2>
              <button type="button" aria-label="Close" onClick={onClose} className="border-2 border-black p-2">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {!cart?.items?.length ? (
                <p className="text-sm text-slate-600">Cart empty — add groceries from feed or go-to shelf.</p>
              ) : (
                <ul className="space-y-2">
                  {cart.items.map((line, i) => (
                    <li key={i} className="flex justify-between border-2 border-black bg-emerald-50 px-3 py-2 text-sm">
                      <span>
                        {line.name}
                        {line.spinId && (
                          <span className="ml-1 font-mono text-[10px] text-slate-500">{line.spinId}</span>
                        )}
                        × {line.qty}
                      </span>
                      <span className="font-mono font-bold">₹{line.line_total_inr}</span>
                    </li>
                  ))}
                </ul>
              )}
              {cart?.bill && (
                <div className="mt-4 space-y-1 border-t-2 border-dashed pt-3 text-sm">
                  <div className="flex justify-between"><span>Items</span><span>₹{cart.bill.itemTotal}</span></div>
                  <div className="flex justify-between"><span>Delivery</span><span>₹{cart.bill.delivery}</span></div>
                  <div className="flex justify-between font-display font-black"><span>Grand total</span><span>₹{cart.bill.grandTotal}</span></div>
                </div>
              )}
              {minWarning && (
                <p className="mt-3 text-xs font-bold text-amber-800">Minimum order ₹99 (mock rule)</p>
              )}
              {error && <p className="mt-3 text-sm font-bold text-red-700">{error}</p>}
            </div>
            <div className="border-t-2 border-black p-4">
              <button
                type="button"
                disabled={busy || !cart?.items?.length || minWarning}
                onClick={() => void checkout()}
                className="bento-button w-full border-emerald-700 bg-emerald-600 text-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "Confirm checkout"}
              </button>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
