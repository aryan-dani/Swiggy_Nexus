export async function GET() {
  return Response.json({
    items: [
      { id: "a1", label: "Mock archive row 1", kind: "thread" },
      { id: "a2", label: "Mock archive row 2", kind: "thread" },
    ],
  });
}
