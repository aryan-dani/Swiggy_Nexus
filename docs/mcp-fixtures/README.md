# MCP fixtures (redacted live captures)

Captured by `python scripts/swiggy_mcp_probe.py` with `USE_MOCK_MCP=false`.

- PII (street, phone) is redacted.
- IDs are replaced with `<id:len>` markers — shapes match live `structuredContent`.
- Used for offline replay when `MCP_REPLAY_FIXTURES=1` and for unit tests.

Authoritative tool inventory: [`../mcp-live-catalog.json`](../mcp-live-catalog.json).
Probe log: [`../mcp-probe-log.md`](../mcp-probe-log.md).
