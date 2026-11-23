from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import AppConfig, load_config
from .ig_export import import_instagram_export
from .pipeline import enqueue_url, get_stats, process_queue


def create_mcp_server(default_cfg: AppConfig | None = None) -> FastMCP:
    base_cfg = default_cfg or load_config()
    mcp = FastMCP("reels-wiki")

    def _resolve_cfg(vault_path: str | None = None) -> AppConfig:
        override = Path(vault_path).expanduser() if vault_path else None
        if override is None:
            return base_cfg
        return load_config(config_path=base_cfg.config_path, vault_override=override)

    @mcp.tool()
    def enqueue_reel(
        url: str,
        source: str = "mcp",
        force: bool = False,
        vault_path: str | None = None,
    ) -> dict[str, Any]:
        """Enqueue an Instagram Reel/post URL into the Obsidian vault queue with shortcode deduplication."""
        cfg = _resolve_cfg(vault_path)
        return enqueue_url(cfg=cfg, url=url, source=source, force=force)

    @mcp.tool()
    def import_ig_export(
        export_path: str,
        reels_only: bool = False,
        force: bool = False,
        vault_path: str | None = None,
    ) -> dict[str, Any]:
        """Bulk-import saved Instagram URLs from saved_posts.json or an export directory."""
        cfg = _resolve_cfg(vault_path)
        return import_instagram_export(
            cfg=cfg,
            export_path=Path(export_path).expanduser(),
            reels_only=reels_only,
            force=force,
        )

    @mcp.tool()
    def process_reels_queue(
        limit: int | None = 10,
        dry_run: bool = False,
        retry_failed: bool = False,
        force: bool = False,
        vault_path: str | None = None,
    ) -> dict[str, Any]:
        """Process queued Instagram Reels through waterfall extraction, LLM synthesis, and Obsidian note writing."""
        cfg = _resolve_cfg(vault_path)
        return process_queue(
            cfg=cfg,
            limit=limit,
            dry_run=dry_run,
            retry_failed=retry_failed,
            force=force,
        )

    @mcp.tool()
    def get_queue_stats(vault_path: str | None = None) -> dict[str, Any]:
        """Return queue counts, index status breakdown, and raw artifact counts for the vault."""
        cfg = _resolve_cfg(vault_path)
        return get_stats(cfg=cfg)

    return mcp


def run_mcp_server(cfg: AppConfig | None = None) -> None:
    server = create_mcp_server(default_cfg=cfg)
    server.run(transport="stdio")
