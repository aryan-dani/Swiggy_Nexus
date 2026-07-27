# Nexus frontend (Next.js)

This package is the **Swiggy Nexus** UI (`app/`, `components/`, `lib/`).

- **Full overview** (repo layout, backend, Vercel): see the [root README](../README.md).

## Commands

Prefer running from **repository root**:

```bash
npm run dev
npm run build
```

Or run only this package:

```bash
npm install
npm run dev
```

Opens [http://localhost:3000](http://localhost:3000).

**Reviewer:** use **Signals & scenarios** above the chat (home page); pitch copy for credential forms lives in repo root [**PITCH.md**](../PITCH.md).

## API routing

| Mode | Configuration |
|------|----------------|
| **Demo / Vercel (chat-only mocks)** | Leave **`NEXT_PUBLIC_API_URL`** unset. Chat uses same-origin Route Handlers. |
| **Concierge / full FastAPI** | Set `NEXT_PUBLIC_API_URL=https://swiggy-nexus-api.onrender.com` (the **API** service, not `-web`). Redeploy after changing. |

## Next.js resources

- [Next.js docs](https://nextjs.org/docs)
- [Deploying to Vercel](https://vercel.com/docs/frameworks/nextjs)
