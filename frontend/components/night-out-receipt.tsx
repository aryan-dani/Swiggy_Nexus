"use client";

import { Calendar, Copy, ExternalLink, MapPin, Users, X } from "lucide-react";
import { motion } from "framer-motion";

import { neoSpring } from "@/lib/motion";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { cn } from "@/lib/utils";

export type NightOutReceiptData = {
  title?: string;
  mode?: string;
  venue?: string;
  slot?: string;
  booking_id?: string | null;
  food_order_id?: string | null;
  instamart_order_id?: string | null;
  calendar_html_link?: string | null;
  calendar_mock?: boolean;
  maps_url?: string | null;
  attendee_emails?: string[];
  guest_count?: number;
  total_inr?: number;
  event_id?: string;
  approval_request_id?: string;
  shares?: Array<{
    email: string;
    name: string;
    amount_inr: number;
    is_host?: boolean;
    upi_link?: string;
  }>;
};

export function receiptDismissKey(receipt: NightOutReceiptData): string {
  return String(
    receipt.booking_id ||
      receipt.approval_request_id ||
      receipt.event_id ||
      `${receipt.title || ""}|${receipt.venue || ""}|${receipt.total_inr ?? ""}`
  );
}

function shortName(email: string) {
  const local = email.split("@")[0] || email;
  return local.charAt(0).toUpperCase() + local.slice(1);
}

export function NightOutReceipt({
  receipt,
  className,
  onDismiss,
}: {
  receipt: NightOutReceiptData;
  className?: string;
  onDismiss?: () => void;
}) {
  const attendees = receipt.attendee_emails || [];
  const shares = receipt.shares || [];

  const copy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      nexusToast(`Copied ${label}`);
    } catch {
      nexusToast("Copy failed");
    }
  };

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn(
        "overflow-hidden rounded-xl border-2 border-black bg-gradient-to-br from-amber-50 via-white to-violet-50 shadow-[4px_4px_0_0_#000]",
        className
      )}
    >
      <header className="relative border-b-2 border-black bg-black px-4 py-3 text-white">
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss night out receipt"
            className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/30 bg-white/10 text-white hover:bg-white/20"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        <p className="font-display text-[10px] font-black uppercase tracking-widest text-amber-300">
          Approved · Night out receipt
        </p>
        <h3 className={cn("font-display text-lg font-black leading-tight", onDismiss && "pr-10")}>
          {receipt.title || receipt.venue || "Night out"}
        </h3>
        {receipt.venue && (
          <p className="mt-0.5 font-mono text-xs text-white/70">
            {receipt.venue}
            {receipt.slot ? ` · ${receipt.slot}` : ""}
            {receipt.booking_id ? ` · ${receipt.booking_id}` : ""}
          </p>
        )}
      </header>

      <div className="flex flex-wrap gap-2 border-b border-black/10 px-4 py-3">
        {receipt.calendar_html_link && (
          <a
            href={receipt.calendar_html_link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border-2 border-black bg-white px-3 py-2 font-display text-[10px] font-black uppercase shadow-[2px_2px_0_0_#000] hover:translate-x-px hover:translate-y-px hover:shadow-none"
          >
            <Calendar className="h-3.5 w-3.5" />
            {receipt.calendar_mock ||
            (receipt.calendar_html_link || "").includes("action=TEMPLATE")
              ? "Add to Calendar"
              : "Open Calendar"}
            <ExternalLink className="h-3 w-3 opacity-50" />
          </a>
        )}
        {receipt.maps_url && (
          <a
            href={receipt.maps_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border-2 border-black bg-neo-mint px-3 py-2 font-display text-[10px] font-black uppercase shadow-[2px_2px_0_0_#000] hover:translate-x-px hover:translate-y-px hover:shadow-none"
          >
            <MapPin className="h-3.5 w-3.5" /> Navigate
            <ExternalLink className="h-3 w-3 opacity-50" />
          </a>
        )}
      </div>

      <div className="space-y-3 px-4 py-3">
        <div>
          <p className="mb-1.5 flex items-center gap-1 font-display text-[10px] font-black uppercase tracking-wide text-slate-500">
            <Users className="h-3 w-3" /> Invited
          </p>
          <div className="flex flex-wrap gap-1.5">
            {attendees.map((email) => (
              <span
                key={email}
                className="rounded-full border border-black/20 bg-white px-2.5 py-1 font-mono text-[11px]"
              >
                {shortName(email)}
              </span>
            ))}
            {!attendees.length && (
              <span className="font-mono text-[11px] text-slate-400">No invitees</span>
            )}
          </div>
        </div>

        {(receipt.food_order_id || receipt.instamart_order_id) && (
          <div className="font-mono text-[11px] text-slate-600">
            {receipt.food_order_id && <div>Food · {receipt.food_order_id}</div>}
            {receipt.instamart_order_id && <div>Instamart · {receipt.instamart_order_id}</div>}
          </div>
        )}

        {shares.length > 0 && (
          <div>
            <p className="mb-1.5 font-display text-[10px] font-black uppercase tracking-wide text-slate-500">
              Equal split · ₹{receipt.total_inr ?? "—"}
            </p>
            <ul className="space-y-1.5">
              {shares.map((s) => (
                <li
                  key={s.email}
                  className="flex items-center justify-between gap-2 rounded-lg border border-black/10 bg-white/80 px-2.5 py-2"
                >
                  <div>
                    <span className="font-display text-xs font-bold">
                      {s.name}
                      {s.is_host ? " · host" : ""}
                    </span>
                    <span className="ml-2 font-mono text-xs">₹{s.amount_inr}</span>
                  </div>
                  {s.upi_link && (
                    <button
                      type="button"
                      onClick={() => void copy(s.upi_link!, "UPI link")}
                      className="inline-flex items-center gap-1 rounded border border-black/20 px-2 py-1 font-display text-[9px] font-bold uppercase"
                    >
                      <Copy className="h-3 w-3" /> UPI
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </motion.article>
  );
}
