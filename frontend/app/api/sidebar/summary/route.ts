export async function GET() {
  return Response.json({
    analytics: {
      sessions_started: 42,
      mock_tool_calls_24h: 128,
      avg_latency_ms: 890,
      top_intent: "group dinner",
      note: "Static demo counters — backend not wired.",
    },
    library: [
      { id: "pin-1", title: "Koramangala shortlist", type: "pins" },
      { id: "pin-2", title: "Office snacks playbook", type: "pins" },
    ],
    archive_preview: [{ id: "arch-7", summary: "Biryani run (synthetic)", at: Date.now() }],
  });
}
