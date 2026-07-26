"""Print recent Telegram chat IDs after you DM the bot."""

from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


def main() -> None:
    if not TOKEN:
        print("Set TELEGRAM_BOT_TOKEN first", file=sys.stderr)
        raise SystemExit(1)
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    data = httpx.get(url, timeout=20).json()
    for upd in data.get("result") or []:
        msg = upd.get("message") or upd.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if chat.get("id"):
            print(f"chat_id={chat['id']} type={chat.get('type')} title={chat.get('title') or chat.get('username')}")


if __name__ == "__main__":
    main()
