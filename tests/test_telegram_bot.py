from __future__ import annotations

import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from reels_wiki.telegram_bot import (
    TelegramBotClient,
    _get_authorized_chat_id,
    extract_instagram_urls,
    handle_update,
)


def test_get_authorized_chat_id_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_ID", raising=False)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        _get_authorized_chat_id()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    with pytest.raises(RuntimeError, match="TELEGRAM_ALLOWED_CHAT_ID"):
        _get_authorized_chat_id()

    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "not-a-number")
    with pytest.raises(RuntimeError, match="numeric"):
        _get_authorized_chat_id()

    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "123456")
    assert _get_authorized_chat_id() == 123456


def test_extract_instagram_urls_dedupes_and_cleans() -> None:
    text = (
        "Check https://www.instagram.com/reel/ABC12345678/?igsh=123, "
        "and https://instagram.com/p/XYZ98765432/ and again "
        "https://www.instagram.com/reel/ABC12345678/?igsh=123."
    )
    urls = extract_instagram_urls(text)
    assert urls == [
        "https://www.instagram.com/reel/ABC12345678/?igsh=123",
        "https://instagram.com/p/XYZ98765432/",
    ]


def test_handle_update_ignores_unauthorized_chat(tmp_path: Path) -> None:
    cfg = SimpleNamespace(vault_path=tmp_path)
    client = MagicMock()
    update = {"message": {"chat": {"id": 999}, "text": "https://www.instagram.com/reel/ABC12345678/"}}

    handle_update(cfg=cfg, client=client, update=update, allowed_chat_id=123)
    client.send_message.assert_not_called()


def test_handle_update_enqueues_valid_url(tmp_path: Path) -> None:
    cfg = SimpleNamespace(vault_path=tmp_path)
    client = MagicMock()
    update = {
        "message": {
            "message_id": 42,
            "chat": {"id": 123},
            "text": "Save this https://www.instagram.com/reel/ABC12345678/",
        }
    }

    with patch(
        "reels_wiki.telegram_bot.enqueue",
        return_value={"enqueued": True, "shortcode": "ABC12345678", "url": "https://www.instagram.com/reel/ABC12345678/"},
    ) as mock_enq:
        handle_update(cfg=cfg, client=client, update=update, allowed_chat_id=123)

    mock_enq.assert_called_once()
    client.send_message.assert_called_once()
    assert "Queued [ABC12345678]" in client.send_message.call_args.kwargs["text"]


def test_telegram_client_redacts_token_on_network_error() -> None:
    secret = "123456:TEST_SECRET_TOKEN"
    client = TelegramBotClient(token=secret)

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError(f"failed calling https://api.telegram.org/bot{secret}/getUpdates"),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            client.get_updates()

    msg = str(exc_info.value)
    assert secret not in msg
    assert "<redacted>" in msg
