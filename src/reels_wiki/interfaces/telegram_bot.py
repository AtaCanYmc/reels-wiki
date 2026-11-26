from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..core.config import Config
from ..ingestion.queue_manager import enqueue

logger = logging.getLogger("reels_wiki.telegram_bot")

MEDIA_URL_PATTERN = re.compile(
    r"https?://(?:"
    r"(?:www\.|m\.)?instagram\.com/(?:[A-Za-z0-9._-]+/)?(?:reel|reels|p|tv|share)/[A-Za-z0-9_/-]+(?:\?[^\s<>\"']*)?"
    r"|(?:www\.|m\.)?youtube\.com/shorts/[A-Za-z0-9_-]{11}/?(?:\?[^\s<>\"']*)?"
    r"|youtu\.be/[A-Za-z0-9_-]{11}/?(?:\?[^\s<>\"']*)?"
    r"|(?:www\.|m\.)?tiktok\.com/(?:@[^/\s]+/)?(?:video|v)/\d+/?(?:\?[^\s<>\"']*)?"
    r")",
    re.IGNORECASE,
)
IG_URL_PATTERN = MEDIA_URL_PATTERN


def _get_authorized_chat_id() -> int:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram capture bot.")

    raw_chat_id = (os.getenv("TELEGRAM_ALLOWED_CHAT_ID") or "").strip()
    if not raw_chat_id:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_CHAT_ID is required; refusing to start without an allowed chat id."
        )
    try:
        return int(raw_chat_id)
    except ValueError as exc:
        raise RuntimeError(
            f"TELEGRAM_ALLOWED_CHAT_ID must be a numeric chat ID, got: {raw_chat_id!r}"
        ) from exc


def _redact_token(message: str, token: str) -> str:
    return message.replace(token, "<redacted>") if token else message


class TelegramBotClient:
    def __init__(self, token: str, timeout: int = 35) -> None:
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout

    def _request(self, method: str, params: dict[str, Any] | None = None, read_timeout: int | None = None) -> dict[str, Any]:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.base_url}/{method}{query}"
        req = urllib.request.Request(url, method="GET")
        effective_timeout = read_timeout if read_timeout is not None else self.timeout
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Telegram request failed on {method}: {_redact_token(str(exc), self.token)}") from None
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error on {method}: {_redact_token(str(payload), self.token)}")
        return payload

    def get_updates(self, offset: int | None = None, poll_timeout: int = 25) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": poll_timeout,
            "allowed_updates": json.dumps(["message", "edited_message"]),
        }
        if offset is not None:
            params["offset"] = offset
        data = self._request("getUpdates", params=params, read_timeout=poll_timeout + 10)
        return data.get("result", [])

    def send_message(self, chat_id: int, text: str, reply_to_message_id: int | None = None) -> None:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
        if reply_to_message_id is not None:
            params["reply_to_message_id"] = reply_to_message_id
        self._request("sendMessage", params=params, read_timeout=15)


def extract_media_urls(text: str) -> list[str]:
    if not text:
        return []
    seen: list[str] = []
    for match in MEDIA_URL_PATTERN.findall(text):
        cleaned = match.rstrip(").,]>\"'")
        if cleaned not in seen:
            seen.append(cleaned)
    return seen


extract_instagram_urls = extract_media_urls


def handle_update(
    cfg: Config,
    client: TelegramBotClient,
    update: dict[str, Any],
    allowed_chat_id: int,
) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not isinstance(msg, dict):
        return

    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id != allowed_chat_id:
        logger.debug("Ignored message from unauthorized chat_id=%s", chat_id)
        return

    text = msg.get("text") or msg.get("caption") or ""
    urls = extract_media_urls(text)
    message_id = msg.get("message_id")

    if not urls:
        client.send_message(
            chat_id=allowed_chat_id,
            text="No supported Instagram, YouTube Shorts, or TikTok URL found in message.",
            reply_to_message_id=message_id,
        )
        return

    lines: list[str] = []
    for url in urls:
        res = enqueue(url=url, source="telegram", vault=cfg.vault_path)
        code = res.get("shortcode", "?")
        if res.get("result") == "enqueued" or res.get("enqueued"):
            lines.append(f"Queued [{code}]: {res.get('url', url)}")
        else:
            reason = res.get("reason") or res.get("message") or "already indexed"
            lines.append(f"Skipped [{code}] ({reason}): {res.get('url', url)}")

    client.send_message(
        chat_id=allowed_chat_id,
        text="\n".join(lines),
        reply_to_message_id=message_id,
    )


def run_telegram_bot(cfg: Config) -> None:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    allowed_chat_id = _get_authorized_chat_id()
    client = TelegramBotClient(token=token)

    logger.info("Starting Telegram share bot for authorized chat_id=%s", allowed_chat_id)
    offset: int | None = None

    while True:
        try:
            updates = client.get_updates(offset=offset, poll_timeout=25)
            for upd in updates:
                update_id = upd.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                handle_update(cfg=cfg, client=client, update=upd, allowed_chat_id=allowed_chat_id)
        except KeyboardInterrupt:
            logger.info("Telegram bot stopped by user.")
            break
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            logger.warning("Telegram polling error, retrying in 5s: %s", _redact_token(str(exc), token))
            time.sleep(5)
