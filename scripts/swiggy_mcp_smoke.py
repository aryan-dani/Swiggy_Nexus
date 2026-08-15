"""Live / mock smoke test for Swiggy MCP — read-only get_addresses first.

Usage (repo root):
  # After OAuth (credentials/swiggy_token.json or SWIGGY_OAUTH_TOKEN):
  set USE_MOCK_MCP=false
  python scripts/swiggy_mcp_smoke.py

  # Optional: also try tools/list and a tiny search (still no checkout/book)
  python scripts/swiggy_mcp_smoke.py --search

Never prints full tokens or raw address PII.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")


def _redact_addresses(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        data = {"addresses": data}
    if not isinstance(data, dict):
        return {"type": type(data).__name__, "preview": str(data)[:120]}

    nested = data.get("data") if isinstance(data.get("data"), dict) else None
    addrs = data.get("addresses")
    if addrs is None and nested is not None:
        addrs = nested.get("addresses")

    if addrs is None and "addresses" not in data:
        keys = list(data.keys())
        raw = data.get("raw_text")
        extra: dict[str, Any] = {
            "keys": keys,
            "note": "no addresses key — showing key inventory only",
            "sample_value_types": {k: type(data[k]).__name__ for k in keys[:12]},
        }
        if isinstance(raw, str):
            extra["raw_text_len"] = len(raw)
            # Structure only — never dump street/phone; show whether ID tokens appear.
            extra["raw_text_has_id_marker"] = "(ID:" in raw or "addressId" in raw
            extra["raw_text_snippet_redacted"] = (
                raw[:80].split(":")[0] + ": <REDACTED>" if ":" in raw[:80] else raw[:40] + "…"
            )
        return extra
    if not isinstance(addrs, list):
        return {"addresses_type": type(addrs).__name__}
    redacted = []
    for i, a in enumerate(addrs[:5]):
        if not isinstance(a, dict):
            redacted.append({"index": i, "type": type(a).__name__})
            continue
        aid = a.get("addressId") or a.get("id") or a.get("address_id")
        redacted.append(
            {
                "index": i,
                "id_present": bool(aid),
                "id_len": len(str(aid or "")),
                "fields": sorted(a.keys()),
                "has_lat": any(k in a for k in ("lat", "latitude", "Lat")),
                "has_lng": any(k in a for k in ("lng", "lon", "longitude", "Lng")),
                "city_present": bool(a.get("city") or a.get("cityName")),
                "label_present": bool(a.get("label") or a.get("addressTag")),
                # never print street / phone / name
            }
        )
    out: dict[str, Any] = {"address_count": len(addrs), "sample": redacted}
    if "pagination" in data and isinstance(data["pagination"], dict):
        out["pagination_keys"] = sorted(data["pagination"].keys())
        out["total"] = data.get("total")
    return out


def _first_address_id(data: Any) -> str | None:
    if isinstance(data, list) and data:
        data = {"addresses": data}
    if not isinstance(data, dict):
        return None
    addrs = data.get("addresses")
    if not isinstance(addrs, list) and isinstance(data.get("data"), dict):
        addrs = data["data"].get("addresses")
    if not isinstance(addrs, list) or not addrs:
        return None
    a0 = addrs[0]
    if not isinstance(a0, dict):
        return None
    for k in ("addressId", "id", "address_id"):
        v = a0.get(k)
        if v:
            return str(v)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Swiggy MCP smoke test (read-only)")
    parser.add_argument(
        "--search",
        action="store_true",
        help="After get_addresses, call search_restaurants with first addressId",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force USE_MOCK_MCP=true for this run",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Force USE_MOCK_MCP=false for this run",
    )
    args = parser.parse_args()

    if args.mock and args.live:
        raise SystemExit("Use only one of --mock / --live")
    if args.mock:
        os.environ["USE_MOCK_MCP"] = "true"
    if args.live:
        os.environ["USE_MOCK_MCP"] = "false"

    # Ensure repo root on path
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from backend.mcp_client import LocalMCPError, call_tool, use_mock_mcp

    mode = "MOCK" if use_mock_mcp() else "LIVE"
    print(f"=== Swiggy MCP smoke ({mode}) ===")
    if mode == "LIVE":
        has_env = bool(os.environ.get("SWIGGY_OAUTH_TOKEN", "").strip())
        has_file = Path("credentials/swiggy_token.json").exists()
        print(f"token: env={'set' if has_env else 'missing'} file={'present' if has_file else 'absent'}")
        if not has_env and not has_file:
            print("Blocked: run python scripts/swiggy_oauth_login.py first.")
            raise SystemExit(2)

    try:
        data = call_tool("food", "get_addresses", {})
    except LocalMCPError as e:
        print("get_addresses FAILED:", e.payload)
        raise SystemExit(1) from e
    except Exception as e:  # noqa: BLE001
        print("get_addresses FAILED:", type(e).__name__, str(e)[:300])
        raise SystemExit(1) from e

    print("get_addresses OK — redacted shape:")
    print(json.dumps(_redact_addresses(data), indent=2))

    if args.search:
        addr_id = _first_address_id(data)
        if not addr_id:
            print("search skipped: no addressId in response")
            return
        try:
            sr = call_tool(
                "food",
                "search_restaurants",
                {"addressId": addr_id, "query": "biryani"},
            )
        except LocalMCPError as e:
            print("search_restaurants FAILED:", e.payload)
            raise SystemExit(1) from e
        if isinstance(sr, dict):
            rest = sr.get("restaurants") or []
            print(
                json.dumps(
                    {
                        "restaurants_count": len(rest) if isinstance(rest, list) else None,
                        "keys": sorted(sr.keys()),
                        "first_restaurant_fields": sorted(rest[0].keys())
                        if isinstance(rest, list) and rest and isinstance(rest[0], dict)
                        else None,
                    },
                    indent=2,
                )
            )
        else:
            print("search_restaurants OK type=", type(sr).__name__)

    print("\nNext: Food search -> menu (still read-only); IM your_go_to_items; Dineout get_saved_locations.")
    print("Do not place_food_order / checkout / book_table until read path is green.")


if __name__ == "__main__":
    main()
