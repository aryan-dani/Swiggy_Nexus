"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUp,
  Check,
  ChevronDown,
  Loader2,
  PlusCircle,
  Terminal,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChatHero } from "@/components/chat-hero";
import {
  captionForMethod,
  DemoDirector,
  DemoSummaryCard,
  stepFromToolMethod,
  type DemoStepId,
} from "@/components/demo-director";
import { NexusLogoMark } from "@/components/nexus-logo-mark";
import { NexusSignalsBar } from "@/components/nexus-signals-bar";
import { VoiceMicButton } from "@/components/voice-mic-button";
import { renderSimpleMarkdown, ToolTraceTheater } from "@/components/tool-trace-theater";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { FeedItem } from "@/lib/api";
import { postChatStream } from "@/lib/api";
import { getToolCoverage, recordToolFromStream } from "@/lib/mcp-client";
import type { NexusDemoSettings, NexusReviewerScenario } from "@/lib/nexus-settings-storage";
import { neoSpring, slideFromLeft, slideFromRight } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Role = "user" | "assistant";
type Msg = { id: string; role: Role; text: string };

type ToolChip = {
  id: string;
  method: string;
  vertical: "food" | "im" | "dineout" | "other";
};

function verticalFromMethod(method: string): ToolChip["vertical"] {
  const m = method.toLowerCase();
  if (m.includes("dineout") || m.includes("book_table") || m.includes("available_slots"))
    return "dineout";
  if (
    m.includes("search_products") ||
    m.includes("update_cart") ||
    m.includes("checkout") ||
    m.includes("instamart") ||
    m.startsWith("im_")
  )
    return "im";
  if (m.includes("food") || m.includes("menu") || m.includes("place_food") || m.includes("restaurant"))
    return "food";
  return "other";
}

const VERT_CHIP: Record<ToolChip["vertical"], string> = {
  dineout: "border-indigo-300 bg-indigo-50 text-indigo-900",
  im: "border-emerald-300 bg-emerald-50 text-emerald-900",
  food: "border-orange-300 bg-orange-50 text-orange-900",
  other: "border-slate-300 bg-slate-50 text-slate-700",
};

export type ChatInterfaceProps = {
  onFeedItems: (items: FeedItem[]) => void;
  devMode: boolean;
  onDevModeChange?: (v: boolean) => void;
  sessionHints?: boolean;
  chatContext?: Record<string, unknown>;
  suggestedPrompt?: string;
  onRegisterSend?: (fn: (text: string) => void) => void;
  onChatComplete?: (assistantText: string) => void;
  demoSettings: NexusDemoSettings;
  onDemoSettingsChange: (next: NexusDemoSettings) => void;
  onResetSession?: () => void;
  onRunWow?: (scenario: NexusReviewerScenario, prompt: string) => void;
  onOpenConcierge?: () => void;
  onPickScenario?: (scenario: NexusReviewerScenario, prompt: string) => void;
};

export default function ChatInterface({
  onFeedItems,
  devMode,
  onDevModeChange,
  sessionHints = true,
  chatContext,
  suggestedPrompt,
  onRegisterSend,
  onChatComplete,
  demoSettings,
  onDemoSettingsChange,
  onResetSession,
  onRunWow,
  onOpenConcierge,
  onPickScenario,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const isChrono =
    chatContext?.scenario === "chrono_host" ||
    suggestedPrompt?.toLowerCase().includes("evening");

  useEffect(() => {
    if (suggestedPrompt) setInput(suggestedPrompt);
  }, [suggestedPrompt]);

  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [thinking, setThinking] = useState<string[]>([]);
  const [showThinking, setShowThinking] = useState(false);
  const [rpcLogs, setRpcLogs] = useState<string[]>([]);
  const [toolChips, setToolChips] = useState<ToolChip[]>([]);
  const [liveTool, setLiveTool] = useState<string | null>(null);
  const [streamPreview, setStreamPreview] = useState("");
  const [toolCount, setToolCount] = useState(0);
  const [demoStep, setDemoStep] = useState<DemoStepId | null>(null);
  const [demoCaption, setDemoCaption] = useState("");
  const [showDirector, setShowDirector] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [demoFailed, setDemoFailed] = useState(false);
  const [runStats, setRunStats] = useState<{ tools: number; verticals: number }>({ tools: 0, verticals: 0 });
  const [verticalsHit, setVerticalsHit] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [msgs, thinking, busy, streamPreview, toolChips, showSummary, scrollToBottom]);

  useEffect(() => {
    setToolCount(getToolCoverage().used);
    const sync = () => setToolCount(getToolCoverage().used);
    window.addEventListener("nexus-mcp-call", sync);
    return () => window.removeEventListener("nexus-mcp-call", sync);
  }, []);

  const appendLog = useCallback((entry: Record<string, unknown>) => {
    const line = JSON.stringify(entry, null, 2);
    setRpcLogs((prev) => [...prev.slice(-80), line]);
  }, []);

  const runSend = useCallback(
    async (overrideText?: string) => {
      const text = (overrideText ?? input).trim();
      if (!text || busy) return;

      if (!overrideText) setInput("");
      setBusy(true);
      setThinking([]);
      setLiveTool(null);
      setStreamPreview("");
      onFeedItems([]);
      setRpcLogs([]);
      setToolChips([]);
      setShowSummary(false);
      setDemoFailed(false);
      setRunStats({ tools: 0, verticals: 0 });
      setVerticalsHit(new Set());

      const chronoMode =
        chatContext?.scenario === "chrono_host" ||
        text.toLowerCase().includes("evening") ||
        text.toLowerCase().includes("12 guests");
      setShowDirector(Boolean(chronoMode));
      setDemoStep(chronoMode ? "plan" : null);
      setDemoCaption(chronoMode ? "Reading intent and picking verticals…" : "");

      const uid = () => crypto.randomUUID();
      setMsgs((m) => [...m, { id: uid(), role: "user", text }]);

      let assistantText = "";
      let sawBundle = false;
      let streamFailed = false;
      let runToolCount = 0;
      const verts = new Set<string>();

      await postChatStream(text, chatContext, (ev) => {
        if (ev.type === "thinking") {
          setThinking((t) => [...t, ev.payload.text]);
          setStreamPreview(ev.payload.text);
          if (chronoMode && !sawBundle) {
            setDemoStep("plan");
            setDemoCaption(ev.payload.text.slice(0, 80));
          }
        }
        if (ev.type === "tool") {
          appendLog(ev.payload);
          recordToolFromStream(ev.payload);
          setToolCount(getToolCoverage().used);
          runToolCount += 1;
          const method = String(ev.payload.method ?? "mcp_tool");
          setLiveTool(method);
          setStreamPreview(captionForMethod(method));
          const v = verticalFromMethod(method);
          verts.add(v);
          setVerticalsHit(new Set(verts));
          setToolChips((prev) => [
            ...prev,
            { id: `${method}-${prev.length}`, method, vertical: v },
          ]);
          if (chronoMode) {
            const step = stepFromToolMethod(method);
            if (step) {
              setDemoStep(step);
              setDemoCaption(captionForMethod(method));
            }
          }
        }
        if (ev.type === "feed") {
          onFeedItems(ev.payload.items);
          if (ev.payload.items?.some((i: FeedItem) => i.type === "event_bundle")) {
            sawBundle = true;
            setDemoStep("bundle");
            setDemoCaption("Bundle ready — review on the right →");
          }
        }
        if (ev.type === "assistant") {
          assistantText = ev.payload.text;
          if (/^(LLM error|Error)[:\s]/i.test(assistantText)) {
            streamFailed = true;
          }
        }
        if (ev.type === "error") {
          assistantText = `Error: ${ev.payload.message}`;
          streamFailed = true;
        }
        if (ev.type === "done") {
          if (ev.payload.feed_items?.length) {
            onFeedItems(ev.payload.feed_items);
            if (ev.payload.feed_items.some((i: FeedItem) => i.type === "event_bundle")) {
              sawBundle = true;
              setDemoStep("bundle");
              setDemoCaption("Bundle ready — review on the right →");
            }
          }
          const final = ev.payload.assistant_reply ?? assistantText;
          if (final) assistantText = final;
        }
      });

      setMsgs((m) => [
        ...m,
        {
          id: uid(),
          role: "assistant",
          text:
            assistantText ||
            "Run complete — check the Activity rail for mock MCP results.",
        },
      ]);

      onChatComplete?.(assistantText);
      setLiveTool(null);
      setStreamPreview("");
      setBusy(false);
      if (chronoMode) {
        if (streamFailed) {
          // Keep the director on the step where it died; never fake completion.
          setDemoFailed(true);
          setDemoCaption("Run failed — see the error message below. Try again.");
          setShowSummary(false);
        } else if (sawBundle) {
          setDemoStep("bundle");
          setRunStats({ tools: runToolCount, verticals: new Set([...verts].filter((v) => v !== "other")).size });
          setShowSummary(true);
        } else {
          // Finished without a bundle (plain answer) — hide the director quietly.
          setShowDirector(false);
        }
      }
    },
    [appendLog, busy, chatContext, input, onChatComplete, onFeedItems]
  );

  const runSendRef = useRef(runSend);
  runSendRef.current = runSend;

  useEffect(() => {
    onRegisterSend?.((text: string) => {
      void runSendRef.current(text);
    });
  }, [onRegisterSend]);

  const empty = msgs.length === 0 && !busy;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 pb-2">
        <h2 className="nexus-section-title text-sm">Chat</h2>
        {(busy || toolCount > 0) && (
          <span className="font-mono text-[10px] font-bold text-slate-500">
            Session tools · {toolCount}
          </span>
        )}
      </div>

      <div
        id="nexus-chat-scroll"
        className="neo-scrollbar min-h-0 flex-1 space-y-4 overflow-y-auto pr-1"
      >
        <DemoDirector
          visible={showDirector && (busy || showSummary || demoFailed)}
          activeStep={demoStep}
          caption={demoCaption}
          failed={demoFailed}
        />

        {empty && onRunWow && onOpenConcierge && onPickScenario ? (
          <ChatHero
            onRunWow={(scenario, prompt) => {
              onRunWow(scenario, prompt);
              setInput(prompt);
              window.setTimeout(() => {
                void runSendRef.current(prompt);
              }, 50);
            }}
            onOpenConcierge={onOpenConcierge}
            onPickScenario={onPickScenario}
          />
        ) : empty && sessionHints ? (
          <p className="bento-card-soft p-4 text-sm text-slate-600">
            {isChrono
              ? "Chrono-Host armed — send the prefilled prompt to stage the 3-vertical bundle."
              : "Ask anything — snacks, team dinner, or biryani. Synthetic Swiggy tools only."}
          </p>
        ) : null}

        {msgs.map((m) =>
          m.role === "user" ? (
            <motion.div
              key={m.id}
              variants={slideFromRight}
              initial="hidden"
              animate="show"
              className="flex items-end justify-end gap-3"
            >
              <div className="bento-card max-w-xl bg-indigo-50 px-4 py-3 shadow-[3px_3px_0px_0px_rgba(99,91,255,1)]">
                <p className="font-display text-[10px] font-black uppercase tracking-widest text-primary-container">
                  You
                </p>
                <p className="mt-1.5 text-left font-sans text-sm font-medium text-black">{m.text}</p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key={m.id}
              variants={slideFromLeft}
              initial="hidden"
              animate="show"
              className="flex items-start gap-3"
            >
              <div className="flex h-10 w-10 shrink-0 overflow-hidden rounded border border-black/20">
                <NexusLogoMark className="h-full w-full" aria-label="Nexus" />
              </div>
              <div className="bento-card-soft min-w-0 flex-1 px-4 py-3">
                <p className="font-sans text-sm font-medium leading-relaxed text-black">
                  {renderSimpleMarkdown(m.text)}
                </p>
              </div>
            </motion.div>
          )
        )}

        {showSummary && !busy && (
          <DemoSummaryCard
            toolCount={runStats.tools || toolChips.length}
            verticals={runStats.verticals}
            onOpenBundle={() => {
              document.getElementById("nexus-activity-rail")?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            }}
            onViewTraces={() => onDevModeChange?.(true)}
          />
        )}

        {toolChips.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {toolChips.map((chip) => (
              <span
                key={chip.id}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold",
                  VERT_CHIP[chip.vertical]
                )}
                title={chip.method}
              >
                <Check className="h-2.5 w-2.5" aria-hidden />
                {chip.method.replace(/^(food_|im_|dineout_)/, "").slice(0, 28)}
              </span>
            ))}
          </div>
        )}

        <AnimatePresence>
          {busy && (
            <motion.div
              key="typing"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={neoSpring}
              className="flex items-start gap-3"
            >
              <div className="flex h-10 w-10 shrink-0 overflow-hidden rounded border border-black/20">
                <NexusLogoMark className="h-full w-full" aria-label="Nexus is working" />
              </div>
              <div className="bento-card-soft flex min-w-0 flex-1 flex-col gap-1 px-4 py-3">
                {liveTool ? (
                  <p className="font-mono text-[11px] font-bold text-amber-800">
                    {captionForMethod(liveTool)}
                  </p>
                ) : streamPreview ? (
                  <p className="font-mono text-[11px] text-violet-700">{streamPreview}</p>
                ) : (
                  <div className="flex gap-1">
                    <span className="h-1 w-1 animate-bounce rounded-full bg-slate-500 [animation-delay:-0.3s]" />
                    <span className="h-1 w-1 animate-bounce rounded-full bg-slate-500 [animation-delay:-0.15s]" />
                    <span className="h-1 w-1 animate-bounce rounded-full bg-slate-500" />
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Dev traces live in the scroll region so they never shove the composer up */}
        <AnimatePresence>
          {devMode && (
            <motion.div
              key="dev-panel"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="rounded border border-amber-400 bg-amber-50 p-2"
            >
              <div className="mb-1 flex items-center gap-2 font-display text-[10px] font-black uppercase text-amber-900">
                <Terminal className="h-3.5 w-3.5" />
                Dev · JSON-RPC + traces
              </div>
              <ToolTraceTheater logs={rpcLogs} className="mb-1" />
              <ScrollArea className="h-24 rounded border border-black/10 bg-white">
                <pre className="p-2 font-mono text-[10px] text-slate-700">
                  {rpcLogs.length === 0 ? "// Tool calls after send…" : rpcLogs.join("\n---\n")}
                </pre>
              </ScrollArea>
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={bottomRef} className="h-px shrink-0" aria-hidden />
      </div>

      <div className="flex shrink-0 flex-col gap-1.5 border-t border-black/10 bg-white pt-2">
        {(thinking.length > 0 || busy) && (
          <div>
            <button
              type="button"
              onClick={() => setShowThinking((s) => !s)}
              className="flex w-full items-center gap-2 font-sans text-[11px] font-medium text-slate-500 hover:text-slate-800"
            >
              <ChevronDown
                className={cn("h-3.5 w-3.5 transition-transform", showThinking && "rotate-180")}
              />
              Planner reasoning · {thinking.length || (busy ? "…" : 0)} steps
            </button>
            <AnimatePresence initial={false}>
              {showThinking && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <ul className="mt-1 max-h-16 space-y-1 overflow-y-auto rounded border border-black/10 bg-slate-50 p-2 font-mono text-[10px] text-slate-600">
                    {thinking.map((line, i) => (
                      <li key={`${i}-${line.slice(0, 16)}`} className="border-l-2 border-violet-300 pl-2">
                        {line}
                      </li>
                    ))}
                    {busy && thinking.length === 0 && (
                      <li className="flex items-center gap-2">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Starting…
                      </li>
                    )}
                  </ul>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        <NexusSignalsBar
          settings={demoSettings}
          onSettingsChange={onDemoSettingsChange}
          onReset={onResetSession}
          onSuggestPrompt={(t) => setInput(t)}
        />

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void runSend();
          }}
          className="flex items-center gap-2 rounded-lg border-2 border-black bg-white p-2 pl-3 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]"
        >
          <button type="button" className="text-slate-400 hover:text-black" aria-label="Attach">
            <PlusCircle size={22} aria-hidden />
          </button>
          <VoiceMicButton
            disabled={busy}
            onTranscript={(text) => {
              setInput(text);
              void runSend(text);
            }}
          />
          <input
            autoFocus
            className="min-w-0 flex-1 border-none bg-transparent py-2.5 font-sans text-sm font-medium text-black outline-none placeholder:text-slate-400"
            placeholder="Ask Nexus…"
            value={input}
            disabled={busy}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void runSend();
              }
            }}
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className={cn(
              "flex h-10 items-center justify-center gap-2 border-2 border-black bg-primary-container px-4 font-display text-[10px] font-black uppercase tracking-widest text-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]",
              "hover:bg-[#5248e6] disabled:cursor-not-allowed disabled:opacity-50"
            )}
          >
            {busy ? (
              <>
                <Loader2 className="animate-spin" size={14} />
              </>
            ) : (
              <>
                Send <ArrowUp size={14} />
              </>
            )}
          </button>
        </form>
        <p className="pb-0.5 text-center font-mono text-[9px] uppercase tracking-widest text-slate-400">
          Demo data only — not real Swiggy orders
        </p>
      </div>
    </div>
  );
}
