from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from reels_wiki.core.config import Config, ConfigError
from reels_wiki.interfaces.http_server import make_http_server


def _post_json(url: str, body: dict, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_http_server_health_and_ingest(tmp_path: Path) -> None:
    server = make_http_server(Config(vault_path=tmp_path), port=0, token="secret-tok")
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
            assert resp.status == 200
            assert json.loads(resp.read().decode("utf-8")) == {"ok": True}

        code, unauth = _post_json(
            f"http://127.0.0.1:{port}/ingest",
            {"url": "https://www.instagram.com/reel/DAbCdEfGhIj/"},
        )
        assert code == 401 and unauth["error"] == "Unauthorized"

        code, ok = _post_json(
            f"http://127.0.0.1:{port}/ingest",
            {"url": "https://www.instagram.com/reel/DAbCdEfGhIj/", "source": "extension"},
            headers={"Authorization": "Bearer secret-tok"},
        )
        assert code == 200
        assert ok["result"] == "enqueued" and ok["shortcode"] == "DAbCdEfGhIj"

        code2, dup = _post_json(
            f"http://127.0.0.1:{port}/ingest",
            {"url": "https://www.instagram.com/reel/DAbCdEfGhIj/"},
            headers={"X-API-Key": "secret-tok"},
        )
        assert code2 == 200
        assert dup["result"] == "duplicate"

        code3, bad = _post_json(
            f"http://127.0.0.1:{port}/ingest",
            {"url": "https://example.com/not-ig"},
            headers={"Authorization": "Bearer secret-tok"},
        )
        assert code3 == 400 and bad["result"] == "invalid"
    finally:
        server.shutdown()
        server.server_close()


def test_http_server_refuses_non_loopback_without_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REELS_WIKI_HTTP_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="REELS_WIKI_HTTP_TOKEN"):
        make_http_server(Config(vault_path=tmp_path), host="0.0.0.0", port=0)
