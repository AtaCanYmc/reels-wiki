from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from .config import Config, load_config
from .ig_export import import_ig_export
from .pipeline import process_queue
from .queue_manager import enqueue, queue_stats


def create_mcp_server(default_cfg: Config | None = None) -> FastMCP:
    base_cfg = default_cfg or load_config()
    mcp = FastMCP("reels-wiki")

    def _resolve_cfg(vault_path: str | None = None) -> Config:
        override = Path(vault_path).expanduser() if vault_path else None
        if override is None:
            return base_cfg
        return load_config(path=getattr(base_cfg, "config_path", None), vault_override=override)

    @mcp.tool()
    def enqueue_reel(
        url: str,
        source: str = "mcp",
        force: bool = False,
        vault_path: str | None = None,
    ) -> dict[str, Any]:
        """Enqueue an Instagram Reel/post URL into the Obsidian vault queue with shortcode deduplication."""
        cfg = _resolve_cfg(vault_path)
        return enqueue(url=url, source=source, vault=cfg.vault_path, force=force)

    @mcp.tool()
    def import_ig_export(
        export_path: str,
        reels_only: bool = False,
        force: bool = False,
        vault_path: str | None = None,
    ) -> dict[str, Any]:
        """Bulk-import saved Instagram URLs from saved_posts.json or an export directory."""
        cfg = _resolve_cfg(vault_path)
        return import_ig_export(
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
        return queue_stats(vault=cfg.vault_path)

    return mcp


def run_mcp_server(cfg: Config | None = None) -> None:
    server = create_mcp_server(default_cfg=cfg)
    server.run(transport="stdio")
