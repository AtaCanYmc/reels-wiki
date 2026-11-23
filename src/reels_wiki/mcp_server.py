"""FastMCP server exposing the pipeline as tools (stdio transport)."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .ig_export import import_ig_export as _import_ig_export
from .pipeline import process_queue as _process_queue
from .queue_manager import QueueManager

mcp = FastMCP("reels-wiki")


def _cfg():
    return load_config()


@mcp.tool()
async def enqueue_reel(url: str, source: str = "mcp", force: bool = False) -> dict:
    """Queue one Instagram reel/post URL. Dedupes by shortcode unless force=True."""
    cfg = _cfg()
    return await asyncio.to_thread(QueueManager(cfg.vault_path).enqueue, url, source, force)


@mcp.tool()
async def import_ig_export(json_path: str, force: bool = False, include_posts: bool = True) -> dict:
    """Bulk-enqueue saved reels from an Instagram data export (saved_posts.json or its folder)."""
    cfg = _cfg()
    return await asyncio.to_thread(
        lambda: _import_ig_export(json_path, vault=cfg.vault_path, force=force, include_posts=include_posts)
    )


@mcp.tool()
async def process_reels_queue(limit: int = 5, retry_failed: bool = False, dry_run: bool = False) -> dict:
    """Extract, synthesize and write notes for pending queue items (slow: keep `limit` small)."""
    cfg = _cfg()
    return await asyncio.to_thread(
        lambda: _process_queue(cfg, limit=limit, retry_failed=retry_failed, dry_run=dry_run)
    )


@mcp.tool()
async def get_queue_stats() -> dict:
    """Counts of queue items by status (pending/processing/processed/skipped/failed) and source."""
    cfg = _cfg()
    return await asyncio.to_thread(QueueManager(cfg.vault_path).stats)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
