"use client";

import { ChevronDown, Music, ShoppingCart, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

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
  activeScenario?: string;
  compactFeed?: boolean;
  onCardAction?: (card: NexusCardResult) => void;
  onChronoConfirm?: (text: string) => void;
  onOpenImCart?: () => void;
  onOpenFoodCart?: () => void;
  watchParty?: boolean;
  /** Optional arena slot rendered above cards (Deadlock / Dialectic). */
  arenaSlot?: ReactNode;
};

const PLAYLIST = [
  { t: "Khuloos · Talwiinder", vibe: "late-night delivery run" },
  { t: "Starboy · The Weeknd", vibe: "dinner with the team" },
  { t: "Magenta Riddim · DJ Snake", vibe: "spicy food energy" },
  { t: "Cold/Mess · Anne-Marie", vibe: "grocery haul calm" },
] as const;

const SECTION_LABEL: Record<NexusCardResult["type"], string> = {
  dineout: "Dineout",
  grocery: "Instamart",
  food: "Food",
};

function bonusRowFromCards(base: NexusCardResult[], round: number): NexusCardResult[] {
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
  compactFeed = true,
  onCardAction,
  onChronoConfirm,
  onOpenImCart,
  onOpenFoodCart,
  watchParty,
  arenaSlot,
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
  const hasContent = items.length > 0 || Boolean(arenaSlot);

  const [optionsRound, setOptionsRound] = useState(0);
  const [playlistOpen, setPlaylistOpen] = useState(false);
  const [compact, setCompact] = useState(compactFeed);
  const [detailsOpen, setDetailsOpen] = useState(false);

  useEffect(() => {
    setCompact(compactFeed);
  }, [compactFeed]);

  useEffect(() => {
    setOptionsRound(0);
    setDetailsOpen(false);
  }, [items]);

  const bonusCards = useMemo(() => {
    if (optionsRound <= 0) return [];
    const out: NexusCardResult[] = [];
    for (let r = 1; r <= optionsRound; r++) {
      out.push(...bonusRowFromCards(cards, r));
    }
    return out;
  }, [cards, optionsRound]);

  const displayCards = useMemo(() => [...cards, ...bonusCards], [cards, bonusCards]);

  const grouped = useMemo(() => {
    const order: NexusCardResult["type"][] = ["dineout", "grocery", "food"];
    const map: Record<string, NexusCardResult[]> = {};
    for (const c of displayCards) {
      (map[c.type] ??= []).push(c);
    }
    return order.filter((t) => map[t]?.length).map((t) => ({ type: t, cards: map[t] }));
  }, [displayCards]);

  const addOne = useCallback(
    (c: NexusCardResult) => {
      onCardAction?.(c);
    },
    [onCardAction]
  );

  const addAll = useCallback(() => {
    if (cards.length === 0) return;
    nexusToast(`Queued ${displayCards.length} item(s) in demo cart — all mock, no charge.`);
  }, [cards.length, displayCards.length]);

  const showMore = useCallback(() => {
    if (cards.length === 0) return;
    setOptionsRound((r) => Math.min(r + 1, 3));
    nexusToast("Loaded alternate mock listings.");
  }, [cards.length]);

  return (
    <div id="nexus-activity-rail" className="relative flex min-h-0 flex-col gap-4 pb-2">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={neoSpring}>
        <h2 className="nexus-section-title">
          {chronoBundle ? "Chrono-Host bundle" : "Activity"}
        </h2>
        <p className="nexus-caption">
          {chronoBundle
            ? "Pinned bundle · confirm each leg below"
            : "Staged MCP results appear here as tools run"}
        </p>
      </motion.div>

      {arenaSlot && (
        <div className="bento-card-soft space-y-2 p-3">
          <p className="font-display text-[10px] font-black uppercase tracking-widest text-slate-500">
            Scenario arena
          </p>
          {arenaSlot}
        </div>
      )}

      <AnimatePresence mode="wait" initial={false}>
        {!hasContent ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={neoSpring}
            className="flex min-h-[28vh] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-black/20 bg-slate-50 p-6 text-center"
          >
            <ShoppingCart className="h-6 w-6 text-slate-400" aria-hidden />
            <p className="max-w-xs font-sans text-sm font-medium text-slate-600">
              {activeScenario === "chrono_host"
                ? "Run the WOW demo — the 3-vertical bundle will pin here."
                : "Send a message. Cards for Food, Instamart and Dineout land in this rail."}
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="feed"
            className="flex min-h-0 flex-col gap-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {chronoBundle && (
              <div className="sticky top-0 z-10">
                <ChronoHostPanel
                  item={chronoBundle}
                  onConfirmViaChat={onChronoConfirm}
                  onOpenImCart={onOpenImCart}
                  onOpenFoodCart={onOpenFoodCart}
                />
              </div>
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

            {(watchParty || activeScenario === "chrono_host") && (
              <GoToShelf partyMode={watchParty || activeScenario === "chrono_host"} />
            )}

            {errors.map((err, i) => (
              <div key={`err-${i}`} className="bento-card-soft border-red-300 bg-red-50 p-3">
                <p className="font-display text-[10px] font-black uppercase text-red-700">Error</p>
                <p className="mt-1 text-sm font-medium">{err.title}</p>
                {err.subtitle && <p className="mt-0.5 text-[11px] text-red-900/80">{err.subtitle}</p>}
              </div>
            ))}

            {grouped.length > 0 && (
              <div className="space-y-4">
                <button
                  type="button"
                  onClick={() => {
                    setDetailsOpen((o) => !o);
                    setCompact((c) => (detailsOpen ? true : false));
                  }}
                  className="flex items-center gap-1.5 font-sans text-[11px] font-medium text-slate-500 hover:text-slate-800"
                >
                  <ChevronDown
                    className={`h-3.5 w-3.5 transition-transform ${detailsOpen ? "rotate-180" : ""}`}
                  />
                  {detailsOpen ? "Compact cards" : "Show card details"}
                </button>

                {grouped.map(({ type, cards: sectionCards }) => (
                  <div key={type} className="space-y-2">
                    <p className="font-display text-[10px] font-black uppercase tracking-widest text-slate-500">
                      {SECTION_LABEL[type]} · {sectionCards.length}
                    </p>
                    <motion.div
                      className="neo-scrollbar flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2"
                      variants={staggerContainer}
                      initial="hidden"
                      animate="show"
                    >
                      {sectionCards.map((card, i) => (
                        <NexusResultCard
                          key={card.id}
                          result={card}
                          index={i}
                          compact={!detailsOpen && compact}
                          onPrimaryAction={addOne}
                        />
                      ))}
                    </motion.div>
                  </div>
                ))}
              </div>
            )}

            {cards.length > 0 && (
              <motion.div
                className="flex flex-wrap gap-2"
                variants={staggerContainer}
                initial="hidden"
                animate="show"
              >
                <motion.button
                  variants={fadeUp}
                  type="button"
                  className="bento-button flex items-center gap-2 border-primary-container bg-primary-container text-white hover:bg-[#5248e6]"
                  onClick={addAll}
                >
                  <ShoppingCart size={14} />
                  Add all
                </motion.button>
                <motion.button
                  variants={fadeUp}
                  type="button"
                  className="rounded border border-black/20 bg-white px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide text-black hover:bg-slate-50"
                  onClick={showMore}
                  disabled={optionsRound >= 3}
                >
                  More options{optionsRound > 0 ? ` (${optionsRound})` : ""}
                </motion.button>
                <motion.button
                  variants={fadeUp}
                  type="button"
                  className="rounded border border-black/20 bg-white px-3 py-2 font-display text-[10px] font-black uppercase tracking-wide text-black hover:bg-slate-50"
                  onClick={() => setPlaylistOpen(true)}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <Music size={14} />
                    Playlist
                  </span>
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
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={neoSpring}
              className="relative w-full max-w-md rounded-lg border-2 border-black bg-white p-5 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded border border-black/20 bg-slate-50"
                aria-label="Close"
                onClick={() => setPlaylistOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
              <h3 className="nexus-section-title pr-8">Demo playlist</h3>
              <ul className="mt-3 space-y-2">
                {PLAYLIST.map((row, i) => (
                  <li
                    key={row.t}
                    className="flex gap-3 rounded border border-black/10 bg-slate-50 px-3 py-2"
                  >
                    <span className="font-mono text-[10px] text-slate-400">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <p className="font-sans text-sm font-medium text-black">{row.t}</p>
                      <p className="nexus-caption">{row.vibe}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
