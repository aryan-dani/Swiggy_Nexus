"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUp,
  Loader2,
  Mic,
  PlusCircle,
  Terminal,
} from "lucide-react";
import { useCallback, useState } from "react";

import { NexusLogoMark } from "@/components/nexus-logo-mark";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { FeedItem } from "@/lib/api";
import { postChatStream } from "@/lib/api";
import { neoSpring, slideFromLeft, slideFromRight } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Role = "user" | "assistant";
type Msg = { id: string; role: Role; text: string };

export type ChatInterfaceProps = {
  onFeedItems: (items: FeedItem[]) => void;
  devMode: boolean;
  sessionHints?: boolean;
  /** Passed to same-origin mock orchestration (`/api/chat/stream`). */
  chatContext?: Record<string, unknown>;
};

export default function ChatInterface({
  onFeedItems,
  devMode,
  sessionHints = true,
  chatContext,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [thinking, setThinking] = useState<string[]>([]);
  const [showThinking, setShowThinking] = useState(true);
  const [rpcLogs, setRpcLogs] = useState<string[]>([]);

  const appendLog = useCallback((entry: Record<string, unknown>) => {
    const line = JSON.stringify(entry, null, 2);
    setRpcLogs((prev) => [...prev.slice(-80), line]);
  }, []);

  const runSend = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;

    setInput("");
    setBusy(true);
    setThinking([]);
    onFeedItems([]);
    setRpcLogs([]);

    const uid = () => crypto.randomUUID();
    setMsgs((m) => [...m, { id: uid(), role: "user", text }]);

    let assistantText = "";

    await postChatStream(text, chatContext, (ev) => {
      if (ev.type === "thinking") {
        setThinking((t) => [...t, ev.payload.text]);
      }
      if (ev.type === "tool") {
        appendLog(ev.payload);
      }
      if (ev.type === "feed") {
        onFeedItems(ev.payload.items);
      }
      if (ev.type === "assistant") {
        assistantText = ev.payload.text;
      }
      if (ev.type === "error") {
        assistantText = `Error: ${ev.payload.message}`;
      }
      if (ev.type === "done") {
        if (ev.payload.feed_items?.length) {
          onFeedItems(ev.payload.feed_items);
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
          "Run complete — check the live feed for mock MCP results.",
      },
    ]);

    setBusy(false);
  }, [appendLog, busy, chatContext, input, onFeedItems]);

  return (
    <div className="flex h-full min-h-[65vh] flex-col gap-4">
      <div
        id="nexus-chat-scroll"
        className="min-h-0 flex-1 space-y-6 overflow-y-auto pr-1 no-scrollbar"
      >
        {msgs.length === 0 && (
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={neoSpring}
            className="bento-card border-dashed bg-slate-50 p-4 font-display text-sm text-slate-600"
          >
            {sessionHints ? (
              <>
                Ask anything — e.g. snacks for coding, team dinner, or biryani
                delivery. Synthetic Swiggy-style tools only.
              </>
            ) : (
              <>Send a message to start. Mock MCP only — not real orders.</>
            )}
          </motion.p>
        )}

        {msgs.map((m) => (
          m.role === "user" ? (
            <motion.div
              key={m.id}
              variants={slideFromRight}
              initial="hidden"
              animate="show"
              className="flex items-end justify-end gap-3"
            >
              <div className="bento-card max-w-xl bg-indigo-50 px-5 py-4 shadow-[4px_4px_0px_0px_rgba(99,91,255,1)]">
                <p className="font-display text-[10px] font-black uppercase tracking-widest text-primary-container">
                  You
                </p>
                <p className="mt-2 text-left font-sans text-sm font-medium text-black">
                  {m.text}
                </p>
              </div>
              <div className="h-12 w-12 shrink-0 overflow-hidden rounded-full border-2 border-black bg-slate-200 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                <img
                  alt=""
                  className="h-full w-full object-cover"
                  src="https://randomuser.me/api/portraits/women/68.jpg"
                />
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
              <motion.div
                className="flex h-12 w-12 shrink-0 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                whileHover={{
                  boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)",
                  transition: neoSpring,
                }}
                whileTap={{ boxShadow: "2px 2px 0px 0px rgba(0,0,0,1)" }}
              >
                <NexusLogoMark className="h-full w-full" aria-label="Nexus" />
              </motion.div>
              <div className="min-w-0 flex-1">
                <div className="bento-card px-5 py-4">
                  <p className="font-sans text-sm font-medium leading-relaxed text-black">
                    {m.text}
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t-2 border-black/5 pt-3">
                    <span className="border-2 border-black bg-slate-100 px-2 py-0.5 font-display text-[10px] font-black uppercase tracking-wider">
                      Demo locale
                    </span>
                    <span className="font-mono text-[10px] text-slate-400">
                      NEXUS · MOCK MCP
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>
          )
        ))}

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
            <motion.div
              className="flex h-12 w-12 shrink-0 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
              animate={{ opacity: [0.75, 1, 0.75] }}
              transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
            >
              <NexusLogoMark className="h-full w-full" aria-label="Nexus is typing" />
            </motion.div>
            <div className="bento-card flex w-24 items-center justify-center py-4">
              <div className="flex gap-1">
                <span className="h-1 w-1 animate-bounce rounded-full bg-slate-500 [animation-delay:-0.3s]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-slate-500 [animation-delay:-0.15s]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-slate-500" />
              </div>
            </div>
          </motion.div>
        )}
        </AnimatePresence>
      </div>

      <div className="border-t-2 border-dashed border-black/10 pt-4">
        <motion.button
          type="button"
          onClick={() => setShowThinking((s) => !s)}
          whileTap={{ scale: 0.99 }}
          className="flex w-full items-center justify-between font-display text-xs font-bold uppercase tracking-widest text-slate-500 transition-colors hover:text-slate-800"
        >
          Agent reasoning
          <span className="tabular-nums">{showThinking ? "Hide" : "Show"}</span>
        </motion.button>
        <AnimatePresence initial={false}>
          {showThinking && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <div className="mt-2 max-h-28 overflow-y-auto border-2 border-black bg-slate-50 p-3 font-mono text-[11px] text-slate-700">
                <ul className="space-y-1">
                  {thinking.length === 0 && !busy && (
                    <li>No trace yet for this session.</li>
                  )}
                  {thinking.map((line, i) => (
                    <motion.li
                      key={`${i}-${line.slice(0, 20)}`}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ ...neoSpring, delay: i * 0.025 }}
                      className="border-l-2 border-primary-container/40 pl-2"
                    >
                      {line}
                    </motion.li>
                  ))}
                  {busy && thinking.length === 0 && (
                    <li className="flex items-center gap-2">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Starting…
                    </li>
                  )}
                </ul>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {devMode && (
          <motion.div
            key="dev-panel"
            initial={{ opacity: 0, height: 0, y: -8 }}
            animate={{ opacity: 1, height: "auto", y: 0 }}
            exit={{ opacity: 0, height: 0, y: -8 }}
            transition={neoSpring}
            className="overflow-hidden border-2 border-black bg-amber-100 p-3 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          >
            <div className="mb-2 flex items-center gap-2 font-display text-xs font-black uppercase text-black">
              <Terminal className="h-4 w-4" />
              JSON-RPC log
            </div>
            <ScrollArea className="h-36 rounded border-2 border-black bg-white">
              <pre className="p-2 font-mono text-[10px] text-slate-700">
                {rpcLogs.length === 0
                  ? "// Tool calls after send…"
                  : rpcLogs.join("\n---\n")}
              </pre>
            </ScrollArea>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-auto">
        <motion.form
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...neoSpring, delay: 0.1 }}
          onSubmit={(e) => {
            e.preventDefault();
            void runSend();
          }}
          whileTap={{ scale: 0.998 }}
          className="flex items-center gap-2 border-2 border-black bg-white p-2 pl-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-shadow focus-within:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
        >
          <motion.button
            type="button"
            className="text-slate-400 hover:text-black"
            whileHover={{ scale: 1.06, transition: neoSpring }}
            whileTap={{ scale: 0.96 }}
          >
            <PlusCircle size={24} aria-hidden />
          </motion.button>
          <input
            className="min-w-0 flex-1 border-none bg-transparent py-3 font-display text-sm font-bold text-black outline-none placeholder:text-slate-400"
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
          <motion.button
            type="button"
            className="text-slate-400 hover:text-black"
            aria-label="Voice (demo)"
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.95 }}
          >
            <Mic size={24} />
          </motion.button>
          <motion.button
            type="submit"
            disabled={busy || !input.trim()}
            whileHover={
              busy || !input.trim()
                ? undefined
                : {
                    scale: 1.03,
                    boxShadow: "5px 5px 0px 0px rgba(0,0,0,1)",
                    transition: neoSpring,
                  }
            }
            whileTap={
              busy || !input.trim()
                ? undefined
                : { scale: 0.97, boxShadow: "2px 2px 0px 0px rgba(0,0,0,1)" }
            }
            className={cn(
              "flex h-12 items-center justify-center gap-2 border-2 border-black bg-primary-container px-5 font-display text-xs font-black uppercase tracking-widest text-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-colors",
              "hover:bg-[#5248e6] disabled:cursor-not-allowed disabled:opacity-50"
            )}
          >
            Send <ArrowUp size={16} />
          </motion.button>
        </motion.form>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
          className="mt-3 text-center font-mono text-[10px] uppercase tracking-widest text-slate-400"
        >
          Nexus can make mistakes. Demo data only — verify before ordering.
        </motion.p>
      </div>
    </div>
  );
}
