# Swiggy Nexus — Pitch & integration overview

**Disclaimer:** Nexus is an independent POC. **Not affiliated with Swiggy.** All catalog, pricing, bookings, and “join” links in the hosted demo are **synthetic** unless you attach real APIs.

---

## One-sentence pitch

Swiggy Nexus is an **autonomous lifestyle orchestrator**: a Planner layer reads user intent plus external cues (calendar, weather, cohort context — simulated in this demo); an **Executor** calls **Swiggy-shaped tools** (Food, Instamart, Dineout) through an MCP-compatible surface so fulfilment stays **deterministic**, not hallucinated prose.

---

## What the hosted (Vercel) demo proves without credentials

The Next.js build runs **everything on one origin**:

- **`POST /api/chat/stream`** streams Server-Sent Events: **Planner-labelled** reasoning lines, **Executor** tool payloads, then **Synth** Normalized **Live Feed** cards (`Food · Instamart · Dineout (mock)`).
- **`GET/POST …/api/sidebar/*`** serve static JSON for sidebar affordances.
- The home page **Reviewer · Signals & scenarios** rail injects **synthetic context** (deep-work block, rain in Pune, watch party) and **three story presets** aligned to the product narrative:
  1. **Social Deadlock Breaker** — Dineout arbiter + slot grid + join strip (mock URL).
  2. **Flow-state fueler** — Instamart SKUs (Americano + protein snack) under a “deep work” story.
  3. **Zero-waste meal** — recipe vs **virtual pantry diff** (missing SKUs only).

No separate Python service or LLM is required for reviewers to see **vertical routing** and **tool-shaped** execution — the graph is **deterministic** on purpose for API review.

---

## Dual-agent architecture (conceptual)

| Role | Responsibility | In this repo today |
|------|----------------|-------------------|
| **Planner** | Intent + vertical selection + params (lat/long, party size, recipe hint) | Labelled `thinking` lines + heuristics in `frontend/lib/demo-chat-mock.ts` (mirrors `backend/agent.py` intent). |
| **Executor** | Calls tools (search, inventory, availability) | SSE `tool` events with `method` / `params` / `result` (JSON-RPC-shaped). |
| **Synth** | Maps tool JSON → UI cards | Feed items → `McpFeed` via `feed-mapper`. |

With **credentials**, Executor `dispatch()` (Python) or TS equivalent swaps mock results for **live Swiggy MCP tools** — same SSE contract to the UI.

---

## Why MCP matters for the real build

REST alone is brittle for autonomous commerce:

- **Tool calling** binds the model to schemas (`food_search_restaurants`, `instamart_get_inventory`, `dineout_check_availability` in mocks).
- **Memory** (preferences + pantry projections) persists across sessions — today localStorage for demo knobs; prod would use Swiggy + user consent.
- **Idempotency + rate limits**: executor should tag requests, respect inventory volatility, and surface partial failures — the UI already has Dev Mode RPC inspection for auditors.

---

## Hand-off after API access

1. Replace mock `dispatch` with MCP / partner SDK exposing the same capability names.
2. Add LLM Planner (optional Phase 2) — today’s POC is deterministic for repeatable reviewer flows.
3. Keep **SSE event shape** stable so Nexus UI does not churn.

Questions welcome on the credential form — cite this file and the deployed demo URL.
