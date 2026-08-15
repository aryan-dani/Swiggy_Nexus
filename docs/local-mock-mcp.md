# Local mock Swiggy MCP (`/food`, `/im`, `/dineout`)

Offline demo stack. With a live OAuth token and `USE_MOCK_MCP` unset/false, the agent
calls **`https://mcp.swiggy.com/{food|im|dineout}`** instead (see
[`mcp-tool-contract.md`](mcp-tool-contract.md) and [`mcp-live-catalog.json`](mcp-live-catalog.json)).

Local FastAPI still exposes three POST endpoints (JSON-RPC `tools/list` + `tools/call`,
plus legacy `{method, params}`) for offline CI. Fixture replay: `MCP_REPLAY_FIXTURES=1`.

## Run

Terminal 1 (repo root):

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — point the Next.js UI at the Python backend:

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

```bash
npm install --prefix frontend
npm run dev
```

Chat prompts (examples):

| Prompt | Behaviour |
|--------|-----------|
| `Find me good food near me` | Food: `get_addresses` → `search_restaurants` → feed cards |
| `Order a pizza` | Food chain through `get_menu`, `add_to_cart`, `place_order` |
| `Buy milk and groceries` | Instamart search → cart → checkout |
| `Book a table for dinner` | Dineout search → slots → reservation |
| **Chrono-Host** preset + `Plan my evening for 12` | Cross-vertical: Dineout + Instamart + Food dessert (staged) |

Use the **Chrono-Host** button in **Reviewer · Signals & scenarios** on the home page, then prompt: *"Plan my evening — dinner out for 12, then dessert at home around 10."*

Developer Mode in the UI still shows MCP-style JSON payloads per step.

### Console logging

Each tool emits:

- `[TOOL CALL] [<vertical>] …` plus `[ARGS]` / `[RESPONSE]` from handlers (latency 300–800 ms jitter).
- A second `[TOOL CALL] … [inproc]` line from [`backend/mcp_client.py`](../backend/mcp_client.py) (agent caller).

Set **`LOCAL_MCP_HTTP=1`** to force real HTTP POSTs to `LOCAL_MCP_BASE` (default `http://127.0.0.1:8000`). Nested `/api/chat/stream` calling `/food` on one worker can **deadlock**; use `--workers 2` or stick with default **in-process** mode.

### Live `mcp.swiggy.com` (feature-flag)

Keep the mock for demos. To hit production MCP without changing agent code:

1. `python scripts/swiggy_oauth_login.py` (DCR + PKCE; phone OTP in browser)
2. Leave `USE_MOCK_MCP` unset/`false` so a present token selects live (or set `SWIGGY_OAUTH_TOKEN`)
3. `python scripts/swiggy_mcp_tools_list.py` — refresh `docs/mcp-live-catalog.json` (44 tools)
4. `python scripts/swiggy_mcp_smoke.py` / `python scripts/swiggy_mcp_probe.py` — read-only probes
5. Offline/CI: `USE_MOCK_MCP=true` (pytest always forces this)

[`backend/mcp_client.py`](../backend/mcp_client.py) routes to live JSON-RPC when not mocking; canonical names via [`backend/mcp_aliases.py`](../backend/mcp_aliases.py).

---

## HTTP contract

```http
POST /food  |  /im  |  /dineout
Content-Type: application/json

{
  "method": "tool_name",
  "params": { ... }
}
```

Production tool names are **aliased** (e.g. `get_restaurant_menu` → `get_menu`, `update_food_cart` → `add_to_cart`, `search_restaurants_dineout` → `search_restaurants` on Dineout).

Session carts use `requestId` in params (server-side via [`mcp_server/session_store.py`](../mcp_server/session_store.py)).

---

## Tools (expanded mock v2)

**Food:** `get_addresses`, `search_restaurants`, `get_menu` / `get_restaurant_menu`, `add_to_cart` / `update_food_cart`, `get_food_cart`, `flush_food_cart`, `fetch_food_coupons`, `apply_food_coupon`, `place_order` / `place_food_order`, `get_food_orders`, `get_food_order_details`, `track_food_order`, `report_error`

**Instamart:** `get_addresses`, `search_products`, `your_go_to_items`, `add_to_cart` / `update_cart`, `get_cart`, `clear_cart`, `checkout`, `get_orders`, `get_order_details`, `track_order`, `create_address`, `delete_address`, `report_error`

**Dineout:** `get_saved_locations`, `search_restaurants` / `search_restaurants_dineout`, `check_availability` / `get_available_slots`, `book_table`, `get_booking_status`, `create_cart`, `report_error`

Mock data lives in [`mock_data/`](../mock_data/) (12 food restaurants, 40+ Instamart SKUs with `spinId`, 8 Dineout venues, [`events.json`](../mock_data/events.json)).

---

## Tests

```bash
pip install pytest
pytest tests/mock_mcp tests/test_chrono_agent.py -q
```

---

## Layout

| Spec name | Implemented path |
|-----------|-------------------|
| `mcp-server/` | [`mcp_server/`](../mcp_server/) |
| `mock-data/` | [`mock_data/`](../mock_data/) |
| Agent | [`backend/agent.py`](../backend/agent.py) + [`backend/mcp_client.py`](../backend/mcp_client.py) |

See [`swiggy_mcp_docs.md`](../swiggy_mcp_docs.md) for production schema reference and [`docs/swiggy-agent-use-cases.md`](swiggy-agent-use-cases.md) for Chrono-Host design notes.
