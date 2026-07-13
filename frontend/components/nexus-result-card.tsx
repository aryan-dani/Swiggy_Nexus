"use client";

import { ArrowRight, Star, Zap } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";

import { fadeUp, neoSpring } from "@/lib/motion";
import { cn } from "@/lib/utils";

export type NexusCardResult = {
  id: string;
  type: "food" | "grocery" | "dineout";
  title: string;
  description: string;
  rating?: number;
  time?: string;
  distance?: string;
  price?: string;
  offer?: string;
  imageUrl: string;
  items?: number;
  vegetarian?: boolean;
  priceInr?: number;
  meta?: Record<string, unknown>;
};

/** Per-type default SVG illustrations — no broken image chains */
const TYPE_SVG: Record<NexusCardResult["type"], string> = {
  food: "/images/demo/food.svg",
  grocery: "/images/demo/grocery.svg",
  dineout: "/images/demo/dineout.svg",
};

/** SVG data-URI fallback if even the type SVG 404s */
const FALLBACK_SVG =
  "data:image/svg+xml," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect fill="#cbd5e1" width="100%" height="100%"/><text x="50%" y="50%" font-family="system-ui" font-size="48" text-anchor="middle" fill="#94a3b8" dominant-baseline="middle">📦</text></svg>'
  );

export default function NexusResultCard({
  result,
  index = 0,
  compact = false,
  onPrimaryAction,
}: {
  result: NexusCardResult;
  index?: number;
  compact?: boolean;
  onPrimaryAction?: (result: NexusCardResult) => void;
}) {
  const typeSvg = TYPE_SVG[result.type];
  const intendedSrc = result.imageUrl || typeSvg;
  const [imgSrc, setImgSrc] = useState(intendedSrc);

  useEffect(() => {
    setImgSrc(intendedSrc);
  }, [intendedSrc]);

  const isInstamart = result.type === "grocery";
  const isDineout = result.type === "dineout";
  const w = compact
    ? "min-w-[240px] max-w-[240px]"
    : "min-w-[260px] max-w-[280px] sm:min-w-[280px]";

  const vegBadge =
    result.vegetarian === true ? (
      <span title="Vegetarian" className="text-[11px]">🟢</span>
    ) : result.vegetarian === false ? (
      <span title="Non-vegetarian" className="text-[11px]">🔴</span>
    ) : null;

  const displayPrice = result.priceInr != null
    ? `₹${result.priceInr}`
    : result.price ?? null;

  return (
    <motion.div
      variants={fadeUp}
      whileHover={{
        y: -8,
        boxShadow: "8px 8px 0px 0px rgba(0,0,0,1)",
        transition: neoSpring,
      }}
      className={`bento-card-interactive flex ${w} shrink-0 cursor-pointer flex-col gap-3 p-4 group relative overflow-hidden snap-start will-change-transform`}
    >
      {/* Quick-action button (hover reveal) */}
      <div className="absolute top-2 right-2 z-10 p-1 opacity-0 transition-opacity group-hover:opacity-100">
        <motion.button
          type="button"
          aria-label="Open details"
          className="flex h-8 w-8 items-center justify-center border-2 border-black bg-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
          whileHover={{ boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)", transition: neoSpring }}
          whileTap={{ scale: 0.96 }}
          onClick={(e) => {
            e.stopPropagation();
            onPrimaryAction?.(result);
          }}
        >
          <ArrowRight size={16} className="text-black" />
        </motion.button>
      </div>

      {/* Image */}
      <div className={cn("relative overflow-hidden border-2 border-black", compact ? "h-28" : "h-32")}>
        <motion.img
          alt={result.title}
          className="h-full w-full object-cover"
          src={imgSrc}
          onError={() =>
            setImgSrc((cur) => {
              if (cur === FALLBACK_SVG) return cur;
              if (cur !== typeSvg) return typeSvg;
              return FALLBACK_SVG;
            })
          }
          initial={{ scale: 1.08, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: index * 0.04, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          whileHover={{ scale: 1.08 }}
        />

        {/* Rating badge */}
        {result.rating != null && (
          <motion.div
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.12 + index * 0.04, ...neoSpring }}
            className="absolute left-2 top-2 flex items-center gap-1 border-2 border-black bg-tertiary-container px-2 py-0.5 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
          >
            <Star size={10} className="fill-black text-black" />
            <span className="font-display text-[10px] font-black text-black">{result.rating}</span>
          </motion.div>
        )}

        {/* Vertical label */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18 + index * 0.04, ...neoSpring }}
          className={cn(
            "absolute bottom-2 left-2 border-2 border-black px-2 py-0.5 text-[9px] font-black uppercase tracking-widest text-white",
            isInstamart ? "bg-rose-600" : isDineout ? "bg-primary-container" : "bg-black"
          )}
        >
          {isInstamart ? "Instamart" : isDineout ? "Dineout" : "Delivery"}
        </motion.div>

        {/* Instamart "fast" badge */}
        {isInstamart && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 + index * 0.04 }}
            className="absolute right-2 bottom-2 flex items-center gap-0.5 border-2 border-black bg-amber-400 px-1.5 py-0.5 text-[9px] font-black uppercase text-black"
          >
            <Zap size={8} className="fill-black" />
            FAST
          </motion.div>
        )}
      </div>

      {/* Title and description */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.08 + index * 0.03 }}
      >
        <div className="flex items-center gap-1.5 mb-0.5">
          {vegBadge}
          <h4 className="truncate font-display text-base font-black uppercase tracking-tight text-black">
            {result.title}
          </h4>
        </div>
        <p className="truncate text-[11px] font-bold uppercase tracking-wider text-slate-500">
          {result.description}
        </p>
      </motion.div>

      {/* Footer: price/ETA + CTA */}
      <div className="mt-auto flex flex-col gap-3 border-t-2 border-black/10 pt-3">
        <div className="flex items-center justify-between text-[11px] font-bold">
          <span className="font-mono tracking-tighter text-slate-400">
            {displayPrice ? "PRICE" : result.time ? "ETA" : result.distance ? "DIST" : "EST."}
          </span>
          <span className={cn("text-black font-display font-black", result.offer ? "text-rose-600" : "")}>
            {result.offer ??
              displayPrice ??
              result.time ??
              result.distance ??
              (result.items != null ? `${result.items} items` : "—")}
          </span>
        </div>
        <motion.button
          type="button"
          className="bento-button w-full text-[10px]"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onPrimaryAction?.(result)}
        >
          {isInstamart ? "Add to cart" : isDineout ? "Book table" : "Order now"}
        </motion.button>
      </div>
    </motion.div>
  );
}
