"""Minimal stdlib HTTP ingest server shared by Apple Shortcuts and browser extensions."""
from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..core.config import Config, ConfigError, load_config
from ..ingestion.queue_manager import enqueue

_MAX_BODY_BYTES = 16 * 1024
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def make_http_server(
    cfg: Config,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    token: str | None = None,
) -> ThreadingHTTPServer:
    """Create a configured ``ThreadingHTTPServer`` without starting its loop."""
    resolved_token = token if token is not None else os.getenv("REELS_WIKI_HTTP_TOKEN") or None
    if host not in _LOOPBACK_HOSTS and not resolved_token:
        raise ConfigError("REELS_WIKI_HTTP_TOKEN is required when binding to a non-loopback host")

    vault: Path = cfg.vault_path

    class _IngestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if not resolved_token:
                return True
            auth = self.headers.get("Authorization", "")
            candidate = auth[7:].strip() if auth.startswith("Bearer ") else self.headers.get("X-API-Key", "").strip()
            return bool(candidate) and hmac.compare_digest(candidate, resolved_token)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, {"ok": True})
            else:
                self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/ingest":
                self._send_json(404, {"error": "Not found"})
                return
            if not self._authorized():
                self._send_json(401, {"error": "Unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "Invalid Content-Length"})
                return
            if length <= 0 or length > _MAX_BODY_BYTES:
                self._send_json(400, {"error": "Invalid or oversized request body"})
                return
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "Invalid JSON body"})
                return
            if not isinstance(data, dict) or not isinstance(data.get("url"), str):
                self._send_json(400, {"error": "Missing string field 'url'"})
                return

            res = enqueue(
                url=data["url"],
                source=str(data.get("source") or "http"),
                vault=vault,
                force=bool(data.get("force", False)),
            )
            status = 400 if res.get("result") == "invalid" else 200
            self._send_json(status, res)

    return ThreadingHTTPServer((host, port), _IngestHandler)


def run_http_server(
    cfg: Config | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    token: str | None = None,
) -> None:
    """Start the HTTP ingest server until interrupted."""
    server = make_http_server(cfg or load_config(), host=host, port=port, token=token)
    try:
        server.serve_forever()
    finally:
        server.server_close()
