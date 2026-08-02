"use client";

import { Check, Circle, Loader2, XCircle } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";

export type DemoStepId = "plan" | "dineout" | "instamart" | "food" | "bundle";

export type DemoStep = {
  id: DemoStepId;
  label: string;
  caption: string;
};

export const DEMO_STEPS: DemoStep[] = [
  { id: "plan", label: "Plan", caption: "Reading intent and picking verticals…" },
  { id: "dineout", label: "Dineout", caption: "Checking table availability…" },
  { id: "instamart", label: "Instamart", caption: "Staging party supplies cart…" },
  { id: "food", label: "Food", caption: "Staging catering / dessert…" },
  { id: "bundle", label: "Bundle", caption: "Bundle ready — review on the right →" },
];

const METHOD_CAPTIONS: Record<string, string> = {
  search_restaurants_dineout: "Searching Dineout venues…",
  check_availability: "Checking table slots…",
  get_available_slots: "Fetching available slots…",
  get_restaurant_details: "Loading venue details…",
  book_table: "Booking table (staged)…",
  search_products: "Searching Instamart…",
  update_cart: "Updating Instamart cart…",
  get_cart: "Reading Instamart cart…",
  checkout: "Checkout staged…",
  search_restaurants: "Searching Food restaurants…",
  get_restaurant_menu: "Loading restaurant menu…",
  get_menu: "Loading menu…",
  update_food_cart: "Updating Food cart…",
  place_food_order: "Food order staged…",
};

export function captionForMethod(method: string): string {
  const bare = method.replace(/^(food_|im_|dineout_)/, "");
  return METHOD_CAPTIONS[bare] || METHOD_CAPTIONS[method] || `Calling ${bare || method}…`;
}

export function stepFromToolMethod(method: string): DemoStepId | null {
  const m = method.toLowerCase();
  // Prefer dineout-specific tools before generic address helpers
  if (
    m.includes("dineout") ||
    m.includes("book_table") ||
    m.includes("available_slots") ||
    m.includes("check_availability") ||
    m.includes("restaurant_details") ||
    m.includes("search_restaurants_dineout") ||
    m.includes("get_saved_locations")
  ) {
    return "dineout";
  }
  // Instamart — include get_addresses only when Chrono is already past Dineout
  // (caller uses advanceDemoStep; mapping address→IM is intentional for Chrono order)
  if (
    m.includes("search_products") ||
    m.includes("update_cart") ||
    m.includes("get_cart") ||
    m.includes("checkout") ||
    m.includes("instamart") ||
    m.startsWith("im_") ||
    m === "food_get_addresses" ||
    m === "get_addresses"
  ) {
    return "instamart";
  }
  if (
    m.includes("get_menu") ||
    m.includes("get_restaurant_menu") ||
    m.includes("place_food") ||
    m.includes("update_food") ||
    m.includes("get_food_cart") ||
    (m.includes("search_restaurants") && !m.includes("dineout"))
  ) {
    return "food";
  }
  return null;
}

const STEP_RANK: Record<DemoStepId, number> = {
  plan: 0,
  dineout: 1,
  instamart: 2,
  food: 3,
  bundle: 4,
};

/** Never go backwards — stops Plan ↔ Instamart thrashing during SSE. */
export function advanceDemoStep(
  current: DemoStepId | null,
  next: DemoStepId | null
): DemoStepId | null {
  if (!next) return current;
  if (!current) return next;
  return STEP_RANK[next] >= STEP_RANK[current] ? next : current;
}

export function stepFromThinkingText(text: string): DemoStepId | null {
  const t = text.toLowerCase();
  if (t.includes("instamart") || t.includes("party supplies") || t.includes("grocery")) {
    return "instamart";
  }
  if (t.includes("dineout") || t.includes("table") || t.includes("venue")) {
    return "dineout";
  }
  if (t.includes("food") || t.includes("dessert") || t.includes("gelato") || t.includes("catering")) {
    return "food";
  }
  if (t.includes("planner") || t.includes("orchestrat") || t.includes("chrono")) {
    return "plan";
  }
  return null;
}

export function DemoDirector({
  activeStep,
  caption,
  visible,
  failed = false,
  className,
}: {
  activeStep: DemoStepId | null;
  caption?: string;
  visible: boolean;
  failed?: boolean;
  className?: string;
}) {
  if (!visible) return null;

  const activeIdx = activeStep ? DEMO_STEPS.findIndex((s) => s.id === activeStep) : 0;
  const current = DEMO_STEPS[Math.max(0, activeIdx)] ?? DEMO_STEPS[0];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={neoSpring}
        className={cn(
          "bento-card-soft space-y-2 p-3",
          failed ? "border-red-300 bg-red-50/80" : "bg-violet-50/80",
          className
        )}
      >
        <p
          className={cn(
            "font-display text-[10px] font-black uppercase tracking-widest",
            failed ? "text-red-800" : "text-violet-800"
          )}
        >
          Demo Director{failed ? " · failed" : ""}
        </p>
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          {DEMO_STEPS.map((step, i) => {
            const done = !failed && i < activeIdx;
            const active = i === activeIdx;
            const failedHere = failed && active;
            return (
              <div key={step.id} className="flex items-center gap-1.5">
                {i > 0 && <span className="hidden h-px w-3 bg-black/15 sm:block" aria-hidden />}
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold",
                    failedHere && "border-red-600 bg-red-100 text-red-900",
                    done && "border-emerald-600/40 bg-emerald-50 text-emerald-800",
                    !failedHere && active && !failed && "border-violet-600 bg-violet-100 text-violet-900",
                    !done && !active && "border-black/10 bg-white text-slate-400",
                    failed && !active && i < activeIdx && "border-black/10 bg-white text-slate-400"
                  )}
                >
                  {failedHere ? (
                    <XCircle className="h-3 w-3" aria-hidden />
                  ) : done ? (
                    <Check className="h-3 w-3" aria-hidden />
                  ) : active && !failed ? (
                    <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                  ) : (
                    <Circle className="h-2.5 w-2.5" aria-hidden />
                  )}
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
        <p
          className={cn(
            "font-sans text-[11px] font-medium",
            failed ? "text-red-800" : "text-slate-700"
          )}
        >
          {caption || current.caption}
        </p>
      </motion.div>
    </AnimatePresence>
  );
}

export function DemoSummaryCard({
  toolCount,
  verticals,
  stagedInr,
  onOpenBundle,
  onViewTraces,
  className,
}: {
  toolCount: number;
  verticals: number;
  stagedInr?: number;
  onOpenBundle?: () => void;
  onViewTraces?: () => void;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={neoSpring}
      className={cn("bento-card border-emerald-600 bg-emerald-50 p-4", className)}
    >
      <p className="font-display text-[10px] font-black uppercase tracking-widest text-emerald-800">
        Demo complete
      </p>
      <p className="mt-1 font-sans text-sm font-medium text-black">
        Used {toolCount} MCP {toolCount === 1 ? "tool" : "tools"} across {verticals}{" "}
        {verticals === 1 ? "vertical" : "verticals"}
        {stagedInr != null && stagedInr > 0 ? ` · ₹${Math.round(stagedInr)} staged` : ""}.
        Nothing was charged — confirm legs in the Activity rail.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {onOpenBundle && (
          <button
            type="button"
            onClick={onOpenBundle}
            className="rounded border-2 border-black bg-white px-3 py-1.5 font-display text-[10px] font-black uppercase tracking-wide shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:bg-slate-50"
          >
            Open bundle
          </button>
        )}
        {onViewTraces && (
          <button
            type="button"
            onClick={onViewTraces}
            className="rounded border border-black/20 bg-white px-3 py-1.5 font-display text-[10px] font-black uppercase tracking-wide text-slate-700 hover:bg-slate-50"
          >
            View tool traces
          </button>
        )}
      </div>
    </motion.div>
  );
}
