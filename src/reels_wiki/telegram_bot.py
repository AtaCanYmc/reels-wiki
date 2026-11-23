"""Minimal Telegram long-polling bot: share an Instagram link to the bot -> it lands in the queue.

Only messages from ``TELEGRAM_ALLOWED_CHAT_ID`` are honoured; everything else is silently ignored.
"""
from __future__ import annotations

import logging
import re
import time

import httpx

from .config import Config, ConfigError, load_config
from .queue_manager import QueueManager

log = logging.getLogger("reels_wiki.telegram")
_URL_RE = re.compile(r"(?:https?://)?(?:www\.|m\.)?(?:instagram\.com|instagr\.am)/[^\s<>()\"']+", re.I)


def extract_urls(message: dict) -> list[str]:
    """URLs from message text/caption, including hidden ``text_link`` entities."""
    text = message.get("text") or message.get("caption") or ""
    urls = _URL_RE.findall(text)
    for ent in (message.get("entities") or []) + (message.get("caption_entities") or []):
        if ent.get("type") == "text_link" and ent.get("url") and _URL_RE.search(ent["url"]):
            urls.append(ent["url"])
    return [u.rstrip(".,;)") for u in dict.fromkeys(urls)]


def handle_update(update: dict, queue: QueueManager, allowed_chat_id: int) -> tuple[int, str] | None:
    """Pure handler: returns ``(chat_id, reply_text)`` or ``None`` (ignore). Unit-testable without network."""
    message = update.get("message") or update.get("channel_post")
    if not message:
        return None
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    if chat_id != allowed_chat_id:
        log.warning("Ignored message from unauthorized chat %s", chat_id)
        return None
    if text.startswith("/stats"):
        s = queue.stats()
        return chat_id, (f"📊 total {s['total']} · pending {s['pending']} · processed {s['processed']} · "
                         f"skipped {s['skipped']} · failed {s['failed']}")
    if text.startswith(("/start", "/help")):
        return chat_id, "Share or paste an Instagram reel link and I'll queue it. /stats shows queue counts."
    urls = extract_urls(message)
    if not urls:
        return chat_id, "No Instagram link found in that message."
    replies = []
    for url in urls:
        res = queue.enqueue(url, source="telegram")
        if res["result"] == "enqueued":
            replies.append(f"✅ Queued {res['shortcode']}")
        elif res["result"] == "duplicate":
            replies.append(f"♻️ Already known: {res['shortcode']} ({res['status']})")
        else:
            replies.append(f"⚠️ Not a valid Instagram reel/post link: {url}")
    return chat_id, "\n".join(replies)


def run_bot(cfg: Config) -> None:
    token = cfg.telegram_bot_token
    if not token:
        raise ConfigError("TELEGRAM_BOT_TOKEN is not set")
    if cfg.telegram_allowed_chat_id is None:
        raise ConfigError("TELEGRAM_ALLOWED_CHAT_ID is not set; refusing to run an open bot")
    queue = QueueManager(cfg.vault_path)
    api = f"https://api.telegram.org/bot{token}"
    offset, backoff = None, 1
    log.info("Telegram bot started (allowed chat: %s)", cfg.telegram_allowed_chat_id)
    with httpx.Client(timeout=70) as client:
        while True:
            try:
                params: dict = {"timeout": 50, "allowed_updates": '["message","channel_post"]'}
                if offset is not None:
                    params["offset"] = offset
                resp = client.get(f"{api}/getUpdates", params=params)
                resp.raise_for_status()
                backoff = 1
                for update in resp.json().get("result", []):
                    offset = update["update_id"] + 1
                    reply = handle_update(update, queue, cfg.telegram_allowed_chat_id)
                    if reply:
                        client.post(f"{api}/sendMessage", json={"chat_id": reply[0], "text": reply[1],
                                                                "disable_web_page_preview": True})
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("Telegram polling error: %s (retry in %ss)", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except KeyboardInterrupt:
                log.info("Stopped")
                return


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_bot(load_config())


if __name__ == "__main__":
    main()
