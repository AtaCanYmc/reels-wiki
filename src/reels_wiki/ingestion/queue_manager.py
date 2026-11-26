"""Shortcode extraction, JSONL queue, and the O(1) ``.reels_index.json`` state map."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import httpx
from filelock import FileLock

from ..core.models import QueueItem, QueueStatus, utcnow_iso
from ..core.utils import atomic_write_text

IG_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am"}
_PATH_RE = re.compile(r"(?:^|/)(reels?|p|tv)/([A-Za-z0-9_-]{11})(?=/|$)")
_SHARE_RE = re.compile(r"(?:^|/)share/([A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)/?$")
ALL_STATUSES: tuple[str, ...] = ("pending", "processing", "processed", "skipped", "failed")


def resolve_share_url(url: str, *, timeout: float = 10.0) -> str:
    """Follow Instagram ``/share/...`` redirects safely on ``www.instagram.com`` only."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if (parsed.hostname or "").lower() not in IG_HOSTS:
        return url
    match = _SHARE_RE.search(parsed.path)
    if not match:
        return url

    # Reconstruct from a fixed allowlisted origin so arbitrary hosts/ports/schemes cannot be probed.
    safe_url = f"https://www.instagram.com/share/{match.group(1)}"
    try:
        resp = httpx.head(safe_url, follow_redirects=False, timeout=timeout)
        location = resp.headers.get("location")
        if not location and resp.status_code in (403, 405):
            resp = httpx.get(safe_url, follow_redirects=False, timeout=timeout)
            location = resp.headers.get("location")
    except httpx.HTTPError:
        return url

    if not location:
        return url
    target = urljoin("https://www.instagram.com", location)
    try:
        t_parsed = urlparse(target)
    except ValueError:
        return url
    if t_parsed.scheme not in ("http", "https") or (t_parsed.hostname or "").lower() not in IG_HOSTS:
        return url
    return target


def parse_instagram_url(url: str) -> tuple[str, str] | None:
    """Return ``(kind, shortcode)`` for any reel/post URL variant, else ``None``.

    Handles ``/reel/<id>/``, ``/reels/<id>/``, ``/p/<id>/``, ``/tv/<id>/``, ``/share/...``,
    a leading ``/<username>/`` segment, missing scheme, and tracking params such as ``?igsh=...``.
    """
    if not url or not isinstance(url, str):
        return None
    candidate = url.strip().strip("<>")
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if (parsed.hostname or "").lower() not in IG_HOSTS:
        return None
    match = _PATH_RE.search(parsed.path)
    if not match and _SHARE_RE.search(parsed.path):
        resolved = resolve_share_url(candidate)
        try:
            r_parsed = urlparse(resolved)
        except ValueError:
            return None
        if (r_parsed.hostname or "").lower() not in IG_HOSTS:
            return None
        match = _PATH_RE.search(r_parsed.path)
    if not match:
        return None
    kind = "post" if match.group(1) == "p" else "reel"
    return kind, match.group(2)


def extract_shortcode(url: str) -> str | None:
    parsed = parse_instagram_url(url)
    return parsed[1] if parsed else None


def normalize_url(shortcode_or_url: str) -> str:
    """Canonical form: ``https://www.instagram.com/reel/<shortcode>/``."""
    sc = extract_shortcode(shortcode_or_url) or shortcode_or_url
    return f"https://www.instagram.com/reel/{sc}/"


def _index_entry(item: QueueItem) -> dict:
    entry = {
        "status": item.status,
        "url": item.url,
        "note_path": item.note_path,
        "updated_at": item.updated_at,
    }
    if item.skip_reason:
        entry["skip_reason"] = item.skip_reason
    if item.error:
        entry["error"] = item.error
    return entry


class QueueManager:
    """State manager for one vault. Safe across processes (file lock) and crashes (atomic index writes)."""

    def __init__(self, vault: Path | str):
        self.vault = Path(vault).expanduser()
        self.queue_path = self.vault / "inbox" / "reels-queue.jsonl"
        self.index_path = self.vault / "sources" / ".reels_index.json"
        self._lock_obj: FileLock | None = None

    @property
    def _lock(self) -> FileLock:
        if self._lock_obj is None:
            self._ensure_dirs()  # the lock file lives in inbox/, which must exist first
            self._lock_obj = FileLock(str(self.vault / "inbox" / ".reels-queue.lock"))
        return self._lock_obj

    # ------------------------------------------------------------------ storage
    def _ensure_dirs(self) -> None:
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, item: QueueItem) -> None:
        self._ensure_dirs()
        with open(self.queue_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(item.model_dump_json() + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def read_queue(self) -> dict[str, QueueItem]:
        """Collapse the append-only log: the last line per shortcode wins; order = first enqueue."""
        items: dict[str, QueueItem] = {}
        if not self.queue_path.exists():
            return items
        with open(self.queue_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = QueueItem.model_validate_json(line)
                except ValueError:
                    continue  # tolerate a torn/corrupt line
                prev = items.get(item.shortcode)
                if prev is not None:
                    item.enqueued_at = prev.enqueued_at
                items[item.shortcode] = item
        return items

    def load_index(self) -> dict[str, dict]:
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return self.rebuild_index() if self.queue_path.exists() else {}

    def _save_index(self, index: dict[str, dict]) -> None:
        atomic_write_text(self.index_path, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def rebuild_index(self) -> dict[str, dict]:
        """Recreate the index from the queue log (self-healing if the index is lost/corrupt)."""
        with self._lock:
            index = {sc: _index_entry(it) for sc, it in self.read_queue().items()}
            if index:
                self._save_index(index)
            return index

    # ------------------------------------------------------------------ enqueue
    def _enqueue_one(self, index: dict[str, dict], url: str, source: str, force: bool) -> dict:
        parsed = parse_instagram_url(url)
        if not parsed:
            return {"ok": False, "result": "invalid", "url": url, "shortcode": None,
                    "message": "Not a recognizable Instagram reel/post URL"}
        kind, shortcode = parsed
        canonical = normalize_url(shortcode)
        existing = index.get(shortcode)
        if existing and not force:
            return {"ok": True, "result": "duplicate", "shortcode": shortcode, "url": canonical,
                    "status": existing.get("status"), "note_path": existing.get("note_path"),
                    "message": f"Already known (status: {existing.get('status')})"}
        item = QueueItem(shortcode=shortcode, url=canonical, source=source)
        if existing:
            item.note_path = existing.get("note_path")  # keep it so a forced re-run overwrites, never duplicates
        self._append(item)
        index[shortcode] = _index_entry(item)
        return {"ok": True, "result": "enqueued", "shortcode": shortcode, "url": canonical,
                "status": "pending", "kind": kind, "message": "Queued"}

    def enqueue(self, url: str, source: str = "manual", force: bool = False) -> dict:
        with self._lock:
            index = self.load_index()
            result = self._enqueue_one(index, url, source, force)
            if result["result"] == "enqueued":
                self._save_index(index)
            return result

    def enqueue_many(self, urls: Iterable[str], source: str = "manual", force: bool = False) -> dict[str, Any]:
        shortcodes: list[str] = []
        summary: dict[str, Any] = {"enqueued": 0, "duplicates": 0, "invalid": 0, "shortcodes": shortcodes}
        with self._lock:
            index = self.load_index()
            seen: set[str] = set()
            for url in urls:
                sc = extract_shortcode(url)
                if sc and sc in seen:
                    summary["duplicates"] += 1
                    continue
                result = self._enqueue_one(index, url, source, force)
                if result["result"] == "enqueued":
                    summary["enqueued"] += 1
                    shortcodes.append(result["shortcode"])
                    seen.add(result["shortcode"])
                elif result["result"] == "duplicate":
                    summary["duplicates"] += 1
                    seen.add(result["shortcode"])
                else:
                    summary["invalid"] += 1
            if summary["enqueued"]:
                self._save_index(index)
        return summary

    # ------------------------------------------------------------------ state
    def get_item(self, shortcode: str) -> QueueItem | None:
        return self.read_queue().get(shortcode)

    def update_status(
        self,
        shortcode: str,
        status: QueueStatus,
        *,
        note_path: str | None = None,
        skip_reason: str | None = None,
        error: str | None = None,
        count_attempt: bool = False,
    ) -> QueueItem:
        with self._lock:
            item = self.read_queue().get(shortcode)
            index = self.load_index()
            if item is None:
                entry = index.get(shortcode)
                if entry is None:
                    raise KeyError(f"Unknown shortcode: {shortcode}")
                item = QueueItem(shortcode=shortcode, url=entry["url"], note_path=entry.get("note_path"))
            updated = item.model_copy(
                update={
                    "status": status,
                    "updated_at": utcnow_iso(),
                    "note_path": note_path if note_path is not None else item.note_path,
                    "skip_reason": skip_reason,
                    "error": (error or None) and error[:500],
                    "attempts": item.attempts + (1 if count_attempt else 0),
                }
            )
            self._append(updated)
            index[shortcode] = _index_entry(updated)
            self._save_index(index)
            return updated

    def pending(self, *, retry_failed: bool = False) -> list[QueueItem]:
        wanted = {"pending"} | ({"failed"} if retry_failed else set())
        return [i for i in self.read_queue().values() if i.status in wanted]

    def reset_stale_processing(self) -> int:
        """Items left in ``processing`` by a crashed run go back to ``pending``."""
        count = 0
        for item in self.read_queue().values():
            if item.status == "processing":
                self.update_status(item.shortcode, "pending")
                count += 1
        return count

    def stats(self) -> dict:
        index = self.load_index()
        counts = {s: 0 for s in ALL_STATUSES}
        for entry in index.values():
            counts[entry.get("status", "pending")] = counts.get(entry.get("status", "pending"), 0) + 1
        by_source: dict[str, int] = {}
        for item in self.read_queue().values():
            by_source[item.source] = by_source.get(item.source, 0) + 1
        stages = {"metadata": 0, "subtitles": 0, "whisper": 0, "vision": 0}
        llm_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "retries": 0}
        artifacts_count = 0
        reels_dir = self.vault / "sources" / "reels"
        if reels_dir.is_dir():
            for path in sorted(reels_dir.glob("*.json")):
                artifacts_count += 1
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                for step in data.get("steps_used") or []:
                    key = step.split(":", 1)[0]
                    if key in stages:
                        stages[key] += 1
                metrics = data.get("synthesis_metrics")
                if isinstance(metrics, dict):
                    for field in llm_usage:
                        llm_usage[field] += int(metrics.get(field) or 0)
        return {
            "vault": str(self.vault),
            "total": len(index),
            **counts,
            "by_source": by_source,
            "artifacts_count": artifacts_count,
            "stages": stages,
            "llm_usage": llm_usage,
        }


# ---------------------------------------------------------------------- module-level SDK helpers
def _resolve_vault(vault: Path | str | None) -> Path:
    if vault:
        return Path(vault)
    from ..core.config import load_config

    return load_config().vault_path


def enqueue(url: str, source: str = "manual", *, vault: Path | str | None = None, force: bool = False) -> dict:
    """Validate ``url``, extract its shortcode, dedupe against the index, append to the queue."""
    return QueueManager(_resolve_vault(vault)).enqueue(url, source, force=force)


def queue_stats(vault: Path | str | None = None) -> dict:
    return QueueManager(_resolve_vault(vault)).stats()
