import os
import requests

def notify_admin(text: str, reply_markup: dict | None = None):
    bot_token = os.getenv("ADMIN_BOT_TOKEN")
    chat_id = os.getenv("ADMIN_CHAT_ID")

    if not bot_token or not chat_id:
        print("Admin notification skipped: ADMIN_BOT_TOKEN or ADMIN_CHAT_ID not set")
        return

    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, json=payload, timeout=10)
