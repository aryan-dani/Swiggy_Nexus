"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Tag, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { callMcp, mcpErrorMessage } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";

type CartLine = {
  item_id?: string;
  name?: string;
  qty?: number;
  unit_price_inr?: number;
  line_total_inr?: number;
};

type FoodCartData = {
  items?: CartLine[];
  subtotal_inr?: number;
  deliveryCharge?: number;
  total?: number;
  restaurantName?: string;
  offers?: { coupon_applied?: string | null };
};

export function FoodCartDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { requestId, selectedAddressId, refreshCarts } = useNexusSession();
  const [cart, setCart] = useState<FoodCartData | null>(null);
  const [coupons, setCoupons] = useState<{ code: string; description: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [cRes, cpRes] = await Promise.all([
      callMcp("food", "get_food_cart", { addressId: selectedAddressId }, requestId),
      callMcp("food", "fetch_food_coupons", {}, requestId),
    ]);
    if (cRes.success) setCart(cRes.data as FoodCartData);
    if (cpRes.success && cpRes.data) {
      const rows = (cpRes.data as { coupons?: { code: string; description: string }[] }).coupons ?? [];
      setCoupons(rows);
    }
    void refreshCarts();
  }, [requestId, selectedAddressId, refreshCarts]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const applyCoupon = async (code: string) => {
    setBusy(true);
    const res = await callMcp("food", "apply_food_coupon", { code }, requestId);
    setBusy(false);
    if (res.success) {
      nexusToast(`Coupon ${code} applied`);
      void load();
    } else {
      nexusToast(mcpErrorMessage(res, "Coupon failed"));
    }
  };

  const placeOrder = async () => {
    setBusy(true);
    setError(null);
    const res = await callMcp("food", "place_order", { addressId: selectedAddressId }, requestId);
    setBusy(false);
    if (res.success) {
      const oid = (res.data as { orderId?: string })?.orderId;
      nexusToast(`Food order placed · ${oid}`);
      onClose();
      void load();
    } else {
      setError(mcpErrorMessage(res, "Could not place order"));
    }
  };

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
            className="flex h-full w-full max-w-md flex-col border-l-4 border-black bg-white shadow-[-8px_0_0_0_rgba(0,0,0,0.08)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b-2 border-black p-4">
              <h2 className="font-display text-lg font-black uppercase">Food cart</h2>
              <button type="button" aria-label="Close" onClick={onClose} className="border-2 border-black p-2">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {cart?.restaurantName && (
                <p className="mb-3 font-display text-xs font-bold uppercase text-slate-500">
                  {cart.restaurantName}
                </p>
              )}
              {!cart?.items?.length ? (
                <p className="text-sm text-slate-600">Cart is empty — add from feed cards or menu.</p>
              ) : (
                <ul className="space-y-2">
                  {cart.items.map((line, i) => (
                    <li key={i} className="flex justify-between border-2 border-black bg-orange-50 px-3 py-2 text-sm">
                      <span>{line.name} × {line.qty}</span>
                      <span className="font-mono font-bold">₹{line.line_total_inr}</span>
                    </li>
                  ))}
                </ul>
              )}
              {cart?.items?.length ? (
                <div className="mt-4 space-y-1 border-t-2 border-dashed border-black/20 pt-3 text-sm">
                  <div className="flex justify-between"><span>Subtotal</span><span>₹{cart.subtotal_inr}</span></div>
                  <div className="flex justify-between"><span>Delivery</span><span>₹{cart.deliveryCharge}</span></div>
                  <div className="flex justify-between font-display font-black"><span>Total</span><span>₹{cart.total}</span></div>
                </div>
              ) : null}
              {coupons.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 flex items-center gap-1 font-display text-[10px] font-black uppercase text-slate-500">
                    <Tag className="h-3 w-3" /> Coupons
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {coupons.map((c) => (
                      <button
                        key={c.code}
                        type="button"
                        disabled={busy}
                        onClick={() => void applyCoupon(c.code)}
                        className="border-2 border-black bg-white px-2 py-1 text-[10px] font-bold hover:bg-slate-50"
                      >
                        {c.code}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {error && <p className="mt-3 text-sm font-bold text-red-700">{error}</p>}
            </div>
            <div className="border-t-2 border-black p-4">
              <button
                type="button"
                disabled={busy || !cart?.items?.length}
                onClick={() => void placeOrder()}
                className="bento-button w-full border-orange-600 bg-orange-500 text-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "Confirm & place order"}
              </button>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
