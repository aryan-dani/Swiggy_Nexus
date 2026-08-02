# Swiggy Nexus — PERFECT dual-monitor runbook (2 beats · ~2–3 min)

**Phone cue card (primary while recording):** open [`docs/demo-speak-sheet.md`](demo-speak-sheet.md) on your phone — SPEAK lines, clicks, Beat 1 then Beat 2, panic one-liners. No PowerShell required.

**This section is the full dual-monitor runbook.** SPEAK out loud. Hands do CLICK / VOICE. Pause on WAIT.  
Never say “ordered” or “booked” until after you tap **Approve** / **Confirm**.

---

## BEFORE YOU START (once)

### 1. Restart the stack

```powershell
cd C:\Users\dania\Documents\Stuff\My_Repositories\Domain_Based\Agentic_AI\Swiggy_Nexus
.\stop-local.ps1
.\start-local.ps1
```

**URLs (must match):**

| What | URL |
|------|-----|
| UI (browser) | http://127.0.0.1:3000 |
| API | http://127.0.0.1:8000 |
| Health check | http://127.0.0.1:8000/health |

Or manually: API on `:8000` **without** `--reload`, UI on `:3000`.

**LLM note:** `backend/.env` → `LLM_PROVIDER=ollama` + `OLLAMA_MODEL=qwen2.5:7b-instruct` for local Qwen. Beat 2 Night Out is **deterministic** (no LLM). Voice **transcription** still uses Groq Whisper (or Gemini fallback).

### 2. Preflight (PASS all lines)

```powershell
.\backend\.venv\Scripts\python.exe scripts\demo_preflight.py
```

### 3. Telegram

1. Open **Telegram Desktop** (or phone in hand).
2. Open chat with **Swiggy Nexus** / `@SwiggyNexusbot`.
3. Leave that chat on screen — do not scroll away mid-demo.

### 4. Clear leftovers

1. Browser → http://127.0.0.1:3000
2. Sidebar: **Developer mode OFF**
3. Stay on **Chat** (left column + Activity rail on the right)
4. Hard refresh once: **Ctrl+Shift+R**
5. If Activity / Ops shows leftover pending HITLs: sidebar → **Concierge** → **Reject** any pending, then return to **Chat** (or **New Chat**)
6. Optional hard reset:

```powershell
curl.exe -X POST http://127.0.0.1:8000/internal/demo/reset -H "X-Nexus-Tick-Secret: nexus-tick-secret"
```

### 5. Cue card / teleprompter (RIGHT monitor)

**Primary:** open [`docs/demo-speak-sheet.md`](demo-speak-sheet.md) on your phone (or a notes app). That is the live script.

Optional PC teleprompter from repo root (API+UI already up):

```powershell
.\run-demo-record.ps1
.\run-demo-record.ps1 -SkipPreflight    # skip demo_preflight.py
.\run-demo-record.ps1 -ListOnly         # print step outline
.\run-demo-record.ps1 -Scene 2          # jump to Telegram Night Out
```

Stage 0 cold open waits until camera + both monitors are ready. Then one step card at a time (CLICK + SPEAK on the same screen). Press Enter to advance; Confirm/Approve steps never auto-advance. Jump to Beat 2 with `-Scene 2` if needed.

### 6. Optional: real Google Calendar (stronger Night Out)

```powershell
.\backend\.venv\Scripts\python.exe scripts\google_auth_setup.py
```

---

## MONITOR MAP (physical layout)

```
 LEFT (audience / camera)              RIGHT (YOU only)
 ┌─────────────────────────────┐      ┌─────────────────────────────┐
 │ Chrome/Edge WINDOW 1        │      │ Phone cue card              │
 │ FULLSCREEN F11              │      │ (docs/demo-speak-sheet.md)  │
 │ http://127.0.0.1:3000       │      │                             │
 │ Chat + Activity rail        │      │ Telegram Desktop            │
 │ (exactly what camera sees)  │      │ → Swiggy Nexus bot chat     │
 │                             │      │   (or phone in hand)        │
 │ Beat 1: stay on Chat        │      │                             │
 │ Beat 2: switch to Concierge │      │ OPTIONAL: 2nd browser       │
 │         Ops (same window)   │      │ window → Concierge Ops      │
 └─────────────────────────────┘      │ if you Approve on web       │
                                      └─────────────────────────────┘
```

### Window placement (do this before record)

| # | Window | Goes on | Exact content |
|---|--------|---------|---------------|
| 1 | Chrome/Edge **window 1** | **LEFT** fullscreen | Nexus app → **Chat** tab. Chat column left, **Activity** rail right. Camera records THIS only. |
| 2 | Phone speak sheet | **RIGHT** / in hand | [`docs/demo-speak-sheet.md`](demo-speak-sheet.md) — read SPEAK lines from here. (Optional: `.\run-demo-record.ps1`.) |
| 3 | Telegram Desktop | **RIGHT** | Chat with Swiggy Nexus. (Phone OK as alt — keep it off-camera or briefly show mic.) |
| 4 | Optional: 2nd browser window | **RIGHT** | Same UI → **Concierge** Ops — only if you Approve/Reject on web instead of Telegram. Primary path = Approve **in Telegram**. |

**Rule:** Audience never sees teleprompter, Telegram UI chrome, or your notes. LEFT = product only.

---

## BEAT-BY-BEAT CLICK CHOREOGRAPHY

### BEAT 1 — Web · 60s WOW / Chrono-Host + Confirm (~90s)

Teleprompter steps: Intro → Click WOW → Tools fan out → Staged/not spent → Confirm table → Confirm groceries → Confirm dessert + close.

| Cue | Do this |
|-----|---------|
| **EYES** | LEFT monitor — Chat hero + empty Activity rail. |
| **SEE** | Big purple card **Run 60s WOW demo**. Activity header says Activity / empty. |
| **SPEAK** (intro — before WOW click) | *This is Swiggy Nexus. One agent across dine-out, Instamart, and food — staged until I confirm.* |
| **CLICK** | **Run 60s WOW demo** (Chat hero purple card). Short beat: *Watch this.* |
| **NOT** | Do **not** type into Ask Nexus. Do **not** click Deadlock / Flow-state / Concierge Ops cards. Do **not** open Settings. |
| **WAIT** | Demo Director / tool chips under chat. Activity fills. Right rail becomes **Chrono-Host bundle** (not “ran out of tool steps”). |
| **SPEAK** (while tools run) | *One sentence — plan my evening — and Chrono-Host fans out across three Swiggy verticals. Dineout for the table. Instamart for party supplies. Food for dessert. Every chip you see is a real MCP tool call.* |
| **POINT** | RIGHT side of LEFT monitor = Activity / Chrono-Host bundle. |
| **SPEAK** | *Everything on the right is staged. Nothing is booked. Nothing is checked out.* |
| **CLICK** | **Confirm table** (own step — ENTER only after you click). |
| **CLICK** | **Confirm groceries** (own step). |
| **CLICK** | **Confirm dessert** (own step). |
| **IF time asked** | Type `8:00` → Send, then resume Confirm order. |
| **SPEAK** (on last Confirm) | *And only now — after my explicit confirm — do the write tools fire. The model stages. The human spends.* |
| **SUCCESS** | Confirms accepted; write tools fire after your clicks; no panic if chips keep updating briefly. |
| **FAIL** | Sidebar **New Chat** → click **Run 60s WOW demo** again. |

---

### BEAT 2 — Telegram voice · Night Out NL (~60–90s)

Teleprompter steps: Concierge → Bridge speak → Telegram VOICE → Wait Approve → Approve → Receipt + bow.

| Cue | Do this |
|-----|---------|
| **EYES** | Glance RIGHT for teleprompter line, then LEFT for Ops; mic hand on Telegram (RIGHT / phone). |
| **CLICK (LEFT)** | Sidebar → **Concierge**. Timeline → **Agent activity**. Leave this on LEFT so camera sees Ops while you talk. |
| **NOT** | Do **not** run the Night out wizard / `/nightout` multi-tap path. Do **not** type a slash command in Telegram. Do **not** spam the mic. |
| **SPEAK to camera** | *Same brain on my phone. One natural sentence — voice, not a slash command — and Night Out stages Calendar, a table, and an equal bill split.* |
| **VOICE** | Telegram mic → **hold** → say clearly → **release**: |
| | `Plan a night out with friends this Saturday — dinner then drinks, then split the bill` |
| **WAIT** | Transcript appears → “Planning night out…” → staged card with **✅ Approve** / **❌ Reject**. Ops timeline updates. **Not** stuck on “Thinking…”. |
| **SPEAK** | *Night Out is the full social loop — Taste Vault guests, preferred venue, Calendar invite, table booking on the mock MCP, equal UPI split. Still waiting on my Approve.* |
| **CLICK** | Telegram → **✅ Approve** (primary). Alt: RIGHT browser Ops → green **Approve**. ENTER only after you click. |
| **WAIT** | Success edit in Telegram · Ops shows **night_out_receipt** (Calendar · Maps · UPI shares). |
| **SPEAK (close)** | *One approve — Calendar for the group, Maps for the cab, equal split so nobody chases Venmo. Demo UPI handles — no real collection — but the math and the links are real. Thank you.* |
| **CLICK** | Stop recording. End frame = LEFT Ops header + night-out receipt. |
| **MIC FAIL** | **TYPE** the same sentence (no slash) → **Approve**. |
| **TRANSCRIPT DRIFT** | Close paraphrases OK if they include “night out” + friends/dinner/split. Worst case: type the exact line. |

---

## PANIC RECOVERY (1-liners)

| Problem | Fix |
|---------|-----|
| WOW failed / tool-steps error | **New Chat** → **Run 60s WOW demo** again. Do not type the prompt. |
| Telegram stuck on Thinking | Do **not** re-spam mic. Check API `:8000` still up. Or **type** the Night Out sentence once. |
| No Approve buttons | Wait 5s; if still none, type the sentence once more (one message). Check Ops pending HITL. |
| Wrong monitor / camera sees notes | Camera = LEFT only. Move teleprompter + Telegram to RIGHT. |
| Wrong tab on LEFT | Beat 1 = **Chat**. Beat 2 = **Concierge**. Not Library / Analytics / Archive. |
| Leftover HITL blocking | Concierge → **Reject** pending → **New Chat** → restart Beat. |
| Stack dead | `.\start-local.ps1` again; confirm `:3000` + `:8000/health`. |
| Said “ordered” too early | Correct on camera: *Staged until Approve.* Keep going. |

---

## FULL SPEAK TRACK

**Use [`docs/demo-speak-sheet.md`](demo-speak-sheet.md) on your phone** — that file is the cue card. Summary below:

1. *This is Swiggy Nexus. One agent across dine-out, Instamart, and food — staged until I confirm.* (before WOW click)

2. *Watch this.* (on WOW click) then while tools run: *One sentence — plan my evening — and Chrono-Host fans out across three Swiggy verticals. Dineout for the table. Instamart for party supplies. Food for dessert. Every chip you see is a real MCP tool call.*

3. *Everything on the right is staged. Nothing is booked. Nothing is checked out.*

4. *And only now — after my explicit confirm — do the write tools fire. The model stages. The human spends.*

5. *Same brain on my phone. One natural sentence — voice, not a slash command — and Night Out stages Calendar, a table, and an equal bill split.*

6. *Night Out is the full social loop — Taste Vault guests, preferred venue, Calendar invite, table booking on the mock MCP, equal UPI split. Still waiting on my Approve.*

7. *One approve — Calendar for the group, Maps for the cab, equal split so nobody chases Venmo. Demo UPI handles — no real collection — but the math and the links are real. Thank you.*

---

## CLICK CHECKLIST (RIGHT monitor / teleprompter)

| # | Where | Exact action |
|---|--------|----------------|
| 0 | LEFT Chat | Point + intro speak (do **not** click WOW yet) |
| 1 | LEFT Chat | **Run 60s WOW demo** |
| 2 | LEFT Activity | **Confirm table** |
| 3 | LEFT Activity | **Confirm groceries** |
| 4 | LEFT Activity | **Confirm dessert** |
| 5 | LEFT Sidebar | **Concierge** · **Agent activity** |
| 6 | RIGHT Telegram | **Voice:** Night Out sentence (or type it) |
| 7 | RIGHT Telegram | **✅ Approve** |
| 8 | LEFT Ops | Skim Calendar · Maps · UPI on receipt (optional) |
| 9 | — | Stop record |

---

## FEATURE COVERAGE MAP

| Feature | Beat |
|---------|------|
| 60s Chrono-Host / 3 verticals | 1 |
| HITL confirm before spend | 1 |
| Telegram voice → NL Night Out | 2 |
| Calendar + Maps + equal split | 2 |
| HITL Approve on Night Out | 2 |

---

## OPTIONAL APPENDIX (not on the primary record path)

Use only if you have extra time after the two beats:

- Telegram text food order + Approve (`order a paneer biryani for dinner`)
- Voice Instamart + Reject (`Get me milk, bread and eggs from Instamart`)
- Ops **Night out** wizard (`/nightout`) for the multi-tap guest → venue → slot walk
- **Push calendar event** webhook replay
- Pantry **Refill low items**

---

## FORBIDDEN LINES

- “It ordered / booked” **before** Approve/Confirm  
- “This is live Swiggy production”  
- “LangGraph / SQLite” — say “a workflow with an approval step”  
- Promising real UPI collection (say “demo handles”)
