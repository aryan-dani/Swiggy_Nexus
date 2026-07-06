import { buildDemoChatEvents } from "@/lib/demo-chat-mock";

export async function POST(req: Request) {
  let message = "";
  let context: Record<string, unknown> = {};
  try {
    const body = (await req.json()) as {
      message?: unknown;
      context?: unknown;
    };
    message = typeof body?.message === "string" ? body.message : "";
    if (
      body?.context !== undefined &&
      body.context !== null &&
      typeof body.context === "object" &&
      !Array.isArray(body.context)
    ) {
      context = body.context as Record<string, unknown>;
    }
  } catch {
    /* empty demo */
  }

  const events = buildDemoChatEvents(message, context);

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      for (let i = 0; i < events.length; i++) {
        const ev = events[i];
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
        if (i > 0) await new Promise((r) => setTimeout(r, 70));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
