# Swiggy Builders Club — What you can use and how

This repo's UI can use either the Next.js route stub (`frontend/app/api/chat/stream`) **or**, with `NEXT_PUBLIC_API_URL`, a **FastAPI backend** wired to fully **local** MCP mocks (`POST /food`, `/im`, `/dineout` — see [local mock docs](local-mock-mcp.md)).
For **real** Swiggy commerce tools, see the official [**Swiggy Builders Club** documentation](https://mcp.swiggy.com/builders/docs/).
The docs site exposes [Markdown twins](https://mcp.swiggy.com/builders/docs/index.md) (append `.md` to page paths) for easy fetching.

---

## What it is

- **Model Context Protocol (MCP)** over **streamable HTTP** at host `https://mcp.swiggy.com`: JSON-RPC tool calls with **OAuth 2.1 + PKCE** (same pattern as MCP clients such as Claude Desktop / Cursor).
- **India-focused** commerce: food delivery, Instamart grocery, Dineout table booking. **Production access** is whitelist/apply-driven; **`http://localhost` is explicitly supported** for building and demoing before production credentials.

---

## The three MCP servers (independent URLs)

| Server | POST endpoint | Purpose | Tools |
|--------|----------------|---------|-------|
| Food | `https://mcp.swiggy.com/food` | Restaurants, menus, variants/add-ons, cart, coupons, order, tracking | 14 |
| Instamart | `https://mcp.swiggy.com/im` | Grocery SKUs, cart, checkout, order history/track | 13 |
| Dineout | `https://mcp.swiggy.com/dineout` | Search restaurants for **going out**, slots, bookings | 8 |

**Sessions are per server.** Carts and orders do **not** automatically carry across Food / Instamart / Dineout. Compose multiple servers in one agent turn only via your orchestration ([combined recipe](https://mcp.swiggy.com/builders/docs/build/recipes/combined.md)).

---

## Tool surface (high level)

### Food (~14 tools)

Examples: `search_restaurants`, `get_restaurant_menu`, `search_menu`, `update_food_cart`, `get_food_cart`, `flush_food_cart`, `fetch_food_coupons`, `apply_food_coupon`, `place_food_order`, `get_food_orders`, `get_food_order_details`, `track_food_order`, `get_addresses` (shared with Instamart), `report_error`.

### Instamart (~13 tools)

Examples: `search_products`, `your_go_to_items`, `update_cart`, `get_cart`, `clear_cart`, `checkout`, `get_orders`, `get_order_details`, `track_order`, address helpers (`get_addresses`, `create_address`, `delete_address`), `report_error`.

### Dineout (~8 tools)

Examples: `search_restaurants_dineout`, `get_restaurant_details`, `get_available_slots`, `create_cart`, `book_table`, `get_booking_status`, `get_saved_locations`, `report_error`.

### Supporting docs

- [Canonical errors](https://mcp.swiggy.com/builders/docs/reference/errors.md)
- [Widgets](https://mcp.swiggy.com/builders/docs/build/widgets.md) (UI fragments alongside tool responses)
- [Multi-turn cart state](https://mcp.swiggy.com/builders/docs/build/agent-patterns/multi-turn-state.md)
- [Voice vs chat](https://mcp.swiggy.com/builders/docs/build/agent-patterns/voice-vs-chat.md)

Full catalogue: [Reference index](https://mcp.swiggy.com/builders/docs/reference/index.md).

---

## How to integrate (developer path)

1. **Loop:** The agent selects a tool → your MCP client sends JSON-RPC to **`/food`**, **`/im`**, or **`/dineout`** → the server returns a structured result.
2. **OAuth:** Authorize at `GET https://mcp.swiggy.com/auth/authorize` (PKCE S256); exchange at `POST https://mcp.swiggy.com/auth/token`; call MCP with `Authorization: Bearer <access_token>`. Discovery: `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource`. Details: [Authenticate](https://mcp.swiggy.com/builders/docs/start/authenticate.md).
3. **Scopes (v1):** `mcp:tools`, `mcp:resources`, `mcp:prompts` — **which product** you may call is gated by your **`client_id` server allowlist**, not finer scopes yet.
4. **Tokens:** Access token TTL is about **five days**. **Refresh-token issuance is not wired in v1.0** — treat expiry or `401` as re-authentication (see Authenticate).
5. **First smoke test:** Call `get_addresses` with `{}`, then `search_restaurants` using an `addressId` from the response ([Developer quickstart](https://mcp.swiggy.com/builders/docs/start/developer/index.md)).
6. **Frameworks:** OpenAI Agents SDK, Anthropic (native MCP), LangGraph / LangChain (`langchain-mcp-adapters`), Vercel AI SDK (`experimental_createMCPClient`), Mastra, PydanticAI, CrewAI, Google ADK, or raw `@modelcontextprotocol/sdk` / Python `mcp`. Walkthroughs: [Build an agent](https://mcp.swiggy.com/builders/docs/start/developer/build-an-agent.md).

Recipes:

- [Order food end-to-end](https://mcp.swiggy.com/builders/docs/build/recipes/order-food.md)
- [Order groceries end-to-end](https://mcp.swiggy.com/builders/docs/build/recipes/order-groceries.md)
- [Book a table](https://mcp.swiggy.com/builders/docs/build/recipes/book-a-table.md)
- [Ship to production](https://mcp.swiggy.com/builders/docs/build/ship-to-production.md)

---

## Other entry points

- **Consumer (no code):** Paste MCP config into Claude, ChatGPT, Cursor, VS Code, or Windsurf — [Connect your AI client](https://mcp.swiggy.com/builders/docs/start/consumer/use-in-ai-client.md).
- **Enterprise / multi-tenant:** [Delegated OAuth](https://mcp.swiggy.com/builders/docs/start/enterprise/delegated-auth.md).
- **Production access:** Apply at [mcp.swiggy.com/access](https://mcp.swiggy.com/access). Operations: [Operate](https://mcp.swiggy.com/builders/docs/operate/index.md), [Access & onboarding](https://mcp.swiggy.com/builders/docs/operate/access.md), [Data & compliance](https://mcp.swiggy.com/builders/docs/operate/data-and-compliance.md).

---

## Getting started in **Swiggy Nexus** (this repo)

**What runs today:** The Next.js UI can work without Python. By default, chat hits [`frontend/app/api/chat/stream/route.ts`](../frontend/app/api/chat/stream/route.ts) (SSE stub). If you set **`NEXT_PUBLIC_API_URL`** to your FastAPI backend, chat uses [`backend/agent.py`](../backend/agent.py) calling **local mock** MCP via [`backend/mcp_client.py`](../backend/mcp_client.py), not real `mcp.swiggy.com` — details in [local-mock-mcp.md](local-mock-mcp.md).

Pick one path below (you can combine 1 + 2 while you build 3/4).

### 1. Start **using** Swiggy MCP with no app code (fastest)

Follow [Connect your AI client](https://mcp.swiggy.com/builders/docs/start/consumer/use-in-ai-client.md): add the Swiggy MCP server entry to **Cursor** (or Claude Desktop, VS Code, etc.), complete **phone + OTP** OAuth in the browser, then prompt the model (e.g. “show my saved addresses”, “search restaurants near my address”). This does not change Swiggy Nexus; it gives you a working mental model of the real tools.

### 2. Get **developer access** (required for your own `client_id`)

1. Apply at [mcp.swiggy.com/access](https://mcp.swiggy.com/access) with redirect URIs (exact match; `http://localhost` is OK for dev) and which servers you need (`food`, `instamart`, `dineout`).
2. Implement or use the **OAuth 2.1 + PKCE** flow from [Authenticate](https://mcp.swiggy.com/builders/docs/start/authenticate.md). You will call MCP with `Authorization: Bearer <access_token>` on `POST https://mcp.swiggy.com/food` (or `/im`, `/dineout`).
3. **Never** put tokens in the browser or `NEXT_PUBLIC_*`. For a web app, OAuth runs on your **server** (or a confidential desktop flow); for local experiments only, a token in **`backend/` environment** is tolerable — rotate and re-auth when it expires (~5 days).

### 3. First **programmatic** checks (before wiring the UI)

Once you have a valid access token:

1. Use the official [Developer quickstart](https://mcp.swiggy.com/builders/docs/start/developer/index.md): call tool **`get_addresses`** with `{}`, then **`search_restaurants`** using an `addressId` from step 1.
2. Follow one end-to-end **[recipe](https://mcp.swiggy.com/builders/docs/build/recipes/order-food.md)** so you see the full chain (cart, coupons, place order, etc.) and error handling from [errors](https://mcp.swiggy.com/builders/docs/reference/errors.md).

Use whichever stack you prefer: **`@modelcontextprotocol/sdk`** / Python **`mcp`**, or [Build an agent](https://mcp.swiggy.com/builders/docs/start/developer/build-an-agent.md) recipes for LangGraph / Vercel AI SDK / OpenAI Agents SDK.

### 4. **Integrate with this codebase** (two realistic directions)

**A. Thin HTTP bridge (keep Nexus “demo graph”, swap the tool implementation)**  
Add a small client module (e.g. under `backend/`) that POSTs **streamable HTTP MCP JSON-RPC** to `https://mcp.swiggy.com/{food|im|dineout}` with the Bearer token, and maps responses into the same shapes your [`synthesize()`](../backend/agent.py) step already expects — *or* generalize feed cards from real tool payloads (widgets docs help). Replace calls to the **local mock** client in [`mcp_client.py`](../backend/mcp_client.py) (`agent.py`) or call real HTTP MCP with Bearer auth with this client for the verticals you enable. Expect to **rename tools and arguments**: real names are `search_restaurants`, `get_restaurant_menu`, etc., not `food_search_restaurants`.

**B. Model-led tool calling (recommended for production-like behaviour)**  
Replace the fixed `analyze_context` → single-tool `call_tools` pipeline with an LLM that sees **tool schemas from Swiggy MCP** (`tools/list`) and chooses steps (LangGraph + `langchain-mcp-adapters`, or framework from the Builders docs). Stream tool + assistant events into the same SSE format [`main.py`](../backend/main.py) already emits so the Nexus UI stays compatible.

### 5. Point the frontend at the backend

After `uvicorn backend.main:app` is running, set in `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Rebuild/restart Next.js so chat requests hit your Python agent instead of the built-in mock route.

---

## Note on `llms.txt`

`https://mcp.swiggy.com/llms.txt` may return **401** without credentials. The indexed doc map is equivalent to [`/builders/docs/index.md`](https://mcp.swiggy.com/builders/docs/index.md).
