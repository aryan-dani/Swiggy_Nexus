"use client";

import { Music, ShoppingCart, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";

import NexusResultCard, {
  type NexusCardResult,
} from "@/components/nexus-result-card";
import { BookingTicket } from "@/components/booking-ticket";
import { ChronoHostPanel } from "@/components/chrono-host-panel";
import { GoToShelf } from "@/components/go-to-shelf";
import { JoinStripCard } from "@/components/deadlock-arena";
import { SentimentComfortCard } from "@/components/sentiment-comfort-card";
import type { FeedItem } from "@/lib/api";
import { mapFeedItemToNexusCard } from "@/lib/feed-mapper";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { fadeUp, neoSpring, staggerContainer } from "@/lib/motion";

export type McpFeedProps = {
  items: FeedItem[];
  /** When set, empty-state copy reflects the active reviewer preset. */
  activeScenario?: string;
  compactFeed?: boolean;
  onCardAction?: (card: NexusCardResult) => void;
  onChronoConfirm?: (text: string) => void;
  onOpenImCart?: () => void;
  onOpenFoodCart?: () => void;
  watchParty?: boolean;
};

const PLAYLIST = [
  { t: "Khuloos · Talwiinder", vibe: "late-night delivery run" },
  { t: "Starboy · The Weeknd", vibe: "dinner with the team" },
  { t: "Magenta Riddim · DJ Snake", vibe: "spicy food energy" },
  { t: "Cold/Mess · Anne-Marie", vibe: "grocery haul calm" },
] as const;

function bonusRowFromCards(
  base: NexusCardResult[],
  round: number
): NexusCardResult[] {
  return base.map((c, i) => ({
    ...c,
    id: `${c.id}-more-r${round}-${i}`,
    title: `${c.title} · alt ${round}`,
    description: "Nearby pick · synthetic listing",
    offer: round % 2 === 0 ? "Demo ₹40 off" : undefined,
  }));
}

export default function McpFeed({
  items,
  activeScenario,
  compactFeed = false,
  onCardAction,
  onChronoConfirm,
  onOpenImCart,
  onOpenFoodCart,
  watchParty,
}: McpFeedProps) {
  const chronoBundle = items.find((i) => i.type === "event_bundle");
  const joinStrip = items.find((i) => i.type === "join_strip");
  const comfortCard = items.find((i) => i.type === "comfort_proposal");
  const bookingCard = items.find((i) => i.type === "booking");
  const scrollItems = items.filter(
    (i) => !["event_bundle", "join_strip", "comfort_proposal", "booking"].includes(i.type)
  );

  const cards = scrollItems
    .map((item, i) => mapFeedItemToNexusCard(item, i))
    .filter((card): card is NonNullable<typeof card> => card != null);

  const errors = items.filter((i) => i.type === "error");
  const hasContent = items.length > 0;

  const [optionsRound, setOptionsRound] = useState(0);
  const [playlistOpen, setPlaylistOpen] = useState(false);
  const [compact, setCompact] = useState(compactFeed);

  useEffect(() => {
    setCompact(compactFeed);
  }, [compactFeed]);

  useEffect(() => {
    setOptionsRound(0);
  }, [items]);

  const bonusCards = useMemo(() => {
    if (optionsRound <= 0) return [];
    const out: NexusCardResult[] = [];
    for (let r = 1; r <= optionsRound; r++) {
      out.push(...bonusRowFromCards(cards, r));
    }
    return out;
  }, [cards, optionsRound]);

  const displayCards = useMemo(
    () => [...cards, ...bonusCards],
    [cards, bonusCards]
  );

  const addOne = useCallback((c: NexusCardResult) => {
    onCardAction?.(c);
  }, [onCardAction]);

  const addAll = useCallback(() => {
    if (cards.length === 0) return;
    const n = displayCards.length;
    nexusToast(`Queued ${n} item(s) in demo cart — all mock, no charge.`);
  }, [cards.length, displayCards.length]);

  const showMore = useCallback(() => {
    if (cards.length === 0) return;
    setOptionsRound((r) => Math.min(r + 1, 3));
    nexusToast("Loaded alternate mock listings — scroll sideways.");
  }, [cards.length]);

  const suggestPlaylist = useCallback(() => {
    setPlaylistOpen(true);
  }, []);

  return (
    <div className="relative flex min-h-0 flex-col gap-4 pb-2">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={neoSpring}
      >
        <h2 className="font-display text-lg font-black uppercase tracking-tight text-black">
          {chronoBundle ? "Chrono-Host · Live bundle" : "Nexus Live Feed"}
        </h2>
        <p className="font-display text-[11px] font-bold uppercase tracking-widest text-slate-500">
          {chronoBundle
            ? "Dineout · Instamart · Food — staged, confirm each leg"
            : "Food · Instamart · Dineout (mock)"}
        </p>
      </motion.div>

      <AnimatePresence mode="wait" initial={false}>
        {!hasContent ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0, scale: 0.97, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: -6 }}
            transition={neoSpring}
            className="flex min-h-[36vh] flex-col items-center justify-center gap-3 border-2 border-dashed border-black bg-white p-8 text-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          >
            <motion.div
              className="flex h-14 w-14 items-center justify-center border-2 border-black bg-tertiary-container shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]"
              animate={{ y: [0, -4, 0] }}
              transition={{
                repeat: Infinity,
                duration: 2.5,
                ease: "easeInOut",
              }}
            >
              <ShoppingCart className="h-7 w-7 text-black" />
            </motion.div>
            <p className="font-display text-sm font-bold text-slate-600">
              {activeScenario === "chrono_host"
                ? "Chrono-Host is armed — send “Plan my evening for 12” to see the 3-vertical bundle panel."
                : "Send a message — cards appear here when the agent calls mock tools."}
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="feed"
            className="flex min-h-0 flex-col gap-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {chronoBundle && (
              <ChronoHostPanel
                item={chronoBundle}
                onConfirmViaChat={onChronoConfirm}
                onOpenImCart={onOpenImCart}
                onOpenFoodCart={onOpenFoodCart}
              />
            )}
            {joinStrip && <JoinStripCard item={joinStrip} />}
            {comfortCard && <SentimentComfortCard item={comfortCard} />}
            {bookingCard && (
              <BookingTicket
                venueName={bookingCard.title}
                slot={bookingCard.subtitle ?? "20:00"}
                guests={Number(bookingCard.meta?.guests ?? 6)}
                bookingId={String(bookingCard.meta?.bookingId ?? "bk-mock")}
              />
            )}
            <GoToShelf partyMode={watchParty || activeScenario === "chrono_host"} />

            {errors.map((err, i) => (
              <motion.div
                key={`err-${i}`}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ ...neoSpring, delay: i * 0.05 }}
                className="bento-card border-red-600 bg-red-50 p-4 text-black"
              >
                <p className="font-display text-xs font-black uppercase text-red-700">
                  Error
                </p>
                <p className="mt-1 text-sm font-bold">{err.title}</p>
                {err.subtitle && (
                  <p className="mt-1 text-xs text-red-900/80">{err.subtitle}</p>
                )}
              </motion.div>
            ))}

            <div className="relative -mx-1 min-w-0 pl-1">
              <motion.div
                className="neo-scrollbar flex snap-x snap-mandatory gap-5 overflow-x-auto overflow-y-visible px-1 pb-8 pt-2 md:gap-6 md:pb-10"
                variants={staggerContainer}
                initial="hidden"
                animate="show"
              >
                {displayCards.map((card, i) => (
                  <NexusResultCard
                    key={card.id}
                    result={card}
                    index={i}
                    compact={compact}
                    onPrimaryAction={addOne}
                  />
                ))}
              </motion.div>
              <p className="pointer-events-none hidden font-display text-[10px] font-bold uppercase tracking-widest text-slate-400 md:block">
                ← Scroll for more →
              </p>
            </div>

            {cards.length > 0 && (
              <motion.div
                className="flex flex-wrap gap-3 pt-1"
                variants={staggerContainer}
                initial="hidden"
                animate="show"
              >
                <motion.button
                  variants={fadeUp}
                  type="button"
                  whileHover={{
                    boxShadow: "5px 5px 0px 0px rgba(0,0,0,1)",
                    scale: 1.02,
                    transition: neoSpring,
                  }}
                  whileTap={{ scale: 0.99, boxShadow: "2px 2px 0px 0px rgba(0,0,0,1)" }}
                  className="bento-button flex items-center gap-2 border-primary-container bg-primary-container text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:bg-[#5248e6]"
                  onClick={addAll}
                >
                  <ShoppingCart size={16} />
                  Add all to cart
                </motion.button>
                <motion.button
                  variants={fadeUp}
                  type="button"
                  whileHover={{
                    scale: 1.02,
                    boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)",
                    transition: neoSpring,
                  }}
                  whileTap={{ scale: 0.98 }}
                  className="bento-button text-black"
                  onClick={showMore}
                  disabled={optionsRound >= 3}
                >
                  Show more options
                  {optionsRound > 0 ? ` (${optionsRound})` : ""}
                </motion.button>
                <motion.button
                  variants={fadeUp}
                  type="button"
                  whileHover={{
                    scale: 1.02,
                    boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)",
                    transition: neoSpring,
                  }}
                  whileTap={{ scale: 0.98 }}
                  className="bento-button flex items-center gap-2 text-black"
                  onClick={suggestPlaylist}
                >
                  <Music size={16} />
                  Suggest a playlist
                </motion.button>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {playlistOpen && (
          <motion.div
            key="playlist-backdrop"
            className="fixed inset-0 z-[90] flex items-end justify-center bg-black/40 p-4 sm:items-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setPlaylistOpen(false)}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="playlist-title"
              initial={{ opacity: 0, y: 24, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={neoSpring}
              className="relative w-full max-w-md border-2 border-black bg-white p-5 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center border-2 border-black bg-slate-100 hover:bg-white"
                aria-label="Close"
                onClick={() => setPlaylistOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
              <div className="mb-4 flex items-center gap-2 pr-10">
                <Music className="h-6 w-6 text-primary-container" />
                <div>
                  <h3
                    id="playlist-title"
                    className="font-display text-lg font-black uppercase text-black"
                  >
                    Demo playlist
                  </h3>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">
                    Synthetic picks for your order vibe
                  </p>
                </div>
              </div>
              <ul className="space-y-3">
                {PLAYLIST.map((row, i) => (
                  <li
                    key={row.t}
                    className="flex items-start justify-between gap-3 border-2 border-black bg-slate-50 px-3 py-2"
                  >
                    <span className="font-mono text-xs text-slate-400">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0 flex-1 text-left">
                      <p className="font-display text-sm font-bold text-black">
                        {row.t}
                      </p>
                      <p className="mt-0.5 text-[11px] font-medium text-slate-600">
                        {row.vibe}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
              <motion.button
                type="button"
                className="bento-button mt-5 w-full border-primary-container bg-primary-container text-white hover:bg-[#5248e6]"
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  void (async () => {
                    try {
                      await navigator.clipboard.writeText(
                        PLAYLIST.map((p) => p.t).join("\n")
                      );
                      nexusToast("Track list copied — paste anywhere.");
                      setPlaylistOpen(false);
                    } catch {
                      nexusToast(
                        "Clipboard blocked — select tracks manually or try HTTPS."
                      );
                    }
                  })();
                }}
              >
                Copy track list
              </motion.button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
