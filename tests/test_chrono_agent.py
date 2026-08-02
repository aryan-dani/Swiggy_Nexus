"""Chrono-Host agent stream test (in-process mock)."""
from __future__ import annotations

import pytest

from backend.agent import run_agent_stream
from mcp_server.im.dispatcher import invoke as im_invoke
from mcp_server.session_store import reset_all_sessions
from mock_data.food_catalog import MENU_BY_RESTAURANT


@pytest.fixture(autouse=True)
def _clean_sessions():
    reset_all_sessions()
    yield
    reset_all_sessions()


def test_chrono_host_stream():
    events = list(
        run_agent_stream(
            "Plan my evening for 12 — dinner out and dessert at home",
            {"scenario": "chrono_host", "event": {"guests": 12, "cuisineHint": "italian", "title": "Housewarming"}},
        )
    )
    types = [e["type"] for e in events]
    assert "tool" in types
    assert types.count("tool") >= 8
    assert events[-1]["type"] == "done"
    reply = events[-1]["payload"].get("assistant_reply", "")
    assert "confirm" in reply.lower() or "staged" in reply.lower()


@pytest.mark.parametrize(
    "dessert_query",
    ["gelato", "mochi dessert", "tiramisu", "kulfi", "filter coffee sweets"],
)
def test_chrono_host_dessert_cart_uses_menu_item_id(dessert_query: str):
    """Dessert cart must use an item_id from the selected restaurant's menu (no foreign ids)."""
    events = list(
        run_agent_stream(
            "Plan my evening for 12 — dinner out and dessert at home",
            {
                "scenario": "chrono_host",
                "event": {
                    "guests": 12,
                    "cuisineHint": "italian",
                    "title": f"Evening · {dessert_query}",
                    "dessertQuery": dessert_query,
                },
            },
        )
    )
    assert events[-1]["type"] == "done"
    # LocalMCPError would surface as error feed / no successful update_food_cart
    cart_events = [
        e
        for e in events
        if e.get("type") == "tool" and (e.get("payload") or {}).get("method") == "update_food_cart"
    ]
    assert cart_events, "expected food update_food_cart in chrono stream"
    params = cart_events[0]["payload"]["params"]
    rid = str(params.get("restaurantId") or "")
    lines = params.get("lines") or params.get("cartItems") or []
    assert rid and lines
    item_id = str(lines[0].get("item_id") or lines[0].get("itemId") or "")
    menu = MENU_BY_RESTAURANT.get(rid) or {}
    valid_ids = {
        str(it["item_id"])
        for cat in menu.get("categories") or []
        for it in cat.get("items") or []
    }
    assert item_id in valid_ids, f"{item_id!r} not on menu for {rid} (query={dessert_query!r})"
    assert cart_events[0]["payload"]["result"].get("success") is True


def test_chrono_confirm_groceries_uses_same_session_cart():
    """Stage Chrono IM cart then confirm groceries on the same requestId — must not be empty."""
    sid = "chrono_confirm_im_sess"
    ctx = {
        "scenario": "chrono_host",
        "requestId": sid,
        "event": {
            "guests": 12,
            "cuisineHint": "italian",
            "title": "Housewarming",
            "imQuery": "party plates napkins drinks",
        },
    }
    stage = list(
        run_agent_stream(
            "Plan my evening for 12 — dinner out and dessert at home",
            ctx,
        )
    )
    assert stage[-1]["type"] == "done"

    bundle = next(
        (e["payload"]["items"] for e in stage if e.get("type") == "feed"),
        [],
    )
    event_bundle = next((i for i in bundle if i.get("type") == "event_bundle"), None)
    assert event_bundle, "expected event_bundle feed card"
    im_meta = (event_bundle.get("meta") or {}).get("instamart") or {}
    assert im_meta.get("total", 0) > 0
    im_items = im_meta.get("items") or []
    assert len(im_items) >= 1
    assert all(i.get("name") for i in im_items)
    assert im_meta.get("cart_id") == f"cart_im_{sid}"
    assert im_meta.get("requestId") == sid

    # Cart still live under the same session before confirm
    ok, cart, err = im_invoke("get_cart", {"requestId": sid})
    assert ok and err is None
    assert cart["total"] > 0
    assert cart["cart_id"] == f"cart_im_{sid}"
    assert len(cart["items"]) >= 1

    confirm = list(run_agent_stream("confirm groceries", {"requestId": sid}))
    assert confirm[-1]["type"] == "done"
    reply = (confirm[-1]["payload"].get("assistant_reply") or "").lower()
    assert "checkout" in reply or "placed" in reply
    assert "empty" not in reply

    checkout_tools = [
        e
        for e in confirm
        if e.get("type") == "tool" and (e.get("payload") or {}).get("method") == "checkout"
    ]
    assert checkout_tools
    assert checkout_tools[0]["payload"]["result"].get("success") is True
    data = checkout_tools[0]["payload"]["result"].get("data") or {}
    assert data.get("order_id") or data.get("orderId")
    assert data.get("cart_id") == f"cart_im_{sid}"


def test_chrono_confirm_dessert_uses_same_session_cart():
    """Dessert place_order must hit the cart staged by Chrono on the same requestId."""
    sid = "chrono_confirm_food_sess"
    ctx = {
        "scenario": "chrono_host",
        "requestId": sid,
        "event": {
            "guests": 8,
            "cuisineHint": "italian",
            "title": "Date night",
            "dessertQuery": "gelato",
        },
    }
    list(
        run_agent_stream(
            "Plan my evening for 8 — dinner out and dessert at home",
            ctx,
        )
    )
    confirm = list(run_agent_stream("confirm dessert", {"requestId": sid}))
    assert confirm[-1]["type"] == "done"
    reply = (confirm[-1]["payload"].get("assistant_reply") or "").lower()
    assert "empty" not in reply
    assert "placed" in reply or "dessert" in reply
    place_tools = [
        e
        for e in confirm
        if e.get("type") == "tool"
        and (e.get("payload") or {}).get("method") in ("place_food_order", "place_order")
    ]
    assert place_tools
    assert place_tools[0]["payload"]["result"].get("success") is True


def test_web_chrono_confirms_do_not_call_telegram(monkeypatch: pytest.MonkeyPatch):
    """Beat 1 confirm table/groceries must never POST to api.telegram.org."""
    import httpx

    from backend.llm_orchestrator import run_llm_agent

    telegram_posts: list[str] = []
    real_post = httpx.AsyncClient.post
    real_get = httpx.AsyncClient.get

    async def spy_post(self, url, *args, **kwargs):
        url_s = str(url)
        if "api.telegram.org" in url_s:
            telegram_posts.append(url_s)
        return await real_post(self, url, *args, **kwargs)

    async def spy_get(self, url, *args, **kwargs):
        url_s = str(url)
        if "api.telegram.org" in url_s:
            telegram_posts.append(url_s)
        return await real_get(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", spy_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", spy_get)

    sid = "chrono_no_tg_sess"
    ctx = {
        "scenario": "chrono_host",
        "requestId": sid,
        "event": {
            "guests": 6,
            "cuisineHint": "italian",
            "title": "Housewarming",
            "imQuery": "party plates napkins drinks",
        },
    }
    list(run_llm_agent("Plan my evening for 6 guests", ctx))
    list(run_llm_agent("confirm table", {"scenario": "chrono_host", "requestId": sid}))
    list(run_llm_agent("confirm groceries", {"scenario": "chrono_host", "requestId": sid}))

    assert telegram_posts == [], f"unexpected Telegram HTTP during web Chrono: {telegram_posts}"
