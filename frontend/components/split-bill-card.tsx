"use client";

import { Copy, IndianRupee, Loader2, Users } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useState } from "react";

import { getApiBase } from "@/lib/api";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { cn } from "@/lib/utils";

type Share = {
  email: string;
  name: string;
  amount_inr: number;
  is_host: boolean;
  upi_link: string;
};

const DEMO_ATTENDEES = ["aryan@nexus.ai", "himali@nexus.ai", "siya@nexus.ai"];

/** BHIM-style equal split (Nexus extension) — shares + mock UPI links. */
export function SplitBillButton({
  totalInr,
  title = "Bill split",
  orderId,
  attendees = DEMO_ATTENDEES,
  /** false = Chrono-Host / WOW (Beat 1) — keep Telegram silent */
  notifyTelegram = true,
  className,
}: {
  totalInr: number;
  title?: string;
  orderId?: string;
  attendees?: string[];
  notifyTelegram?: boolean;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [shares, setShares] = useState<Share[] | null>(null);

  const runSplit = useCallback(async () => {
    if (busy || totalInr <= 0) return;
    setBusy(true);
    try {
      const res = await fetch(`${getApiBase()}/api/concierge/split`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          total_inr: totalInr,
          attendees,
          order_id: orderId,
          title,
          notify: notifyTelegram,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || res.statusText);
      setShares(json.shares || []);
      nexusToast(
        notifyTelegram
          ? `Split ₹${json.total_inr} across ${json.attendee_count} — sent to Telegram`
          : `Split ₹${json.total_inr} across ${json.attendee_count} — UI only (no Telegram)`
      );
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Split failed — is the API on :8000?");
    } finally {
      setBusy(false);
    }
  }, [attendees, busy, notifyTelegram, orderId, title, totalInr]);

  return (
    <div className={className}>
      {!shares && (
        <button
          type="button"
          disabled={busy || totalInr <= 0}
          onClick={() => void runSplit()}
          className="inline-flex items-center gap-1.5 rounded border border-black/20 bg-white px-2.5 py-1.5 font-display text-[10px] font-black uppercase tracking-wide text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {busy ? (
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
          ) : (
            <Users className="h-3 w-3" aria-hidden />
          )}
          Split bill · ₹{Math.round(totalInr)}
        </button>
      )}
      <AnimatePresence>
        {shares && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-1 rounded border border-emerald-300 bg-emerald-50 p-2"
          >
            <p className="mb-1 flex items-center gap-1 font-display text-[9px] font-black uppercase tracking-widest text-emerald-800">
              <IndianRupee className="h-3 w-3" aria-hidden />
              {notifyTelegram
                ? "Equal split · sent to Telegram · demo UPI"
                : "Equal split · UI only · demo UPI"}
            </p>
            <ul className="space-y-1">
              {shares.map((s) => (
                <li key={s.email} className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate font-sans text-[11px] font-medium text-slate-800">
                    {s.name}
                    {s.is_host ? " (host)" : ""}
                  </span>
                  <span className="font-mono text-[11px] font-bold text-black">₹{s.amount_inr}</span>
                  <button
                    type="button"
                    className="rounded border border-black/15 bg-white p-1 text-slate-500 hover:text-black"
                    title="Copy UPI link"
                    aria-label={`Copy UPI link for ${s.name}`}
                    onClick={() => {
                      void navigator.clipboard
                        .writeText(s.upi_link)
                        .then(() => nexusToast(`UPI link copied for ${s.name}`))
                        .catch(() => nexusToast("Clipboard blocked"));
                    }}
                  >
                    <Copy className="h-3 w-3" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export { DEMO_ATTENDEES };
