export type StreamEvent =
  | { type: "thinking"; payload: { text: string } }
  | { type: "tool"; payload: Record<string, unknown> }
  | { type: "feed"; payload: { items: FeedItem[] } }
  | { type: "assistant"; payload: { text: string } }
  | { type: "done"; payload: { assistant_reply?: string | null; feed_items: FeedItem[] } }
  | { type: "error"; payload: { message: string } };

export type FeedItem = {
  type: string;
  title: string;
  subtitle?: string;
  meta?: Record<string, unknown>;
};

/** Normalize API base — Render Blueprint may inject hostname without `https://`. */
export function normalizeApiBase(raw?: string): string {
  if (raw === undefined || raw === "") return "";
  let base = raw.trim().replace(/\/$/, "");
  if (!/^https?:\/\//i.test(base)) {
    base = `https://${base}`;
  }
  return base;
}

/**
 * Same-origin `/api/*` when unset — uses built-in Route Handlers in `app/api/` (demo / Vercel).
 * Set `NEXT_PUBLIC_API_URL` to your FastAPI base (no trailing slash) to use an external backend.
 *
 * Must be the **API** host (`swiggy-nexus-api.onrender.com`), not the Render Next.js web service.
 */
export function getApiBase(): string {
  let base = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL);
  // Guard common misconfig: Concierge lives on FastAPI, not the frontend web service.
  if (base.includes("swiggy-nexus-web.")) {
    base = base.replace("swiggy-nexus-web.", "swiggy-nexus-api.");
  }
  return base;
}

export async function postChatStream(
  message: string,
  context: Record<string, unknown> | undefined,
  onEvent: (ev: StreamEvent) => void
): Promise<void> {
  const res = await fetch(`${getApiBase()}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, context: context ?? {} }),
  });

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => res.statusText);
    onEvent({ type: "error", payload: { message: text || `HTTP ${res.status}` } });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const block of parts) {
      const line = block.trim();
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      try {
        const parsed = JSON.parse(raw) as StreamEvent;
        onEvent(parsed);
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
}
