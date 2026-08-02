"use client";

import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AnalyticsView } from "@/components/analytics-view";
import { AppSidebar } from "@/components/app-sidebar";
import ChatInterface from "@/components/chat-interface";
import { DashboardHeader } from "@/components/dashboard-header";
import { DeadlockArena } from "@/components/deadlock-arena";
import { DialecticArena } from "@/components/dialectic-arena";
import { FoodCartDrawer } from "@/components/food-cart-drawer";
import { InstamartCartDrawer } from "@/components/instamart-cart-drawer";
import { LibraryView, saveLibrarySession } from "@/components/library-view";
import { MenuExplorer } from "@/components/menu-explorer";
import McpFeed from "@/components/mcp-feed";
import { NexusCommandCenter } from "@/components/nexus-command-center";
import { ConciergeOps } from "@/components/concierge-ops";
import { VariantPicker } from "@/components/variant-picker";
import type { FeedItem } from "@/lib/api";
import type { NexusCardResult } from "@/components/nexus-result-card";
import { useNexusSession } from "@/lib/nexus-session-context";
import { callMcp } from "@/lib/mcp-client";
import {
  DEMO_SETTINGS_DEFAULTS,
  loadDemoSettings,
  orchestrationContextFromSettings,
  saveDemoSettings,
  type NexusDemoSettings,
  type NexusReviewerScenario,
} from "@/lib/nexus-settings-storage";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { fadeUp, neoSpring, staggerContainer } from "@/lib/motion";

function HomeInner() {
  const sendRef = useRef<(text: string) => void>();
  const { requestId, refreshCarts, setOnSendChat } = useNexusSession();
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);
  const [sessionId, setSessionId] = useState(0);
  const [suggestedPrompt, setSuggestedPrompt] = useState("");
  const [activeTab, setActiveTab] = useState<string>("chat");
  const [demo, setDemo] = useState<NexusDemoSettings>(() => DEMO_SETTINGS_DEFAULTS);
  const [foodCartOpen, setFoodCartOpen] = useState(false);
  const [imCartOpen, setImCartOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState<{ id: string; name: string } | null>(null);
  const [variantOpen, setVariantOpen] = useState<{
    productId: string;
    name: string;
    variants: { spinId: string; label: string; price_inr: number }[];
  } | null>(null);

  useEffect(() => {
    setDemo(loadDemoSettings());
  }, []);

  const chatContext = useMemo(() => orchestrationContextFromSettings(demo), [demo]);

  const handleDemoPatch = useCallback((next: NexusDemoSettings) => {
    setDemo(next);
  }, []);

  const handleNewChat = useCallback(() => {
    setFeedItems([]);
    setSessionId((s) => s + 1);
    setSuggestedPrompt("");
    setActiveTab("chat");
  }, []);

  const scrollChatToTop = useCallback(() => {
    document.getElementById("nexus-chat-scroll")?.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const setDevModePersist = useCallback((v: boolean) => {
    setDemo(saveDemoSettings({ devMode: v }));
  }, []);

  const handleRegisterSend = useCallback(
    (fn: (text: string) => void) => {
      sendRef.current = fn;
      setOnSendChat(fn);
    },
    [setOnSendChat]
  );

  const reviewerScenarioRef = useRef(demo.reviewerScenario);
  reviewerScenarioRef.current = demo.reviewerScenario;

  const handleChatComplete = useCallback(
    (text: string) => {
      saveLibrarySession(text.slice(0, 48), reviewerScenarioRef.current);
      void refreshCarts();
    },
    [refreshCarts]
  );

  /** WOW demo — do NOT force developer mode; Demo Director narrates instead. */
  const handleWowDemo = useCallback(
    (scenario: NexusReviewerScenario, prompt: string, variant?: import("@/lib/wow-variants").WowVariant) => {
      if (variant && typeof window !== "undefined") {
        try {
          window.sessionStorage.setItem("nexus_wow_variant_v1", JSON.stringify(variant));
        } catch {
          /* ignore */
        }
      }
      const next = saveDemoSettings({ reviewerScenario: scenario });
      setDemo(next);
      setSuggestedPrompt(prompt);
      setActiveTab("chat");
      setFeedItems([]);
    },
    []
  );

  const handlePickScenario = useCallback((scenario: NexusReviewerScenario, prompt: string) => {
    const next = saveDemoSettings({ reviewerScenario: scenario });
    setDemo(next);
    setSuggestedPrompt(prompt);
    setActiveTab("chat");
  }, []);

  const handleCardAction = useCallback(
    async (card: NexusCardResult) => {
      const meta = card.meta ?? {};
      if (card.type === "food") {
        const rid = String(meta.restaurant_id ?? meta.restaurantId ?? "fd_dom_101");
        setMenuOpen({ id: rid, name: card.title });
        return;
      }
      if (card.type === "grocery") {
        const pid = String(meta.product_id ?? "im_chips_03");
        const spin = String(meta.spinId ?? "spin_lays_52");
        setVariantOpen({
          productId: pid,
          name: card.title,
          variants: [{ spinId: spin, label: "default", price_inr: Number(meta.price_inr ?? 20) }],
        });
        return;
      }
      if (card.type === "dineout") {
        const rid = String(meta.restaurant_id ?? "do_italian_804");
        nexusToast(`Open slots for ${card.title} — use Deadlock arena or chat.`);
        void callMcp(
          "dineout",
          "check_availability",
          { restaurantId: rid, guestCount: demo.deadlockPartySize },
          requestId
        );
      }
    },
    [demo.deadlockPartySize, requestId]
  );

  const sidebarProps = {
    onNewChat: handleNewChat,
    onRecent: scrollChatToTop,
    devMode: demo.devMode,
    onDevModeChange: setDevModePersist,
    onNavigate: setActiveTab,
  };

  return (
    <>
      <motion.aside
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={neoSpring}
        className="fixed bottom-0 left-0 top-0 z-40 box-border hidden w-72 min-w-72 max-w-72 flex-col overflow-x-hidden overflow-y-auto border-r border-black/15 bg-white px-6 pb-8 pt-8 pr-8 md:flex"
      >
        <AppSidebar {...sidebarProps} className="h-full min-h-0" />
      </motion.aside>

      <div className="flex h-dvh min-h-0 flex-col overflow-x-clip overflow-y-auto bg-white font-sans text-on-surface selection:bg-primary-container selection:text-white md:overflow-hidden md:pl-72">
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="shrink-0">
            <DashboardHeader sidebarProps={sidebarProps} />
          </div>

          <div className="shrink-0 border-b border-black/10 px-4 py-2 md:px-8">
            <NexusCommandCenter
              onOpenFoodCart={() => setFoodCartOpen(true)}
              onOpenImCart={() => setImCartOpen(true)}
            />
          </div>

          <motion.main
            className={
              activeTab === "chat"
                ? "flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 sm:px-6 lg:flex-row lg:gap-0 lg:overflow-hidden lg:px-8 lg:py-4"
                : "neo-scrollbar flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 sm:px-6 lg:px-8 lg:py-4"
            }
            variants={staggerContainer}
            initial="hidden"
            animate="show"
          >
            {activeTab === "chat" ? (
              <>
                <motion.section
                  variants={fadeUp}
                  className="flex h-full min-h-0 min-w-0 flex-1 flex-col lg:max-w-xl lg:overflow-hidden xl:max-w-2xl"
                >
                  <ChatInterface
                    key={sessionId}
                    onFeedItems={setFeedItems}
                    devMode={demo.devMode}
                    onDevModeChange={setDevModePersist}
                    sessionHints={demo.sessionHints}
                    chatContext={chatContext}
                    suggestedPrompt={suggestedPrompt}
                    onRegisterSend={handleRegisterSend}
                    onChatComplete={handleChatComplete}
                    demoSettings={demo}
                    onDemoSettingsChange={handleDemoPatch}
                    onResetSession={handleNewChat}
                    onRunWow={handleWowDemo}
                    onOpenConcierge={() => setActiveTab("concierge")}
                    onPickScenario={handlePickScenario}
                  />
                </motion.section>
                <motion.section
                  variants={fadeUp}
                  className="flex h-full min-h-0 min-w-0 flex-1 flex-col border-t border-black/10 pt-6 lg:overflow-y-auto lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0"
                >
                  <McpFeed
                    items={feedItems}
                    activeScenario={demo.reviewerScenario}
                    compactFeed={demo.compactFeed !== false}
                    onCardAction={handleCardAction}
                    onChronoConfirm={(text) => sendRef.current?.(text)}
                    onOpenImCart={() => setImCartOpen(true)}
                    onOpenFoodCart={() => setFoodCartOpen(true)}
                    watchParty={demo.signalWatchParty}
                    arenaSlot={
                      demo.reviewerScenario === "deadlock" ? (
                        <DeadlockArena
                          partySize={demo.deadlockPartySize}
                          budgetInr={demo.deadlockBudgetInr}
                        />
                      ) : demo.reviewerScenario === "dialectic" ? (
                        <DialecticArena
                          onTriggerCommerce={(action) => {
                            sendRef.current?.(action);
                          }}
                        />
                      ) : undefined
                    }
                  />
                </motion.section>
              </>
            ) : activeTab === "concierge" ? (
              <motion.div
                variants={fadeUp}
                className="neo-scrollbar w-full min-h-0 flex-1 overflow-y-auto px-2 pb-10"
              >
                <ConciergeOps />
              </motion.div>
            ) : activeTab === "analytics" ? (
              <motion.div
                variants={fadeUp}
                className="neo-scrollbar w-full min-h-0 flex-1 overflow-y-auto px-2 pb-10"
              >
                <AnalyticsView />
              </motion.div>
            ) : activeTab === "library" ? (
              <motion.div
                variants={fadeUp}
                className="neo-scrollbar w-full min-h-0 flex-1 overflow-y-auto px-2 pb-10"
              >
                <LibraryView />
              </motion.div>
            ) : (
              <motion.div
                variants={fadeUp}
                className="flex w-full flex-col items-center justify-center rounded-xl border border-black/15 bg-slate-50 p-12 text-center"
              >
                <h2 className="mb-4 font-display text-3xl font-black uppercase tracking-tight text-black">
                  Archive
                </h2>
                <p className="max-w-md font-sans text-sm font-medium text-slate-600">
                  Demo archive entries live on the FastAPI backend when running locally.
                </p>
                <button
                  type="button"
                  onClick={handleNewChat}
                  className="mt-8 border-2 border-black bg-neo-mint px-6 py-3 font-display text-sm font-black uppercase tracking-widest text-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                >
                  Return to Chat
                </button>
              </motion.div>
            )}
          </motion.main>
        </div>
      </div>

      <FoodCartDrawer open={foodCartOpen} onClose={() => setFoodCartOpen(false)} />
      <InstamartCartDrawer open={imCartOpen} onClose={() => setImCartOpen(false)} />
      {menuOpen && (
        <MenuExplorer
          open
          restaurantId={menuOpen.id}
          restaurantName={menuOpen.name}
          onClose={() => setMenuOpen(null)}
        />
      )}
      {variantOpen && (
        <VariantPicker
          open
          productId={variantOpen.productId}
          productName={variantOpen.name}
          variants={variantOpen.variants}
          onClose={() => setVariantOpen(null)}
        />
      )}
    </>
  );
}

export default function Home() {
  return <HomeInner />;
}
