"""Orchestration shared by the CLI, MCP server and Telegram bot: queue -> extract -> synthesize -> write."""
from __future__ import annotations

import time
from typing import Callable

from filelock import FileLock, Timeout

from ..core.config import Config
from ..core.models import QueueItem
from ..ingestion.queue_manager import QueueManager
from ..vault.context import VaultContext
from ..vault.writer import write_synthesis
from .extractor import ExtractionError, artifact_path, extract_reel, load_artifact, save_artifact
from .synthesizer import synthesize

Progress = Callable[[dict], None]


def _ctx(cfg: Config) -> VaultContext:
    return VaultContext.load(cfg.vault_path, allowed_override=cfg.allowed_folders, default_folder=cfg.default_folder)


def process_item(
    cfg: Config,
    queue: QueueManager,
    item: QueueItem,
    *,
    re_extract: bool = False,
    reuse_artifact_only: bool = False,
) -> dict:
    """Process one queue item end-to-end. Never raises: failures are recorded as ``failed`` in the queue."""
    sc = item.shortcode
    queue.update_status(sc, "processing", count_attempt=True)
    downloaded = False
    try:
        artifact = None if re_extract else load_artifact(cfg.vault_path, sc)
        if artifact is None:
            if reuse_artifact_only:
                raise ExtractionError(f"No stored artifact for {sc} (sources/reels/{sc}.json); cannot reprocess offline")
            artifact = extract_reel(item.url, sc, cfg)
            save_artifact(cfg.vault_path, artifact)
            downloaded = True
        ctx = _ctx(cfg)
        syn = synthesize(artifact, ctx, cfg)
        if artifact.synthesis_metrics is not None:
            save_artifact(cfg.vault_path, artifact)
        result = write_synthesis(queue, ctx, artifact, syn, overwrite_path=item.note_path)
        result["warnings"] = artifact.warnings
        result["steps"] = artifact.steps_used
        result["downloaded"] = downloaded
        if artifact.synthesis_metrics is not None:
            result["synthesis_metrics"] = artifact.synthesis_metrics.model_dump()
        return result
    except Exception as exc:  # noqa: BLE001 - one bad reel must not stop the batch
        message = f"{type(exc).__name__}: {exc}"
        queue.update_status(sc, "failed", error=message)
        return {"status": "failed", "shortcode": sc, "error": message[:500], "downloaded": downloaded}


def process_queue(
    cfg: Config,
    *,
    limit: int | None = None,
    retry_failed: bool = False,
    re_extract: bool = False,
    dry_run: bool = False,
    on_event: Progress | None = None,
) -> dict:
    """Process pending items (and optionally failed ones). Only one processor may run per vault at a time."""
    queue = QueueManager(cfg.vault_path)
    queue._ensure_dirs()
    lock = FileLock(str(cfg.vault_path / "inbox" / ".reels-process.lock"))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return {"error": "another reels-sync process is already running for this vault", "processed": 0}
    try:
        recovered = queue.reset_stale_processing()
        items = queue.pending(retry_failed=retry_failed)
        if limit is not None:
            items = items[: max(limit, 0)]
        summary: dict = {"selected": len(items), "recovered_stale": recovered, "processed": 0, "skipped": 0,
                         "failed": 0, "results": [], "dry_run": dry_run}
        if dry_run:
            summary["results"] = [{"shortcode": i.shortcode, "url": i.url, "status": i.status} for i in items]
            return summary
        for n, item in enumerate(items):
            result = process_item(cfg, queue, item, re_extract=re_extract)
            summary[{"processed": "processed", "skipped": "skipped"}.get(result["status"], "failed")] += 1
            summary["results"].append(result)
            if on_event:
                on_event(result)
            if result.get("downloaded") and n < len(items) - 1 and cfg.delay_seconds:
                time.sleep(cfg.delay_seconds)
        return summary
    finally:
        lock.release()


def reprocess(cfg: Config, shortcodes: list[str] | None = None, *, all_items: bool = False, on_event: Progress | None = None) -> dict:
    """Re-synthesize from stored ``sources/reels/*.json`` artifacts: no downloads, no transcription cost."""
    queue = QueueManager(cfg.vault_path)
    known = queue.read_queue()
    if all_items:
        targets = [sc for sc in known if artifact_path(cfg.vault_path, sc).is_file()]
    else:
        targets = list(shortcodes or [])
    summary: dict = {"selected": len(targets), "processed": 0, "skipped": 0, "failed": 0, "results": []}
    for sc in targets:
        item = known.get(sc)
        if item is None:
            result = {"status": "failed", "shortcode": sc, "error": "unknown shortcode (not in the queue)"}
        else:
            result = process_item(cfg, queue, item, reuse_artifact_only=True)
        summary[{"processed": "processed", "skipped": "skipped"}.get(result["status"], "failed")] += 1
        summary["results"].append(result)
        if on_event:
            on_event(result)
    return summary
