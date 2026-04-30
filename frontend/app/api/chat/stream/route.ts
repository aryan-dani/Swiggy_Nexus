import { buildDemoChatEvents } from "@/lib/demo-chat-mock";

export async function POST(req: Request) {
  let message = "";
  try {
    const body = (await req.json()) as { message?: unknown };
    message = typeof body?.message === "string" ? body.message : "";
  } catch {
    /* empty demo */
  }

  const events = buildDemoChatEvents(message);

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      for (let i = 0; i < events.length; i++) {
        const ev = events[i];
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
        if (i > 0) await new Promise((r) => setTimeout(r, 120));
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
