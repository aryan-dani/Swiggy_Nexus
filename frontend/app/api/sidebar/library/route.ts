export async function GET() {
  return Response.json({
    pins: [
      { id: "p1", title: "Koramangala shortlist", type: "pin" },
      { id: "p2", title: "Protein-forward wraps", type: "pin" },
      { id: "p3", title: "Budget team lunch", type: "pin" },
    ],
  });
}
