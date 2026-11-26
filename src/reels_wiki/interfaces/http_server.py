"""Minimal stdlib HTTP ingest server shared by Apple Shortcuts and browser extensions."""
from __future__ import annotations

import hmac
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..core.config import Config, ConfigError, load_config
from ..ingestion.queue_manager import enqueue, queue_stats
from ..pipeline.runner import process_queue, reprocess
from ..vault.digest import generate_digest

logger = logging.getLogger("reels_wiki.http")
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

    resolved_cfg = cfg
    vault: Path = resolved_cfg.vault_path

    class _IngestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            if resolved_cfg.http_access_logs:
                logger.info("%s - %s", self.address_string(), format % args)

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

        def _read_json_body(self, *, allow_empty: bool = False) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "Invalid Content-Length"})
                return None
            if length == 0 and allow_empty:
                return {}
            if length <= 0 or length > _MAX_BODY_BYTES:
                self._send_json(400, {"error": "Invalid or oversized request body"})
                return None
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "Invalid JSON body"})
                return None
            if not isinstance(data, dict):
                self._send_json(400, {"error": "JSON body must be an object"})
                return None
            return data

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, {"ok": True})
            elif self.path == "/stats":
                if not self._authorized():
                    self._send_json(401, {"error": "Unauthorized"})
                    return
                self._send_json(200, queue_stats(vault=vault))
            else:
                self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/ingest", "/process", "/reprocess", "/digest"}:
                self._send_json(404, {"error": "Not found"})
                return
            if not self._authorized():
                self._send_json(401, {"error": "Unauthorized"})
                return

            if self.path == "/ingest":
                data = self._read_json_body(allow_empty=False)
                if data is None:
                    return
                if not isinstance(data.get("url"), str):
                    self._send_json(400, {"error": "Missing string field 'url'"})
                    return
                res = enqueue(
                    url=data["url"],
                    source=str(data.get("source") or "http"),
                    vault=vault,
                    force=bool(data.get("force", False)),
                )
                self._send_json(400 if res.get("result") == "invalid" else 200, res)
                return

            if self.path == "/process":
                data = self._read_json_body(allow_empty=True)
                if data is None:
                    return
                raw_limit = data.get("limit")
                if raw_limit is None:
                    limit: int | None = None
                elif isinstance(raw_limit, bool):
                    self._send_json(400, {"error": "Invalid integer field 'limit'"})
                    return
                else:
                    try:
                        limit = int(raw_limit)
                    except (TypeError, ValueError):
                        self._send_json(400, {"error": "Invalid integer field 'limit'"})
                        return
                res = process_queue(
                    cfg=resolved_cfg,
                    limit=limit,
                    dry_run=bool(data.get("dry_run", False)),
                    retry_failed=bool(data.get("retry_failed", False)),
                    re_extract=bool(data.get("force", False)),
                )
                self._send_json(200, res)
                return

            if self.path == "/reprocess":
                data = self._read_json_body(allow_empty=False)
                if data is None:
                    return
                sc = data.get("shortcode")
                all_items = bool(data.get("all", False))
                if not isinstance(sc, str) and not all_items:
                    self._send_json(400, {"error": "Provide 'shortcode' or set 'all': true"})
                    return
                res = reprocess(
                    cfg=resolved_cfg,
                    shortcodes=[sc] if isinstance(sc, str) and sc.strip() else None,
                    all_items=all_items,
                )
                self._send_json(200, res)
                return

            data = self._read_json_body(allow_empty=True)
            if data is None:
                return
            days = int(data.get("days", 7))
            tag = data.get("tag") if isinstance(data.get("tag"), str) else None
            dry_run = bool(data.get("dry_run", False))
            self._send_json(200, generate_digest(vault, days=days, tag=tag, dry_run=dry_run))

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
    print(f"reels-wiki HTTP server listening on http://{host}:{port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down HTTP server.", flush=True)
    finally:
        server.server_close()
