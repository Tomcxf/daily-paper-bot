#!/usr/bin/env python3
"""
辅助脚本：打印你的 Telegram chat_id。

用法：
  1. 先在 Telegram 里给你的机器人发一句话（比如 hi）
  2. 运行：
       .venv/bin/python get_chat_id.py <你的BOT_TOKEN>
     或先 export TELEGRAM_BOT_TOKEN=... 再直接 .venv/bin/python get_chat_id.py
"""

import os
import sys

import requests


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("用法: python get_chat_id.py <BOT_TOKEN>  （或先 export TELEGRAM_BOT_TOKEN）")

    resp = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates", timeout=30
    )
    data = resp.json()

    if not data.get("ok"):
        sys.exit(f"请求失败，检查 token 是否正确：{data}")

    results = data.get("result", [])
    if not results:
        sys.exit("没拿到任何消息。请确认：你已经先在 Telegram 里给机器人发过一句话。")

    seen = {}
    for upd in results:
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat", {})
        cid = chat.get("id")
        if cid is not None and cid not in seen:
            name = chat.get("title") or chat.get("first_name") or chat.get("username") or ""
            ctype = chat.get("type", "")
            seen[cid] = f"{ctype} {name}".strip()

    print("找到以下会话（chat_id → 说明）：")
    for cid, desc in seen.items():
        print(f"  {cid}    {desc}")
    print("\n把上面的数字填到 run.sh 的 TELEGRAM_CHAT_ID 即可（私聊选正数那个）。")


if __name__ == "__main__":
    main()
