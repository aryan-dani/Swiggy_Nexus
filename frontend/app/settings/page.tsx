"use client";

import { ArrowLeft, Bell, Database, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";

import { NexusLogoMark } from "@/components/nexus-logo-mark";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  loadDemoSettings,
  saveDemoSettings,
  type NexusDemoSettings,
} from "@/lib/nexus-settings-storage";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { fadeUp, staggerContainer } from "@/lib/motion";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      variants={fadeUp}
      className="border-2 border-black bg-white p-5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
    >
      <h2 className="mb-4 font-display text-xs font-black uppercase tracking-widest text-slate-500">
        {title}
      </h2>
      {children}
    </motion.section>
  );
}

export default function SettingsPage() {
  const [s, setS] = useState<NexusDemoSettings | null>(null);

  useEffect(() => {
    setS(loadDemoSettings());
  }, []);

  if (!s) {
    return (
      <div className="bg-white flex min-h-screen items-center justify-center font-display text-sm font-bold text-slate-500">
        Loading…
      </div>
    );
  }

  const patch = (partial: Partial<NexusDemoSettings>) => {
    const next = saveDemoSettings(partial);
    setS(next);
    nexusToast("Settings saved locally (demo).");
  };

  return (
    <div className="bg-white min-h-screen font-sans text-on-surface">
      <header className="sticky top-0 z-30 border-b-2 border-black bg-white px-4 py-4 md:px-8">
        <div className="mx-auto flex max-w-2xl items-center gap-4">
          <Link
            href="/"
            className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-black bg-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-colors hover:bg-slate-50"
            aria-label="Back to Nexus"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="font-display text-xl font-black text-black">
              Settings
            </h1>
            <p className="font-display text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Demo preferences · stored in your browser
            </p>
          </div>
        </div>
      </header>

      <motion.main
        className="mx-auto max-w-2xl space-y-6 px-4 py-8 md:px-8"
        variants={staggerContainer}
        initial="hidden"
        animate="show"
      >
        <Section title="Workspace">
          <div className="flex items-center justify-between gap-4 border-b-2 border-black/10 py-4 first:pt-0">
            <div className="flex items-center gap-3">
              <NexusLogoMark className="h-9 w-9 shrink-0" />
              <div>
                <Label htmlFor="dev-mode" className="font-display text-sm font-bold">
                  Developer mode
                </Label>
                <p className="mt-1 text-xs font-medium text-slate-500">
                  Show JSON-RPC tool log in the chat panel.
                </p>
              </div>
            </div>
            <Switch
              id="dev-mode"
              checked={s.devMode}
              onCheckedChange={(v) => patch({ devMode: v })}
            />
          </div>
          <div className="flex items-center justify-between gap-4 border-b-2 border-black/10 py-4">
            <div className="flex items-center gap-3">
              <LayoutGrid className="h-5 w-5 text-black" />
              <div>
                <Label htmlFor="compact" className="font-display text-sm font-bold">
                  Compact live feed
                </Label>
                <p className="mt-1 text-xs font-medium text-slate-500">
                  Slightly smaller result cards on wide screens.
                </p>
              </div>
            </div>
            <Switch
              id="compact"
              checked={s.compactFeed}
              onCheckedChange={(v) => patch({ compactFeed: v })}
            />
          </div>
          <div className="flex items-center justify-between gap-4 py-4">
            <div className="flex items-center gap-3">
              <Bell className="h-5 w-5 text-black" />
              <div>
                <Label htmlFor="hints" className="font-display text-sm font-bold">
                  Session hints
                </Label>
                <p className="mt-1 text-xs font-medium text-slate-500">
                  Extra placeholder copy in the chat empty state.
                </p>
              </div>
            </div>
            <Switch
              id="hints"
              checked={s.sessionHints}
              onCheckedChange={(v) => patch({ sessionHints: v })}
            />
          </div>
        </Section>

        <Section title="Reviewer demo parameters">
          <p className="mb-4 text-sm font-medium text-slate-600">
            Used by the <strong>Social Deadlock Breaker</strong> and{" "}
            <strong>Zero-waste meal</strong> scenarios on the home page (synthetic only).
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="party-size" className="font-display text-xs font-bold">
                Party size (deadlock)
              </Label>
              <input
                id="party-size"
                type="number"
                min={2}
                max={20}
                className="mt-1 w-full border-2 border-black bg-slate-50 px-3 py-2 font-display text-sm font-medium"
                value={s.deadlockPartySize}
                onChange={(e) =>
                  patch({ deadlockPartySize: Number(e.target.value) || s.deadlockPartySize })
                }
              />
            </div>
            <div>
              <Label htmlFor="budget" className="font-display text-xs font-bold">
                Budget / head (₹)
              </Label>
              <input
                id="budget"
                type="number"
                min={200}
                max={5000}
                step={50}
                className="mt-1 w-full border-2 border-black bg-slate-50 px-3 py-2 font-display text-sm font-medium"
                value={s.deadlockBudgetInr}
                onChange={(e) =>
                  patch({ deadlockBudgetInr: Number(e.target.value) || s.deadlockBudgetInr })
                }
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="city" className="font-display text-xs font-bold">
                City label (signals)
              </Label>
              <input
                id="city"
                type="text"
                className="mt-1 w-full border-2 border-black bg-slate-50 px-3 py-2 font-display text-sm font-medium"
                value={s.deadlockCity}
                onChange={(e) => patch({ deadlockCity: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="recipe" className="font-display text-xs font-bold">
                Recipe hint (zero-waste pantry diff)
              </Label>
              <input
                id="recipe"
                type="text"
                className="mt-1 w-full border-2 border-black bg-slate-50 px-3 py-2 font-display text-sm font-medium"
                value={s.zerowasteRecipeHint}
                onChange={(e) => patch({ zerowasteRecipeHint: e.target.value })}
              />
            </div>
          </div>
        </Section>

        <Section title="Data & demo">
          <div className="flex gap-3">
            <Database className="h-5 w-5 shrink-0 text-slate-400" />
            <p className="text-sm font-medium leading-relaxed text-slate-600">
              Nothing leaves your device except chat requests to your configured
              API. Clear site data in the browser to reset these toggles.
            </p>
          </div>
        </Section>

        <motion.div variants={fadeUp} className="pb-12">
          <Link
            href="/"
            className="inline-flex border-2 border-black bg-primary-container px-5 py-3 font-display text-xs font-black uppercase tracking-widest text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-shadow hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
          >
            Back to Nexus
          </Link>
        </motion.div>
      </motion.main>
    </div>
  );
}
