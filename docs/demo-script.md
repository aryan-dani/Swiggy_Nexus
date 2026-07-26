# Concierge demo script — what to say and what happens

Plain-language guide for reviewers and live demos.  
**Nexus Concierge is not a chatbot.** It stages carts/slots, pauses for your approval, then runs write tools on the mock Swiggy MCP.

---

## One-sentence pitch

> Plan → stage carts → human Approve → order. Nothing spends money without that Approve.

---

## Real-life analogy

| Real life | Nexus |
|-----------|--------|
| Friend makes a shopping list | **Staging** (read-only MCP tools) |
| Friend texts “Should I buy this?” | **Waiting for Approve** (HITL / Telegram) |
| You reply “Yes” | **Approve** |
| Friend buys it | **Complete** (mock checkout / book_table) |

You are the person who says yes/no. Nexus prepared the list.

---

## Click path: Trigger Zero-Touch Host

**Meaning of the button:** “Pretend I’m hosting at home. Prepare Instamart + Food carts.”  
It does **not** mean “order now.”

| Step | What the system does | What you see |
|------|----------------------|--------------|
| 1. Profile guests | Taste Vault for demo emails (`dani@nexus.ai`, `priya@nexus.ai`) | Behind the scenes |
| 2. Stage | Search menus, build carts — **no checkout yet** | Banner: Staging |
| 3. Pause (HITL) | Telegram + Pending approvals | Banner: Waiting for Approve |
| 4. You Approve | Runs `checkout` / `place_food_order` on **mock** MCP | Banner: Complete + timeline |
| 5. You Reject | Clears carts, places nothing | Banner: Rejected |

---

## Spoken script (copy for live demos)

### While clicking Trigger Zero-Touch Host

> “Someone’s hosting at home. Instead of opening Swiggy myself, Nexus prepares an Instamart cart and a food cart based on the guests’ preferences.”

### When it says Waiting for Approve

> “Important: it has not ordered anything yet. It always pauses for human approval — that’s the safety gate.”

### Show Telegram or the green Approve button

> “I get this on Telegram too. One tap to approve.”

### After Approve / Complete

> “Now it places the orders on the mock Swiggy tools. In production this would be real MCP. Today it’s a safe demo — no real charges.”

### Closing line

> “So it’s not a chatbot. It’s an automation: plan → stage carts → human approve → order.”

### 20-second version

> “I trigger a house-party flow. Nexus stages groceries and food, asks me to approve, then places the demo order. Nothing spends money without that Approve.”

---

## What not to say

- Don’t say “it ordered food automatically” **before** Approve  
- Don’t say “this is live Swiggy” — say **mock / demo MCP**  
- Don’t over-explain LangGraph — say “workflow with an approval step”

---

## Other Concierge Ops buttons (same pattern)

| Button | Story |
|--------|--------|
| **Trigger Dineout** | Dinner out → find slots → pause → Approve → `book_table` |
| **Guests** | Surprise guests → Instamart party basket → Approve → checkout |
| **Rain / Rooftop** | Rain near outdoor booking → order home / indoor / keep |
| **IPL / Fuel** | Match timeout or late-night study → snack prompt → Approve |

Always: **stage → ask you → write.**

---

## Chat tab: Run 60s WOW demo

Separate from Concierge Ops. One prompt stages a **Chrono-Host** bundle (Dineout + Instamart + Food).  
Watch the **Demo Director** stepper: Plan → Dineout → Instamart → Food → Bundle.  
Confirm legs in the Activity rail. Still mock / demo.

---

## Telegram on localhost

Inline Approve buttons need the API to receive callback clicks.  
With `BASE_URL` on localhost, the API uses **long-polling** (no ngrok required for Approve).  
Restart uvicorn and look for: `Local BASE_URL — starting Telegram long-poll`.

You can also Approve in the Concierge Ops UI — same backend action.

---

## Honest “what’s real vs demo”

| Piece | Real / mock |
|--------|-------------|
| Concierge Ops triggers | Real workflow against local API |
| Telegram approvals | Real bot messages |
| Taste Vault diets | Demo profiles in SQLite |
| Swiggy orders / bookings | **Mock** until staging + `USE_MOCK_MCP=false` |
| Google Calendar start | Needs ngrok + watch channel (see [concierge-setup.md](concierge-setup.md)) |

---

## Pre-demo checklist

1. API on `:8000` — `http://127.0.0.1:8000/health/concierge`  
2. Frontend on `:3000` with UTF-8 `frontend/.env.local`:  
   `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`  
3. `NOTIFICATION_PLATFORM=telegram` + bot token + chat id in `backend/.env`  
4. Hard-refresh browser after starting Next  
5. Concierge → Zero-Touch → Approve (Telegram or UI) → timeline updates  
