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
| **Demo / Vercel** | Leave **`NEXT_PUBLIC_API_URL`** unset. The UI uses [`app/api/`](./app/api/) Route Handlers on the same origin. |
| **External FastAPI** | Set `NEXT_PUBLIC_API_URL` to your API base URL (see [`.env.example`](./.env.example)). |

## Next.js resources

- [Next.js docs](https://nextjs.org/docs)
- [Deploying to Vercel](https://vercel.com/docs/frameworks/nextjs)
