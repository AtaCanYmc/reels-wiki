from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef,attr-defined]

from ..core.config import Config, load_config
from ..ingestion.ig_export import import_ig_export as _import_ig_export
from ..ingestion.queue_manager import enqueue, queue_stats
from ..pipeline.runner import process_queue, reprocess


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
        return _import_ig_export(
            Path(export_path).expanduser(),
            vault=cfg.vault_path,
            force=force,
            include_posts=not reels_only,
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
            re_extract=force,
        )

    @mcp.tool()
    def get_queue_stats(vault_path: str | None = None) -> dict[str, Any]:
        """Return queue counts, index status breakdown, and raw artifact counts for the vault."""
        cfg = _resolve_cfg(vault_path)
        return queue_stats(vault=cfg.vault_path)

    @mcp.tool()
    def reprocess_reel(
        shortcode: str | None = None,
        all_items: bool = False,
        vault_path: str | None = None,
    ) -> dict[str, Any]:
        """Re-synthesize notes from stored sources/reels/<shortcode>.json artifacts without downloading media."""
        cfg = _resolve_cfg(vault_path)
        if not shortcode and not all_items:
            return {"error": "Provide a shortcode or set all_items=True."}
        return reprocess(
            cfg=cfg,
            shortcodes=[shortcode] if shortcode else None,
            all_items=all_items,
        )

    @mcp.tool()
    def search_vault_notes(
        query: str,
        limit: int = 10,
        vault_path: str | None = None,
    ) -> dict[str, Any]:
        """Search Markdown notes inside the Obsidian vault (excluding sources/ and inbox/)."""
        cfg = _resolve_cfg(vault_path)
        root = cfg.vault_path.resolve()
        needle = query.strip().lower()
        matches: list[dict[str, str]] = []
        if not needle or not root.is_dir():
            return {"query": query, "count": 0, "matches": matches}
        max_hits = max(limit, 1)
        for path in sorted(root.rglob("*.md")):
            resolved = path.resolve()
            try:
                rel = resolved.relative_to(root)
            except ValueError:
                continue
            if rel.parts[0] in {"sources", "inbox"} or any(p.startswith(".") for p in rel.parts):
                continue
            try:
                text = resolved.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            idx = text.lower().find(needle)
            if idx != -1:
                start = max(0, idx - 60)
                snippet = " ".join(text[start : idx + len(needle) + 120].split())
                matches.append({"path": rel.as_posix(), "snippet": snippet})
                if len(matches) >= max_hits:
                    break
        return {"query": query, "count": len(matches), "matches": matches}

    return mcp


def run_mcp_server(cfg: Config | None = None) -> None:
    server = create_mcp_server(default_cfg=cfg)
    server.run(transport="stdio")
