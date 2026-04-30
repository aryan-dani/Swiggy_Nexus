export async function POST() {
  const n = Math.floor(Math.random() * 900) + 100;
  return Response.json({
    ok: true,
    message: "New demo session scaffolded",
    session_number: n,
    id: `demo_${Date.now().toString(36)}`,
    label: "Fresh thread",
    created_at: Math.floor(Date.now() / 1000),
  });
}
