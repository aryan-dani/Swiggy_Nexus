# Swiggy Builders Club MCP — Local Knowledge Base

> **Source:** [mcp.swiggy.com/builders](https://mcp.swiggy.com/builders) (fetched 2026-07-06). 
> Synthesized for Swiggy Nexus local development. Not affiliated with Swiggy.

**Machine-readable upstream:**
- Index: `https://mcp.swiggy.com/builders/llms.txt`
- Full dump: `https://mcp.swiggy.com/builders/llms-full.txt`
- Per-page: append `.md` to any `/builders/docs/...` URL

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Authentication & Transport](#2-authentication--transport)
3. [Rate Limits & Error Handling](#3-rate-limits--error-handling)
4. [Agent Patterns](#4-agent-patterns)
5. [End-to-End Recipes](#5-end-to-end-recipes)
6. [Complete Tool Reference (35 tools)](#6-complete-tool-reference-35-tools)
7. [TypeScript Schema Appendix](#7-typescript-schema-appendix)
8. [Mock-vs-Production Gap Matrix](#8-mock-vs-production-gap-matrix)

---

## 1. Architecture Overview

Swiggy Builders Club exposes **35 MCP tools** across **3 independent streamable-HTTP servers**:

| Server | Endpoint | Tools | Domain |
| --- | --- | --- | --- |
| Food | `POST https://mcp.swiggy.com/food` | 14 | Restaurant delivery, menus, cart, coupons, orders |
| Instamart | `POST https://mcp.swiggy.com/im` | 13 | Grocery quick-commerce |
| Dineout | `POST https://mcp.swiggy.com/dineout` | 8 | Table booking / reservations |

**Key architectural facts:**

- **Transport:** MCP streamable HTTP with JSON-RPC 2.0 (`tools/call`, `tools/list`).
- **Auth:** OAuth 2.1 + PKCE (S256). One Bearer token works across all three servers.
- **Sessions:** Per-server carts and orders; carts do **not** cross Food / Instamart / Dineout.
- **Region:** India-only (AWS Mumbai primary, Singapore failover).
- **Widgets:** Food server has `hasWidgets: true` (iframe layer; v1.1).
- **Payment (v1):** COD only for Builders Club orders; Food cart cap **₹1000**; Instamart minimum **₹99**.

### Standard response envelope

```json
{
  "success": true,
  "data": { /* tool-specific payload */ },
  "message": "optional human-readable message"
}
```

Failure:

```json
{
  "success": false,
  "error": {
    "message": "human-readable description",
    "reportLink": "https://... (optional)",
    "reportHint": "Run report_error to share diagnostics (optional)"
  }
}
```

### JSON-RPC call shape

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_restaurants",
    "arguments": { "addressId": "addr_01HXYZ", "query": "biryani" }
  },
  "id": 1
}
```

---

## 2. Authentication & Transport

### OAuth 2.1 + PKCE (from official docs)

> OAuth 2.1 with PKCE - how to get credentials, complete the flow, and handle expired tokens.

Swiggy MCP uses **OAuth 2.1 with PKCE** for every external caller. The same flow Claude Desktop, Cursor, and ChatGPT use automatically is what your agent framework uses under the hood. Understand it here, then let your framework handle it in production.

If you're a platform operator brokering Swiggy for end users (voice assistant, in-app agent), read [delegated auth](/docs/start/enterprise/delegated-auth.md) instead - this page covers the direct developer flow.

## The flow at a glance

```
┌──────────┐                  ┌─────────────┐
│  Client  │                  │   Swiggy    │
│ (your    │                  │   OAuth     │
│  agent)  │                  │   server    │
└────┬─────┘                  └──────┬──────┘
     │  1. /authorize (PKCE S256)    │
     ├──────────────────────────────►│
     │                               │  2. Phone + OTP in browser
     │  3. 302 → redirect_uri + code │
     │◄──────────────────────────────┤
     │                               │
     │  4. POST /auth/token          │
     │     (code + verifier)         │
     ├──────────────────────────────►│
     │                               │  5. Issue signed JWT
     │◄──────────────────────────────┤
     │  { access_token, expires_in } │
     │                               │
     │  6. POST /food                │
     │     Authorization: Bearer ... │
     ├──────────────────────────────►│
```

## Endpoints

Base: `https://mcp.swiggy.com`

| Endpoint | Purpose |
| --- | --- |
| `GET  /auth/authorize` | Start the flow - user lands on consent UI |
| `POST /auth/token` | Exchange authorization code for access token |
| `POST /auth/logout` | Revoke current session |
| `GET  /.well-known/oauth-authorization-server` | OAuth server metadata (RFC 8414) |
| `GET  /.well-known/oauth-protected-resource` | Resource metadata (RFC 9728) |

The consent UI served at `/auth/authorize` uses internal endpoints (`/auth/send-otp`, `/auth/verify-otp`) to collect phone + OTP in the browser - these are **not part of the OAuth contract** and are not callable by third-party clients.

## Step-by-step (manual walkthrough)

You don't need to apply for or manage a client identity. Swiggy MCP supports [Dynamic Client Registration (RFC 7591)](https://datatracker.ietf.org/doc/html/rfc7591) at `POST /auth/register` - MCP-compatible clients (Claude Desktop, Cursor, ChatGPT, mcp-remote) call it transparently and you never see the step.

### 1. Generate PKCE verifier + challenge

```ts

const codeVerifier = crypto.randomBytes(32).toString("base64url");
const codeChallenge = crypto
  .createHash("sha256")
  .update(codeVerifier)
  .digest("base64url");
```

### 2. Redirect the user to `/auth/authorize`

```
https://mcp.swiggy.com/auth/authorize?
  response_type=code&
  client_id=<from-dcr>&
  redirect_uri=<your-callback>&
  code_challenge=<codeChallenge>&
  code_challenge_method=S256&
  state=<random-csrf-token>&
  scope=mcp:tools
```

### 3. Exchange the code

Your `redirect_uri` receives `?code=...&state=...`. Exchange:

```bash
curl -X POST https://mcp.swiggy.com/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "code": "<code-from-step-2>",
    "code_verifier": "<verifier-from-step-1>",
    "redirect_uri": "<your-callback>"
  }'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJI...",
  "token_type": "Bearer",
  "expires_in": 432000,
  "scope": "mcp:tools mcp:resources mcp:prompts"
}
```

### 4. Call Swiggy MCP

```
POST /food HTTP/1.1
Host: mcp.swiggy.com
Authorization: Bearer eyJhbGciOiJI...
```

## Scopes

| Scope | Grants |
| --- | --- |
| `mcp:tools` | Call any tool on any Swiggy MCP server the authenticated user is allowed to use |
| `mcp:resources` | Read MCP resources (widget registry, static metadata) |
| `mcp:prompts` | Access server-supplied prompt templates |

The v1 scope model is **server-level**, not read/write-split. Today, access to Food, Instamart, and Dineout is controlled at the user level (via the user's Swiggy account) rather than via per-application allowlists. Finer-grained read/write and per-domain scopes (`food.read`, `im.write`, ...) and per-application server allowlists are on the roadmap but not enforced today.

## Redirect URIs

- **HTTPS required** (except `http://localhost` for local development)
- Exact-match allowlist - no wildcards
- Custom schemes allowed for known MCP clients (`cursor://`, `vscode://`, `claude://`, `windsurf://`)
- No open redirects

To register a new client redirect URI or scheme, email [builders@swiggy.in](mailto:builders@swiggy.in).

## Token lifecycle

| Item | Lifetime |
| --- | --- |
| Access token | 5 days |
| User session | 30 days idle, sliding |
| Authorization code | 120 seconds, single-use |

Tokens can be revoked server-side before `exp` (user logs out, security event). Always treat 401 as "re-run authorization"; never cache success assumptions.

## Handling expired tokens

When a tool call returns 401:

```ts
async function callWithReauth<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (e: any) {
    if (e?.status === 401) {
      await reAuthenticate();
      return fn();
    }
    throw e;
  }
}
```

Most frameworks handle this for you. For raw MCP clients, wrap your `callTool` in the pattern above.

The metadata document advertises `refresh_token` as a supported grant type, but **refresh-token issuance is not wired in v1.0** - `/auth/token` only handles `authorization_code`. Treat the 5-day access token as the full session: when it expires (or is revoked), re-run the authorization flow. Rolling refresh tokens are on the roadmap for v1.1 - see [versioning](/docs/operate/versioning.md).

## What to store

- Store `access_token` in memory or secure storage (OS keychain, vault).
- Store `expires_at = now() + expires_in` and proactively refresh when ≤ 60s remain.
- **Never** log tokens to disk in plaintext.
- **Never** send tokens over non-HTTPS transports.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| 401 on every call | No or invalid credentials | Re-run authorization |
| 401 after some time | Token expired | Silent re-auth if session still valid |
| 419 | Session revoked | Full re-auth (phone + OTP) |
| 403 | Scope too narrow | Re-auth with broader scope |
| Stuck on `/authorize` | Bad `redirect_uri` | Must exact-match allowlisted URI |
| "Cannot resolve session" | Missing `Authorization` header | Add `Bearer <token>` to every call |

See [Ship to production](/docs/build/ship-to-production.md) for the full error-handling pattern.


---

## 3. Rate Limits & Error Handling

### Rate limits

> How Swiggy MCP handles abusive traffic today, the quotas we plan to advertise, and how to request a larger allocation.

## Status today

Rate limiting is **not enforced at the MCP layer in v1.0**. Abusive traffic is shed upstream (at Swiggy's ingress and core services), not by the MCP server itself. That means:

- You will not see `429 Too Many Requests` from a Swiggy MCP endpoint today.
- You will not see `X-RateLimit-*` response headers today.
- If upstream sheds your traffic, the tool call surfaces as an `UPSTREAM_ERROR`-class failure (see [errors](/docs/reference/errors.md)) - retry with exponential backoff.

If you're building for production traffic that will exceed the planned quotas below, email [builders@swiggy.in](mailto:builders@swiggy.in) **before** you launch so we can negotiate a custom ceiling and keep you off the upstream shedder.

## Planned quotas (v1.x developer tier)

These are the ceilings we'll advertise once MCP-layer rate limiting ships. They are **guidance, not enforcement**, today.

| Scope | Planned limit |
| --- | --- |
| Per authenticated user, per server | 120 requests / minute |
| Per authenticated user, per server (write tools) | 30 requests / minute |
| Burst (10-second window) | 2× steady-state |

Limits are keyed on the authenticated user. Enterprise integrators will get bespoke ceilings scoped at onboarding.

## Planned response contract

When MCP-layer rate limiting ships, every successful response will carry:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1720000060
```

Throttled calls will return:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 23
```

With the standard error envelope (`error.message` populated). A symbolic `error.code` of `RATE_LIMITED` will be added once the error-code registry ships - see [errors](/docs/reference/errors.md).

## How to upgrade

Mail [builders@swiggy.in](mailto:builders@swiggy.in) with:

1. Your integration name and a contact email.
2. Expected QPS (sustained and peak) with justification.
3. Surface context - voice agent, batch jobs, chat agent all have different burst shapes.

Turnaround: typically same business day once validated. Enterprise partners get bespoke ceilings written into the contract.

## Best practices (apply today)

- **Batch where possible** - one `get_addresses` per session is plenty; don't re-fetch on every turn.
- **Cache low-churn data** - saved addresses, restaurant metadata, menu images change slowly.
- **Don't poll `track_*` faster than 10s** - delivery-partner ETA updates arrive at that cadence.
- **Back off aggressively on transient upstream errors** - exponential backoff with jitter, max 5 retries.
- **Separate user activity from background jobs** - if you run nightly analytics, talk to us at onboarding so we can carve out a bespoke ceiling and keep that traffic off your interactive budget.

## Voice & ambient guidance

Voice agents and TV surfaces have different shapes than text chat:

- **Lower QPS, higher burstiness** - a user says "order food" and your agent makes 4-6 tool calls in 3 seconds.
- **Peak-hour amplification** - Indian mealtime traffic (12:00-14:00, 19:00-22:00 IST) amplifies through voice surfaces; your daily budget may be fine while your hourly peak isn't.
- **Stick to `your_go_to_items` for reorders** - one call replaces 3-5 search calls for a returning user.

Enterprise voice/ambient partners get a rate-limit profile shaped to their surface, not the developer-tier defaults.


### Error codes

> How Swiggy MCP tools report failures, and how to react to each class of error.

## What the server emits today

All tools return failure responses in a uniform envelope:

```json
{
  "success": false,
  "error": {
    "message": "human-readable description",
    "reportLink": "https://...",
    "reportHint": "Run report_error to share diagnostics"
  }
}
```

- `message` - always present.
- `reportLink` / `reportHint` - optional, surfaced when the server has captured a diagnostic bundle the caller can share with the Builders team.

Auth failures are additionally reported via JSON-RPC error codes at the transport layer (`-32001` for unauthenticated/expired sessions, `-32603` for unexpected internal failures). Treat the HTTP status code and JSON-RPC code as secondary signals; the primary contract is the `error.message` string.

## How to classify errors today

Until the symbolic code registry below ships, classify by `error.message` prefix and HTTP status. The canonical buckets:

| Bucket | How to detect | React |
| --- | --- | --- |
| Auth failure | HTTP 401 or JSON-RPC `-32001` | Re-run the OAuth flow |
| Bad input | HTTP 400 with message starting `Invalid ...` / `Missing ...` | Fix the arguments; do not retry |
| Upstream timeout | HTTP 504 or message containing `timeout` | Exponential backoff, max 5 retries |
| Upstream error | HTTP 502/503 | Exponential backoff, max 5 retries |
| Domain failure | HTTP 200 with `success: false` | Read `message`; most are terminal (out of stock, slot gone, restaurant closed) - surface to the user, do not retry |
| Internal error | HTTP 500 or JSON-RPC `-32603` | Exponential backoff once; escalate via `report_error` if it persists |

For every failure, `report_error` is available on each server to generate a shareable diagnostic link.

## Retry strategy

Exponential backoff with jitter. Start at 500ms, double up to 8s, cap at 5 retries. See [Ship to production](/docs/build/ship-to-production.md) for the full pattern and per-tool idempotency guarantees.

## Roadmap: symbolic code registry

A stable `error.code` field is planned. Once it ships, the server will populate the following codes; agents can then branch on `error.code` instead of parsing messages. **None of these are emitted today** - rely on the message/HTTP-status buckets above.

### Core codes (planned)

| Code | Meaning | HTTP |
| --- | --- | --- |
| `UNAUTHENTICATED` | No or invalid session credentials | 401 |
| `TOKEN_EXPIRED` | Access token past its expiry | 401 |
| `SESSION_REVOKED` | Session invalidated | 419 |
| `INSUFFICIENT_SCOPE` | Need broader OAuth scope | 403 |
| `RATE_LIMITED` | Too many requests | 429 |
| `VALIDATION_ERROR` | Input failed schema check | 400 |
| `NOT_FOUND` | Resource doesn't exist | 404 |
| `UPSTREAM_TIMEOUT` | Swiggy upstream slow | 504 |
| `UPSTREAM_ERROR` | Swiggy upstream failure | 502 |
| `INTERNAL_ERROR` | Unexpected server-side failure | 500 |

### Domain codes (planned)

- **Instamart**: `ITEM_OUT_OF_STOCK`, `CART_EXPIRED`, `ADDRESS_NOT_SERVICEABLE`, `MIN_ORDER_NOT_MET`.
- **Food**: `RESTAURANT_CLOSED`, `ITEM_UNAVAILABLE`, `COUPON_INVALID`, `COUPON_NOT_APPLICABLE`, `COUPON_REQUIRES_ONLINE_PAYMENT`.
- **Dineout**: `SLOT_UNAVAILABLE`, `RESTAURANT_NOT_BOOKABLE`, `BOOKING_WINDOW_CLOSED`.

When the registry ships, the `code` field will be added to `error` without changing the rest of the envelope - agents that already parse `message` keep working.


### Documented response fields (from official agent guidance)

These fields are explicitly referenced in Swiggy docs but not fully specified in response schemas:

| Tool / context | Fields |
| --- | --- |
| `search_restaurants` | `availabilityStatus` (`OPEN` \| `CLOSED` \| `UNAVAILABLE`), `distanceKm`, `nextOffset` |
| `search_products` | `products[].variants[].spinId` (SKU identifier for cart) |
| `get_food_cart` | `valid_addons`, `availablePaymentMethods`, `total`, `offers.coupon_applied`, `coupon_discount` |
| `update_food_cart` | `offers.coupon_applied` (coupon_discount=0 means suggested, not applied) |
| `place_food_order` | `orderId`, branded success `message` |
| `track_food_order` / `track_order` | ETA, delivery status timeline |
| `get_addresses` | `addressId`, `label`, display text — **no** lat/lng |
| `get_saved_locations` (Dineout) | `lat`, `lng`, address IDs |
| `get_available_slots` | `slots[].slotId`, `slots[].deals[].itemId`, `slot.reservationTime` |
| `book_table` | `bookingId` / order ID in `data` |

*Label: partial schema — inferred from agent guidance.*

---

## 4. Agent Patterns

### Multi-turn cart state

> Carrying cart identity across user turns on a stateless protocol.

Swiggy's cart state lives server-side, keyed to the authenticated session. Tools like `update_food_cart` and `update_cart` mutate that server-side cart; subsequent `get_food_cart` / `get_cart` calls see the mutation.

That means: your agent doesn't need to carry cart IDs or contents between turns. Just call `get_*_cart` at the top of any turn that might touch the cart, and you'll see the truth.

## Pattern: refresh at turn boundary

```ts
// Every turn that might involve cart state, start with:
const cart = await client.callTool({ name: "get_food_cart" });

// Decide next step based on what's actually in the cart server-side,
// NOT based on what you remember from the last turn
```

This avoids drift between "what the agent thinks is in the cart" and "what Swiggy actually has".

## Pattern: confirm before mutating

Because the cart is shared state, mutating it in a multi-turn conversation requires care:

```
Turn 1:  User: "Add chicken biryani"
         Agent: [update_food_cart(add biryani)]
                "Added 1 chicken biryani (₹349). Anything else?"

Turn 2:  User: "Make it 2"
         Agent: [get_food_cart → sees 1 biryani]
                [update_food_cart(set biryani quantity to 2)]
                "Now 2 biryanis (₹698). Anything else?"

Turn 3:  User: "Actually, place the order"
         Agent: [get_food_cart → confirms current state]
                "Order: 2 chicken biryanis, total ₹698, COD. Place now?"
```

Call `get_food_cart` **before** `place_food_order` regardless of how confident you are - the user may have edited in the Swiggy app between turns.

## Restaurant switch (Food)

A Food cart binds to one restaurant. If the user asks for something from a different restaurant, the cart flushes automatically. Surface this:

```
User:  "Add butter chicken from Punjab Grill"
Agent: [currently 2 biryanis from Biryani House in cart]
       "That will clear your Biryani House cart (2 chicken biryanis,
        ₹698). Continue?"
```

If you don't warn, the user loses work silently - bad for trust.

## Address switch (Instamart)

An Instamart cart binds to the delivery address (different addresses may have different serviceability and stock). Changing address mid-cart risks serviceability and stock failures on the new address.

Safer pattern: `clear_cart` before switching address.

## Across server boundaries

If your agent uses Food + Instamart + Dineout in one session:

- **Carts are per-server, not shared.** A Food cart doesn't affect an Instamart cart.
- **Authentication is shared.** One OAuth token works across all three servers.
- **Orders are per-server.** `get_food_orders` won't show Instamart orders.

## Abandoned carts

Carts have a TTL. If the user walks away mid-conversation and returns later, a stale cart may return `CART_EXPIRED`. Re-fetch, rebuild if necessary, confirm with the user before re-placing items.

## Don't cache cart state in your agent's memory

Tempting optimization: "I'll just remember what I added so I don't have to re-fetch". Don't. The authoritative copy is server-side, and:

- The user may edit in the Swiggy app.
- Items may go out of stock between turns.
- Prices may change.
- Coupons may become invalid.

`get_*_cart` is cheap (milliseconds). Always read before you mutate or confirm.

### Voice vs chat

> The same Swiggy tool, different response contracts. Design for TTS and rich cards separately.

A `search_restaurants` response that works great in Claude's chat UI (long list, rich cards, ratings, distances) is a disaster on a car's voice assistant - it'll read 18 restaurant names while the user tries to change lanes.

Voice and chat surfaces want different things from the same tool. Your agent's job is to shape the answer for its surface.

## When to assume voice

You're on voice if any of these are true:

- The client is a car, TV, smart speaker, or ambient surface.
- The response will be TTS-rendered without a screen.
- The user typed no input (they spoke).
- Your framework's surface metadata says voice (some frameworks expose `ctx.surface === "voice"`).

Otherwise, assume chat: a visible screen, the user can scan, widgets help.

## Voice response contract

Your system prompt should include something like:

> **Note**
>
> You are on a voice surface. Your responses will be spoken, not shown. Follow these rules:
> 
> - **Maximum 3 items** in any list you read aloud. Summarise "+ 5 more" if there are more.
> - Say **prices in Indian rupees** aloud - "₹249" → "two hundred and forty-nine rupees".
> - Spell out **delivery times** naturally - "35-40 MINS" → "about 40 minutes".
> - **Confirm before acting**: always say back the cart total and delivery time before calling `place_food_order`. Wait for "yes".
> - **Never read tool IDs aloud** - `addressId`, `restaurantId`, `spinId` are never voice-appropriate.
> - Default to the user's **saved Home address** without asking, unless they said otherwise.

## Chat response contract

```
You are on a chat surface (Claude, ChatGPT, or similar). Your responses will
be rendered with markdown and may include widgets.

- Present up to 8 restaurants in a search result as a concise list with
  name, cuisine, rating, distance, delivery time.
- Use the widget returned alongside search_restaurants (restaurant-card) when
  your client supports rendering it.
- Show cart items as a markdown table with item, quantity, price, total.
- Still confirm before place_food_order, but in text ("Confirm order? Reply
  yes to place.").
```

## Sample voice exchange

```
User:   Order biryani
Agent:  I found two options near your home address. The closest is Biryani
        House, about 30 minutes, forty-nine rupees off with a welcome
        coupon. Want that one?
User:   Yes
Agent:  One chicken biryani from Biryani House. Total four hundred and sixty
        nine rupees, cash on delivery. Confirm to place?
User:   Confirm
Agent:  Placed. You'll see delivery updates in the Swiggy app.
```

## Sample chat exchange

```markdown
**User**: Order biryani

**Agent**:

I found these near your home:

| Restaurant       | Rating | Distance | Delivery |
|------------------|--------|----------|----------|
| Biryani House    | 4.5 ★  | 2.1 km   | 30 min   |
| Paradise Biryani | 4.3 ★  | 3.8 km   | 40 min   |
| Kebab Factory    | 4.4 ★  | 5.2 km   | 45 min   |

[Restaurant card widget for Biryani House]

Which one?
```

## Tool-selection differences

Some tools are more useful on voice than chat:

| Tool | Voice | Chat |
| --- | --- | --- |
| `your_go_to_items` (Instamart reorder) | **Perfect** - "reorder your usual?" one-shot | Also good, but search is fine on screen |
| `search_menu` with many results | Compress to top 3 | Show up to 10 |
| `fetch_food_coupons` | Read top 1 | Show whole list |
| `track_food_order` | Say ETA only | Show full timeline |

## What Swiggy does for you

Tool responses include fields optimized for both surfaces:

- `shortDescription` (voice-friendly, 1 sentence)
- `longDescription` (chat-friendly, includes structured data)
- `deliveryTimeSpoken` (e.g. "about 30 minutes") vs `deliveryTimeRange` (e.g. "25-35 MIN")

Use the right field for your surface.

## Guardrails common to both

- **Never autonomously place an order** without user confirmation. Surfaces differ in the *shape* of the confirmation, not its necessity.
- **Always surface distance** for far restaurants (>5 km on Food, >10 km on Dineout).
- **Respect the ₹1000 cart cap** on Food; tell the user before they pick an 8th item they can't afford.
- **Never read raw IDs, tokens, or internal codes** aloud or in screen UI.

### Framework integration (LangGraph / others)

> Working code to wire Swiggy MCP into the framework you already use.

Swiggy MCP speaks standard streamable HTTP. Every major agent framework in 2026 has first-class MCP support. Pick your framework, paste the connector, give your agent access to 35 Swiggy tools.

Swiggy MCP is OAuth 2.1 + PKCE - there is no static API key. SDK support for the flow splits into two camps:

- **Native `authProvider` support** (raw MCP TS / Python SDKs, OpenAI Agents JS, Vercel AI SDK 6, Mastra) - pass an OAuth client provider and the SDK runs PKCE against Swiggy's `/.well-known/oauth-protected-resource` and `/.well-known/oauth-authorization-server` automatically.
- **Bearer-header only** (OpenAI Agents Python, LangChain MCP adapters, PydanticAI, CrewAI, Google ADK, Anthropic hosted MCP connector) - the SDK has no OAuth hook, so you obtain an access token via the [Authenticate](/docs/start/authenticate.md) flow and forward it as `Authorization: Bearer <token>`.

The snippets below assume:

- `swiggyOAuthProvider` / `swiggy_oauth_provider` - your implementation of the MCP SDK's `OAuthClientProvider` interface, wrapping the [Authenticate](/docs/start/authenticate.md) flow. The Mastra tab shows a ready-made one via `MCPOAuthClientProvider`.
- `getSwiggyAccessToken()` - your helper that runs the [Authenticate](/docs/start/authenticate.md) flow and returns a fresh Bearer token. Re-run on 401.

Refresh tokens are not yet wired in v1.0; treat the 5-day access token as the full session and re-run authorization on 401.

#### OpenAI Agents SDK

```ts

const agent = new Agent({
  name: "FoodOrderingAgent",
  instructions: "Help users order food on Swiggy. Always call get_addresses first.",
  mcpServers: [swiggyFood],
});

await swiggyFood.connect();
const result = await Runner.run(agent, "Order biryani to my home address.");
console.log(result.finalOutput);
```

Python (the `agents` SDK doesn't expose an OAuth hook today - pass a Bearer token in headers):

```python

const swiggyToken = await getSwiggyAccessToken(); // your OAuth helper

const response = await anthropic.beta.messages.create({
  model: "claude-opus-4-7",
  max_tokens: 1024,
  betas: ["mcp-client-2025-11-20"],
  mcp_servers: [
    {
      type: "url",
      url: "https://mcp.swiggy.com/food",
      name: "swiggy-food",
      authorization_token: swiggyToken,
    },
    {
      type: "url",
      url: "https://mcp.swiggy.com/im",
      name: "swiggy-instamart",
      authorization_token: swiggyToken,
    },
  ],
  tools: [
    { type: "mcp_toolset", mcp_server_name: "swiggy-food" },
    { type: "mcp_toolset", mcp_server_name: "swiggy-instamart" },
  ],
  messages: [
    { role: "user", content: "Order biryani and 2L milk to my home address." },
  ],
});
```

Claude reads the tool catalogues from each server and picks the right tools automatically.

#### LangGraph

Use the official `langchain-mcp-adapters` to load Swiggy tools into any LangGraph agent.

`langchain-mcp-adapters` only supports header-based auth in its per-server config - fetch a token via [Authenticate](/docs/start/authenticate.md) first.

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

token = await get_swiggy_access_token()  # your OAuth helper

client = MultiServerMCPClient({
    "swiggy-food": {
        "url": "https://mcp.swiggy.com/food",
        "transport": "streamable_http",
        "headers": {"Authorization": f"Bearer {token}"},
    },
})

tools = await client.get_tools()

agent = create_react_agent(ChatOpenAI(model="gpt-4o"), tools)

result = await agent.ainvoke({
    "messages": [{"role": "user", "content": "Order biryani to my home address."}],
})
```

#### Vercel AI SDK

Vercel AI SDK 6 ships `createMCPClient` with first-class streamable-HTTP support.

```ts

const tools = await mcp.tools();

const { text } = await generateText({
  model: anthropic("claude-opus-4-7"),
  tools,
  prompt: "Order biryani to my home address.",
});

await mcp.close();
```

#### Mastra

Mastra supports MCP both as client (consuming) and server (exposing agents). Here's client usage:

```ts

const swiggyOAuth = new MCPOAuthClientProvider({
  serverUrl: "https://mcp.swiggy.com/food",
  redirectUrl: "http://localhost:3000/oauth/callback",
  clientMetadata: {
    client_name: "my-mastra-agent",
    redirect_uris: ["http://localhost:3000/oauth/callback"],
    grant_types: ["authorization_code", "refresh_token"],
    response_types: ["code"],
  },
});

const mcp = new MCPClient({
  servers: {
    "swiggy-food": {
      url: new URL("https://mcp.swiggy.com/food"),
      authProvider: swiggyOAuth,
    },
  },
});

const agent = new Agent({
  name: "FoodAgent",
  model: anthropic("claude-opus-4-7"),
  tools: await mcp.getTools(),
});

const result = await agent.generate("Order biryani to my home address.");
```

#### PydanticAI

PydanticAI doesn't run the OAuth flow for you - fetch a token via [Authenticate](/docs/start/authenticate.md) and pass it as a header.

```python

const client = new Client({ name: "my-agent", version: "1.0.0" });
await client.connect(transport);

const { tools } = await client.listTools();
const result = await client.callTool({
  name: "search_restaurants",
  arguments: { addressId: "addr_01HXYZ", query: "biryani" },
});
```

Python:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(
    "https://mcp.swiggy.com/food",
    auth=my_swiggy_oauth_provider,  # implements OAuthClientProvider
) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            "search_restaurants",
            arguments={"addressId": "addr_01HXYZ", "query": "biryani"},
        )
```

## Handling expired tokens

Access tokens live 5 days. When a call returns 401 (or JSON-RPC `-32001`), re-run the OAuth flow and retry. Most frameworks expose a hook for this; for raw clients:

```ts
async function callWithReauth<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (e: any) {
    if (e?.status === 401) {
      await reAuthenticate();
      return fn();
    }
    throw e;
  }
}
```

See [Authenticate](/docs/start/authenticate.md) for the full OAuth walkthrough.

## Wire more than one Swiggy server

Each server is independent - connect multiple if your agent needs to span domains:

```ts
mcpServers: [
  { url: "https://mcp.swiggy.com/food" },
  { url: "https://mcp.swiggy.com/im" },
  { url: "https://mcp.swiggy.com/dineout" },
]
```

Tool names are unique across servers, so your agent can dispatch across all 35 tools without conflict.

## Where to go next

- [Recipes](/docs/build.md) - end-to-end journeys for food, grocery, dineout, and combined flows.
- [Agent patterns](/docs/build/agent-patterns/voice-vs-chat.md) - voice vs chat response shaping, multi-turn state.
- [Reference](/docs/reference.md) - every tool, every parameter.
- [Ship to production](/docs/build/ship-to-production.md) - retries, observability, go-live checklist.

---

## 5. End-to-End Recipes

### Order food

> The canonical 7-tool Food journey - from address to placed order to delivery tracking.

The full food-ordering journey across Swiggy's Food MCP server. COD payment, ₹1000 cart cap. Pseudo-code in TypeScript; the same sequence works in any framework.

## The flow

```
get_addresses
     │
     ▼
search_restaurants ──► get_restaurant_menu
                            │
                            ▼
                       update_food_cart ◄── fetch_food_coupons
                            │                       │
                            ▼                       │
                       get_food_cart ◄── apply_food_coupon
                            │
                            ▼
                       place_food_order
                            │
                            ▼
                       track_food_order
```

## Step 1 - Resolve the delivery address

```ts
const addresses = await client.callTool({ name: "get_addresses" });
const home = addresses.data.find((a) => a.label === "Home") ?? addresses.data[0];
if (!home) throw new Error("User has no saved addresses; prompt them to add one.");
```

[`get_addresses`](/docs/reference/food/get_addresses.md) returns label, addressId, and display text - never raw coordinates.

## Step 2 - Find restaurants

```ts
const restaurants = await client.callTool({
  name: "search_restaurants",
  arguments: { addressId: home.id, query: "biryani" },
});
```

Check `availabilityStatus` for each result - only recommend those marked `"OPEN"`. Sort by a mix of distance and rating; always surface distance when picking far restaurants so the user isn't surprised.

## Step 3 - Browse the menu

```ts
const menu = await client.callTool({
  name: "get_restaurant_menu",
  arguments: { restaurantId: restaurants.data.restaurants[0].id },
});
```

Menus have categories, items, variants, and add-ons. Use [`search_menu`](/docs/reference/food/search_menu.md) for keyword search within (or across) restaurants.

## Step 4 - Build the cart

```ts
await client.callTool({
  name: "update_food_cart",
  arguments: {
    restaurantId: menu.data.restaurantId,
    items: [
      { itemId: menu.data.items[0].id, quantity: 1 },
    ],
  },
});
```

Cart is tied to a single restaurant. Changing restaurant flushes the cart. Use [`flush_food_cart`](/docs/reference/food/flush_food_cart.md) explicitly when the user starts over.

## Step 5 - Apply a coupon (optional)

```ts
const coupons = await client.callTool({ name: "fetch_food_coupons" });

// v1 supports COD only - filter coupons that don't require online payment
const codCoupon = coupons.data.find((c) => !c.requiresOnlinePayment);

if (codCoupon) {
  await client.callTool({
    name: "apply_food_coupon",
    arguments: { code: codCoupon.code },
  });
}
```

## Step 6 - Confirm and place the order

```ts
const cart = await client.callTool({ name: "get_food_cart" });

// Swiggy v1: hard ₹1000 cap on Builders Club orders
if (cart.data.total > 1000) {
  throw new Error("Cart exceeds ₹1000 cap - ask user to reduce items.");
}

// Surface to the user before placing
// "Your order is: <items>. Total ₹<total>. Place now? (yes / no)"

const order = await client.callTool({
  name: "place_food_order",
  arguments: { paymentMethod: "COD" },
});
```

**Critical**: `place_food_order` is **not idempotent**. If it fails with 5xx, call [`get_food_orders`](/docs/reference/food/get_food_orders.md) to check if the order actually placed before retrying. See [ship to production](/docs/build/ship-to-production.md).

## Step 7 - Track the order

```ts
const status = await client.callTool({
  name: "track_food_order",
  arguments: { orderId: order.data.orderId },
});

// Poll no faster than every 10 seconds; delivery-partner ETA updates arrive at that cadence
```

## Full agent prompt

Good system prompt for the agent driving this flow:

> **Note**
>
> You help users order food on Swiggy. Always resolve the user's saved address via `get_addresses` before searching. Only recommend restaurants with `availabilityStatus: "OPEN"`. Confirm the cart and total with the user before calling `place_food_order` - that call places a real order. Only COD is supported in v1; filter coupons to those not requiring online payment. Never exceed ₹1000 cart total.

## What can go wrong

Until the symbolic error-code registry ships (see [errors](/docs/reference/errors.md)), classify by `error.message` text and HTTP status. Expect:

- **Restaurant closed** between search and order → re-run `search_restaurants`.
- **Coupon requires online payment** → filter upstream; only COD is supported in v1.
- **Minimum order not met** → prompt user to add items.
- **Upstream shedding / timeout** → exponential backoff; capacity questions go to [rate-limits](/docs/operate/rate-limits.md).

### Order groceries (Instamart)

> Full Instamart journey - find products, build a cart, checkout, track delivery.

Instamart is Swiggy's quick-commerce grocery service across 1000+ Indian cities. Same shape as Food (discover → cart → order → track), different catalogue.

## The flow

```
get_addresses
     │
     ▼
search_products ──► update_cart ──► get_cart ──► checkout ──► track_order
     ▲                  │
     └──────────────────┘
     your_go_to_items (bypass search)
```

## Step 1 - Resolve the delivery address

```ts
const addresses = await client.callTool({ name: "get_addresses" });
const home = addresses.data.find((a) => a.label === "Home") ?? addresses.data[0];
```

If the user has no addresses, walk them through [`create_address`](/docs/reference/instamart/create_address.md).

## Step 2 - Find products (or reorder)

Two paths. For quick reorders:

```ts
const goTo = await client.callTool({
  name: "your_go_to_items",
  arguments: { addressId: home.id },
});
// goTo.data has frequently-ordered SKUs - present as one-tap add
```

For search:

```ts
const results = await client.callTool({
  name: "search_products",
  arguments: { addressId: home.id, query: "bananas" },
});
```

Each product returns one or more `variants` with their own `spinId` (the SKU-level identifier). You add variants to the cart, not the parent product.

## Step 3 - Build the cart

```ts
await client.callTool({
  name: "update_cart",
  arguments: {
    items: [
      { spinId: results.data.products[0].variants[0].spinId, quantity: 2 },
    ],
  },
});
```

Swapping address mid-cart? Don't. Run [`clear_cart`](/docs/reference/instamart/clear_cart.md) first to avoid cross-address SKU mismatches.

## Step 4 - Review the cart

```ts
const cart = await client.callTool({ name: "get_cart" });
// cart.data has items[], bill breakdown, payment methods available
```

Check `ADDRESS_NOT_SERVICEABLE` or `MIN_ORDER_NOT_MET` errors; Instamart has a ₹99 minimum and service-area restrictions.

## Step 5 - Checkout

```ts
const order = await client.callTool({
  name: "checkout",
  arguments: { paymentMethod: "COD" },
});
```

Same non-idempotency rule as Food: if `checkout` 5xxs, check [`get_orders`](/docs/reference/instamart/get_orders.md) before retrying.

## Step 6 - Track

```ts
const status = await client.callTool({
  name: "track_order",
  arguments: { orderId: order.data.orderId },
});
// ETA typically 10-20 min post-checkout
```

Poll no faster than every 10s.

## Agent prompt

> **Note**
>
> You help users shop on Swiggy Instamart. Start by resolving the user's saved address. Offer `your_go_to_items` for quick reorders; use `search_products` for new queries. Always confirm the cart and total before `checkout`. COD-only in v1.

## Common errors

Until the symbolic `error.code` registry ships (see [errors](/docs/reference/errors.md)), classify by `error.message` text. Expect:

- **Item out of stock** at this address → suggest alternatives from `search_products`.
- **Address not serviceable** → Instamart doesn't deliver here; ask for another address or offer Food.
- **Minimum order not met** (cart under ₹99) → prompt user to add items.
- **Cart expired / abandoned** → rebuild the cart.

### Book a table (Dineout)

> Dineout journey - find a restaurant, check availability, reserve.

Dineout is Swiggy's table-reservation surface across 50+ Indian cities. The flow is compact: find → check slots → book → confirm.

## The flow

```
get_saved_locations
     │
     ▼
search_restaurants_dineout ──► get_restaurant_details
                                        │
                                        ▼
                               get_available_slots ──► book_table ──► get_booking_status
```

## Step 1 - Start with a location

```ts
const locations = await client.callTool({ name: "get_saved_locations" });
// Unlike Food/Instamart, Dineout returns lat/lng explicitly for "near me" queries
```

If the user asks "restaurants near me for Friday dinner", use the first saved location's coordinates.

## Step 2 - Search

```ts
const restaurants = await client.callTool({
  name: "search_restaurants_dineout",
  arguments: {
    lat: locations.data[0].lat,
    lng: locations.data[0].lng,
    query: "italian",
  },
});
```

Results include availability status, offers, cuisines, and price range. Filter to restaurants where availability is `"AVAILABLE"` before presenting.

## Step 3 - Dig into details

```ts
const details = await client.callTool({
  name: "get_restaurant_details",
  arguments: { restaurantId: restaurants.data.restaurants[0].id },
});
// details.data: ratings, amenities, menu images, exclusive Dineout deals
```

## Step 4 - Check available slots

```ts
const slots = await client.callTool({
  name: "get_available_slots",
  arguments: {
    restaurantId: details.data.id,
    date: "2026-05-01",
    guestCount: 4,
  },
});
// slots.data has 7-day forward availability, broken into breakfast/lunch/dinner bands
```

Surface slot times in the user's timezone (all restaurants are in India; IST applies).

## Step 5 - Book

```ts
const booking = await client.callTool({
  name: "book_table",
  arguments: {
    restaurantId: details.data.id,
    slotId: slots.data.slots[0].slotId,
    guestCount: 4,
  },
});
```

**Important**: `book_table` is **not idempotent**. On 5xx, call [`get_booking_status`](/docs/reference/dineout/get_booking_status.md) with the restaurant and slot before retrying.

## Step 6 - Confirm

```ts
const status = await client.callTool({
  name: "get_booking_status",
  arguments: { bookingId: booking.data.bookingId },
});
```

Send the user the confirmation number and the restaurant's address.

## Agent prompt

> **Note**
>
> You help users book restaurant tables on Swiggy Dineout. Resolve the user's location first (via `get_saved_locations` or lat/lng), then search. Always confirm slot date, time, and party size with the user before `book_table`. Show restaurant details (amenities, deals) before asking for slot confirmation.

## Common errors

- `SLOT_UNAVAILABLE` → slot filled; refetch availability and offer alternatives.
- `RESTAURANT_NOT_BOOKABLE` → restaurant isn't Dineout-enabled; offer dine-in walk-in guidance or a Food order instead.
- `BOOKING_WINDOW_CLOSED` → outside booking hours; present next available day.

Full catalogue: [errors](/docs/reference/errors.md).

### Combined evening planner

> One user ask, two MCP servers - Food delivery and Dineout reservations composed in a single agent turn.

A fun showcase of MCP's tool-composition strength: the user says "plan my evening for 4 - dinner out, dessert delivered later", and your agent fans out across two Swiggy servers.

## The ask

> **Note**
>
> "Plan my evening for Friday. I want dinner out with 3 friends around 8pm, something Italian in Indiranagar. Then order dessert to my place for 10pm."

This requires both [Dineout](/docs/reference/dineout.md) (for the reservation) and [Food](/docs/reference/food.md) (for the delivery). Both servers share the underlying Swiggy session - one OAuth, two MCP URLs.

## Connect both servers

Most frameworks allow multiple MCP servers side-by-side. Example with OpenAI Agents SDK:

```ts
const dineout = new MCPServerStreamableHttp({
  url: "https://mcp.swiggy.com/dineout",
  requestInit: { headers: { Authorization: `Bearer ${token}` } },
});
const food = new MCPServerStreamableHttp({
  url: "https://mcp.swiggy.com/food",
  requestInit: { headers: { Authorization: `Bearer ${token}` } },
});

const agent = new Agent({
  name: "EveningPlanner",
  instructions: "Plan the user's evening using both servers.",
  mcpServers: [dineout, food],
});
```

Tool names don't collide - `search_restaurants` (Food) and `search_restaurants_dineout` are distinct.

## What the agent does

Internally, the model orchestrates the two flows in parallel:

```
                  ┌──────────────────────────┐
                  │  User: Plan my evening    │
                  └─────────────┬─────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
   get_saved_locations                  get_addresses (Food)
              │                                   │
              ▼                                   │
   search_restaurants_dineout                     │
      (query="italian",                           │
       lat/lng of saved home)                     │
              │                                   │
              ▼                                   │
   get_restaurant_details                         │
              │                                   │
              ▼                                   │
   get_available_slots                            │
      (date=Friday, guestCount=4)                 │
              │                                   │
              ▼                                   │
   book_table                          (later, after dinner recommendation)
                                                  │
                                                  ▼
                                        search_restaurants
                                           (query="gelato",
                                            addressId=home)
                                                  │
                                                  ▼
                                        get_restaurant_menu
                                                  │
                                                  ▼
                                        update_food_cart
                                                  │
                                                  ▼
                                        place_food_order (scheduled 10pm)
```

## Agent prompt for this pattern

> **Note**
>
> You compose Swiggy Dineout and Swiggy Food tools to plan user evenings. When the user asks for a restaurant reservation AND food delivery in one request, handle them sequentially: reservation first (so they see slot options early), then dessert/delivery second. Always confirm reservation details and food cart separately before calling `book_table` and `place_food_order`.

## Handle auth expiry across both servers

If one server returns 401, your session is gone for both. Re-run the OAuth flow once, update the bearer for both clients, retry.

## Gotchas

- **Scheduling**: `place_food_order` places orders for immediate delivery. Swiggy Food doesn't support future-scheduled delivery in v1 - if the user wants dessert at 10pm exactly, your agent needs to remind them / place the order at the right time.
- **Address vs location**: Dineout uses lat/lng for "near me"; Food uses `addressId`. They're different scopes. Don't try to pass an addressId to Dineout search.
- **Cart conflicts**: Food cart is per-restaurant. If your agent adds to cart, then searches a different restaurant, the cart will be flushed. Surface that explicitly.

---

## 6. Complete Tool Reference (35 tools)

### 6.1 Food (14 tools)

#### `search_restaurants`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Discover | **Behaviour:** read-only

Search and order food from restaurants for delivery. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to order food, get food delivered, or search restaurants for delivery. Swiggy Food delive...

**Input (TypeScript):**
```typescript
export interface SearchRestaurantsInput {
  addressId: string;  // Address ID from get_addresses tool
  query: string;  // Search query (restaurant name or cuisine)
  offset?: number;  // Pagination offset. Use nextOffset from previous response to load more results. Default: 0.
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Address ID from get_addresses tool |
| `query` | `string` | yes | Search query (restaurant name or cuisine) |
| `offset` | `number` | no | Pagination offset. Use nextOffset from previous response to load more results. Default: 0. |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_restaurants",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

IMPORTANT: Each restaurant in the response includes an "availabilityStatus" field with values "OPEN", "CLOSED", or "UNAVAILABLE". Always check this status before proceeding: only recommend or add items from restaurants with availabilityStatus "OPEN". If a restaurant is "CLOSED" or "UNAVAILABLE", inform the user and suggest open alternatives from the results.

After showing results, let the user pick a restaurant before searching the menu. Do NOT automatically call search_menu - wait for the user to choose.

IMPORTANT: When user asks for more options or different dishes after seeing search_menu results, first call get_restaurant_menu to discover available menu categories at the restaurant. Then call search_menu with a different category/dish name to show fresh results. Do NOT re-run search_menu with the exact same query - it will return identical results.

DISTANCE & RELEVANCE: Results are sorted by a mix of distance, rating, and relevance. Each restaurant has a "distanceKm" field. When presenting results in text: (1) Prioritize nearby restaurants with good ratings first, (2) Always mention distance for far restaurants so the user can decide - e.g. "Biryani House (8.2 km away, ~40 min delivery)", (3) Never silently recommend a far restaurant without mentioning distance and expected delivery time.

GENERIC QUERIES: When user asks generic things like "popular restaurants", "best food", "what should I eat", "suggest something" - the search API handles natural language queries with query understanding. Search with broad cuisine terms like "biryani", "pizza", "chinese", "thali" based on meal time (lunch → thali/biryani/rice, dinner → similar, snack → rolls/momos/sandwich, late night → pizza/burger). Present a curated mix of top-rated nearby options across cuisines rather than dumping raw results.

**Next in journey:** `get_restaurant_menu`

#### `get_restaurant_menu`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Discover | **Behaviour:** read-only

Get the complete menu of a restaurant, paginated by category. Use this to BROWSE a restaurant menu and see what is available. This is the PRIMARY tool for showing MORE options - use page/pageSize to ...

**Input (TypeScript):**
```typescript
export interface GetRestaurantMenuInput {
  addressId: string;  // Address ID from get_addresses tool
  restaurantId: string;  // Restaurant ID to fetch menu for (from search_restaurants)
  page?: number;  // Page number for pagination (default: 1)
  pageSize?: number;  // Number of categories per page (default: 5, max: 8)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Address ID from get_addresses tool |
| `restaurantId` | `string` | yes | Restaurant ID to fetch menu for (from search_restaurants) |
| `page` | `number` | no | Page number for pagination (default: 1) |
| `pageSize` | `number` | no | Number of categories per page (default: 5, max: 8) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_restaurant_menu",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `update_food_cart`

#### `search_menu`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Discover | **Behaviour:** read-only

Search for dishes and menu items to order for food delivery. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to find specific dishes, browse menu items, see what a restaurant offers, or orde...

**Input (TypeScript):**
```typescript
export interface SearchMenuInput {
  addressId: string;  // Address ID from get_addresses tool
  query: string;  // Search query (dish name)
  restaurantIdOfAddedItem?: string;  // Optional restaurant ID to scope search
  vegFilter?: number;  // Veg filter flag (0 or 1). Pass 1 for veg-only items. 0 or omitted returns mixed veg + non-veg. There is NO non-veg-only filter - if user asks for "non-veg only", pass 0 (mixed) and mention in text that you are showing all items including non-veg, since a non-veg-only filter is not available yet.
  offset?: number;  // Pagination offset. Use nextOffset from previous response to load more results. Default: 0.
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Address ID from get_addresses tool |
| `query` | `string` | yes | Search query (dish name) |
| `restaurantIdOfAddedItem` | `string` | no | Optional restaurant ID to scope search |
| `vegFilter` | `number` | no | Veg filter flag (0 or 1). Pass 1 for veg-only items. 0 or omitted returns mixed veg + non-veg. There is NO non-veg-only filter - if user asks for "non-veg only", pass 0 (mixed) and mention in text that you are showing all items including non-veg, since a non-veg-only filter is not available yet. |
| `offset` | `number` | no | Pagination offset. Use nextOffset from previous response to load more results. Default: 0. |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_menu",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

CROSS-RESTAURANT SEARCH: When user asks for a dish, first search within the current restaurant (using restaurantIdOfAddedItem if items are in cart). If no results or poor matches, search again WITHOUT restaurantIdOfAddedItem to find the dish at other restaurants. Inform the user: "I couldn't find that at [restaurant]. Here are options from other restaurants."

ADDONS & CUSTOMIZATIONS: When user asks about addons or customizations for an item, use the addons data already returned in this search_menu response - do NOT call search_menu again. Present the available addon choices (name + price) in text. If the item has hasAddons=true, the addons array contains all options.

MORE OPTIONS: search_menu returns paginated results. Use nextOffset from the response to load more items for the same query. For different dishes, call search_menu with a DIFFERENT query or use get_restaurant_menu to browse categories.

After showing results, let the user review the items and confirm what to add. Do NOT automatically call update_food_cart - wait for the user to decide.

**Next in journey:** `get_restaurant_menu`

#### `update_food_cart`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Cart | **Behaviour:** mutating

Add items to food delivery cart or update cart contents. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to add food items, dishes, or meals to their delivery cart. Swiggy Food delivery. Sup...

**Input (TypeScript):**
```typescript
export interface UpdateFoodCartInput {
  restaurantId: string;  // Restaurant ID for the cart
  cartItems: Record<string, unknown>[];  // Array of items to add to cart with their customizations
  addressId: string;  // Address ID to get accurate delivery charges based on location.
  restaurantName?: string;  // Restaurant name from search_restaurants or search_menu results. Pass this so the cart widget can display the restaurant name (the cart API does not always return it).
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `restaurantId` | `string` | yes | Restaurant ID for the cart |
| `cartItems` | `object[]` | yes | Array of items to add to cart with their customizations |
| `addressId` | `string` | yes | Address ID to get accurate delivery charges based on location. |
| `restaurantName` | `string` | no | Restaurant name from search_restaurants or search_menu results. Pass this so the cart widget can display the restaurant name (the cart API does not always return it). |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "update_food_cart",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

> **Warning**
>
> NO WIDGET: This tool does NOT render any widget or cart UI. The user CANNOT see the cart after this call. You MUST follow up by calling get_food_cart immediately to show the updated cart to the user. Do NOT say "your cart is shown above" or "cart reflected above" - there is nothing to see until you call get_food_cart.

**RESPONSE FORMAT**: Keep your text response brief - just confirm what was updated, e.g. "Added 2x Chicken Biryani to your cart." Then immediately call get_food_cart.

**COUPON NOTE**: The response may include offers.coupon_applied with coupon_discount=0 - this means the coupon is auto-suggested (best available) but NOT actually applied. Do NOT tell the user a coupon is "applied" unless coupon_discount > 0. Only mention savings if there is an actual discount amount.

**IMPORTANT **- QUANTITY CHANGES FOR CUSTOMIZED ITEMS: When user taps +/- or asks to change quantity of an item that has addons or variants:
(1) Do NOT silently replicate the same addons for the new quantity.
(2) ASK the user: "Would you like the same add-ons (e.g. Extra Raita, Salan) for the additional item, or different ones?"
(3) Also briefly mention other available addons they haven't picked yet - e.g. "You can also add Gulab Jamun or Extra Gravy."
(4) Only after the user confirms, call update_food_cart with the chosen customization.
For items WITHOUT addons/variants, quantity changes can be applied directly without asking.

**Next in journey:** `get_food_cart`

#### `get_food_cart`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Cart | **Behaviour:** read-only

Get current food delivery cart with all items. PRIMARY FOOD DELIVERY SERVICE - Use this to view cart contents when ordering food for delivery. Swiggy Food delivery. Response includes valid_addons fie...

**Input (TypeScript):**
```typescript
export interface GetFoodCartInput {
  addressId: string;  // Address ID to get accurate delivery charges based on location.
  restaurantName?: string;  // Restaurant name from search_restaurants or search_menu results. Pass this so the cart widget can display the restaurant name (the cart API does not always return it).
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Address ID to get accurate delivery charges based on location. |
| `restaurantName` | `string` | no | Restaurant name from search_restaurants or search_menu results. Pass this so the cart widget can display the restaurant name (the cart API does not always return it). |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_food_cart",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

PAYMENT METHODS: The response includes an "availablePaymentMethods" array in data. Display whatever payment method(s) are returned to the user before placing the order. Do not mention or assume any payment option that is not in the response.

COUPON NOTE: The response may include offers.coupon_applied with coupon_discount=0 - this means the coupon is auto-suggested (best available) but NOT actually applied. Do NOT tell the user a coupon is "applied" or show savings unless coupon_discount > 0.

**Next in journey:** `apply_food_coupon`

#### `flush_food_cart`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Cart | **Behaviour:** mutating

Clear or empty the food delivery cart. PRIMARY FOOD DELIVERY SERVICE - Use this to remove all items from the food delivery cart. Swiggy Food delivery. NOT for groceries.

**Input (TypeScript):**
```typescript
// flush_food_cart: no arguments
export type FlushFoodCartInput = Record<string, never>;
```

**Parameters:** none (session auth handled automatically)

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "flush_food_cart",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `update_food_cart`

#### `fetch_food_coupons`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Cart | **Behaviour:** read-only

Get available coupons and offers for food delivery order. PRIMARY FOOD DELIVERY SERVICE - Use this to find discounts, coupons, or offers when ordering food for delivery. Swiggy Food delivery. IMPORTA...

**Input (TypeScript):**
```typescript
export interface FetchFoodCouponsInput {
  restaurantId: string;  // Restaurant ID for the cart
  addressId: string;  // Address ID where the order will be delivered (coordinates will be fetched automatically)
  couponCode?: string;  // Optional coupon code to check applicability of a specific coupon
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `restaurantId` | `string` | yes | Restaurant ID for the cart |
| `addressId` | `string` | yes | Address ID where the order will be delivered (coordinates will be fetched automatically) |
| `couponCode` | `string` | no | Optional coupon code to check applicability of a specific coupon |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "fetch_food_coupons",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `apply_food_coupon`

#### `apply_food_coupon`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Cart | **Behaviour:** mutating

Apply coupon code or discount to food delivery order. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to apply a coupon, discount code, or offer to their food delivery order. Swiggy Food del...

**Input (TypeScript):**
```typescript
export interface ApplyFoodCouponInput {
  couponCode: string;  // Coupon code to apply
  addressId: string;  // Address ID where the order will be delivered (coordinates will be fetched automatically)
  cartId?: string;  // Optional cart ID
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `couponCode` | `string` | yes | Coupon code to apply |
| `addressId` | `string` | yes | Address ID where the order will be delivered (coordinates will be fetched automatically) |
| `cartId` | `string` | no | Optional cart ID |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "apply_food_coupon",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `place_food_order`

#### `place_food_order`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Order | **Behaviour:** mutating

Place food delivery order and confirm order placement. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to place order, confirm order, or complete food delivery order. Swiggy Food delivery. R...

**Input (TypeScript):**
```typescript
export interface PlaceFoodOrderInput {
  addressId: string;  // Address ID from the user's saved addresses (coordinates will be fetched automatically)
  paymentMethod?: string;  // Payment method to use. Check availablePaymentMethods from get_food_cart response. Auto-defaults to the user's available payment method if not specified.
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Address ID from the user's saved addresses (coordinates will be fetched automatically) |
| `paymentMethod` | `string` | no | Payment method to use. Check availablePaymentMethods from get_food_cart response. Auto-defaults to the user's available payment method if not specified. |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "place_food_order",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

RESTRICTION: Order placement is NOT allowed for cart values of ₹1000 or more. This is because MCP is currently in beta and is being used strictly for testing purposes. For larger orders, inform the user to use the Swiggy Food app instead to place the order directly.

PAYMENT: Use the availablePaymentMethods from get_food_cart response. Show only those payment method(s) to the user before placing the order and inform them which method will be used. The system will auto-select the correct payment method. Do not mention any payment option not present in that response.

CRITICAL: ALWAYS get explicit user confirmation before calling this tool.
1. Call get_food_cart first to display complete order summary (items, costs, available payment methods)
2. Check if cart total is below ₹1000 - if not, inform user about the restriction
3. Show the available payment method(s) from get_food_cart (availablePaymentMethods) and inform the user which will be used
4. Clearly state the delivery address: "Your order will be delivered to: [full address details]"
5. Ask: "Do you want to proceed with placing this order to this address?"
6. Wait for clear confirmation (yes/confirm/proceed)
7. NEVER proceed without explicit user permission

BRANDING: When the order is placed successfully, always use the message from the tool response as-is. It includes Swiggy branding. Do NOT rephrase it to a plain "Order placed" - always show "Swiggy order placed successfully". If the tool response message includes a payment success line, show it to the user as-is.

CANCELLATION: If the user asks to cancel their food order, do NOT call any tool. Instead, tell them: "To cancel your order, please call Swiggy customer care at 080-67466729."

**Next in journey:** `track_food_order`

#### `get_food_orders`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Track | **Behaviour:** read-only

Get active food delivery orders and order status. PRIMARY FOOD DELIVERY SERVICE - Use this when user asks about their orders, order status, or current food delivery orders. Swiggy Food delivery. Retu...

**Input (TypeScript):**
```typescript
export interface GetFoodOrdersInput {
  orderCount?: number;  // Number of orders to fetch (default: 5, max: 20)
  addressId: string;  // Address ID to use for fetching orders (can be obtained from get_addresses)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `orderCount` | `number` | no | Number of orders to fetch (default: 5, max: 20) |
| `addressId` | `string` | yes | Address ID to use for fetching orders (can be obtained from get_addresses) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_food_orders",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `get_food_order_details`

#### `get_food_order_details`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Track | **Behaviour:** read-only

Get detailed information about a specific food delivery order. PRIMARY FOOD DELIVERY SERVICE - Use this when user asks about order details, order information, or wants to see what they ordered. Swigg...

**Input (TypeScript):**
```typescript
export interface GetFoodOrderDetailsInput {
  orderId: string;  // Order ID to fetch details for (can be obtained from get_food_orders)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `orderId` | `string` | yes | Order ID to fetch details for (can be obtained from get_food_orders) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_food_order_details",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

#### `track_food_order`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Track | **Behaviour:** read-only

Track food delivery order status and delivery progress. PRIMARY FOOD DELIVERY SERVICE - Use this when user asks to track order, check delivery status, or see where their food order is. Swiggy Food de...

**Input (TypeScript):**
```typescript
export interface TrackFoodOrderInput {
  orderId?: string;  // Optional: Specific order ID to track. If not provided, returns all active orders.
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `orderId` | `string` | no | Optional: Specific order ID to track. If not provided, returns all active orders. |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "track_food_order",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `get_food_order_details`

#### `get_addresses`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Discover | **Behaviour:** read-only

Swiggy (Instamart/Food): Get all saved delivery addresses for the authenticated Swiggy user, sorted by last order date. This tool works for Swiggy Instamart and Food services. Addresses are returned ...

**Input (TypeScript):**
```typescript
// get_addresses: no arguments
export type GetAddressesInput = Record<string, never>;
```

**Parameters:** none (session auth handled automatically)

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_addresses",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

**IMPORTANT **- STOP here and let the user choose:
1. Show the address list to the user
2. Ask: "Which address would you like to use for delivery?"
3. Do NOT call any other tool until the user has selected an address
4. Remember the selected addressId for all subsequent operations
5. If no addresses are returned, inform the user that they need to add an address first

**Next in journey:** `search_restaurants`

#### `report_error`

**Server:** Food | **Endpoint:** `POST https://mcp.swiggy.com/food` | **Stage:** Support | **Behaviour:** mutating

Generate an error report to share with the Swiggy MCP team. Use this when the user encounters an error and wants to report it. Returns a pre-filled mailto: link and a human-readable summary. The user...

**Input (TypeScript):**
```typescript
export interface ReportErrorInput {
  tool: string;  // Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order")
  domain?: string;  // MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided.
  errorMessage: string;  // The error message the user saw
  flowDescription?: string;  // Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed")
  toolContext?: Record<string, unknown>;  // Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed.
  userNotes?: string;  // Any additional notes or context the user wants to share
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tool` | `string` | yes | Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order") |
| `domain` | `string` | no | MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided. |
| `errorMessage` | `string` | yes | The error message the user saw |
| `flowDescription` | `string` | no | Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed") |
| `toolContext` | `object` | no | Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed. |
| `userNotes` | `string` | no | Any additional notes or context the user wants to share |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "report_error",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

### 6.2 Instamart (13 tools)

#### `search_products`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Discover | **Behaviour:** read-only

Search for products available at the selected address. Returns products with their variants (e.g., different pack sizes, quantities). When a user asks to add a product, ALWAYS search first to see ava...

**Input (TypeScript):**
```typescript
export interface SearchProductsInput {
  addressId: string;  // Address ID from get_addresses tool
  query: string;  // Search query (product name, category, or brand)
  offset?: number;  // Pagination offset (default: 0)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Address ID from get_addresses tool |
| `query` | `string` | yes | Search query (product name, category, or brand) |
| `offset` | `number` | no | Pagination offset (default: 0) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_products",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `update_cart`

#### `your_go_to_items`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Discover | **Behaviour:** read-only

Fetch the user's Your Go To Items (frequently or recently ordered items) for the selected delivery address. Use addressId from get_addresses. Returns products with variants; use spinId from the chose...

**Input (TypeScript):**
```typescript
export interface YourGoToItemsInput {
  addressId: string;  // Address ID from get_addresses tool
  offset?: number;  // Pagination offset (default: 0)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Address ID from get_addresses tool |
| `offset` | `number` | no | Pagination offset (default: 0) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "your_go_to_items",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `update_cart`

#### `update_cart`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Cart | **Behaviour:** mutating

Swiggy Instamart (Grocery): Update Swiggy Instamart grocery cart with items. Replaces entire cart with the provided items. Use this for Instamart grocery orders, NOT for Food delivery. Authentication...

**Input (TypeScript):**
```typescript
export interface UpdateCartInput {
  selectedAddressId: string;  // Selected delivery address ID from get_addresses tool
  items: Record<string, unknown>[];  // Array of items to add to cart
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `selectedAddressId` | `string` | yes | Selected delivery address ID from get_addresses tool |
| `items` | `object[]` | yes | Array of items to add to cart |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "update_cart",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `get_cart`

#### `get_cart`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Cart | **Behaviour:** read-only

Swiggy Instamart (Grocery): Get current Swiggy Instamart grocery cart with all items and bill breakdown. Use this for Instamart grocery orders, NOT for Food delivery. Authentication is handled automa...

**Input (TypeScript):**
```typescript
// get_cart: no arguments
export type GetCartInput = Record<string, never>;
```

**Parameters:** none (session auth handled automatically)

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_cart",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

**PAYMENT METHODS**: The response includes an "availablePaymentMethods" array in data. Display whatever payment method(s) are returned to the user before placing the order. Do not mention or assume any payment option that is not in the response.

**Next in journey:** `checkout`

#### `clear_cart`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Cart | **Behaviour:** mutating

Clear (remove all items from) the Instamart cart. Authentication is handled automatically.

**Input (TypeScript):**
```typescript
// clear_cart: no arguments
export type ClearCartInput = Record<string, never>;
```

**Parameters:** none (session auth handled automatically)

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "clear_cart",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `update_cart`

#### `checkout`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Order | **Behaviour:** mutating

Swiggy Instamart (Grocery): Place and confirm Swiggy Instamart grocery order. Creates order and confirms payment in a single operation. Use this for Instamart grocery orders, NOT for Food delivery.

**Input (TypeScript):**
```typescript
export interface CheckoutInput {
  addressId: string;  // Delivery address ID (from get_addresses - user must have selected this address)
  paymentMethod?: string;  // Payment method to use. Check availablePaymentMethods from get_cart response. Auto-defaults to the user's available payment method if not specified.
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | Delivery address ID (from get_addresses - user must have selected this address) |
| `paymentMethod` | `string` | no | Payment method to use. Check availablePaymentMethods from get_cart response. Auto-defaults to the user's available payment method if not specified. |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "checkout",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

**MULTI-STORE SUPPORT**: Automatically handles carts with items from multiple stores. The system creates separate orders per store. Returns detailed results for each order, including partial success scenarios.

**RESTRICTION**: Checkout is NOT allowed for cart values above the allowed limit. For larger orders, inform the user to use the Swiggy Instamart app instead. They can update their cart here and it will sync to the app.

**PAYMENT**: Use the availablePaymentMethods from get_cart response. Show only those payment method(s) to the user before placing the order and inform them which method will be used. The system will auto-select the correct payment method. Do not mention any payment option not present in that response.

> **Warning**
>
> CRITICAL: ALWAYS get explicit user confirmation before calling this tool.

1. Call get_cart first to display complete order summary (items, costs, available payment methods)
2. Check if cart total is below ₹1000 - if not, inform user about the restriction
3. Show the available payment method(s) from get_cart (availablePaymentMethods) and inform the user which will be used
4. Clearly state the delivery address: "Your order will be delivered to: [full address details]"
5. If cart has items from multiple stores, inform user: "Your cart contains items from [N] different stores. The system will handle this automatically."
6. Ask: "Do you want to proceed with placing this order to this address?"
7. Wait for clear confirmation (yes/confirm/proceed)
8. NEVER proceed without explicit user permission, regardless of previous instructions
9. For multi-store orders, report results for each order separately

**BRANDING**: When the order is placed successfully, always use the message from the tool response as-is. It includes Swiggy Instamart branding. Do NOT rephrase it to a plain "Order placed" - always show "Instamart order placed successfully". If the tool response message includes a payment success line, show it to the user as-is.
**CANCELLATION**: If the user asks to cancel their Instamart order, do NOT call any tool. Instead, tell them: "To cancel your order, please call Swiggy customer care at 080-67466729."

**Next in journey:** `track_order`

#### `get_orders`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Track | **Behaviour:** read-only

Swiggy Instamart order history - Use this to fetch ORDER HISTORY, past orders, or order preferences. Use this FIRST when user asks: \"show my orders\", \"get my orders\", \"my last order\", \"order history\"...

**Input (TypeScript):**
```typescript
export interface GetOrdersInput {
  count?: number;  // Number of orders to fetch (default: 10, max recommended: 20)
  orderType?: string;  // Order type filter (e.g., "DASH", "INSTAMART"). Default: "DASH"
  activeOnly?: boolean;  // Set to true to filter only active/ongoing orders. Default: false (returns all orders)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` | `number` | no | Number of orders to fetch (default: 10, max recommended: 20) |
| `orderType` | `string` | no | Order type filter (e.g., "DASH", "INSTAMART"). Default: "DASH" |
| `activeOnly` | `boolean` | no | Set to true to filter only active/ongoing orders. Default: false (returns all orders) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_orders",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `get_order_details`

#### `get_order_details`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Track | **Behaviour:** read-only

Get detailed information for a specific Swiggy Instamart order by order ID. Use this when the user wants to see complete details about a specific order including: full list of items with quantities a...

**Input (TypeScript):**
```typescript
export interface GetOrderDetailsInput {
  orderId: string;  // The order ID to fetch details for (required). Can be obtained from get_orders tool.
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `orderId` | `string` | yes | The order ID to fetch details for (required). Can be obtained from get_orders tool. |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_order_details",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

#### `track_order`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Track | **Behaviour:** read-only

Track Swiggy Instamart order status in real-time. PRIMARY TOOL for order tracking - Use this FIRST when user asks: \"where is my order\", \"track my order\", \"order status\", \"what's the status of my orde...

**Input (TypeScript):**
```typescript
export interface TrackOrderInput {
  orderId: string;  // The order ID to track (required). Can be obtained from get_orders tool.
  lat: number;  // Latitude of the delivery address (required for accurate tracking)
  lng: number;  // Longitude of the delivery address (required for accurate tracking)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `orderId` | `string` | yes | The order ID to track (required). Can be obtained from get_orders tool. |
| `lat` | `number` | yes | Latitude of the delivery address (required for accurate tracking) |
| `lng` | `number` | yes | Longitude of the delivery address (required for accurate tracking) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "track_order",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `get_order_details`

#### `get_addresses`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Discover | **Behaviour:** read-only

Swiggy (Instamart/Food): Get all saved delivery addresses for the authenticated Swiggy user, sorted by last order date. This tool works for Swiggy Instamart and Food services. Addresses are returned ...

**Input (TypeScript):**
```typescript
// get_addresses: no arguments
export type GetAddressesInput = Record<string, never>;
```

**Parameters:** none (session auth handled automatically)

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_addresses",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

**IMPORTANT **- STOP here and let the user choose:
1. Show the address list to the user
2. Ask: "Which address would you like to use for delivery?"
3. Do NOT call any other tool until the user has selected an address
4. Remember the selected addressId for all subsequent operations
5. If no addresses are returned, inform the user that they need to add an address first

**Next in journey:** `search_products`

#### `create_address`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Discover | **Behaviour:** mutating

Swiggy (Instamart/Food): Create a new delivery address for the authenticated user.

**Input (TypeScript):**
```typescript
export interface CreateAddressInput {
  fullAddress: string;  // Complete address as provided by the user
  addressLine: string;  // Main street/building/house number (REQUIRED)
  addressLine2: string;  // Apartment, floor, wing, or additional details (REQUIRED - extract from full address, use empty string "" if not found)
  locality?: string;  // Area, neighborhood, or locality name (optional)
  city: string;  // City name (REQUIRED)
  postalCode: string;  // Postal/ZIP code (REQUIRED)
  latitude: number;  // Latitude coordinate of the address (REQUIRED)
  longitude: number;  // Longitude coordinate of the address (REQUIRED)
  addressCategory: "HOME" | "WORK" | "OFFICE" | "FRIENDS_AND_FAMILY" | "OTHER";  // Type of address: HOME, WORK, OFFICE, FRIENDS_AND_FAMILY, or OTHER (REQUIRED)
  addressTag?: string;  // Friendly name/label for the address (e.g., "My Home", "Office", "Mom's Place") (optional)
  userName: string;  // Account holder name (authenticated user) (REQUIRED)
  userPhone: string;  // Account holder phone number (authenticated user) (REQUIRED)
  receiverName?: string;  // Receiver name if delivering to someone else (optional)
  receiverPhone?: string;  // Receiver phone if delivering to someone else (optional)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `fullAddress` | `string` | yes | Complete address as provided by the user |
| `addressLine` | `string` | yes | Main street/building/house number (REQUIRED) |
| `addressLine2` | `string` | yes | Apartment, floor, wing, or additional details (REQUIRED - extract from full address, use empty string "" if not found) |
| `locality` | `string` | no | Area, neighborhood, or locality name (optional) |
| `city` | `string` | yes | City name (REQUIRED) |
| `postalCode` | `string` | yes | Postal/ZIP code (REQUIRED) |
| `latitude` | `number` | yes | Latitude coordinate of the address (REQUIRED) |
| `longitude` | `number` | yes | Longitude coordinate of the address (REQUIRED) |
| `addressCategory` | `"HOME" \| "WORK" \| "OFFICE" \| "FRIENDS_AND_FAMILY" \| "OTHER"` | yes | Type of address: HOME, WORK, OFFICE, FRIENDS_AND_FAMILY, or OTHER (REQUIRED) |
| `addressTag` | `string` | no | Friendly name/label for the address (e.g., "My Home", "Office", "Mom's Place") (optional) |
| `userName` | `string` | yes | Account holder name (authenticated user) (REQUIRED) |
| `userPhone` | `string` | yes | Account holder phone number (authenticated user) (REQUIRED) |
| `receiverName` | `string` | no | Receiver name if delivering to someone else (optional) |
| `receiverPhone` | `string` | no | Receiver phone if delivering to someone else (optional) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_address",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

**WORKFLOW **- What to ASK the user:
1. Ask: "What is your complete delivery address?" (Get the full address as a single string)
2. Ask: "What is the latitude of your address?"
3. Ask: "What is the longitude of your address?"
4. Ask: "What is your name?"
5. Ask: "What is your phone number?"
6. Ask: "What type of address is this?" (Options: HOME, WORK, OFFICE, FRIENDS_AND_FAMILY, or OTHER)
7. Ask (optional): "Would you like to give a name/label to this address?" (e.g., "My Home", "Office")
8. Ask: "Is this address for you or someone else?"
   - If for someone else: Ask for the receiver's name and phone number

**AUTOMATIC PARSING **- What YOU must do (DO NOT ask user for these):
After getting the full address, YOU must automatically parse it and extract:
- addressLine: Main street/building/house number (REQUIRED - extract from full address)
- addressLine2: Apartment/floor/wing/additional details (REQUIRED - extract from full address)
- city: City name (REQUIRED - extract from full address)
- postalCode: Postal/ZIP code (REQUIRED - extract from full address)
- locality: Area/neighborhood (optional - extract if available)

> **Warning**
>
> CRITICAL RULES:

- NEVER ask the user to provide addressLine, addressLine2, city, or postalCode separately
- YOU parse the full address and extract these components automatically
- The user provides: full address, latitude, longitude, name, phone, address type, optional tag, and receiver details if applicable
- Account details (userName, userPhone) are ALWAYS the authenticated user
- Receiver details (receiverName, receiverPhone) are only used when delivering to someone else

**Next in journey:** `search_products`

#### `delete_address`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Discover | **Behaviour:** mutating

Swiggy (Instamart/Food): Delete a saved delivery address for the authenticated user.

**Input (TypeScript):**
```typescript
export interface DeleteAddressInput {
  addressId: string;  // The ID of the address to delete (from get_addresses response)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `addressId` | `string` | yes | The ID of the address to delete (from get_addresses response) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "delete_address",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

WORKFLOW:
1. First call get_addresses to show the user their saved addresses
2. Ask the user which address they want to delete
3. Get the addressId from the user's selection
4. Call this tool with the addressId

> **Warning**
>
> WARNING: This action is permanent and cannot be undone. Always confirm with the user before deleting.

**Next in journey:** `get_addresses`

#### `report_error`

**Server:** Instamart | **Endpoint:** `POST https://mcp.swiggy.com/im` | **Stage:** Support | **Behaviour:** mutating

Generate an error report to share with the Swiggy MCP team. Use this when the user encounters an error and wants to report it. Returns a pre-filled mailto: link and a human-readable summary. The user...

**Input (TypeScript):**
```typescript
export interface ReportErrorInput {
  tool: string;  // Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order")
  domain?: string;  // MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided.
  errorMessage: string;  // The error message the user saw
  flowDescription?: string;  // Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed")
  toolContext?: Record<string, unknown>;  // Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed.
  userNotes?: string;  // Any additional notes or context the user wants to share
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tool` | `string` | yes | Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order") |
| `domain` | `string` | no | MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided. |
| `errorMessage` | `string` | yes | The error message the user saw |
| `flowDescription` | `string` | no | Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed") |
| `toolContext` | `object` | no | Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed. |
| `userNotes` | `string` | no | Any additional notes or context the user wants to share |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "report_error",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

### 6.3 Dineout (8 tools)

#### `search_restaurants_dineout`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Find | **Behaviour:** read-only

Swiggy Dineout: Search restaurants for TABLE BOOKING/RESERVATIONS. Use when user wants to GO OUT and book a table. NOT for food delivery. Returns rich results: cuisines, ratings with count, costForTw...

**Input (TypeScript):**
```typescript
export interface SearchRestaurantsDineoutInput {
  query: string;  // Search query - restaurant name, cuisine type (Italian, Chinese, Indian), locality/area (Koramangala, Indiranagar), or descriptive terms (romantic, rooftop). Do NOT include location/city in query.
  entityType?: undefined;  // Search filter type. "locality" for area search (Indiranagar, Koramangala). "CUISINE" for cuisine search (Italian, Chinese, Biryani). "RESTAURANT_CATEGORY" for category search (cafe, pub, bar, brewery, lounge, buffet). Omit for restaurant name searches.
  addressId?: string;  // Address ID from get_saved_locations. Coordinates are resolved server-side. Use this instead of latitude/longitude when searching near a saved address.
  latitude?: number;  // Latitude for search. Use for direct city/area searches. Not needed if addressId is provided.
  longitude?: number;  // Longitude for search. Use for direct city/area searches. Not needed if addressId is provided.
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | `string` | yes | Search query - restaurant name, cuisine type (Italian, Chinese, Indian), locality/area (Koramangala, Indiranagar), or descriptive terms (romantic, rooftop). Do NOT include location/city in query. |
| `entityType` | `undefined` | no | Search filter type. "locality" for area search (Indiranagar, Koramangala). "CUISINE" for cuisine search (Italian, Chinese, Biryani). "RESTAURANT_CATEGORY" for category search (cafe, pub, bar, brewery, lounge, buffet). Omit for restaurant name searches. |
| `addressId` | `string` | no | Address ID from get_saved_locations. Coordinates are resolved server-side. Use this instead of latitude/longitude when searching near a saved address. |
| `latitude` | `number` | no | Latitude for search. Use for direct city/area searches. Not needed if addressId is provided. |
| `longitude` | `number` | no | Longitude for search. Use for direct city/area searches. Not needed if addressId is provided. |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_restaurants_dineout",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

**LOCATION **- Provide location using ONE of these methods: 
1. SAVED ADDRESS: If user says "near my home", "near my office", "my location" → First call get_saved_locations, then pass the chosen addressId here. 
2. CITY/AREA NAME: If user mentions a place (Bangalore, Koramangala, Mumbai, Indiranagar), use latitude/longitude for that location. Common coordinates: 
   - Bangalore center: 12.9716, 77.5946 
   - Koramangala: 12.9352, 77.6245 
   - Indiranagar: 12.9784, 77.6408 
   - Mumbai center: 19.0760, 72.8777 
   - Delhi center: 28.6139, 77.2090

ENTITY TYPE (IMPORTANT): Set entityType to filter search results correctly:
- Locality/area search (Indiranagar, Koramangala, JP Nagar) → entityType="locality"
- Cuisine search (Chinese, Italian, Biryani) → entityType="CUISINE"
- Category search (cafe, pub, bar, brewery, lounge, buffet) → entityType="RESTAURANT_CATEGORY"
- Restaurant name search (Social, Ironhill, Zaika) → omit entityType

> **Warning**
>
> Without entityType, locality and cuisine queries return generic nearby results instead of filtered results.

SEARCH BEHAVIOR:
- With entityType: Returns rich data (cuisines, ratings, costForTwo, highlights, offers)
- Without entityType: Returns exact name matches but limited data. Call get_restaurant_details for full info on results with source="autosuggest".

**QUERY**: Restaurant name, cuisine type, locality/area name, category, or descriptive terms. Do NOT include location/city in query if already provided via lat/lng.

EXAMPLES: 
- "Italian in Bangalore" → query="Italian", entityType="CUISINE", lat=12.9716, lng=77.5946 
- "restaurants in Indiranagar" → query="Indiranagar", entityType="locality", lat=12.9784, lng=77.6408 
- "cafes in Koramangala" → query="cafe", entityType="RESTAURANT_CATEGORY", lat=12.9352, lng=77.6245 
- "pubs in Bangalore" → query="pub", entityType="RESTAURANT_CATEGORY", lat=12.9716, lng=77.5946 
- "Social" → query="Social", no entityType, lat=12.9352, lng=77.6245 
- "near my home" → First call get_saved_locations, then pass addressId here

**Next in journey:** `get_restaurant_details`

#### `get_restaurant_details`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Find | **Behaviour:** read-only

Swiggy Dineout: Get details about a specific restaurant for TABLE BOOKING. Returns ratings, deals, timings, address. Use restaurant ID from search_restaurants_dineout results. Use same coordinates th...

**Input (TypeScript):**
```typescript
export interface GetRestaurantDetailsInput {
  restaurantId: string;  // Restaurant ID from search results
  latitude: number;  // Latitude (use same as search)
  longitude: number;  // Longitude (use same as search)
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `restaurantId` | `string` | yes | Restaurant ID from search results |
| `latitude` | `number` | yes | Latitude (use same as search) |
| `longitude` | `number` | yes | Longitude (use same as search) |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_restaurant_details",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `get_available_slots`

#### `get_available_slots`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Reserve | **Behaviour:** read-only

Swiggy Dineout (Reservations): Check available time slots for TABLE BOOKING at a restaurant. Returns slots across up to 7 days from the requested date. Shows breakfast, lunch, and dinner slots with a...

**Input (TypeScript):**
```typescript
export interface GetAvailableSlotsInput {
  restaurantId: string;  // Restaurant ID from search or details
  date: string;  // Starting date as YYYY-MM-DD string (e.g., "2025-11-20") or epoch timestamp as numeric string (e.g., "1735689600"). Returns slots for up to 7 days from this date.
  latitude: number;  // User's latitude
  longitude: number;  // User's longitude
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `restaurantId` | `string` | yes | Restaurant ID from search or details |
| `date` | `string` | yes | Starting date as YYYY-MM-DD string (e.g., "2025-11-20") or epoch timestamp as numeric string (e.g., "1735689600"). Returns slots for up to 7 days from this date. |
| `latitude` | `number` | yes | User's latitude |
| `longitude` | `number` | yes | User's longitude |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_available_slots",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `book_table`

#### `create_cart`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Reserve | **Behaviour:** mutating

Swiggy Dineout: Create a cart for TABLE BOOKING or bill payment. For booking (DEAL_TICKET_PURCHASE): requires restaurant ID, slot details, and guest count. Validates billToPay = 0 and skipPayment = t...

**Input (TypeScript):**
```typescript
export interface CreateCartInput {
  restaurantId: string;  // Restaurant ID
  cartType: "DEAL_TICKET_PURCHASE" | "DINEOUT";  // Cart type: DEAL_TICKET_PURCHASE for booking, DINEOUT for bill payment
  latitude: number;  // Latitude
  longitude: number;  // Longitude
  slotId?: number;  // Slot ID (required for booking cart)
  itemId?: string;  // Item ID (required for booking cart, format: "restaurantId-ticketId")
  reservationTime?: number;  // Unix timestamp (required for booking cart)
  guestCount?: number;  // Number of guests (required for booking cart, 1-20)
  billAmount?: number;  // Bill amount in rupees (required for bill payment cart)
  source?: string;  // Source for bill payment cart (default: "direct-payment-cart")
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `restaurantId` | `string` | yes | Restaurant ID |
| `cartType` | `"DEAL_TICKET_PURCHASE" \| "DINEOUT"` | yes | Cart type: DEAL_TICKET_PURCHASE for booking, DINEOUT for bill payment |
| `latitude` | `number` | yes | Latitude |
| `longitude` | `number` | yes | Longitude |
| `slotId` | `number` | no | Slot ID (required for booking cart) |
| `itemId` | `string` | no | Item ID (required for booking cart, format: "restaurantId-ticketId") |
| `reservationTime` | `number` | no | Unix timestamp (required for booking cart) |
| `guestCount` | `number` | no | Number of guests (required for booking cart, 1-20) |
| `billAmount` | `number` | no | Bill amount in rupees (required for bill payment cart) |
| `source` | `string` | no | Source for bill payment cart (default: "direct-payment-cart") |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_cart",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `book_table`

#### `book_table`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Reserve | **Behaviour:** mutating

Swiggy Dineout (Reservations): Book a table at a restaurant for a specific time slot. Only supports FREE reservations (isFree=true, bookingPrice=0). Paid deals will be rejected. Creates a cart then p...

**Input (TypeScript):**
```typescript
export interface BookTableInput {
  restaurantId: string;  // Restaurant ID
  slotId: number;  // Slot ID from selected slot (slot.deals[].slotId)
  itemId: string;  // Deal/ticket item ID (slot.deals[].itemId, format: "restaurantId-ticketId")
  reservationTime: number;  // Unix timestamp from selected slot (slot.reservationTime)
  guestCount: number;  // Number of guests (1-20)
  latitude: number;  // Latitude from user address
  longitude: number;  // Longitude from user address
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `restaurantId` | `string` | yes | Restaurant ID |
| `slotId` | `number` | yes | Slot ID from selected slot (slot.deals[].slotId) |
| `itemId` | `string` | yes | Deal/ticket item ID (slot.deals[].itemId, format: "restaurantId-ticketId") |
| `reservationTime` | `number` | yes | Unix timestamp from selected slot (slot.reservationTime) |
| `guestCount` | `number` | yes | Number of guests (1-20) |
| `latitude` | `number` | yes | Latitude from user address |
| `longitude` | `number` | yes | Longitude from user address |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "book_table",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Next in journey:** `get_booking_status`

#### `get_booking_status`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Manage | **Behaviour:** read-only

Get booking status and details for a dineout order. Returns restaurant name, date, time, guests, deal title, and status. Example: \"What is the status of my booking?\" → Call with order ID.

**Input (TypeScript):**
```typescript
export interface GetBookingStatusInput {
  orderId: string;  // Order ID from booking confirmation
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `orderId` | `string` | yes | Order ID from booking confirmation |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_booking_status",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

#### `get_saved_locations`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Find | **Behaviour:** read-only

Swiggy Dineout: Get user's saved addresses for restaurant search. Returns address IDs that can be passed to search_restaurants_dineout.

**Input (TypeScript):**
```typescript
// get_saved_locations: no arguments
export type GetSavedLocationsInput = Record<string, never>;
```

**Parameters:** none (session auth handled automatically)

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_saved_locations",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

**Agent guidance:**

How Swiggy agents and orchestration logic use this tool. Surface these expectations in your prompts or tool-selection policies.

WHEN TO USE THIS TOOL: 
- User says "near my home" 
- User says "near my office" 
- User says "my location" or "my address" 
- User says "where I live" or "my place"

DO NOT USE when user mentions a specific city/area (Bangalore, Koramangala, Mumbai) - use coordinates directly in search_restaurants_dineout instead.

WORKFLOW: 
1. Call this tool to get saved locations 
2. Show locations to user as numbered list 
3. Ask: "Which location would you like to search near?" 
4. Pass the chosen location's id as addressId in search_restaurants_dineout

RETURNS: List with index (1, 2, 3...), id, and addressLine for each saved address.

**Next in journey:** `search_restaurants_dineout`

#### `report_error`

**Server:** Dineout | **Endpoint:** `POST https://mcp.swiggy.com/dineout` | **Stage:** Support | **Behaviour:** mutating

Generate an error report to share with the Swiggy MCP team. Use this when the user encounters an error and wants to report it. Returns a pre-filled mailto: link and a human-readable summary. The user...

**Input (TypeScript):**
```typescript
export interface ReportErrorInput {
  tool: string;  // Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order")
  domain?: string;  // MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided.
  errorMessage: string;  // The error message the user saw
  flowDescription?: string;  // Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed")
  toolContext?: Record<string, unknown>;  // Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed.
  userNotes?: string;  // Any additional notes or context the user wants to share
}
```

**Parameters:**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tool` | `string` | yes | Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order") |
| `domain` | `string` | no | MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided. |
| `errorMessage` | `string` | yes | The error message the user saw |
| `flowDescription` | `string` | no | Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed") |
| `toolContext` | `object` | no | Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed. |
| `userNotes` | `string` | no | Any additional notes or context the user wants to share |

**Response envelope:**
```json
{ "success": true, "data": { /* tool-specific payload */ }, "message": "optional" }
```

*Partial response fields (from recipes/agent guidance, not full official schema):* see tool-specific notes in Section 5 recipes where applicable.

**JSON-RPC example:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "report_error",
    "arguments": { /* see TypeScript interface */ }
  },
  "id": 1
}
```

---

## 7. TypeScript Schema Appendix

### Shared types

```typescript
export interface SwiggySuccess<T> {
  success: true;
  data: T;
  message?: string;
}

export interface SwiggyError {
  success: false;
  error: {
    message: string;
    reportLink?: string;
    reportHint?: string;
  };
}

export type SwiggyResponse<T> = SwiggySuccess<T> | SwiggyError;

export type AddressCategory = "HOME" | "WORK" | "OFFICE" | "FRIENDS_AND_FAMILY" | "OTHER";

export type PaymentMethod = string; // from get_food_cart / get_cart availablePaymentMethods
```

### Per-tool input interfaces

```typescript
export interface SearchRestaurantsInput {
  addressId: string;  // Address ID from get_addresses tool
  query: string;  // Search query (restaurant name or cuisine)
  offset?: number;  // Pagination offset. Use nextOffset from previous response to load more results. Default: 0.
}

export interface GetRestaurantMenuInput {
  addressId: string;  // Address ID from get_addresses tool
  restaurantId: string;  // Restaurant ID to fetch menu for (from search_restaurants)
  page?: number;  // Page number for pagination (default: 1)
  pageSize?: number;  // Number of categories per page (default: 5, max: 8)
}

export interface SearchMenuInput {
  addressId: string;  // Address ID from get_addresses tool
  query: string;  // Search query (dish name)
  restaurantIdOfAddedItem?: string;  // Optional restaurant ID to scope search
  vegFilter?: number;  // Veg filter flag (0 or 1). Pass 1 for veg-only items. 0 or omitted returns mixed veg + non-veg. There is NO non-veg-only filter - if user asks for "non-veg only", pass 0 (mixed) and mention in text that you are showing all items including non-veg, since a non-veg-only filter is not available yet.
  offset?: number;  // Pagination offset. Use nextOffset from previous response to load more results. Default: 0.
}

export interface UpdateFoodCartInput {
  restaurantId: string;  // Restaurant ID for the cart
  cartItems: Record<string, unknown>[];  // Array of items to add to cart with their customizations
  addressId: string;  // Address ID to get accurate delivery charges based on location.
  restaurantName?: string;  // Restaurant name from search_restaurants or search_menu results. Pass this so the cart widget can display the restaurant name (the cart API does not always return it).
}

export interface GetFoodCartInput {
  addressId: string;  // Address ID to get accurate delivery charges based on location.
  restaurantName?: string;  // Restaurant name from search_restaurants or search_menu results. Pass this so the cart widget can display the restaurant name (the cart API does not always return it).
}

// flush_food_cart: no arguments
export type FlushFoodCartInput = Record<string, never>;

export interface FetchFoodCouponsInput {
  restaurantId: string;  // Restaurant ID for the cart
  addressId: string;  // Address ID where the order will be delivered (coordinates will be fetched automatically)
  couponCode?: string;  // Optional coupon code to check applicability of a specific coupon
}

export interface ApplyFoodCouponInput {
  couponCode: string;  // Coupon code to apply
  addressId: string;  // Address ID where the order will be delivered (coordinates will be fetched automatically)
  cartId?: string;  // Optional cart ID
}

export interface PlaceFoodOrderInput {
  addressId: string;  // Address ID from the user's saved addresses (coordinates will be fetched automatically)
  paymentMethod?: string;  // Payment method to use. Check availablePaymentMethods from get_food_cart response. Auto-defaults to the user's available payment method if not specified.
}

export interface GetFoodOrdersInput {
  orderCount?: number;  // Number of orders to fetch (default: 5, max: 20)
  addressId: string;  // Address ID to use for fetching orders (can be obtained from get_addresses)
}

export interface GetFoodOrderDetailsInput {
  orderId: string;  // Order ID to fetch details for (can be obtained from get_food_orders)
}

export interface TrackFoodOrderInput {
  orderId?: string;  // Optional: Specific order ID to track. If not provided, returns all active orders.
}

// get_addresses: no arguments
export type GetAddressesInput = Record<string, never>;

export interface ReportErrorInput {
  tool: string;  // Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order")
  domain?: string;  // MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided.
  errorMessage: string;  // The error message the user saw
  flowDescription?: string;  // Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed")
  toolContext?: Record<string, unknown>;  // Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed.
  userNotes?: string;  // Any additional notes or context the user wants to share
}

export interface SearchProductsInput {
  addressId: string;  // Address ID from get_addresses tool
  query: string;  // Search query (product name, category, or brand)
  offset?: number;  // Pagination offset (default: 0)
}

export interface YourGoToItemsInput {
  addressId: string;  // Address ID from get_addresses tool
  offset?: number;  // Pagination offset (default: 0)
}

export interface UpdateCartInput {
  selectedAddressId: string;  // Selected delivery address ID from get_addresses tool
  items: Record<string, unknown>[];  // Array of items to add to cart
}

// get_cart: no arguments
export type GetCartInput = Record<string, never>;

// clear_cart: no arguments
export type ClearCartInput = Record<string, never>;

export interface CheckoutInput {
  addressId: string;  // Delivery address ID (from get_addresses - user must have selected this address)
  paymentMethod?: string;  // Payment method to use. Check availablePaymentMethods from get_cart response. Auto-defaults to the user's available payment method if not specified.
}

export interface GetOrdersInput {
  count?: number;  // Number of orders to fetch (default: 10, max recommended: 20)
  orderType?: string;  // Order type filter (e.g., "DASH", "INSTAMART"). Default: "DASH"
  activeOnly?: boolean;  // Set to true to filter only active/ongoing orders. Default: false (returns all orders)
}

export interface GetOrderDetailsInput {
  orderId: string;  // The order ID to fetch details for (required). Can be obtained from get_orders tool.
}

export interface TrackOrderInput {
  orderId: string;  // The order ID to track (required). Can be obtained from get_orders tool.
  lat: number;  // Latitude of the delivery address (required for accurate tracking)
  lng: number;  // Longitude of the delivery address (required for accurate tracking)
}

// get_addresses: no arguments
export type GetAddressesInput = Record<string, never>;

export interface CreateAddressInput {
  fullAddress: string;  // Complete address as provided by the user
  addressLine: string;  // Main street/building/house number (REQUIRED)
  addressLine2: string;  // Apartment, floor, wing, or additional details (REQUIRED - extract from full address, use empty string "" if not found)
  locality?: string;  // Area, neighborhood, or locality name (optional)
  city: string;  // City name (REQUIRED)
  postalCode: string;  // Postal/ZIP code (REQUIRED)
  latitude: number;  // Latitude coordinate of the address (REQUIRED)
  longitude: number;  // Longitude coordinate of the address (REQUIRED)
  addressCategory: "HOME" | "WORK" | "OFFICE" | "FRIENDS_AND_FAMILY" | "OTHER";  // Type of address: HOME, WORK, OFFICE, FRIENDS_AND_FAMILY, or OTHER (REQUIRED)
  addressTag?: string;  // Friendly name/label for the address (e.g., "My Home", "Office", "Mom's Place") (optional)
  userName: string;  // Account holder name (authenticated user) (REQUIRED)
  userPhone: string;  // Account holder phone number (authenticated user) (REQUIRED)
  receiverName?: string;  // Receiver name if delivering to someone else (optional)
  receiverPhone?: string;  // Receiver phone if delivering to someone else (optional)
}

export interface DeleteAddressInput {
  addressId: string;  // The ID of the address to delete (from get_addresses response)
}

export interface ReportErrorInput {
  tool: string;  // Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order")
  domain?: string;  // MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided.
  errorMessage: string;  // The error message the user saw
  flowDescription?: string;  // Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed")
  toolContext?: Record<string, unknown>;  // Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed.
  userNotes?: string;  // Any additional notes or context the user wants to share
}

export interface SearchRestaurantsDineoutInput {
  query: string;  // Search query - restaurant name, cuisine type (Italian, Chinese, Indian), locality/area (Koramangala, Indiranagar), or descriptive terms (romantic, rooftop). Do NOT include location/city in query.
  entityType?: undefined;  // Search filter type. "locality" for area search (Indiranagar, Koramangala). "CUISINE" for cuisine search (Italian, Chinese, Biryani). "RESTAURANT_CATEGORY" for category search (cafe, pub, bar, brewery, lounge, buffet). Omit for restaurant name searches.
  addressId?: string;  // Address ID from get_saved_locations. Coordinates are resolved server-side. Use this instead of latitude/longitude when searching near a saved address.
  latitude?: number;  // Latitude for search. Use for direct city/area searches. Not needed if addressId is provided.
  longitude?: number;  // Longitude for search. Use for direct city/area searches. Not needed if addressId is provided.
}

export interface GetRestaurantDetailsInput {
  restaurantId: string;  // Restaurant ID from search results
  latitude: number;  // Latitude (use same as search)
  longitude: number;  // Longitude (use same as search)
}

export interface GetAvailableSlotsInput {
  restaurantId: string;  // Restaurant ID from search or details
  date: string;  // Starting date as YYYY-MM-DD string (e.g., "2025-11-20") or epoch timestamp as numeric string (e.g., "1735689600"). Returns slots for up to 7 days from this date.
  latitude: number;  // User's latitude
  longitude: number;  // User's longitude
}

export interface CreateCartInput {
  restaurantId: string;  // Restaurant ID
  cartType: "DEAL_TICKET_PURCHASE" | "DINEOUT";  // Cart type: DEAL_TICKET_PURCHASE for booking, DINEOUT for bill payment
  latitude: number;  // Latitude
  longitude: number;  // Longitude
  slotId?: number;  // Slot ID (required for booking cart)
  itemId?: string;  // Item ID (required for booking cart, format: "restaurantId-ticketId")
  reservationTime?: number;  // Unix timestamp (required for booking cart)
  guestCount?: number;  // Number of guests (required for booking cart, 1-20)
  billAmount?: number;  // Bill amount in rupees (required for bill payment cart)
  source?: string;  // Source for bill payment cart (default: "direct-payment-cart")
}

export interface BookTableInput {
  restaurantId: string;  // Restaurant ID
  slotId: number;  // Slot ID from selected slot (slot.deals[].slotId)
  itemId: string;  // Deal/ticket item ID (slot.deals[].itemId, format: "restaurantId-ticketId")
  reservationTime: number;  // Unix timestamp from selected slot (slot.reservationTime)
  guestCount: number;  // Number of guests (1-20)
  latitude: number;  // Latitude from user address
  longitude: number;  // Longitude from user address
}

export interface GetBookingStatusInput {
  orderId: string;  // Order ID from booking confirmation
}

// get_saved_locations: no arguments
export type GetSavedLocationsInput = Record<string, never>;

export interface ReportErrorInput {
  tool: string;  // Name of the tool that errored (e.g., "checkout", "search_products", "place_food_order")
  domain?: string;  // MCP server name where the error occurred (e.g., "im", "food", "dineout"). Auto-detected if not provided.
  errorMessage: string;  // The error message the user saw
  flowDescription?: string;  // Brief description of what the user was doing (e.g., "searched for milk → added to cart → checkout failed")
  toolContext?: Record<string, unknown>;  // Key-value pairs of identifiers from the failed tool call. Include ALL relevant IDs such as: orderId, restaurantId, addressId, spinId, menu_item_id, couponCode, query, cartId, slotId, paymentMethod, guestCount, itemId - whichever were part of the request that failed.
  userNotes?: string;  // Any additional notes or context the user wants to share
}

```

---

## 8. Mock-vs-Production Gap Matrix

| Area | Current mock ([`mcp_server/`](mcp_server/)) | Production Swiggy MCP |
| --- | --- | --- |
| Protocol | `{ "method", "params" }` on `/food`, `/im`, `/dineout` | JSON-RPC 2.0 `tools/call` on streamable HTTP |
| Auth | None | OAuth 2.1 + PKCE Bearer token |
| Food tools | 5: `get_addresses`, `search_restaurants`, `get_menu`, `add_to_cart`, `place_order` | 14 tools (see Section 6.1) |
| Instamart tools | 3: `search_products`, `add_to_cart`, `checkout` | 13 tools (see Section 6.2) |
| Dineout tools | 3: `search_restaurants`, `check_availability`, `book_table` | 8 tools incl. `get_available_slots`, `create_cart` |
| Cart model | Client `requestId` + `cartId` in [`mcp_server/food/dispatcher.py`](mcp_server/food/dispatcher.py) | Server-side session cart; no client cart ID |
| Address shape | `line1`, `area`, `pin` in [`mock_data/pune_addresses.py`](mock_data/pune_addresses.py) | `fullAddress`, `addressCategory`; coords omitted from `get_addresses` |
| LLM tools | Prefixed names in [`backend/llm_orchestrator.py`](backend/llm_orchestrator.py) (`food_*`, `im_*`) | Canonical tool names from MCP `tools/list` |

**Phase 3 goal:** Mock server must expose all 35 tools with production input/output schemas so agent core logic requires zero changes when swapping `LOCAL_MCP_BASE` for `mcp.swiggy.com`.
