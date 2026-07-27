"use client";

import { cn } from "@/lib/utils";

export type ItemLine = {
  name?: string;
  quantity?: number;
  price_inr?: number | null;
};

/** Compact structured line-item list used by approvals, pantry, and split cards. */
export function ItemLinesList({
  lines,
  totalInr,
  className,
}: {
  lines: ItemLine[];
  totalInr?: number | null;
  className?: string;
}) {
  const rows = (lines || []).filter((l) => l && (l.name || l.quantity));
  if (rows.length === 0) return null;
  return (
    <div className={cn("overflow-hidden rounded border border-black/10 bg-white", className)}>
      <ul className="divide-y divide-black/5">
        {rows.map((l, i) => (
          <li key={`${l.name}-${i}`} className="flex items-center gap-2 px-2.5 py-1.5">
            <span className="min-w-0 flex-1 truncate font-sans text-[11px] font-medium text-slate-800">
              {l.name || "Item"}
            </span>
            <span className="font-mono text-[10px] text-slate-500">× {l.quantity ?? 1}</span>
            {l.price_inr != null && l.price_inr > 0 && (
              <span className="font-mono text-[10px] font-bold text-slate-700">
                ₹{Math.round(l.price_inr * (l.quantity ?? 1))}
              </span>
            )}
          </li>
        ))}
      </ul>
      {totalInr != null && totalInr > 0 && (
        <div className="flex items-center justify-between border-t border-black/10 bg-slate-50 px-2.5 py-1.5">
          <span className="font-display text-[9px] font-black uppercase tracking-widest text-slate-500">
            Est. total
          </span>
          <span className="font-mono text-[11px] font-bold text-black">₹{Math.round(totalInr)}</span>
        </div>
      )}
    </div>
  );
}
