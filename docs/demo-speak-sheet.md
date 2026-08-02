# Nexus demo -- phone cue card

Open this on your phone. Speak the quoted lines. Hands do CLICK / VOICE.

---

## MONITORS (3 lines)

1. LEFT = Chrome fullscreen `http://127.0.0.1:3000` -- camera sees THIS only.
2. RIGHT = Telegram (Desktop or phone in hand) -- off-camera until Beat 2.
3. Ignore phone notes / this sheet on camera. Beat 1 = Chat. Beat 2 = Concierge.

---

## BEAT 1 -- Web WOW (~90s)

Telegram stays silent. Do not touch the bot chat.

CLICK: Chat hero purple card **"Run 60s WOW demo"**
(Do NOT type. Do NOT open Concierge / Settings / other scenario cards.)

SPEAK (before click):
"This is Swiggy Nexus. One agent across dine-out, Instamart, and food -- staged until I confirm."

SPEAK (on click):
"Watch this."

WAIT: Demo Director + tool chips. Activity becomes Chrono-Host bundle.

SPEAK (while tools run):
"One sentence -- plan my evening -- and Chrono-Host fans out across three Swiggy verticals. Dineout for the table. Instamart for party supplies. Food for dessert. Every chip you see is a real MCP tool call."

SPEAK (point at Activity rail):
"Everything on the right is staged. Nothing is booked. Nothing is checked out."

CLICK: **"Confirm table"**
CLICK: **"Confirm groceries"**
CLICK: **"Confirm dessert"**

SPEAK (on last Confirm):
"And only now -- after my explicit confirm -- do the write tools fire. The model stages. The human spends."

---

## BEAT 2 -- Telegram voice (~60-90s)

CLICK (LEFT): Sidebar **"Concierge"** -> **"Agent activity"**

SPEAK (to camera):
"Same brain on my phone. One natural sentence -- voice, not a slash command -- and Night Out stages Calendar, a table, and an equal bill split."

VOICE (Telegram mic -- hold, say clearly, release):
"Plan a night out with friends this Saturday -- dinner then drinks, then split the bill"

WAIT: transcript -> Planning... -> **Approve** / **Reject** buttons. Ops timeline updates.

SPEAK:
"Night Out is the full social loop -- Taste Vault guests, preferred venue, Calendar invite, table booking on the mock MCP, equal UPI split. Still waiting on my Approve."

CLICK: Telegram **Approve**

WAIT: success edit + Ops receipt (Calendar / Maps / UPI).

SPEAK (close):
"One approve -- Calendar for the group, Maps for the cab, equal split so nobody chases Venmo. Demo UPI handles -- no real collection -- but the math and the links are real. Thank you."

Stop recording. End on LEFT Ops receipt.

---

## PANIC (one-liners)

- WOW failed -> New Chat -> Run 60s WOW demo again.
- Telegram Thinking stuck -> do not re-spam mic; type the Night Out sentence once.
- No Approve buttons -> wait 5s; type sentence once more; check Ops pending.
- Wrong tab -> Beat 1 = Chat. Beat 2 = Concierge.
- Leftover HITL -> Concierge Reject pending -> New Chat.
- Said "ordered" too early -> say "Staged until Approve" and keep going.
- Mic fail -> TYPE the Night Out sentence (no slash) -> Approve.

---

Optional PC teleprompter: `.\run-demo-record.ps1` (not required if you use this sheet).
Full dual-monitor runbook: `docs/demo-script.md`
