"""``reels-sync`` command line interface."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer

from .config import Config, ConfigError, load_config

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Saved Instagram Reels -> Obsidian LLM Wiki atomic notes.")


def _state(ctx: typer.Context) -> dict:
    return ctx.obj or {}


def _cfg(ctx: typer.Context, *, require_vault: bool = True) -> Config:
    st = _state(ctx)
    try:
        return load_config(st.get("config"), vault_override=st.get("vault"), require_vault=require_vault)
    except ConfigError as exc:
        typer.secho(f"Config error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)


def _emit(ctx: typer.Context, data: dict, human: str) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2) if _state(ctx).get("json") else human)


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.yaml (or $REELS_WIKI_CONFIG)."),
    vault: Optional[Path] = typer.Option(None, "--vault", help="Override vault_path (or $REELS_WIKI_VAULT)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output (for agents)."),
) -> None:
    ctx.obj = {"config": config, "vault": vault, "json": json_output}


@app.command()
def ingest(
    ctx: typer.Context,
    urls: List[str] = typer.Argument(..., help="Instagram reel/post URL(s)."),
    source: str = typer.Option("manual", help="Source label stored in the queue."),
    force: bool = typer.Option(False, "--force", help="Re-enqueue even if the shortcode is already known."),
) -> None:
    """Enqueue one or more Instagram URLs (deduplicated by shortcode)."""
    from .queue_manager import QueueManager

    queue = QueueManager(_cfg(ctx).vault_path)
    results = [queue.enqueue(u, source=source, force=force) for u in urls]
    lines = [f"[{r['result']}] {r.get('shortcode') or r['url']} — {r['message']}" for r in results]
    _emit(ctx, {"results": results}, "\n".join(lines))
    if any(r["result"] == "invalid" for r in results):
        raise typer.Exit(1)


@app.command("import-ig")
def import_ig(
    ctx: typer.Context,
    path: Path = typer.Argument(..., exists=True, help="saved_posts.json (or the export folder containing it)."),
    force: bool = typer.Option(False, "--force", help="Re-enqueue shortcodes that are already known."),
    reels_only: bool = typer.Option(False, "--reels-only", help="Ignore /p/ post links."),
) -> None:
    """Bulk-enqueue everything from Instagram's official data export."""
    from .ig_export import import_ig_export

    try:
        res = import_ig_export(path, vault=_cfg(ctx).vault_path, force=force, include_posts=not reels_only)
    except (OSError, ValueError) as exc:
        typer.secho(f"Import failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    _emit(ctx, res, f"{res['instagram_media_links']} Instagram links found -> {res['enqueued']} enqueued, "
                    f"{res['duplicates']} duplicates, {res['ignored_links']} ignored")


@app.command()
def process(
    ctx: typer.Context,
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Process at most N items."),
    retry_failed: bool = typer.Option(False, "--retry-failed", help="Also retry items in 'failed' state."),
    re_extract: bool = typer.Option(False, "--re-extract", help="Ignore stored artifacts and download again."),
    dry_run: bool = typer.Option(False, "--dry-run", help="List what would be processed."),
) -> None:
    """Run the extraction -> synthesis -> write pipeline over pending queue items."""
    from .pipeline import process_queue

    cfg = _cfg(ctx)

    def show(r: dict) -> None:
        if not _state(ctx).get("json"):
            detail = r.get("note_path") or r.get("skip_reason") or r.get("error") or ""
            typer.echo(f"[{r['status']}] {r['shortcode']} {detail}")

    res = process_queue(cfg, limit=limit, retry_failed=retry_failed, re_extract=re_extract, dry_run=dry_run, on_event=show)
    if res.get("error"):
        typer.secho(res["error"], fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    _emit(ctx, res, f"Done: {res['processed']} written, {res['skipped']} skipped, {res['failed']} failed "
                    f"(of {res['selected']} selected)" + (" [dry run]" if dry_run else ""))
    if res["failed"]:
        raise typer.Exit(1)


@app.command()
def reprocess(
    ctx: typer.Context,
    shortcodes: Optional[List[str]] = typer.Argument(None, help="Shortcodes to re-synthesize from stored artifacts."),
    all_items: bool = typer.Option(False, "--all", help="Re-synthesize every item that has a stored artifact."),
) -> None:
    """Re-run synthesis + writing from sources/reels/*.json (no downloads, no transcription)."""
    from .pipeline import reprocess as run

    if not shortcodes and not all_items:
        typer.secho("Give one or more shortcodes, or --all.", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    res = run(_cfg(ctx), shortcodes, all_items=all_items,
              on_event=lambda r: None if _state(ctx).get("json") else typer.echo(f"[{r['status']}] {r['shortcode']} {r.get('note_path') or r.get('error') or r.get('skip_reason') or ''}"))
    _emit(ctx, res, f"Done: {res['processed']} written, {res['skipped']} skipped, {res['failed']} failed")
    if res["failed"]:
        raise typer.Exit(1)


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show queue counts by status and source."""
    from .queue_manager import QueueManager

    s = QueueManager(_cfg(ctx).vault_path).stats()
    sources = ", ".join(f"{k}={v}" for k, v in sorted(s["by_source"].items())) or "-"
    _emit(ctx, s, (f"total={s['total']}  pending={s['pending']}  processing={s['processing']}  processed={s['processed']}  "
                   f"skipped={s['skipped']}  failed={s['failed']}\nsources: {sources}"))


@app.command()
def telegram(ctx: typer.Context) -> None:
    """Run the Telegram share-capture bot (long polling)."""
    from .telegram_bot import run_bot

    run_bot(_cfg(ctx))


@app.command()
def mcp(ctx: typer.Context) -> None:
    """Run the MCP server over stdio."""
    from .mcp_server import main as serve

    serve()


if __name__ == "__main__":
    app()
