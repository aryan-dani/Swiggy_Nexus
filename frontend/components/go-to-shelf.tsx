"use client";

import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { VariantPicker } from "@/components/variant-picker";
import { callMcp } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { neoSpring } from "@/lib/motion";

type Product = {
  product_id: string;
  name: string;
  variants: { spinId: string; label: string; price_inr: number }[];
};

export function GoToShelf({ partyMode = false }: { partyMode?: boolean }) {
  const { requestId, selectedAddressId } = useNexusSession();
  const [products, setProducts] = useState<Product[]>([]);
  const [picker, setPicker] = useState<Product | null>(null);

  const load = useCallback(async () => {
    const res = await callMcp(
      "im",
      "your_go_to_items",
      { addressId: selectedAddressId, party: partyMode, partyMode },
      requestId
    );
    if (res.success && res.data) {
      setProducts((res.data as { products?: Product[] }).products ?? []);
    }
  }, [requestId, selectedAddressId, partyMode]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!products.length) return null;

  return (
  <>
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={neoSpring}
      className="border-2 border-black bg-emerald-50/50 p-3"
    >
      <div className="mb-2 flex items-center justify-between">
        <p className="font-display text-[10px] font-black uppercase tracking-widest text-emerald-900">
          <RotateCcw className="mr-1 inline h-3 w-3" />
          Order again · your_go_to_items
        </p>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {products.map((p) => (
          <button
            key={p.product_id}
            type="button"
            onClick={() => setPicker(p)}
            className="shrink-0 border-2 border-black bg-white px-3 py-2 text-left text-xs font-bold hover:bg-emerald-100"
          >
            {p.name}
            <span className="mt-0.5 block font-mono text-[10px] text-slate-500">
              ₹{p.variants[0]?.price_inr}
            </span>
          </button>
        ))}
      </div>
    </motion.div>
    {picker && (
      <VariantPicker
        open
        productName={picker.name}
        productId={picker.product_id}
        variants={picker.variants}
        onClose={() => setPicker(null)}
      />
    )}
  </>
  );
}
