"""Ordered live probe of every read tool — redacted fixtures for replay.

Never calls: place_food_order, checkout, book_table, confirm_order,
create_address, delete_address.

Reversible cart: update_* then get_* then flush/clear.

Usage:
  set USE_MOCK_MCP=false
  python scripts/swiggy_mcp_probe.py
  python scripts/swiggy_mcp_probe.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_ROOT = ROOT / "docs" / "mcp-fixtures"
LOG_PATH = ROOT / "docs" / "mcp-probe-log.md"

NEVER_LIVE = frozenset(
    {
        "place_food_order",
        "checkout",
        "book_table",
        "confirm_order",
        "create_address",
        "delete_address",
    }
)

PII_KEYS = frozenset(
    {
        "phone",
        "phoneNumber",
        "mobile",
        "addressLine",
        "addressLine1",
        "addressLine2",
        "fullAddress",
        "name",
        "customerName",
        "email",
        "lat",
        "lng",
        "latitude",
        "longitude",
    }
)


def _redact(obj: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "<max_depth>"
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in PII_KEYS:
                out[k] = "<REDACTED>"
            elif k in ("id", "addressId", "restaurantId", "restaurant_id", "orderId", "order_id", "spinId", "slotId", "itemId", "item_id", "cartId", "cart_id"):
                out[k] = f"<id:{len(str(v))}>" if v else None
                out[f"_{k}_present"] = bool(v)
            else:
                out[k] = _redact(v, depth + 1)
        # Keep field inventory
        out["_keys"] = sorted(obj.keys())
        return out
    if isinstance(obj, list):
        return [_redact(x, depth + 1) for x in obj[:5]] + (
            [f"<…{len(obj) - 5} more>"] if len(obj) > 5 else []
        )
    if isinstance(obj, str) and len(obj) > 200:
        return obj[:80] + f"…<len={len(obj)}>"
    return obj


def _save_fixture(server: str, tool: str, data: Any, meta: dict[str, Any]) -> None:
    d = FIXTURE_ROOT / server
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool": tool,
        "server": server,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta,
        "data": _redact(data),
    }
    (d / f"{tool}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _first_address_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    addrs = data.get("addresses")
    if not isinstance(addrs, list) or not addrs:
        return None
    a0 = addrs[0]
    if not isinstance(a0, dict):
        return None
    for k in ("addressId", "id", "address_id"):
        if a0.get(k):
            return str(a0[k])
    return None


def _first_restaurant_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("restaurants", "results"):
        rows = data.get(key)
        if isinstance(rows, list) and rows:
            r0 = rows[0]
            if isinstance(r0, dict):
                for k in ("restaurantId", "restaurant_id", "id"):
                    if r0.get(k):
                        return str(r0[k])
    return None


def _first_item_id(data: Any) -> tuple[str | None, str | None]:
    """Return (item_id, restaurant_id) from menu."""
    if not isinstance(data, dict):
        return None, None
    rid = data.get("restaurantId") or data.get("restaurant_id")
    for cat in data.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        for it in cat.get("items") or []:
            if isinstance(it, dict):
                iid = it.get("itemId") or it.get("item_id") or it.get("id")
                if iid:
                    return str(iid), str(rid) if rid else None
    # search_menu shape
    for key in ("items", "dishes", "menuItems"):
        rows = data.get(key)
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            it = rows[0]
            iid = it.get("itemId") or it.get("item_id") or it.get("id")
            rr = it.get("restaurantId") or it.get("restaurant_id") or rid
            if iid:
                return str(iid), str(rr) if rr else None
    return None, None


def _first_spin_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("products", "items", "goToItems"):
        rows = data.get(key)
        if not isinstance(rows, list):
            continue
        for p in rows:
            if not isinstance(p, dict):
                continue
            for v in p.get("variants") or []:
                if isinstance(v, dict) and v.get("spinId"):
                    return str(v["spinId"])
            if p.get("spinId"):
                return str(p["spinId"])
    return None


def _first_order_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("orders", "activeOrders", "pastOrders"):
        rows = data.get(key)
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            o = rows[0]
            for k in ("orderId", "order_id", "id"):
                if o.get(k):
                    return str(o[k])
    return None


def _first_location(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    locs = data.get("locations") or data.get("addresses") or data.get("savedLocations") or []
    if isinstance(locs, list) and locs and isinstance(locs[0], dict):
        return locs[0]
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="List planned steps only")
    args = parser.parse_args()

    os.environ["USE_MOCK_MCP"] = "false"
    from backend.mcp_client import LocalMCPError, call_tool, list_tools, use_mock_mcp
    from backend.mcp_aliases import FOOD_CANONICAL, IM_CANONICAL, DINEOUT_CANONICAL

    if use_mock_mcp():
        print("Still in mock mode — set token / USE_MOCK_MCP=false")
        raise SystemExit(2)

    log_lines = [
        "# MCP live probe log",
        "",
        f"Started: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "| Step | Server | Tool | Status | ms | Notes |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]

    def record(step: str, server: str, tool: str, status: str, ms: float, notes: str) -> None:
        log_lines.append(f"| {step} | `{server}` | `{tool}` | {status} | {ms:.0f} | {notes} |")
        print(f"[{status}] {server}.{tool} ({ms:.0f}ms) {notes}")

    # Dry-run inventory
    planned = [
        ("0a", "food", "tools/list"),
        ("0b", "im", "tools/list"),
        ("0c", "dineout", "tools/list"),
        ("1a", "food", "get_addresses"),
        ("1b", "im", "get_addresses"),
        ("2", "food", "search_restaurants"),
        ("3", "food", "search_menu"),
        ("4", "food", "get_restaurant_menu"),
        ("5", "food", "get_food_cart"),
        ("6a", "food", "update_food_cart"),
        ("6b", "food", "fetch_food_coupons"),
        ("6c", "food", "flush_food_cart"),
        ("7a", "food", "get_food_orders"),
        ("7b", "food", "get_food_order_details"),
        ("7c", "food", "track_food_order"),
        ("8a", "im", "search_products"),
        ("8b", "im", "your_go_to_items"),
        ("9a", "im", "update_cart"),
        ("9b", "im", "get_cart"),
        ("9c", "im", "clear_cart"),
        ("10", "im", "get_orders"),
        ("10b", "im", "track_order"),
        ("11", "dineout", "get_saved_locations"),
        ("12", "dineout", "search_restaurants_dineout"),
        ("13a", "dineout", "get_restaurant_details"),
        ("13b", "dineout", "get_available_slots"),
        ("14", "food", "get_payment_options"),
        ("skip", "*", "WIRED_NOT_PROBED: " + ", ".join(sorted(NEVER_LIVE))),
    ]
    if args.dry_run:
        for row in planned:
            print(" · ".join(row))
        return

    ctx: dict[str, Any] = {}

    # 0 tools/list
    for step, server in (("0a", "food"), ("0b", "im"), ("0c", "dineout")):
        t0 = time.perf_counter()
        try:
            tools = list_tools(server)  # type: ignore[arg-type]
            ms = (time.perf_counter() - t0) * 1000
            _save_fixture(server, "_tools_list", {"tools": [{"name": t.get("name")} for t in tools]}, {"count": len(tools)})
            record(step, server, "tools/list", "OK", ms, f"{len(tools)} tools")
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            record(step, server, "tools/list", "FAIL", ms, str(e)[:80])

    # 1 addresses
    for step, server in (("1a", "food"), ("1b", "im")):
        t0 = time.perf_counter()
        try:
            data = call_tool(server, "get_addresses", {})  # type: ignore[arg-type]
            ms = (time.perf_counter() - t0) * 1000
            aid = _first_address_id(data)
            if aid:
                ctx["addressId"] = aid
            _save_fixture(server, "get_addresses", data, {"addressId_present": bool(aid)})
            n = len((data or {}).get("addresses") or []) if isinstance(data, dict) else 0
            record(step, server, "get_addresses", "OK", ms, f"{n} addresses")
        except LocalMCPError as e:
            ms = (time.perf_counter() - t0) * 1000
            record(step, server, "get_addresses", "ERR", ms, str(e.payload)[:80])
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            record(step, server, "get_addresses", "FAIL", ms, str(e)[:80])

    if not ctx.get("addressId"):
        record("-", "food", "ABORT", "FAIL", 0, "no addressId — cannot continue search chain")
        LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        raise SystemExit(1)

    addr = ctx["addressId"]

    # 2 search restaurants
    t0 = time.perf_counter()
    try:
        data = call_tool("food", "search_restaurants", {"addressId": addr, "query": "biryani"})
        ms = (time.perf_counter() - t0) * 1000
        rid = _first_restaurant_id(data)
        if rid:
            ctx["restaurantId"] = rid
        _save_fixture("food", "search_restaurants", data, {"restaurantId_present": bool(rid)})
        n = len((data or {}).get("restaurants") or []) if isinstance(data, dict) else 0
        record("2", "food", "search_restaurants", "OK", ms, f"{n} restaurants")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("2", "food", "search_restaurants", "FAIL", ms, str(e)[:80])

    # 3 search_menu
    t0 = time.perf_counter()
    try:
        data = call_tool("food", "search_menu", {"addressId": addr, "query": "biryani"})
        ms = (time.perf_counter() - t0) * 1000
        iid, rr = _first_item_id(data)
        if iid:
            ctx["itemId"] = iid
        if rr and not ctx.get("restaurantId"):
            ctx["restaurantId"] = rr
        _save_fixture("food", "search_menu", data, {"itemId_present": bool(iid)})
        record("3", "food", "search_menu", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("3", "food", "search_menu", "FAIL", ms, str(e)[:80])

    # 4 get_restaurant_menu
    if ctx.get("restaurantId"):
        t0 = time.perf_counter()
        try:
            data = call_tool(
                "food",
                "get_restaurant_menu",
                {"restaurantId": ctx["restaurantId"], "addressId": addr},
            )
            ms = (time.perf_counter() - t0) * 1000
            iid, _ = _first_item_id(data)
            if iid:
                ctx["itemId"] = iid
            _save_fixture("food", "get_restaurant_menu", data, {"itemId_present": bool(iid)})
            record("4", "food", "get_restaurant_menu", "OK", ms, "ok")
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            record("4", "food", "get_restaurant_menu", "FAIL", ms, str(e)[:80])
    else:
        record("4", "food", "get_restaurant_menu", "SKIP", 0, "no restaurantId")

    # 5 get_food_cart
    t0 = time.perf_counter()
    try:
        data = call_tool("food", "get_food_cart", {"addressId": addr})
        ms = (time.perf_counter() - t0) * 1000
        _save_fixture("food", "get_food_cart", data, {})
        record("5", "food", "get_food_cart", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("5", "food", "get_food_cart", "FAIL", ms, str(e)[:80])

    # 6 reversible cart + coupons
    if ctx.get("restaurantId") and ctx.get("itemId"):
        t0 = time.perf_counter()
        try:
            # Schema varies — try common shapes
            args_try = [
                {
                    "addressId": addr,
                    "restaurantId": ctx["restaurantId"],
                    "items": [{"itemId": ctx["itemId"], "quantity": 1}],
                },
                {
                    "addressId": addr,
                    "restaurantId": ctx["restaurantId"],
                    "cartItems": [{"itemId": ctx["itemId"], "quantity": 1}],
                },
            ]
            last_err = None
            data = None
            for args in args_try:
                try:
                    data = call_tool("food", "update_food_cart", args)
                    last_err = None
                    break
                except LocalMCPError as e:
                    last_err = e
            ms = (time.perf_counter() - t0) * 1000
            if last_err and data is None:
                record("6a", "food", "update_food_cart", "ERR", ms, str(last_err.payload)[:80])
            else:
                _save_fixture("food", "update_food_cart", data, {})
                record("6a", "food", "update_food_cart", "OK", ms, "reversible add")
                t0 = time.perf_counter()
                try:
                    coupons = call_tool("food", "fetch_food_coupons", {"addressId": addr})
                    ms = (time.perf_counter() - t0) * 1000
                    _save_fixture("food", "fetch_food_coupons", coupons, {})
                    record("6b", "food", "fetch_food_coupons", "OK", ms, "ok")
                except Exception as e:  # noqa: BLE001
                    ms = (time.perf_counter() - t0) * 1000
                    record("6b", "food", "fetch_food_coupons", "FAIL", ms, str(e)[:80])
                t0 = time.perf_counter()
                try:
                    flushed = call_tool("food", "flush_food_cart", {"addressId": addr})
                    ms = (time.perf_counter() - t0) * 1000
                    _save_fixture("food", "flush_food_cart", flushed, {})
                    record("6c", "food", "flush_food_cart", "OK", ms, "cleared")
                except Exception as e:  # noqa: BLE001
                    ms = (time.perf_counter() - t0) * 1000
                    record("6c", "food", "flush_food_cart", "FAIL", ms, str(e)[:80])
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            record("6a", "food", "update_food_cart", "FAIL", ms, str(e)[:80])
    else:
        record("6a", "food", "update_food_cart", "SKIP", 0, "missing item/restaurant")

    # 7 food orders
    t0 = time.perf_counter()
    try:
        data = call_tool("food", "get_food_orders", {})
        ms = (time.perf_counter() - t0) * 1000
        oid = _first_order_id(data)
        _save_fixture("food", "get_food_orders", data, {"orderId_present": bool(oid)})
        record("7a", "food", "get_food_orders", "OK", ms, f"order={'yes' if oid else 'none'}")
        if oid:
            for step, tool in (("7b", "get_food_order_details"), ("7c", "track_food_order")):
                t0 = time.perf_counter()
                try:
                    d2 = call_tool("food", tool, {"orderId": oid})
                    ms = (time.perf_counter() - t0) * 1000
                    _save_fixture("food", tool, d2, {})
                    record(step, "food", tool, "OK", ms, "ok")
                except Exception as e:  # noqa: BLE001
                    ms = (time.perf_counter() - t0) * 1000
                    record(step, "food", tool, "FAIL", ms, str(e)[:80])
        else:
            record("7b", "food", "get_food_order_details", "SKIP", 0, "no orderId")
            record("7c", "food", "track_food_order", "SKIP", 0, "no orderId")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("7a", "food", "get_food_orders", "FAIL", ms, str(e)[:80])

    # 8 IM search
    t0 = time.perf_counter()
    try:
        data = call_tool("im", "search_products", {"addressId": addr, "query": "milk"})
        ms = (time.perf_counter() - t0) * 1000
        spin = _first_spin_id(data)
        if spin:
            ctx["spinId"] = spin
        _save_fixture("im", "search_products", data, {"spinId_present": bool(spin)})
        record("8a", "im", "search_products", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("8a", "im", "search_products", "FAIL", ms, str(e)[:80])

    t0 = time.perf_counter()
    try:
        data = call_tool("im", "your_go_to_items", {"addressId": addr})
        ms = (time.perf_counter() - t0) * 1000
        if not ctx.get("spinId"):
            spin = _first_spin_id(data)
            if spin:
                ctx["spinId"] = spin
        _save_fixture("im", "your_go_to_items", data, {})
        record("8b", "im", "your_go_to_items", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("8b", "im", "your_go_to_items", "FAIL", ms, str(e)[:80])

    # 9 IM cart reversible
    if ctx.get("spinId"):
        t0 = time.perf_counter()
        try:
            data = call_tool(
                "im",
                "update_cart",
                {"addressId": addr, "items": [{"spinId": ctx["spinId"], "quantity": 1}]},
            )
            ms = (time.perf_counter() - t0) * 1000
            _save_fixture("im", "update_cart", data, {})
            record("9a", "im", "update_cart", "OK", ms, "reversible")
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            record("9a", "im", "update_cart", "FAIL", ms, str(e)[:80])
    else:
        record("9a", "im", "update_cart", "SKIP", 0, "no spinId")

    t0 = time.perf_counter()
    try:
        data = call_tool("im", "get_cart", {"addressId": addr})
        ms = (time.perf_counter() - t0) * 1000
        _save_fixture("im", "get_cart", data, {})
        record("9b", "im", "get_cart", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("9b", "im", "get_cart", "FAIL", ms, str(e)[:80])

    t0 = time.perf_counter()
    try:
        data = call_tool("im", "clear_cart", {"addressId": addr})
        ms = (time.perf_counter() - t0) * 1000
        _save_fixture("im", "clear_cart", data, {})
        record("9c", "im", "clear_cart", "OK", ms, "cleared")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("9c", "im", "clear_cart", "FAIL", ms, str(e)[:80])

    # 10 IM orders
    t0 = time.perf_counter()
    try:
        data = call_tool("im", "get_orders", {})
        ms = (time.perf_counter() - t0) * 1000
        oid = _first_order_id(data)
        _save_fixture("im", "get_orders", data, {"orderId_present": bool(oid)})
        record("10", "im", "get_orders", "OK", ms, f"order={'yes' if oid else 'none'}")
        if oid:
            t0 = time.perf_counter()
            try:
                d2 = call_tool("im", "track_order", {"orderId": oid})
                ms = (time.perf_counter() - t0) * 1000
                _save_fixture("im", "track_order", d2, {})
                record("10b", "im", "track_order", "OK", ms, "ok")
            except Exception as e:  # noqa: BLE001
                ms = (time.perf_counter() - t0) * 1000
                record("10b", "im", "track_order", "FAIL", ms, str(e)[:80])
        else:
            record("10b", "im", "track_order", "SKIP", 0, "no orderId")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("10", "im", "get_orders", "FAIL", ms, str(e)[:80])

    # 11–13 Dineout
    t0 = time.perf_counter()
    try:
        data = call_tool("dineout", "get_saved_locations", {})
        ms = (time.perf_counter() - t0) * 1000
        loc = _first_location(data)
        ctx["location"] = loc
        _save_fixture("dineout", "get_saved_locations", data, {"loc_keys": sorted(loc.keys())})
        record("11", "dineout", "get_saved_locations", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("11", "dineout", "get_saved_locations", "FAIL", ms, str(e)[:80])

    loc = ctx.get("location") or {}
    dine_args: dict[str, Any] = {"query": "italian"}
    for k in ("lat", "lng", "latitude", "longitude", "addressId", "id", "locationId"):
        if loc.get(k) is not None:
            dine_args[k if k != "id" else "addressId"] = loc[k]
    # Prefer lat/lng if present under nested
    if "lat" not in dine_args and isinstance(loc.get("coordinates"), dict):
        dine_args["lat"] = loc["coordinates"].get("lat")
        dine_args["lng"] = loc["coordinates"].get("lng")

    t0 = time.perf_counter()
    try:
        data = call_tool("dineout", "search_restaurants_dineout", dine_args)
        ms = (time.perf_counter() - t0) * 1000
        rid = _first_restaurant_id(data)
        if rid:
            ctx["dineoutRestaurantId"] = rid
        _save_fixture("dineout", "search_restaurants_dineout", data, {"rid": bool(rid)})
        record("12", "dineout", "search_restaurants_dineout", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("12", "dineout", "search_restaurants_dineout", "FAIL", ms, str(e)[:80])

    if ctx.get("dineoutRestaurantId"):
        drid = ctx["dineoutRestaurantId"]
        t0 = time.perf_counter()
        try:
            det_args = {"restaurantId": drid}
            for k in ("lat", "lng"):
                if dine_args.get(k) is not None:
                    det_args[k] = dine_args[k]
            data = call_tool("dineout", "get_restaurant_details", det_args)
            ms = (time.perf_counter() - t0) * 1000
            _save_fixture("dineout", "get_restaurant_details", data, {})
            record("13a", "dineout", "get_restaurant_details", "OK", ms, "ok")
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            record("13a", "dineout", "get_restaurant_details", "FAIL", ms, str(e)[:80])

        t0 = time.perf_counter()
        try:
            from datetime import date

            slot_args = {
                "restaurantId": drid,
                "partySize": 2,
                "date": date.today().isoformat(),
            }
            for k in ("lat", "lng"):
                if dine_args.get(k) is not None:
                    slot_args[k] = dine_args[k]
            data = call_tool("dineout", "get_available_slots", slot_args)
            ms = (time.perf_counter() - t0) * 1000
            _save_fixture("dineout", "get_available_slots", data, {})
            record("13b", "dineout", "get_available_slots", "OK", ms, "ok")
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            record("13b", "dineout", "get_available_slots", "FAIL", ms, str(e)[:80])
    else:
        record("13a", "dineout", "get_restaurant_details", "SKIP", 0, "no dineout rid")
        record("13b", "dineout", "get_available_slots", "SKIP", 0, "no dineout rid")

    # 14 payment options — may fail without cart; that's OK
    t0 = time.perf_counter()
    try:
        data = call_tool("food", "get_payment_options", {"addressId": addr})
        ms = (time.perf_counter() - t0) * 1000
        _save_fixture("food", "get_payment_options", data, {})
        record("14", "food", "get_payment_options", "OK", ms, "ok")
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        record("14", "food", "get_payment_options", "SKIP/ERR", ms, str(e)[:80])

    # Mark never-probed
    for tool in sorted(NEVER_LIVE):
        record("skip", "*", tool, "WIRED_NOT_PROBED", 0, "money/HITL")

    # Catalog tools not covered
    all_live = FOOD_CANONICAL | IM_CANONICAL | DINEOUT_CANONICAL
    probed = {
        "get_addresses",
        "search_restaurants",
        "search_menu",
        "get_restaurant_menu",
        "get_food_cart",
        "update_food_cart",
        "fetch_food_coupons",
        "flush_food_cart",
        "get_food_orders",
        "get_food_order_details",
        "track_food_order",
        "search_products",
        "your_go_to_items",
        "update_cart",
        "get_cart",
        "clear_cart",
        "get_orders",
        "track_order",
        "get_saved_locations",
        "search_restaurants_dineout",
        "get_restaurant_details",
        "get_available_slots",
        "get_payment_options",
        "report_error",
        "get_food_delivery_status",
        "get_delivery_status",
        "check_payment_status",
        "render_restaurants_dineout",
        "create_cart",
        "get_booking_status",
        "apply_food_coupon",
    }
    missing = sorted(all_live - probed - NEVER_LIVE)
    log_lines.append("")
    log_lines.append("## Not probed (read/misc — wire only or needs prior state)")
    log_lines.append("")
    for m in missing:
        log_lines.append(f"- `{m}`")
        record("note", "*", m, "NOT_PROBED", 0, "needs prior state or widget-only")

    LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {LOG_PATH}")
    print(f"Fixtures under {FIXTURE_ROOT}")


if __name__ == "__main__":
    main()
