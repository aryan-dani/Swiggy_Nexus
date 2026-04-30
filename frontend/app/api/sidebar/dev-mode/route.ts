export async function POST(req: Request) {
  let enabled = false;
  try {
    const body = (await req.json()) as { enabled?: unknown };
    enabled = Boolean(body?.enabled);
  } catch {
    /* noop */
  }
  return Response.json({
    received: true,
    dev_mode: enabled,
    logged_at: Date.now(),
  });
}
