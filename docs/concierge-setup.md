# Indian QoL Concierge — Setup Guide

End-to-end automation: Google Calendar → Taste Vault → LangGraph → HITL (Telegram) → Swiggy MCP (35 tools).

## Architecture (short)

1. Calendar event with `#swiggy` / `#host` hits `POST /webhooks/calendar`.
2. LangGraph **stages** carts/slots with **read tools only**.
3. `hitl_notify` creates a durable approval + Telegram inline buttons.
4. Graph **interrupts** until Approve/Reject.
5. Only then: `book_table` / `checkout` / `place_food_order`.
6. Calendar description write-back + QoL timeline.

Honest API gap: **no `cancel_reservation`** tool — Rooftop Rescue tells users to cancel in the Swiggy app.

## Local run

```bash
pip install -r requirements.txt
# Terminal A
uvicorn backend.main:app --reload --port 8000
# Terminal B
cd frontend && npm run dev
```

Open http://localhost:3000 → sidebar **Concierge** for Ops tab (requires `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | AI Sommelier (rule fallback if empty) |
| `USE_MOCK_MCP` | `true` (default) local 35-tool mock |
| `SWIGGY_OAUTH_TOKEN` | Bearer when `USE_MOCK_MCP=false` |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | HITL channel |
| `NOTIFICATION_PLATFORM` | `telegram` \| `console` \| `discord` \| `slack` |
| `OPENWEATHER_API_KEY` | Live monsoon checks |
| `GOOGLE_CALENDAR_TOKEN_PATH` | OAuth token JSON |
| `GOOGLE_PUBSUB_VERIFICATION_TOKEN` | Calendar watch channel token |
| `BASE_URL` | Public URL for Telegram webhook + approve links |
| `INTERNAL_TICK_SECRET` | Header for `POST /internal/tick` |
| `HOME_LAT` / `HOME_LNG` | Pune defaults |

Copy [backend/.env.example](../backend/.env.example).

---

## What you do at your end

### 1. Google Calendar (~15 min)

1. Google Cloud Console → new project → enable **Google Calendar API**.
2. OAuth consent (External) → add your Gmail as test user.
3. Credentials → OAuth client ID → **Desktop app** → download JSON → save as `credentials/google_credentials.json`.
4. Run:

```bash
python scripts/google_auth_setup.py
```

Produces `credentials/google_token.json`.

5. Local webhooks: run `ngrok http 8000`, set `BASE_URL=https://….ngrok.io`, then:

```bash
python scripts/google_calendar_watch.py
```

On Render, set `BASE_URL` to the API URL; watch registration renews via `/internal/tick`.

### 2. Telegram (~5 min)

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy token → `TELEGRAM_BOT_TOKEN`.
2. DM your bot once.
3. Run:

```bash
python scripts/telegram_chat_id.py
```

→ set `TELEGRAM_CHAT_ID`, `NOTIFICATION_PLATFORM=telegram`.

4. With public `BASE_URL`, the API auto-registers `POST /api/hitl/telegram/webhook`.

Commands: `/guests 6`, `/fuel`, `/status`, `/approve REQ-…`, `/reject REQ-…`.

### 3. OpenWeather (~5 min)

1. Free key at openweathermap.org → `OPENWEATHER_API_KEY`.
2. Or use Concierge Ops **Rain** simulate (scenario provider).

### 4. Render

1. Redeploy `swiggy-nexus-api` (Dockerfile now copies `app/`).
2. Set env vars above.
3. Free cron (cron-job.org): every 5 min  
   `POST https://YOUR-API.onrender.com/internal/tick`  
   Header: `X-Nexus-Tick-Secret: <INTERNAL_TICK_SECRET>`.

### 5. Swiggy MCP live (after whitelist / OAuth)

```bash
python scripts/swiggy_oauth_login.py   # browser phone+OTP → credentials/swiggy_token.json
# backend/.env:
#   USE_MOCK_MCP=false
#   SWIGGY_CLIENT_ID=swiggy-mcp
#   SWIGGY_OAUTH_TOKEN=<access_token from token file>
python scripts/swiggy_mcp_smoke.py     # read-only get_addresses (PII redacted)
```

Leave `USE_MOCK_MCP=true` for the offline demo. Concierge + chat agent use **official** tool names — live path is gated only by the flag + Bearer token.

### 6. Frontend

Vercel / local:

```
NEXT_PUBLIC_API_URL=https://YOUR-API.onrender.com
NEXT_PUBLIC_GROQ_ENABLED=true
```

---

## Demo script for reviewers (Concierge Ops)

**Full spoken script + plain-language explanation:** [`docs/demo-script.md`](demo-script.md).

1. **Trigger Zero-Touch Host** → pending approval → Approve → Instamart checkout + food place.
2. **Trigger Dineout** → staged table → Approve → `book_table` only after HITL.
3. **Rain / Rooftop** → Hinglish pivot (Order home / Indoor / Keep).
4. **Guests slider** → Bin Bulaye Mehmaan Instamart SOS.
5. **IPL chase** → finger-food HITL.
6. Watch **QoL timeline** + MCP coverage in chat tab.

On localhost, Telegram Approve uses **long-polling** (see API log: `starting Telegram long-poll`). Ops UI Approve is the same HITL gate.

## Key endpoints

| Method | Path |
|--------|------|
| POST | `/webhooks/calendar` |
| POST | `/api/concierge/trigger` |
| GET | `/api/concierge/timeline` |
| GET | `/api/concierge/approvals` |
| POST | `/api/hitl/approve/{id}` |
| POST | `/api/hitl/reject/{id}` |
| POST | `/api/hitl/telegram/webhook` |
| POST | `/api/concierge/simulate/{weather\|guests\|ipl\|fuel}` |
| POST | `/internal/tick` |
| GET | `/health/concierge` |
