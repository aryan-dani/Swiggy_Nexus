"use client";

import { Calendar, IceCream, ShoppingBag, UtensilsCrossed } from "lucide-react";
import { motion } from "framer-motion";
import { useState } from "react";

import { callMcp } from "@/lib/mcp-client";
import { useNexusSession } from "@/lib/nexus-session-context";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";
import type { FeedItem } from "@/lib/api";

type ChronoHostPanelProps = {
  item: FeedItem;
  onConfirmViaChat?: (text: string) => void;
  onOpenImCart?: () => void;
  onOpenFoodCart?: () => void;
};

const STEPS = ["Staged", "Confirmed", "Placed"] as const;

function Leg({
  icon: Icon,
  label,
  title,
  detail,
  accent,
  action,
  step,
}: {
  icon: typeof Calendar;
  label: string;
  title: string;
  detail: string;
  accent: string;
  action?: React.ReactNode;
  step: number;
}) {
  return (
    <div className={`flex flex-col gap-2 border-2 border-black p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] ${accent}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 shrink-0" aria-hidden />
          <span className="font-display text-[10px] font-black uppercase tracking-widest">{label}</span>
        </div>
        <span className="font-mono text-[9px] font-bold uppercase text-slate-500">{STEPS[step]}</span>
      </div>
      <p className="font-display text-sm font-black leading-tight text-black">{title}</p>
      <p className="text-xs font-medium leading-snug text-slate-700">{detail}</p>
      {action}
    </div>
  );
}

export function ChronoHostPanel({
  item,
  onConfirmViaChat,
  onOpenImCart,
  onOpenFoodCart,
}: ChronoHostPanelProps) {
  const { requestId, selectedAddressId, refreshCarts } = useNexusSession();
  const meta = (item.meta ?? {}) as Record<string, unknown>;
  const dineout = meta.dineout as Record<string, unknown> | undefined;
  const instamart = meta.instamart as Record<string, unknown> | undefined;
  const food = meta.food as Record<string, unknown> | undefined;
  const guests =
    meta.guests ??
    (dineout?.guests as number | undefined) ??
    meta.partySize ??
    12;

  const [legSteps, setLegSteps] = useState<[number, number, number]>([0, 0, 0]);

  const guestCount = Number(guests) || 12;
  const imTotal = Number(instamart?.total ?? 0);
  const foodTotal = Number(food?.total ?? 0);
  const budget = Number(meta.budgetInr ?? guestCount * 800);
  const spent = imTotal + foodTotal;

  const dineTitle =
    typeof dineout?.restaurant === "string"
      ? `${dineout.restaurant} · ${dineout.slot ?? "~8 PM"}`
      : dineout?.slot
        ? `Table · ${dineout.slot}`
        : String(meta.event ?? item.title).replace("Evening plan · ", "");

  const confirmTable = async () => {
    const rid = String(dineout?.restaurantId ?? "do_italian_804");
    const res = await callMcp(
      "dineout",
      "book_table",
      {
        restaurantId: rid,
        partySize: guests,
        slot: dineout?.slot ?? "20:00",
        slotId: dineout?.slotId ?? 4204,
      },
      requestId
    );
    if (res.success) {
      setLegSteps((s) => [2, s[1], s[2]]);
      nexusToast("Table confirmed (mock book_table)");
    } else if (onConfirmViaChat) {
      onConfirmViaChat("confirm table");
    }
  };

  const confirmGroceries = () => {
    setLegSteps((s) => [s[0], 1, s[2]]);
    onOpenImCart?.();
    onConfirmViaChat?.("confirm groceries");
  };

  const confirmDessert = async () => {
    setLegSteps((s) => [s[0], s[1], 1]);
    const res = await callMcp("food", "place_order", { addressId: selectedAddressId }, requestId);
    if (res.success) {
      setLegSteps((s) => [s[0], s[1], 2]);
      nexusToast("Dessert placed — 10 PM reminder is manual in v1");
      void refreshCarts();
    } else {
      onOpenFoodCart?.();
      onConfirmViaChat?.("confirm dessert");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className="w-full border-4 border-black bg-gradient-to-br from-violet-50 via-white to-emerald-50 p-4 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Calendar className="h-5 w-5 text-violet-700" aria-hidden />
        <h3 className="font-display text-base font-black uppercase tracking-tight text-black">
          Chrono-Host · Evening bundle
        </h3>
      </div>

      <div className="mb-4 flex items-center gap-2 font-mono text-[10px]">
        {["7 PM", "8 PM", "10 PM"].map((t, i) => (
          <span key={t} className="flex flex-1 flex-col items-center gap-1">
            <span className={`h-2 w-full border-2 border-black ${i < 2 ? "bg-violet-400" : "bg-sky-400"}`} />
            <span className="font-bold">{t}</span>
          </span>
        ))}
      </div>

      <div className="mb-4">
        <div className="mb-1 flex justify-between text-[10px] font-bold uppercase">
          <span>Budget thermometer</span>
          <span>₹{spent} staged / ₹{budget}</span>
        </div>
        <div className="h-2 border-2 border-black bg-white">
          <div
            className="h-full bg-amber-400"
            style={{ width: `${Math.min(100, (spent / budget) * 100)}%` }}
          />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Leg
          icon={UtensilsCrossed}
          label="Dineout"
          title={dineTitle}
          detail="Table ~8 PM"
          accent="bg-orange-50"
          step={legSteps[0]}
          action={
            legSteps[0] < 2 ? (
              <button type="button" className="mt-1 border-2 border-black bg-white px-2 py-1 text-[10px] font-black uppercase" onClick={() => void confirmTable()}>
                Confirm table
              </button>
            ) : null
          }
        />
        <Leg
          icon={ShoppingBag}
          label="Instamart"
          title="Party supplies"
          detail={imTotal ? `Cart ₹${imTotal}` : "Staged supplies"}
          accent="bg-emerald-50"
          step={legSteps[1]}
          action={
            legSteps[1] < 2 ? (
              <button type="button" className="mt-1 border-2 border-black bg-white px-2 py-1 text-[10px] font-black uppercase" onClick={confirmGroceries}>
                Confirm groceries
              </button>
            ) : null
          }
        />
        <Leg
          icon={IceCream}
          label="Food dessert"
          title="Gelato @ 10 PM"
          detail={foodTotal ? `Staged ₹${foodTotal}` : "Dessert queued"}
          accent="bg-sky-50"
          step={legSteps[2]}
          action={
            legSteps[2] < 2 ? (
              <button type="button" className="mt-1 border-2 border-black bg-white px-2 py-1 text-[10px] font-black uppercase" onClick={() => void confirmDessert()}>
                Confirm dessert
              </button>
            ) : null
          }
        />
      </div>
      <p className="mt-3 text-[10px] font-medium text-violet-800">
        Food has no scheduled delivery in v1 — dessert uses a 10 PM reminder toast after confirm.
      </p>
    </motion.div>
  );
}
