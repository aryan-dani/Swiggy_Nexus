# Swiggy Nexus — one-click deploy on Render

This repo ships a **Render Blueprint** (`render.yaml`) that provisions:

| Service | Name | What it runs |
|---------|------|----------------|
| **Web (Docker)** | `swiggy-nexus-api` | FastAPI + offline mock MCP (`/food`, `/im`, `/dineout`) + SSE chat |
| **Web (Node)** | `swiggy-nexus-web` | Next.js UI (wired to the API automatically) |

## Deploy (≈5 minutes)

### 1. Push to GitHub

```bash
git push origin main
```

### 2. Create the Blueprint on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
2. Connect your GitHub account and select this repository.
3. Render detects `render.yaml` — click **Apply**.

### 3. Optional secrets (dashboard prompts)

| Variable | Service | Required? |
|----------|---------|-----------|
| `GROQ_API_KEY` | `swiggy-nexus-api` | Yes for LLM chat + AI Sommelier |
| `NEXT_PUBLIC_GROQ_ENABLED` | `swiggy-nexus-web` / Vercel | `true` when Groq is configured |
| `BASE_URL` | `swiggy-nexus-api` | Public API URL (Telegram webhook + approve links) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | API | HITL approvals |
| `NOTIFICATION_PLATFORM` | API | `telegram` (or `console`) |
| `INTERNAL_TICK_SECRET` | API | Shared secret for `POST /internal/tick` |
| `OPENWEATHER_API_KEY` | API | Optional monsoon sensor |
| `USE_MOCK_MCP` | API | Default `true` until Swiggy staging token |

Full Concierge setup: [`docs/concierge-setup.md`](concierge-setup.md).

Leave Telegram blank to use console HITL locally.

### 4. Open the app

When both services are **Live**:

- **UI:** `https://swiggy-nexus-web.onrender.com` (your URL may differ slightly)
- **API health:** `https://swiggy-nexus-api.onrender.com/health`

Click **Run 60s WOW demo** on the home page.

> **Free tier:** services spin down after ~15 min idle. First load after sleep can take 30–60s.

## What gets configured automatically

- `NEXT_PUBLIC_API_URL` on the frontend → API hostname from `swiggy-nexus-api`
- `CORS_ORIGIN_REGEX` on the API → allows `*.onrender.com` and `*.vercel.app`
- Docker image uses `$PORT` (Render injects this)
- Health checks: `/health` (API), `/` (web)

## Verify API

```bash
curl https://swiggy-nexus-api.onrender.com/health
# {"status":"ok","service":"swiggy-nexus-backend","groq_configured":false}

curl -X POST https://swiggy-nexus-api.onrender.com/food \
  -H "Content-Type: application/json" \
  -d '{"method":"get_addresses","params":{}}'
```

## Frontend-only on Vercel (optional)

If you prefer Vercel for the UI and Render for the API only:

1. Deploy **only** `swiggy-nexus-api` from the Blueprint (or delete the web service after).
2. Vercel → import repo → **Root Directory:** `frontend`.
3. Set `NEXT_PUBLIC_API_URL=https://swiggy-nexus-api.onrender.com`.
4. On Render API, `CORS_ORIGIN_REGEX` already allows `*.vercel.app`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| CORS errors in browser | Confirm web URL matches `*.onrender.com`. Redeploy API after changing `CORS_*` vars. |
| Chat works locally but not on Render | Check `NEXT_PUBLIC_API_URL` on web service (build-time). **Redeploy web** after changing it. |
| MCP 502 from UI | API may be waking from sleep — wait and retry. |
| Groq not used | Set `GROQ_API_KEY` on API + `NEXT_PUBLIC_GROQ_ENABLED=true` on web, redeploy **both**. |

## Local parity

```bash
# Terminal 1 — API
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — UI pointed at API
echo NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 > frontend/.env.local
cd frontend && npm run dev
```
