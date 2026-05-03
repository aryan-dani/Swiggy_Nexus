# Local mock Swiggy MCP (`/food`, `/im`, `/dineout`)

Offline demo stack — **no** calls to `mcp.swiggy.com`. The FastAPI app exposes three POST endpoints plus the existing SSE chat routes.

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

Developer Mode in the UI still shows MCP-style JSON payloads per step.

### Console logging

Each tool emits:

- `[TOOL CALL] [<vertical>] …` plus `[ARGS]` / `[RESPONSE]` from handlers (latency 300–800 ms jitter).
- A second `[TOOL CALL] … [inproc]` line from [`backend/mcp_client.py`](../backend/mcp_client.py) (agent caller).

Set **`LOCAL_MCP_HTTP=1`** to force real HTTP POSTs to `LOCAL_MCP_BASE` (default `http://127.0.0.1:8000`). Nested `/api/chat/stream` calling `/food` on one worker can **deadlock**; use `--workers 2` or stick with default **in-process** mode.

Windows:

```powershell
$env:LOCAL_MCP_HTTP = "1"
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 2
```

Default (**in-process**) avoids that deadlock entirely.

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

Success:

```json
{ "success": true, "data": { ... } }
```

Failure:

```json
{ "success": false, "error": { "code": "VALIDATION", "message": "..." } }
```

---

## Example curl calls

Food — addresses:

```bash
curl -s -X POST http://127.0.0.1:8000/food \
  -H "Content-Type: application/json" \
  -d "{\"method\":\"get_addresses\",\"params\":{}}"
```

Food — restaurants (use an `addressId` from the prior response):

```bash
curl -s -X POST http://127.0.0.1:8000/food \
  -H "Content-Type: application/json" \
  -d "{\"method\":\"search_restaurants\",\"params\":{\"addressId\":\"addr_kp_001\"}}"
```

Instamart:

```bash
curl -s -X POST http://127.0.0.1:8000/im \
  -H "Content-Type: application/json" \
  -d "{\"method\":\"search_products\",\"params\":{\"query\":\"milk\"}}"
```

Dineout:

```bash
curl -s -X POST http://127.0.0.1:8000/dineout \
  -H "Content-Type: application/json" \
  -d "{\"method\":\"search_restaurants\",\"params\":{}}"
```

---

## Layout vs original spec

| Spec name | Implemented path |
|-----------|-------------------|
| `mcp-server/` | [`mcp_server/`](../mcp_server/) |
| `mock-data/` | [`mock_data/`](../mock_data/) |
| Agent | [`backend/agent.py`](../backend/agent.py) + [`backend/mcp_client.py`](../backend/mcp_client.py) |

**Tools:**

- Food: `get_addresses`, `search_restaurants`, `get_menu`, `add_to_cart`, `place_order`
- Instamart: `search_products`, `add_to_cart`, `checkout`
- Dineout: `search_restaurants`, `check_availability`, `book_table`
