export async function GET() {
  return Response.json({
    sessions_started: 42,
    mock_tool_calls_24h: 128,
    avg_latency_ms: 890,
    top_intent: "group dinner",
    note: "Static demo — replace with `/api/analytics` from FastAPI.",
  });
}
