"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import { getNexusToastEventName } from "@/lib/nexus-toast-bus";
import { neoSpring } from "@/lib/motion";

export function NexusToastHost() {
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const name = getNexusToastEventName();
    const onToast = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (typeof detail === "string") {
        setMsg(detail);
      }
    };
    window.addEventListener(name, onToast);
    return () => window.removeEventListener(name, onToast);
  }, []);

  useEffect(() => {
    if (!msg) return;
    const t = window.setTimeout(() => setMsg(null), 3400);
    return () => window.clearTimeout(t);
  }, [msg]);

  return (
    <div
      className="pointer-events-none fixed bottom-6 left-1/2 z-[100] flex w-[min(100%-2rem,28rem)] -translate-x-1/2 justify-center px-4"
      aria-live="polite"
    >
      <AnimatePresence mode="wait">
        {msg && (
          <motion.div
            key={msg}
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={neoSpring}
            className="pointer-events-auto border-2 border-black bg-white px-5 py-3 text-center font-display text-xs font-bold uppercase tracking-wide text-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          >
            {msg}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
