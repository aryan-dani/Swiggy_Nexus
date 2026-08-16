"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Lock, Radio, Sparkles, UtensilsCrossed, ShoppingBag, CalendarDays } from "lucide-react";
import { motion } from "framer-motion";

import { NexusLogoMark } from "@/components/nexus-logo-mark";
import { fadeUp, neoSpring, staggerContainer } from "@/lib/motion";

const TOOLS = [
  "get_addresses",
  "search_restaurants",
  "get_restaurant_menu",
  "update_food_cart",
  "get_food_cart",
  "place_food_order",
  "search_products",
  "update_cart",
  "get_cart",
  "checkout",
  "get_saved_locations",
  "search_restaurants_dineout",
  "get_available_slots",
  "book_table",
  "your_go_to_items",
  "fetch_food_coupons",
];

const VERTICALS = [
  {
    n: "01",
    name: "Food",
    hue: "bg-orange-400",
    icon: UtensilsCrossed,
    line: "Search, menu, cart, coupons — dessert staged for 10 PM, never auto-placed.",
  },
  {
    n: "02",
    name: "Instamart",
    hue: "bg-neo-mint",
    icon: ShoppingBag,
    line: "Live catalog, variations + spinId, party supplies in one cart. Confirm to checkout.",
  },
  {
    n: "03",
    name: "Dineout",
    hue: "bg-indigo-400",
    icon: CalendarDays,
    line: "Saved locations, restaurant search, slots. Table books only after you say so.",
  },
];

const STEPS = [
  { k: "Plan", d: "Natural language in. Chrono-Host or free-form Groq with 44 MCP tools." },
  { k: "Stage", d: "Read tools fire in parallel. Carts and slots land in the Activity rail." },
  { k: "Confirm", d: "HITL on every write. Browser confirm or Telegram Night Out — your call." },
];

const TRACE = [
  { who: "you", text: "Plan my housewarming evening for 12 — Italian vibes" },
  { who: "tool", text: "dineout.get_saved_locations" },
  { who: "tool", text: "im.search_products · party plates napkins drinks" },
  { who: "tool", text: "food.search_restaurants · gelato" },
  { who: "agent", text: "Table staged · groceries staged · dessert staged. Nothing placed." },
];

function Marquee() {
  const row = [...TOOLS, ...TOOLS];
  return (
    <div className="overflow-hidden border-y-2 border-black bg-black py-3">
      <div className="nexus-marquee flex w-max gap-8">
        {row.map((t, i) => (
          <span
            key={`${t}-${i}`}
            className="font-mono text-[11px] font-semibold uppercase tracking-[0.22em] text-neo-yellow"
          >
            {t}
            <span className="ml-8 text-neo-mint">◆</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <div className="landing-grain relative min-h-screen overflow-x-clip bg-[#f6f4ee] text-black">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(0,0,0,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,0,0,0.06) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <header className="relative z-20 border-b-2 border-black bg-white/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-6">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <NexusLogoMark className="h-12 w-12 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]" />
            <div className="leading-tight">
              <p className="font-display text-base font-black tracking-tight">Swiggy Nexus</p>
              <p className="font-display text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                Agentic MCP demo
              </p>
            </div>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <span className="hidden items-center gap-1.5 border-2 border-black bg-neo-mint px-2 py-1 font-display text-[10px] font-black uppercase tracking-widest sm:inline-flex">
              <Radio className="h-3 w-3" aria-hidden />
              Live MCP ready
            </span>
            <Link
              href="/app"
              className="inline-flex items-center gap-1.5 border-2 border-black bg-neo-yellow px-3 py-2 font-display text-[11px] font-black uppercase tracking-widest shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] transition-transform hover:-translate-y-0.5"
            >
              Enter console
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          </div>
        </div>
      </header>

      <main className="relative z-10">
        <section className="mx-auto grid max-w-6xl gap-10 px-4 py-12 md:grid-cols-[1.15fr_0.85fr] md:items-center md:px-6 md:py-20">
          <motion.div variants={staggerContainer} initial="hidden" animate="show">
            <motion.p
              variants={fadeUp}
              className="mb-4 inline-flex border-2 border-black bg-white px-2 py-1 font-display text-[10px] font-black uppercase tracking-[0.2em] shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]"
            >
              Builders Club · 44 tools · HITL
            </motion.p>
            <motion.h1
              variants={fadeUp}
              className="font-display text-[clamp(2.6rem,7vw,5.4rem)] font-black leading-[0.9] tracking-tight"
            >
              Dinner out.
              <br />
              Groceries in.
              <span className="mt-1 block bg-neo-yellow px-1 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
                Dessert staged.
              </span>
            </motion.h1>
            <motion.p
              variants={fadeUp}
              className="mt-6 max-w-lg text-base font-medium leading-relaxed text-slate-700 sm:text-lg"
            >
              One agent orchestrates Swiggy Food, Instamart, and Dineout over JSON-RPC MCP.
              It stages the evening. You confirm the money moves.
            </motion.p>
            <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/app"
                className="inline-flex items-center gap-2 border-2 border-black bg-primary-container px-5 py-3 font-display text-xs font-black uppercase tracking-widest text-white shadow-[5px_5px_0px_0px_rgba(0,0,0,1)] transition-transform hover:-translate-y-0.5"
              >
                Launch the console
                <Sparkles className="h-4 w-4" aria-hidden />
              </Link>
              <Link
                href="/app"
                className="inline-flex items-center gap-2 border-2 border-black bg-white px-5 py-3 font-display text-xs font-black uppercase tracking-widest shadow-[5px_5px_0px_0px_rgba(0,0,0,1)] transition-transform hover:-translate-y-0.5"
              >
                Run 60s WOW
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            </motion.div>
            <motion.ul
              variants={fadeUp}
              className="mt-8 flex flex-wrap gap-x-6 gap-y-2 font-display text-[11px] font-bold uppercase tracking-widest text-slate-600"
            >
              <li>Groq + Gemini</li>
              <li>Telegram Night Out</li>
              <li>Mock or live MCP</li>
            </motion.ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 28, rotate: 2 }}
            animate={{ opacity: 1, y: 0, rotate: 1.5 }}
            transition={neoSpring}
            className="relative"
          >
            <div className="absolute -left-6 -top-6 hidden h-24 w-24 border-2 border-black bg-neo-mint shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] sm:block" />
            <div className="absolute -bottom-8 -right-4 hidden h-16 w-28 border-2 border-black bg-neo-yellow shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] sm:block" />
            <div className="relative border-2 border-black bg-white p-3 shadow-[10px_10px_0px_0px_rgba(0,0,0,1)]">
              <div className="mb-3 flex items-center justify-between border-b-2 border-black pb-2">
                <span className="font-display text-[10px] font-black uppercase tracking-widest">
                  Agent trace
                </span>
                <span className="bg-black px-1.5 py-0.5 font-mono text-[10px] text-neo-mint">
                  JSON-RPC 2.0
                </span>
              </div>
              <div className="mb-3 flex items-center gap-3 border-2 border-black bg-[#ececec] p-2">
                <Image
                  src="/images/nexus-bird.png"
                  alt=""
                  width={56}
                  height={56}
                  className="h-14 w-14 object-contain"
                  priority
                />
                <div>
                  <p className="font-display text-sm font-black">Chrono-Host</p>
                  <p className="font-mono text-[10px] text-slate-600">3 verticals · 0 auto-charges</p>
                </div>
              </div>
              <ol className="space-y-2">
                {TRACE.map((row) => (
                  <li
                    key={row.text}
                    className={
                      row.who === "you"
                        ? "border-2 border-black bg-indigo-50 px-3 py-2"
                        : row.who === "tool"
                          ? "border-2 border-black bg-black px-3 py-2 font-mono text-[11px] text-neo-yellow"
                          : "border-2 border-black bg-neo-mint px-3 py-2 text-sm font-semibold"
                    }
                  >
                    {row.who === "you" ? (
                      <p className="text-sm font-medium leading-snug">{row.text}</p>
                    ) : (
                      row.text
                    )}
                  </li>
                ))}
              </ol>
            </div>
          </motion.div>
        </section>

        <Marquee />

        <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
          <p className="mb-2 font-display text-[11px] font-black uppercase tracking-[0.22em] text-slate-500">
            Three servers. One conversation.
          </p>
          <h2 className="mb-10 max-w-2xl font-display text-3xl font-black tracking-tight sm:text-5xl">
            The agent does not pick a vertical. It uses all of them.
          </h2>
          <div className="grid gap-5 md:grid-cols-3">
            {VERTICALS.map((v, i) => {
              const Icon = v.icon;
              return (
                <motion.article
                  key={v.name}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-40px" }}
                  transition={{ ...neoSpring, delay: i * 0.06 }}
                  className={`border-2 border-black p-5 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] ${v.hue} ${i === 1 ? "md:-translate-y-4" : ""} ${i === 2 ? "md:translate-y-3" : ""}`}
                >
                  <div className="mb-6 flex items-start justify-between">
                    <span className="font-display text-4xl font-black opacity-40">{v.n}</span>
                    <span className="border-2 border-black bg-white p-2">
                      <Icon className="h-5 w-5" aria-hidden />
                    </span>
                  </div>
                  <h3 className="font-display text-2xl font-black uppercase">{v.name}</h3>
                  <p className="mt-3 text-sm font-medium leading-relaxed text-black/80">{v.line}</p>
                </motion.article>
              );
            })}
          </div>
        </section>

        <section className="border-y-2 border-black bg-black text-white">
          <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 md:grid-cols-2 md:px-6">
            <div>
              <p className="mb-3 inline-flex items-center gap-2 border-2 border-white px-2 py-1 font-display text-[10px] font-black uppercase tracking-widest">
                <Lock className="h-3.5 w-3.5" aria-hidden />
                Writes are gated
              </p>
              <h2 className="font-display text-4xl font-black tracking-tight sm:text-5xl">
                Stage everything.
                <br />
                Place nothing.
              </h2>
              <p className="mt-4 max-w-md text-sm font-medium leading-relaxed text-white/75">
                Place, checkout, and book_table wait for an explicit confirm — in the browser or
                on Telegram. The 60-second WOW is a scripted evening, not a surprise invoice.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 md:grid-cols-1 lg:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.k} className="border-2 border-white bg-white p-4 text-black shadow-[5px_5px_0px_0px_#FFD700]">
                  <p className="font-display text-xs font-black uppercase tracking-widest text-indigo-600">
                    {s.k}
                  </p>
                  <p className="mt-2 text-sm font-medium leading-snug">{s.d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-stretch">
            <div className="flex flex-col justify-between border-2 border-black bg-neo-yellow p-6 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] sm:p-8">
              <div>
                <p className="font-display text-[11px] font-black uppercase tracking-[0.2em]">
                  Chrono-Host
                </p>
                <h2 className="mt-3 font-display text-4xl font-black leading-[0.95] tracking-tight">
                  A whole night in one prompt.
                </h2>
                <p className="mt-4 text-sm font-medium leading-relaxed text-black/80">
                  Italian table for 12. Party plates on Instamart. Gelato staged for later.
                  Confirm table. Confirm groceries. Confirm dessert. The director narrates each tool.
                </p>
              </div>
              <Link
                href="/app"
                className="mt-8 inline-flex w-fit items-center gap-2 border-2 border-black bg-black px-5 py-3 font-display text-xs font-black uppercase tracking-widest text-neo-yellow shadow-[4px_4px_0px_0px_rgba(255,255,255,0.4)]"
              >
                Open the demo
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            </div>
            <pre className="overflow-x-auto border-2 border-black bg-[#0b0b0f] p-5 font-mono text-[11px] leading-relaxed text-neo-mint shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] sm:text-xs">
{`{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_products",
    "arguments": { "query": "party plates" }
  }
}

// live  → mcp.swiggy.com/{food|im|dineout}
// mock  → in-process fixture replay
// writes → HITL only`}
            </pre>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t-2 border-black bg-white px-4 py-8 md:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-display text-lg font-black">Swiggy Nexus</p>
            <p className="mt-1 max-w-md text-[11px] font-medium leading-relaxed text-slate-500">
              Not affiliated with Swiggy. Synthetic / live MCP demo for Builders Club only.
              Do not place real orders unless you intend to.
            </p>
          </div>
          <Link
            href="/app"
            className="inline-flex items-center gap-2 font-display text-xs font-black uppercase tracking-widest underline decoration-2 underline-offset-4"
          >
            Skip intro → console
          </Link>
        </div>
      </footer>
    </div>
  );
}
