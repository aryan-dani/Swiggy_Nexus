"""Download Swiggy Builders Club MCP documentation into docs/_swiggy_cache/."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://mcp.swiggy.com/builders"
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "docs" / "_swiggy_cache"

FOOD_TOOLS = [
    "search_restaurants",
    "get_restaurant_menu",
    "search_menu",
    "update_food_cart",
    "get_food_cart",
    "flush_food_cart",
    "fetch_food_coupons",
    "apply_food_coupon",
    "place_food_order",
    "get_food_orders",
    "get_food_order_details",
    "track_food_order",
    "get_addresses",
    "report_error",
]

INSTAMART_TOOLS = [
    "search_products",
    "your_go_to_items",
    "update_cart",
    "get_cart",
    "clear_cart",
    "checkout",
    "get_orders",
    "get_order_details",
    "track_order",
    "get_addresses",
    "create_address",
    "delete_address",
    "report_error",
]

DINEOUT_TOOLS = [
    "search_restaurants_dineout",
    "get_restaurant_details",
    "get_available_slots",
    "create_cart",
    "book_table",
    "get_booking_status",
    "get_saved_locations",
    "report_error",
]

EXTRA_PAGES = [
    "docs/start/developer/build-an-agent.md",
    "docs/start/authenticate.md",
    "docs/build/recipes/order-food.md",
    "docs/build/recipes/order-groceries.md",
    "docs/build/recipes/book-a-table.md",
    "docs/build/recipes/combined.md",
    "docs/build/agent-patterns/multi-turn-state.md",
    "docs/build/agent-patterns/voice-vs-chat.md",
    "docs/operate/rate-limits.md",
    "docs/reference/errors.md",
    "docs/reference/index.md",
]


def fetch(url: str, dest: Path, retries: int = 3) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SwiggyNexus-DocFetcher/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            dest.write_bytes(data)
            print(f"OK  {dest.relative_to(ROOT)} ({len(data)} bytes)")
            return True
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"RETRY {url} ({attempt + 1}/{retries}): {e}")
            time.sleep(2 ** attempt)
    print(f"FAIL {url}")
    return False


def main() -> None:
    manifest: dict = {"fetched": [], "failed": []}

    bulk = [
        ("llms-full.txt", CACHE / "llms-full.txt"),
        ("llms.txt", CACHE / "llms.txt"),
    ]
    for path, dest in bulk:
        ok = fetch(f"{BASE}/{path}", dest)
        (manifest["fetched"] if ok else manifest["failed"]).append(path)

    for rel in EXTRA_PAGES:
        dest = CACHE / rel.replace("/", "__")
        ok = fetch(f"{BASE}/{rel}", dest)
        entry = f"{BASE}/{rel}"
        (manifest["fetched"] if ok else manifest["failed"]).append(entry)

    for tool in FOOD_TOOLS:
        rel = f"docs/reference/food/{tool}.md"
        dest = CACHE / "reference" / "food" / f"{tool}.md"
        ok = fetch(f"{BASE}/{rel}", dest)
        (manifest["fetched"] if ok else manifest["failed"]).append(tool)

    for tool in INSTAMART_TOOLS:
        rel = f"docs/reference/instamart/{tool}.md"
        dest = CACHE / "reference" / "instamart" / f"{tool}.md"
        ok = fetch(f"{BASE}/{rel}", dest)
        (manifest["fetched"] if ok else manifest["failed"]).append(tool)

    for tool in DINEOUT_TOOLS:
        rel = f"docs/reference/dineout/{tool}.md"
        dest = CACHE / "reference" / "dineout" / f"{tool}.md"
        ok = fetch(f"{BASE}/{rel}", dest)
        (manifest["fetched"] if ok else manifest["failed"]).append(tool)

    (CACHE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDone: {len(manifest['fetched'])} ok, {len(manifest['failed'])} failed")


if __name__ == "__main__":
    main()
