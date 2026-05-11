"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import {
  Award,
  BarChart2,
  ChevronRight,
  History,
  Library,
  Plus,
  Settings2,
} from "lucide-react";
import { motion } from "framer-motion";

import { NexusLockup } from "@/components/nexus-logo-mark";
import { fadeUp, neoSpring, staggerContainer } from "@/lib/motion";
import {
  fetchSidebarAnalytics,
  fetchSidebarArchive,
  fetchSidebarLibrary,
  fetchSidebarPro,
  postSidebarDevMode,
  postSidebarNewChat,
} from "@/lib/sidebar-api";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { cn } from "@/lib/utils";

const sidebarNeoHover = {
  scale: 1.02,
  boxShadow: "6px 6px 0px 0px rgba(0,0,0,1)",
  transition: neoSpring,
};

const sidebarNeoTap = {
  scale: 0.99,
  boxShadow: "2px 2px 0px 0px rgba(0,0,0,1)",
  transition: neoSpring,
};

export type AppSidebarProps = {
  className?: string;
  onNewChat: () => void;
  onRecent?: () => void;
  devMode: boolean;
  onDevModeChange: (v: boolean) => void;
  onNavigate?: (tab?: string) => void;
};

function SidebarLink({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void | Promise<void>;
}) {
  return (
    <motion.button
      type="button"
      variants={fadeUp}
      whileHover={sidebarNeoHover}
      whileTap={sidebarNeoTap}
      onClick={onClick}
      className={cn(
        "flex w-full max-w-full items-center gap-3 border-2 border-black px-3 py-3 text-left font-display text-sm font-bold shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-colors",
        active
          ? "bg-indigo-50 text-indigo-900 [&_svg]:text-indigo-900"
          : "bg-white text-slate-800 hover:bg-slate-50 [&_svg]:text-slate-800"
      )}
    >
      {icon}
      <span>{label}</span>
    </motion.button>
  );
}

export function AppSidebar({
  className,
  onNewChat,
  onRecent,
  devMode,
  onDevModeChange,
  onNavigate,
}: AppSidebarProps) {
  const close = (tab?: string) => onNavigate?.(tab);

  return (
    <motion.div
      className={cn("flex h-full min-h-0 min-w-0 max-w-full flex-col", className)}
      initial="hidden"
      animate="show"
      variants={staggerContainer}
    >
      <motion.div
        variants={fadeUp}
        className="mb-6 w-full min-w-0 shrink-0 py-4"
      >
        <NexusLockup />
      </motion.div>

      <div className="neo-scrollbar flex min-h-0 min-w-0 max-w-full flex-1 flex-col gap-2 overflow-x-hidden overflow-y-auto pb-1">
        <motion.button
          type="button"
          variants={fadeUp}
          whileHover={sidebarNeoHover}
          whileTap={sidebarNeoTap}
          onClick={async () => {
            close("chat");
            try {
              const r = await postSidebarNewChat();
              nexusToast(`${r.message} · #${r.session_number}`);
            } catch {
              nexusToast("Backend offline — new chat started locally.");
            }
            onNewChat();
          }}
          className="flex w-full max-w-full items-center gap-3 border-2 border-black bg-primary-container px-4 py-3 text-left font-display text-xs font-black uppercase tracking-widest text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-white">
            <Plus className="h-4 w-4 text-white" strokeWidth={2.5} aria-hidden />
          </span>
          <span>New Chat</span>
        </motion.button>

        <div className="mt-4 space-y-2">
          <SidebarLink
            icon={<Library size={18} />}
            label="Library"
            active
            onClick={async () => {
              onRecent?.();
              close("library");
              try {
                const { pins } = await fetchSidebarLibrary();
                nexusToast(`${pins.length} pin(s): ${pins.map((p) => p.title).join(" · ")}`);
              } catch {
                nexusToast("Library API unreachable — scrolled chat only.");
              }
            }}
          />
          <SidebarLink
            icon={<BarChart2 size={18} />}
            label="Analytics"
            onClick={async () => {
              close("analytics");
              try {
                const a = await fetchSidebarAnalytics();
                nexusToast(
                  `Sessions: ${a.sessions_started} · ${a.mock_tool_calls_24h} mock tool calls (24h demo).`
                );
              } catch {
                nexusToast("Analytics API unreachable.");
              }
            }}
          />
          <SidebarLink
            icon={<History size={18} />}
            label="Archive"
            onClick={async () => {
              close("archive");
              try {
                const { items } = await fetchSidebarArchive();
                nexusToast(`Archive: ${items.length} entr(y/ies) on demo backend.`);
              } catch {
                nexusToast("Archive API unreachable.");
              }
            }}
          />
        </div>

        <motion.div
          variants={fadeUp}
          className="mt-6 border-t-2 border-black pt-4"
        >
          <Link
            href="/settings"
            onClick={close}
            className="mb-2 flex w-full items-center gap-2 px-1 font-display text-[10px] font-black uppercase tracking-widest text-slate-500 transition-colors hover:text-black"
          >
            <Settings2 className="h-3 w-3" />
            Settings
          </Link>
          <motion.button
            type="button"
            role="switch"
            aria-checked={devMode}
            whileTap={{ scale: 0.99 }}
            onClick={() => {
              const next = !devMode;
              onDevModeChange(next);
              void postSidebarDevMode(next).catch(() => {
                nexusToast("Dev mode saved locally only (API log failed).");
              });
            }}
            className="flex w-full items-center justify-between gap-3 border-2 border-black bg-white px-3 py-3 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
          >
            <span className="text-left font-display text-xs font-bold text-black">
              Developer mode
            </span>
            <span
              className={cn(
                "relative h-7 w-12 shrink-0 border-2 border-black",
                devMode ? "bg-primary-container" : "bg-slate-200"
              )}
            >
              <motion.span
                className="absolute top-0.5 left-0.5 h-5 w-5 border-2 border-black bg-white shadow-sm"
                animate={{ x: devMode ? 18 : 0 }}
                transition={{ type: "spring", stiffness: 500, damping: 35 }}
              />
            </span>
          </motion.button>
        </motion.div>
      </div>

      <motion.div variants={fadeUp} className="mt-auto shrink-0 pt-6">
        <motion.button
          type="button"
          onClick={async () => {
            close();
            try {
              const p = await fetchSidebarPro();
              nexusToast(`${p.headline}: ${p.bullets.join(" · ")}`);
            } catch {
              nexusToast("Pro pitch API unreachable — still 100% demo.");
            }
          }}
          whileHover={sidebarNeoHover}
          whileTap={sidebarNeoTap}
          className="group flex w-full max-w-full items-center justify-between border-2 border-black bg-neo-mint px-4 py-4 text-left shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
        >
          <div className="flex items-center gap-2">
            <Award className="text-black" size={18} />
            <span className="font-display text-xs font-black uppercase tracking-widest text-black">
              Upgrade to Pro
            </span>
          </div>
          <motion.div
            animate={{ opacity: [0.55, 1, 0.55] }}
            transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
          >
            <ChevronRight className="text-black" size={16} />
          </motion.div>
        </motion.button>
        <p className="mt-3 text-[10px] font-medium leading-relaxed text-slate-500">
          Not affiliated with Swiggy. Synthetic API — Builders Club demo only.
        </p>
      </motion.div>
    </motion.div>
  );
}
