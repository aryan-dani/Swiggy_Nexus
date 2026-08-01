# Swiggy Nexus — SPEAK & CLICK teleprompter (~4 min)

Read **SPEAK** out loud. Do **CLICK / TYPE** with your hands. Pause on **WAIT**.  
Never say “ordered” or “booked” until after you tap Approve / Confirm.

---

## BEFORE RECORD (do once, camera off)

1. Start API (no `--reload`):

```powershell
cd C:\Users\dania\Documents\Stuff\My_Repositories\Domain_Based\Agentic_AI\Swiggy_Nexus
.\backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000
```

*(Do not use `--reload`. Approvals are durable in SQLite; the LangGraph interrupt lives in-memory for the process lifetime.)*

2. Start UI:

```powershell
cd frontend
npm run build
npm start
```

3. Reset:

```powershell
curl.exe -X POST http://127.0.0.1:8000/internal/demo/reset -H "X-Nexus-Tick-Secret: nexus-tick-secret"
```

4. Open http://127.0.0.1:3000  
5. Sidebar: turn **Developer mode OFF**  
6. Stay on **Chat** (not Concierge yet)  
7. Open Telegram Desktop to your Nexus bot in another window (for Scene 4+)

---

# SCENE 1 — Cold open (15 seconds)

**YOU SEE:** Chat hero with “Run 60s WOW demo” card. Activity rail empty on the right.

**CLICK:** Nothing. Just point at the title “Swiggy Nexus”.

**SPEAK (exactly):**

> This is Swiggy Nexus. It is not a chatbot. It is an autonomous concierge that orchestrates Food, Instamart, and Dineout through the official Swiggy MCP tool surface. One rule: it can stage anything — but it never spends money until I approve.

---

# SCENE 2 — 60 second WOW (60–75 seconds)

**CLICK:** The big purple / primary card **“Run 60s WOW demo”**.

*(That auto-sends: `Plan my evening for 12 guests`.)*

**WAIT:** Demo Director bar appears (Plan → Dineout → Instamart → Food). Tool chips start popping under the chat. Right side “Activity” starts filling.

**SPEAK (while tools run — slow, calm):**

> Watch this. One sentence — plan my evening for twelve guests — and Chrono-Host fans out across three Swiggy verticals. Dineout for the table. Instamart for party supplies. Food for dessert. Every chip you see is a real MCP tool call.

**CLICK:** Point (don’t click) at the right rail when the Chrono-Host bundle / cards appear.

**SPEAK:**

> Everything on the right is staged. Nothing is booked. Nothing is checked out. The agent prepared the night — it did not spend.

**IF IT FAILS:** Sidebar → **+ NEW CHAT** → click **Run 60s WOW demo** again.

---

# SCENE 3 — Confirm = money gate (30 seconds)

**YOU SEE:** Chrono-Host panel on the Activity rail with buttons like **Confirm table**, **Confirm groceries**, **Confirm dessert** — or the chat asking you to confirm a time slot.

**CLICK (in order, one beat each):**

1. **Confirm table** (or type in chat: `confirm table` and hit **Send**)
2. **Confirm groceries** (or type: `confirm groceries` → **Send**)
3. **Confirm dessert** (or type: `confirm dessert` → **Send**)

If the bot asks for a time first:

**TYPE in chat:** `8:00` then **Send**, then say:

**SPEAK:**

> Yes — confirm that slot.

Then click the three Confirm buttons above.

**SPEAK (as you click the last Confirm):**

> And only now — after my explicit confirm — do the write tools fire. Same human-in-the-loop rule we use in production. The model stages. The human spends.

---

# SCENE 4 — Telegram mirror (60 seconds)

**CLICK:** Left sidebar → **Concierge**.

**ARRANGE SCREEN:** Browser (Concierge Ops) on the left half. Telegram Desktop on the right half. Both visible.

**CLICK:** On the dark **QoL timeline** box → button **Agent activity** (not All).

**SPEAK:**

> Now the same agent on my phone. Control tower on the left. Telegram on the right.

**TYPE in Telegram (exact, then send):**

```
order a paneer biryani for dinner
```

**WAIT:** Bot shows typing / “Searching…” edits. Timeline on the left fills with agent tools. Then Telegram shows an approval card with **Approve** and **Reject**.

**CLICK:** Point at the left timeline, then at **Needs your approval** on Ops (same cart).

**SPEAK:**

> Same brain. Same twenty-three Swiggy tools. Mirrored live on the ops timeline. The cart is staged with a real total — but it is not ordered.

**CLICK in Telegram:** the green **Approve** button.

*(If Telegram is slow: on Ops under Needs your approval → green **Approve**.)*

**SPEAK:**

> One tap. Now the write tools run — update cart, place order. Not before.

**WAIT:** Approval clears. Timeline shows the approve / write events.

---

# SCENE 5 — Voice note + Reject (25 seconds)

**CLICK:** In Telegram, hold the **microphone** button.

**SPEAK into the mic (this is the voice note, not narration):**

> Get me milk, bread and eggs from Instamart.

Release the mic.

**WAIT:** Bot replies with the transcript in quotes, then an Instamart approval card.

**SPEAK (to camera):**

> Same pipeline from a voice note. Transcription, planning, cart — and it still stops at the approval gate.

**CLICK in Telegram:** **Reject**.

**SPEAK:**

> I am rejecting this one on purpose. Cart flushed. Nothing ordered. The human is still in charge.

**IF MIC FAILS — TYPE instead:**

```
get me milk bread and eggs from Instamart
```

Then Reject the same way.

---

# SCENE 6 — Calendar push (45 seconds)

**YOU SEE:** Concierge Ops → section **Workflows**.

**CLICK:** **Push calendar event**.

**SPEAK (immediately after click):**

> That button replays the exact payload Google Calendar would push to our webhook — a housewarming tagged hash-host and hash-swiggy. I am not depending on ngrok for this take. The gate, the graph, and the approval are identical to the live path.

**WAIT:** Banner goes to staging, then “Waiting for your Approve”. New card under **Needs your approval**. Telegram may ping too.

**SPEAK:**

> The event is tagged, so the concierge wakes up. It pulls guest diets from the Taste Vault — vegan, lactose intolerant — merges those as hard constraints, and stages Instamart and food that respect them.

**CLICK:** Open the approval card so line items are readable → green **Approve** (Ops or Telegram).

**SPEAK:**

> After I approve, it writes the plan back into the calendar event description — so the group sees what was staged without opening this dashboard.

**IF BUTTON FAILS:** Click **Trigger Zero-Touch Host** instead and say:

> Same staging graph — triggered from ops instead of the calendar payload.

---

# SCENE 7 — Pantry closer (25 seconds)

**CLICK:** Scroll down on Concierge Ops to **Khatam Hone Wala Hai** / pantry list.

**SPEAK:**

> It also learns your Instamart reorder cadence — milk every few days, staples on a longer loop.

**CLICK:** **Refill low items**.

**WAIT:** A new staged approval appears (optional: leave it pending or Reject to keep the end clean).

**SPEAK (closing — one breath):**

> When something is about to run out, it stages a refill — still behind Approve. Honest wrap: today this runs on a mock MCP with synthetic catalog and no real money, but every tool name and field shape matches Swiggy’s official surface — pointing at mcp.swiggy.com is a config flip, not a rewrite. There is no cancel tool in the API, so we never fake a cancel. Bill split is a Nexus extension and we flag it as such. We would love staging access to run this exact demo against the real thing. Thank you, Builders Club.

**CLICK:** Stop recording. End frame = Concierge Ops header chips (Gemini · Telegram live · HITL-gated).

---

# FULL SPEAK TRACK (copy to WhatsApp Notes)

Use this if you only want the words. Do the CLICKs from the scenes above in parallel.

1. *This is Swiggy Nexus. It is not a chatbot. It is an autonomous concierge that orchestrates Food, Instamart, and Dineout through the official Swiggy MCP tool surface. One rule: it can stage anything — but it never spends money until I approve.*

2. *Watch this. One sentence — plan my evening for twelve guests — and Chrono-Host fans out across three Swiggy verticals. Dineout for the table. Instamart for party supplies. Food for dessert. Every chip you see is a real MCP tool call.*

3. *Everything on the right is staged. Nothing is booked. Nothing is checked out. The agent prepared the night — it did not spend.*

4. *And only now — after my explicit confirm — do the write tools fire. Same human-in-the-loop rule we use in production. The model stages. The human spends.*

5. *Now the same agent on my phone. Control tower on the left. Telegram on the right.*

6. *Same brain. Same twenty-three Swiggy tools. Mirrored live on the ops timeline. The cart is staged with a real total — but it is not ordered.*

7. *One tap. Now the write tools run — update cart, place order. Not before.*

8. *Same pipeline from a voice note. Transcription, planning, cart — and it still stops at the approval gate.*

9. *I am rejecting this one on purpose. Cart flushed. Nothing ordered. The human is still in charge.*

10. *That button replays the exact payload Google Calendar would push to our webhook — a housewarming tagged hash-host and hash-swiggy. I am not depending on ngrok for this take. The gate, the graph, and the approval are identical to the live path.*

11. *The event is tagged, so the concierge wakes up. It pulls guest diets from the Taste Vault — vegan, lactose intolerant — merges those as hard constraints, and stages Instamart and food that respect them.*

12. *After I approve, it writes the plan back into the calendar event description — so the group sees what was staged without opening this dashboard.*

13. *It also learns your Instamart reorder cadence — milk every few days, staples on a longer loop.*

14. *When something is about to run out, it stages a refill — still behind Approve. Honest wrap: today this runs on a mock MCP with synthetic catalog and no real money, but every tool name and field shape matches Swiggy’s official surface — pointing at mcp.swiggy.com is a config flip, not a rewrite. There is no cancel tool in the API, so we never fake a cancel. Bill split is a Nexus extension and we flag it as such. We would love staging access to run this exact demo against the real thing. Thank you, Builders Club.*

---

# CLICK CHECKLIST (print / second monitor)

| # | Where | Exact click / type |
|---|--------|-------------------|
| 1 | Chat | Point only |
| 2 | Chat | **Run 60s WOW demo** |
| 3 | Activity | **Confirm table** → **Confirm groceries** → **Confirm dessert** |
| 4 | Sidebar | **Concierge** |
| 5 | Timeline | **Agent activity** |
| 6 | Telegram | type `order a paneer biryani for dinner` → send |
| 7 | Telegram | **Approve** |
| 8 | Telegram | mic: *milk, bread and eggs from Instamart* |
| 9 | Telegram | **Reject** |
| 10 | Ops Workflows | **Push calendar event** |
| 11 | Ops | **Approve** |
| 12 | Pantry | **Refill low items** |
| 13 | — | Stop record |

---

# FORBIDDEN LINES

- “It ordered food” / “It booked the table” **before** Approve/Confirm  
- “This is live Swiggy”  
- “LangGraph” / “SQLite” — say “a workflow with an approval step”
