import { NextResponse } from "next/server";

import { normalizeApiBase } from "@/lib/api";
import { invokeMockMcp, type McpVertical } from "@/lib/mcp-mock/dispatcher";

function backendBase(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? process.env.MCP_BACKEND_URL;
  const base = normalizeApiBase(raw);
  return base || null;
}

export async function POST(
  req: Request,
  ctx: { params: Promise<{ vertical: string }> }
) {
  const { vertical: rawVertical } = await ctx.params;
  const vertical = rawVertical as McpVertical;
  if (!["food", "im", "dineout"].includes(vertical)) {
    return NextResponse.json({ success: false, error: { code: "BAD_VERTICAL", message: "Invalid vertical" } }, { status: 400 });
  }

  let body: { method?: string; params?: Record<string, unknown> };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: { code: "BAD_JSON", message: "Invalid JSON" } }, { status: 400 });
  }

  const method = body.method?.trim();
  if (!method) {
    return NextResponse.json({ success: false, error: { code: "VALIDATION", message: "method required" } }, { status: 400 });
  }

  const params = body.params ?? {};
  const base = backendBase();

  if (base) {
    try {
      const path = vertical === "im" ? "im" : vertical;
      const res = await fetch(`${base}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ method, params }),
      });
      const json = await res.json();
      return NextResponse.json(json, { status: res.status });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Backend proxy failed";
      return NextResponse.json({ success: false, error: { code: "PROXY", message: msg } }, { status: 502 });
    }
  }

  const result = invokeMockMcp(vertical, method, params);
  return NextResponse.json(result);
}
