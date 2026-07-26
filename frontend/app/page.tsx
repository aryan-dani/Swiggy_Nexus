"use client";

import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AddressRail } from "@/components/address-rail";
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
import { NexusSignalsBar } from "@/components/nexus-signals-bar";
import { NexusWowLauncher } from "@/components/nexus-wow-launcher";
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

  const handleWowDemo = useCallback(
    (scenario: NexusReviewerScenario, prompt: string) => {
      const next = saveDemoSettings({ reviewerScenario: scenario, devMode: true });
      setDemo(next);
      setSuggestedPrompt(prompt);
      setActiveTab("chat");
      window.setTimeout(() => sendRef.current?.(prompt), 200);
    },
    []
  );

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
        void callMcp("dineout", "check_availability", { restaurantId: rid, guestCount: demo.deadlockPartySize }, requestId);
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
        className="fixed bottom-0 left-0 top-0 z-40 box-border hidden w-72 min-w-72 max-w-72 flex-col overflow-x-hidden overflow-y-auto border-r-2 border-black bg-white px-6 pb-8 pt-8 pr-8 shadow-[6px_0_0_0_rgba(0,0,0,0.04)] md:flex"
      >
        <AppSidebar {...sidebarProps} className="h-full min-h-0" />
      </motion.aside>

      <div className="bg-white selection:bg-primary-container selection:text-white min-h-screen overflow-x-clip pb-px font-sans text-on-surface md:pl-72">
        <div className="flex min-h-screen flex-col">
          <DashboardHeader sidebarProps={sidebarProps} />

          <div className="border-b-2 border-black/10 px-4 py-2 md:px-8">
            <NexusCommandCenter
              onOpenFoodCart={() => setFoodCartOpen(true)}
              onOpenImCart={() => setImCartOpen(true)}
            />
          </div>

          <motion.main
            className="flex min-h-0 flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:flex-row lg:px-8 lg:py-8"
            variants={staggerContainer}
            initial="hidden"
            animate="show"
          >
            {activeTab === "chat" ? (
              <>
                <motion.section
                  variants={fadeUp}
                  className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 lg:max-w-xl xl:max-w-2xl"
                >
                  <AddressRail />
                  <NexusWowLauncher onRunDemo={handleWowDemo} />
                  <NexusSignalsBar
                    settings={demo}
                    onSettingsChange={handleDemoPatch}
                    onReset={handleNewChat}
                    onSuggestPrompt={setSuggestedPrompt}
                  />
                  {demo.reviewerScenario === "dialectic" && (
                    <DialecticArena
                      onTriggerCommerce={(action) => {
                        sendRef.current?.(action);
                      }}
                    />
                  )}
                  <ChatInterface
                    key={sessionId}
                    onFeedItems={setFeedItems}
                    devMode={demo.devMode}
                    sessionHints={demo.sessionHints}
                    chatContext={chatContext}
                    suggestedPrompt={suggestedPrompt}
                    onRegisterSend={handleRegisterSend}
                    onChatComplete={handleChatComplete}
                  />
                </motion.section>
                <motion.section
                  variants={fadeUp}
                  className="flex min-h-0 min-w-0 flex-1 flex-col border-t-2 border-black pt-6 lg:min-h-[70vh] lg:border-l-2 lg:border-t-0 lg:pl-8 lg:pt-0"
                >
                  {demo.reviewerScenario === "deadlock" && (
                    <div className="mb-4">
                      <DeadlockArena
                        partySize={demo.deadlockPartySize}
                        budgetInr={demo.deadlockBudgetInr}
                      />
                    </div>
                  )}
                  <McpFeed
                    items={feedItems}
                    activeScenario={demo.reviewerScenario}
                    compactFeed={demo.compactFeed}
                    onCardAction={handleCardAction}
                    onChronoConfirm={(text) => sendRef.current?.(text)}
                    onOpenImCart={() => setImCartOpen(true)}
                    onOpenFoodCart={() => setFoodCartOpen(true)}
                    watchParty={demo.signalWatchParty}
                  />
                </motion.section>
              </>
            ) : activeTab === "library" ? (
              <motion.div variants={fadeUp} className="w-full px-2">
                <LibraryView />
              </motion.div>
            ) : activeTab === "concierge" ? (
              <motion.div variants={fadeUp} className="w-full px-2">
                <ConciergeOps />
              </motion.div>
            ) : activeTab === "analytics" ? (
              <motion.div variants={fadeUp} className="w-full px-2">
                <AnalyticsView />
              </motion.div>
            ) : (
              <motion.div
                variants={fadeUp}
                className="flex w-full flex-col items-center justify-center rounded-xl border-4 border-black bg-slate-50 p-12 text-center shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]"
              >
                <h2 className="mb-4 font-display text-4xl font-black uppercase tracking-tight text-black">
                  Archive
                </h2>
                <p className="max-w-md font-sans text-lg font-medium text-slate-600">
                  Demo archive entries live on the FastAPI backend when running locally.
                </p>
                <motion.button
                  whileHover={{ scale: 1.05, boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)" }}
                  whileTap={{ scale: 0.95, boxShadow: "2px 2px 0px 0px rgba(0,0,0,1)" }}
                  onClick={handleNewChat}
                  className="mt-8 border-2 border-black bg-neo-mint px-6 py-3 font-display text-sm font-black uppercase tracking-widest text-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                >
                  Return to Chat
                </motion.button>
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
