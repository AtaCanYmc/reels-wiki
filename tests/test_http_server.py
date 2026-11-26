from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from reels_wiki.core.config import Config, ConfigError
from reels_wiki.interfaces.http_server import make_http_server, run_http_server


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


def test_http_server_stats_reprocess_and_digest_endpoints(tmp_path: Path) -> None:
    from datetime import date

    today = date.today().isoformat()
    ideas = tmp_path / "ideas"
    ideas.mkdir()
    (ideas / "sample.md").write_text(
        f"---\ntitle: Sample Note\ncreated: '{today}'\ntags: [obsidian]\n---\nBody\n",
        encoding="utf-8",
    )
    server = make_http_server(Config(vault_path=tmp_path), port=0, token="obsidian-tok")
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    auth = {"Authorization": "Bearer obsidian-tok"}
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/stats", headers=auth)
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            stats = json.loads(resp.read().decode("utf-8"))
        assert stats["total"] == 0

        code_bad, _ = _post_json(f"http://127.0.0.1:{port}/reprocess", {}, headers=auth)
        assert code_bad == 400

        with patch(
            "reels_wiki.interfaces.http_server.reprocess",
            return_value={"selected": 1, "processed": 1, "skipped": 0, "failed": 0},
        ) as mock_rep:
            code_rep, rep = _post_json(
                f"http://127.0.0.1:{port}/reprocess",
                {"shortcode": "DAbCdEfGhIj"},
                headers=auth,
            )
        assert code_rep == 200 and rep["processed"] == 1
        mock_rep.assert_called_once()

        code_dig, dig = _post_json(
            f"http://127.0.0.1:{port}/digest",
            {"days": 7, "tag": "obsidian"},
            headers=auth,
        )
        assert code_dig == 200 and dig["notes_count"] == 1
        assert dig["digest_path"].endswith("-obsidian-digest.md")
    finally:
        server.shutdown()
        server.server_close()


def test_run_http_server_handles_keyboard_interrupt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dummy_server = MagicMock()
    dummy_server.serve_forever.side_effect = KeyboardInterrupt

    with patch("reels_wiki.interfaces.http_server.make_http_server", return_value=dummy_server):
        run_http_server(Config(vault_path=tmp_path), host="127.0.0.1", port=8765)

    out = capsys.readouterr().out
    assert "http://127.0.0.1:8765" in out
    assert "Shutting down HTTP server." in out
    dummy_server.server_close.assert_called_once_with()


def test_http_server_access_logs_toggle(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="reels_wiki.http")

    for enabled in (True, False):
        caplog.clear()
        server = make_http_server(Config(vault_path=tmp_path, http_access_logs=enabled), port=0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
                assert resp.status == 200
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        http_records = [r for r in caplog.records if r.name == "reels_wiki.http"]
        if enabled:
            assert any("/health" in r.getMessage() for r in http_records)
        else:
            assert http_records == []


def test_http_server_process_endpoint(tmp_path: Path) -> None:
    server = make_http_server(Config(vault_path=tmp_path), port=0, token="proc-tok")
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    auth = {"Authorization": "Bearer proc-tok"}
    try:
        code_bad, bad = _post_json(
            f"http://127.0.0.1:{port}/process",
            {"limit": "not-an-int"},
            headers=auth,
        )
        assert code_bad == 400 and "limit" in bad["error"]

        mock_summary = {
            "selected": 2,
            "recovered_stale": 0,
            "processed": 2,
            "skipped": 0,
            "failed": 0,
            "results": [],
            "dry_run": True,
        }
        with patch("reels_wiki.interfaces.http_server.process_queue", return_value=mock_summary) as mock_proc:
            code_ok, ok = _post_json(
                f"http://127.0.0.1:{port}/process",
                {"limit": 5, "dry_run": True, "retry_failed": True, "force": True},
                headers=auth,
            )
        assert code_ok == 200 and ok["processed"] == 2
        mock_proc.assert_called_once()
        kwargs = mock_proc.call_args.kwargs
        assert kwargs["limit"] == 5
        assert kwargs["dry_run"] is True
        assert kwargs["retry_failed"] is True
        assert kwargs["re_extract"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
