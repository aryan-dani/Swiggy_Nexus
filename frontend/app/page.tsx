"use client";

import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { DashboardHeader } from "@/components/dashboard-header";
import ChatInterface from "@/components/chat-interface";
import McpFeed from "@/components/mcp-feed";
import type { FeedItem } from "@/lib/api";
import { loadDemoSettings, saveDemoSettings } from "@/lib/nexus-settings-storage";
import { fadeUp, neoSpring, staggerContainer } from "@/lib/motion";

export default function Home() {
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);
  const [sessionId, setSessionId] = useState(0);
  const [devMode, setDevMode] = useState(false);
  const [sessionHints, setSessionHints] = useState(true);

  useEffect(() => {
    const s = loadDemoSettings();
    setDevMode(s.devMode);
    setSessionHints(s.sessionHints);
  }, []);

  useEffect(() => {
    const sync = () => {
      const s = loadDemoSettings();
      setDevMode(s.devMode);
      setSessionHints(s.sessionHints);
    };
    window.addEventListener("focus", sync);
    return () => window.removeEventListener("focus", sync);
  }, []);

  const handleNewChat = useCallback(() => {
    setFeedItems([]);
    setSessionId((s) => s + 1);
  }, []);

  const scrollChatToTop = useCallback(() => {
    document
      .getElementById("nexus-chat-scroll")
      ?.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const setDevModePersist = useCallback((v: boolean) => {
    setDevMode(v);
    saveDemoSettings({ devMode: v });
  }, []);

  const sidebarProps = {
    onNewChat: handleNewChat,
    onRecent: scrollChatToTop,
    devMode,
    onDevModeChange: setDevModePersist,
  };

  return (
    <>
      <motion.aside
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={neoSpring}
        className="fixed bottom-0 left-0 top-0 z-40 box-border hidden w-72 min-w-72 max-w-72 flex-col overflow-x-hidden overflow-y-auto border-r-2 border-black bg-white px-6 pb-6 pt-8 pr-7 shadow-[6px_0_0_0_rgba(0,0,0,0.04)] md:flex"
      >
        <AppSidebar {...sidebarProps} className="h-full min-h-0" />
      </motion.aside>

      <div className="bg-white selection:bg-primary-container selection:text-white min-h-screen overflow-x-clip pb-px font-sans text-on-surface md:pl-72">
        <div className="flex min-h-screen flex-col">
          <DashboardHeader sidebarProps={sidebarProps} />

          <motion.main
            className="flex min-h-0 flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:flex-row lg:px-8 lg:py-8"
            variants={staggerContainer}
            initial="hidden"
            animate="show"
          >
            <motion.section
              variants={fadeUp}
              className="flex min-h-0 min-w-0 flex-1 flex-col lg:max-w-xl xl:max-w-2xl"
            >
              <ChatInterface
                key={sessionId}
                onFeedItems={setFeedItems}
                devMode={devMode}
                sessionHints={sessionHints}
              />
            </motion.section>
            <motion.section
              variants={fadeUp}
              className="flex min-h-0 min-w-0 flex-1 flex-col border-t-2 border-black pt-6 lg:min-h-[70vh] lg:border-l-2 lg:border-t-0 lg:pl-8 lg:pt-0"
            >
              <McpFeed items={feedItems} />
            </motion.section>
          </motion.main>
        </div>
      </div>
    </>
  );
}
