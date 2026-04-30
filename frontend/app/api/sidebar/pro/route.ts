export async function GET() {
  return Response.json({
    headline: "Nexus Pro — demo ledger",
    bullets: ["Priority lane (mock)", "Team seats (mock)", "Audit JSON-RPC exports"],
  });
}
