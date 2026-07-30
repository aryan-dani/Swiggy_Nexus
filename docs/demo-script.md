# Swiggy Nexus — demo recording script

Shot-by-shot plan for a 5–6 minute walkthrough. Every segment has a fallback, so a
flaky API or an exhausted LLM quota never ends the take.

**The one idea to land:** Nexus is not a chatbot. It is an autonomous concierge that
stages real Swiggy MCP tool calls across Food, Instamart and Dineout, and stops dead
at a human approval before anything spends money — whether the trigger is a calendar
event, a Telegram message, or a voice note.

---

## 0. Pre-flight (do this before you hit record)

### Environment

```powershell
cd C:\Users\dania\Documents\Stuff\My_Repositories\Domain_Based\Agentic_AI\Swiggy_Nexus
```

`backend/.env` must have:

```env
GEMINI_API_KEY=...            # primary brain
LLM_PROVIDER=auto             # Gemini first, Groq fallback
GROQ_API_KEY=...              # fallback + Whisper voice transcription
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
NOTIFICATION_PLATFORM=telegram
BASE_URL=http://127.0.0.1:8000
```

`frontend/.env.local` (must be UTF-8, not UTF-16):

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### Start the stack

Terminal A — API. **Use `backend.main:app` and do NOT pass `--reload`.** The LangGraph
checkpoint lives in memory by default, so a reload mid-take strands a pending approval.

```powershell
$env:LANGGRAPH_SQLITE=1
.\backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete` and `starting Telegram long-poll`.

Terminal B — UI. **Record against a production build**, not the dev server: no Fast
Refresh, no dev error overlay badge in the corner of your video, and faster rendering.

```powershell
cd frontend
npm run build
npm start
```

Terminal C — kept free for the calendar push command.

### Clean slate + verify

```powershell
curl.exe -X POST http://127.0.0.1:8000/internal/demo/reset -H "X-Nexus-Tick-Secret: nexus-tick-secret"
```

This clears approvals, the timeline, idempotency keys, execution snapshots, MCP carts
and Telegram chat memory — and **reseeds the pantry to a believable household cadence**
(milk every ~3 days, bread ~4, dal ~15). Without it, earlier demo runs leave nonsense
like "Coca-Cola every 0.1 days" on screen.

Then check http://127.0.0.1:8000/api/concierge/agent — you want
`"configured": true` and `"telegram_ready": true`.

### Screen layout

Browser on the left showing **Concierge Ops**, Telegram Desktop on the right. Both
visible at once is the whole trick: the phone and the dashboard move together.

Zoom the browser to ~110%. Close other tabs. Silence notifications.

---

## 1. Cold open — 25s

**On screen:** Concierge Ops, freshly reset.

> "This is Swiggy Nexus. It is not a chatbot — it is an autonomous concierge. It reads
> your calendar, listens to your messages, and orchestrates Food, Instamart and Dineout
> through the Swiggy MCP tool surface. The one rule: it can prepare anything, but it can
> never spend money without me tapping Approve."

Point at the header chips: the active brain (Gemini), Telegram live, and
**3 tools HITL-gated**.

> "Those three gated tools are place order, checkout, and book table. The money tools.
> The model is never allowed to call them directly."

---

## 2. Telegram agent orders dinner — 90s ★ main segment

**On Telegram, type:**

```
order a paneer biryani for dinner
```

While it works, narrate what the bot is showing you (it live-edits a status message):

> "That is a real LLM with the 23 Swiggy tool schemas. It is searching restaurants,
> loading that restaurant's actual menu, and building a cart — all read-only tools."

**Now the punchline.** Point at the browser without touching it:

> "And watch the dashboard. Same agent, same tools, mirrored live on the ops timeline.
> Phone in one hand, control tower in the other."

Switch the timeline filter to **Agent activity** to isolate the tool trail.

When the bot posts the **⏸ Human approval needed** card with Approve/Reject:

> "Here is the gate. It staged a cart with a real total, and stopped. Nothing is
> ordered. The model was told 'awaiting human approval' and it is telling me exactly
> that in plain language."

Show the same request in **Needs your approval** on the dashboard, with the itemised
lines and total.

**Tap Approve in Telegram.**

> "One tap, and only now do the write tools fire — update cart, then checkout."

The timeline shows `hitl_approved`. The card clears.

**Fallbacks:** if Telegram is slow, tap the green **Approve** on the dashboard — same
backend path, same result. If the LLM is quota-limited, the bot says so plainly; switch
to segment 3 and come back.

---

## 3. Voice note — 30s

Hold the mic in Telegram and say:

> "Get me milk, bread and eggs from Instamart."

The bot echoes the transcript in quotes, then runs the identical agent loop and stages
an Instamart checkout.

> "Same pipeline from a voice note. Groq Whisper transcribes it, the agent plans it,
> and it still stops at the approval gate. In production this is a WhatsApp voice note."

Approve or Reject — either is a good beat. Rejecting is a nice flex:

> "I will reject this one. Carts flushed, nothing ordered."

---

## 4. Google Calendar → concierge — 75s

This is the "it works while I am not even looking" segment.

### Path A — live Google push (only if ngrok is already running)

```powershell
ngrok http 8000
# set BASE_URL to the https URL in backend/.env, restart the API, then:
python scripts\google_calendar_watch.py
```

Create a Google Calendar event titled `Housewarming with the team #host #swiggy`,
location `Home`, and add guests. Save it.

### Path B — replay (recommended for a clean take)

Click **Push calendar event** in the Workflows row, or run:

```powershell
python scripts\demo_calendar_push.py --mode host
```

> "That is the exact payload Google pushes to our webhook. I am replaying it so the
> recording does not depend on a tunnel — the gate, the graph and the approval are
> identical."

**Narrate what happens on its own:**

> "The event is tagged hash-swiggy, so the concierge wakes up. It pulls each guest's
> dietary profile from the Taste Vault — one guest is vegan, another is lactose
> intolerant — merges those into hard constraints, and stages an Instamart run plus a
> food order that respects all of them."

Show the approval card with line items, then **Approve**.

> "And after approval it writes the plan back into the calendar event description, so
> the group sees what was ordered without opening this dashboard."

**Fallback:** if the graph errors, use **Trigger Zero-Touch Host** — same graph, started
from the UI instead of a calendar payload.

---

## 5. Closers — pick two, 45s

- **Pantry radar:** "It learns your Instamart reorder cadence. Milk every three days,
  dal every fifteen. When something is about to run out it stages a refill — Khatam
  Hone Wala Hai — still behind the same Approve." Click **Refill low items**.
- **Rain / Rooftop:** "Monsoon hits a rooftop booking, and it offers a pivot. Honest
  limitation: the Swiggy API has no cancel tool, so we tell the user to cancel in the
  app rather than pretend."
- **Bill split:** "Group dinner splits into equal shares with UPI links. That one is a
  Nexus extension, not a Swiggy tool — I am flagging it so nobody thinks it is official."
- **Chat tab WOW demo:** the Chrono-Host three-vertical bundle with the Demo Director
  stepper.

---

## 6. Close — 30s

> "Everything you saw runs on official Swiggy MCP tool names against a local 35-tool
> mock, so pointing it at mcp.swiggy.com is a config flip, not a rewrite. Writes are
> gated, staged carts are durable in SQLite, and the approval survives a restart.
>
> We would love staging access to run this exact demo against the real thing. Thanks,
> Builders Club."

End on `/api/concierge/agent` or the clean dashboard.

---

## Honest limits to say out loud (once each)

- Mock MCP, synthetic catalog, no real money. Real tool names and field shapes.
- No cancel tool in the Swiggy API — Rooftop Rescue guides a manual cancel.
- Food has no scheduled delivery in v1; the 10 PM dessert leg is a reminder, not a
  deferred order.
- Bill Split is a Nexus extension, not an official tool.
- Instamart minimum order 99 INR; food cart caps at 1000 INR.

## Do not say

- "It ordered food" before you tap Approve.
- "This is live Swiggy."
- Anything about LangGraph internals — say "a workflow with an approval step".

---

## Troubleshooting mid-take

| Symptom | Fix |
|---|---|
| Bot silent on free text | Check the API log for `starting Telegram long-poll`; localhost uses polling, not webhooks |
| "My LLM quota is exhausted" | Groq free tier is 100k tokens/day. Set `GEMINI_API_KEY` and `LLM_PROVIDER=auto` |
| Concierge tab shows 404s | `frontend/.env.local` must be UTF-8 and point at `127.0.0.1:8000`, then restart `npm run dev` |
| Calendar push returns `ignored` | The event needs `#swiggy` or `#host`; a repeated explicit `event_id` is deduped |
| Approvals piling up between takes | `POST /internal/demo/reset` with the `X-Nexus-Tick-Secret` header |
| Approval vanished after a code save | You ran uvicorn with `--reload`; restart without it and set `LANGGRAPH_SQLITE=1` |
| Red Next.js error badge on screen | You are on `npm run dev`. Record with `npm run build; npm start` — the dev overlay does not exist in production |
| Pantry radar shows silly intervals | Run the demo reset; it reseeds the household baseline |

## Keep off camera

Analytics and Library tabs are thin localStorage views with nothing to show.
