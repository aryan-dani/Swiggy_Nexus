# Swiggy Nexus

Synthetic “Nexus” assistant UI demo: neo-brutalist ChatGPT-style workspace with a mock MCP feed. **Not affiliated with Swiggy.** Intended as a POC for agentic UX and optional FastAPI integration.

## Repository layout

| Path | Purpose |
|------|---------|
| `frontend/` | **Next.js 16** App Router UI. Includes **built-in `/api/*` Route Handlers** so the demo runs without a separate backend (local + Vercel). |
| `backend/` | Optional **FastAPI** service (`uvicorn backend.main:app`). Use when you want real streaming/agent logic behind the UI. |
| `docs/local-mock-mcp.md` | **Offline** MCP-style mock servers `POST /food`, `/im`, `/dineout` + streaming agent wired for demo video. |
| `docs/swiggy-builders-club.md` | **Swiggy Builders Club** digest: official `mcp.swiggy.com` MCP (for production integration). |

Real Swiggy MCP lives at `https://mcp.swiggy.com`; this repo ships a **fully local mock** (`mcp_server/` + [`docs/local-mock-mcp.md`](docs/local-mock-mcp.md)) for demos with no outbound API calls.

For partnering with Swiggy in production see [**Swiggy Builders Club — What you can use and how**](docs/swiggy-builders-club.md).

## Prerequisites

- **Node.js** 20.x or newer (LTS recommended) for `frontend/`
- **Python 3.11+** only if you run `backend/` locally or via Docker

## Quick start (frontend only, mocked API)

From the repo root:

```bash
npm install --prefix frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

With **no** `NEXT_PUBLIC_API_URL`, the UI calls **same-origin** routes under `frontend/app/api/` (SSE chat stub + sidebar JSON). No Python server required.

**Reviewer path:** Open the home page and use **Reviewer · Signals & scenarios** (synthetic triggers + story presets — Social Deadlock, Flow-state fueler, Zero-waste meal). Credential narrative and dual-agent framing: see [`PITCH.md`](./PITCH.md).

### Environment (frontend)

Copy the example and edit as needed:

```bash
copy frontend\.env.example frontend\.env.local   # Windows
# cp frontend/.env.example frontend/.env.local    # macOS/Linux
```

See [`frontend/.env.example`](frontend/.env.example) for details.

## Optional: run the FastAPI backend

Install and run:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Then point the UI at it by setting **`NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`** in `frontend/.env.local` (no trailing slash). You get **offline mock MCP**: `POST /food`, `/im`, `/dineout` plus multi-step SSE chat — see [`docs/local-mock-mcp.md`](docs/local-mock-mcp.md) for prompts, `curl` samples, `LOCAL_MCP_HTTP`, and UX notes.

CORS: the backend reads **`FRONTEND_ORIGIN`** or **`CORS_ORIGINS`** (`backend/main.py`). Set e.g. `FRONTEND_ORIGIN=http://localhost:3000` when developing.

### Docker (API only)

```bash
docker build -t swiggy-nexus-api .
docker run -p 8000:8000 -e FRONTEND_ORIGIN=http://localhost:3000 swiggy-nexus-api
```

### Procfile / Heroku-style

[`Procfile`](Procfile) runs the API with `uvicorn` (adjust `PORT` as your host provides).

## Deploy on Render (recommended — full stack)

**One-click:** push to GitHub, then [Render → New Blueprint](https://dashboard.render.com) → connect this repo → **Apply**.

The root [`render.yaml`](render.yaml) provisions:

- **`swiggy-nexus-api`** — FastAPI + mock MCP (Docker)
- **`swiggy-nexus-web`** — Next.js UI (auto-wired to the API)

Full walkthrough: [**docs/deploy-render.md**](docs/deploy-render.md)

Optional: add `GROQ_API_KEY` on the API service and `NEXT_PUBLIC_GROQ_ENABLED=true` on the web service for LLM mode. Skip both for the deterministic WOW demo.

## Deploy on Vercel (frontend only)

1. Push this repo to GitHub/GitLab/Bitbucket.
2. In [Vercel](https://vercel.com) → **New Project** → import the repo.
3. Set **Root Directory** to **`frontend`** so builds use `frontend/package.json` and Next.js detection.
4. **No env vars required** for the dummy (mocks ship with the app). Add **`NEXT_PUBLIC_API_URL`** only when your API is hosted elsewhere (HTTPS base URL, no trailing slash).

Production build from repo root:

```bash
npm run build
npm run start
```

## NPM scripts (root)

| Script | Command |
|--------|---------|
| `npm run dev` | `next dev` in `frontend/` |
| `npm run build` | `next build` in `frontend/` |
| `npm run start` | `next start` in `frontend/` |
| `npm run lint` | `next lint` in `frontend/` |

## License / disclaimer

Demo and synthetic APIs only; verify behaviour before relying on outputs for real ordering or fulfilment decisions.
