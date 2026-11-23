from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .ig_export import import_ig_export
from .mcp_server import run_mcp_server
from .pipeline import process_queue, reprocess
from .queue_manager import enqueue, queue_stats
from .telegram_bot import run_telegram_bot

logger = logging.getLogger("reels_wiki.cli")


def _configure_logging(verbose: bool, json_mode: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    stream = sys.stderr if json_mode else sys.stdout
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=stream,
    )


def _emit(payload: dict[str, Any], json_mode: bool, human_lines: list[str] | None = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return
    if human_lines:
        for line in human_lines:
            print(line)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reels-sync",
        description="Turn saved Instagram Reels into atomic Obsidian LLM Wiki notes.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (overrides REELS_WIKI_CONFIG and default search paths).",
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help="Override Obsidian vault path (overrides REELS_WIKI_VAULT and config vault_path).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON output (place before subcommand).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Enqueue a single Instagram Reel/post URL.")
    p_ingest.add_argument("url", help="Instagram Reel, post, or TV URL.")
    p_ingest.add_argument(
        "--source",
        default="cli",
        help="Ingestion source label (default: cli).",
    )
    p_ingest.add_argument(
        "--force",
        action="store_true",
        help="Re-enqueue even if shortcode already exists in index.",
    )

    # import-ig
    p_import = subparsers.add_parser(
        "import-ig",
        help="Bulk-import URLs from Instagram data export (saved_posts.json or directory).",
    )
    p_import.add_argument("export_path", type=Path, help="Path to saved_posts.json or export folder.")
    p_import.add_argument(
        "--reels-only",
        action="store_true",
        help="Skip /p/ photo/carousel posts and keep only /reel/ or /reels/ links.",
    )
    p_import.add_argument(
        "--force",
        action="store_true",
        help="Re-enqueue items already present in the index.",
    )

    # process
    p_process = subparsers.add_parser(
        "process",
        help="Run waterfall extraction, LLM synthesis, and Obsidian note writing.",
    )
    p_process.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of queue items to process in this run.",
    )
    p_process.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be processed without writing notes or mutating state.",
    )
    p_process.add_argument(
        "--retry-failed",
        action="store_true",
        help="Include previously failed items in addition to pending items.",
    )
    p_process.add_argument(
        "--force",
        action="store_true",
        help="Re-process items and overwrite existing note_path if present.",
    )

    # reprocess
    p_reprocess = subparsers.add_parser(
        "reprocess",
        help="Re-synthesize from stored sources/reels/<code>.json without downloading media.",
    )
    p_reprocess.add_argument(
        "shortcode",
        nargs="?",
        default=None,
        help="11-character Instagram shortcode to re-synthesize.",
    )
    p_reprocess.add_argument(
        "--all",
        action="store_true",
        help="Re-synthesize all stored raw artifacts in sources/reels/.",
    )
    p_reprocess.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview re-synthesis without writing files.",
    )

    # stats
    subparsers.add_parser("stats", help="Show queue counts, index status breakdown, and vault info.")

    # doctor
    subparsers.add_parser("doctor", help="Verify runtime dependencies, cookies, API keys, and vault permissions.")

    # telegram
    subparsers.add_parser("telegram", help="Run long-polling Telegram share capture bot.")

    # mcp
    subparsers.add_parser("mcp", help="Run MCP server over stdio.")

    return parser


def run_doctor(cfg: Config) -> dict[str, Any]:
    """Check Python version, ffmpeg, cookie configuration, API key presence, and vault permissions."""
    py_ok = sys.version_info >= (3, 10)
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    ffmpeg_path = shutil.which(cfg.extraction.ffmpeg_path)

    browser = cfg.extraction.cookies_from_browser
    cookies_file = cfg.extraction.cookies_file
    cookies_file_exists = bool(cookies_file and Path(cookies_file).expanduser().is_file())
    cookies_ok = bool(browser or cookies_file_exists)

    groq_set = bool(getattr(cfg, "groq_api_key", None) or os.getenv("GROQ_API_KEY"))
    gemini_set = bool(getattr(cfg, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY"))
    primary = cfg.synthesis.provider
    fallback = cfg.synthesis.fallback_provider
    api_ok = bool((primary == "groq" and groq_set) or (primary == "gemini" and gemini_set))

    vault_dir = Path(cfg.vault_path)
    vault_exists = vault_dir.is_dir()
    vault_writable = vault_exists and os.access(vault_dir, os.W_OK)

    overall_ok = bool(py_ok and vault_writable and api_ok)
    return {
        "ok": overall_ok,
        "python": {"ok": py_ok, "version": py_ver},
        "ffmpeg": {"ok": bool(ffmpeg_path), "path": ffmpeg_path},
        "cookies": {
            "ok": cookies_ok,
            "cookies_from_browser": browser,
            "cookies_file": str(cookies_file) if cookies_file else None,
            "cookies_file_exists": cookies_file_exists,
        },
        "api_keys": {
            "ok": api_ok,
            "primary_provider": primary,
            "fallback_provider": fallback,
            "groq_configured": groq_set,
            "gemini_configured": gemini_set,
        },
        "vault": {
            "ok": vault_writable,
            "path": str(vault_dir),
            "exists": vault_exists,
            "writable": vault_writable,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(verbose=args.verbose, json_mode=args.json_output)

    try:
        cfg = load_config(path=args.config, vault_override=args.vault)

        if args.command == "ingest":
            result = enqueue(
                url=args.url,
                source=args.source,
                vault=cfg.vault_path,
                force=args.force,
            )
            status_msg = "enqueued" if result.get("enqueued") else f"skipped ({result.get('reason', 'duplicate')})"
            _emit(
                result,
                args.json_output,
                [f"[{status_msg}] {result.get('shortcode', '?')} -> {result.get('url', args.url)}"],
            )
            return 0

        if args.command == "import-ig":
            result = import_ig_export(
                args.export_path,
                vault=cfg.vault_path,
                force=args.force,
                include_posts=not args.reels_only,
            )
            _emit(
                result,
                args.json_output,
                [
                    f"IG export imported: found={result.get('found', 0)}, "
                    f"enqueued={result.get('enqueued', 0)}, "
                    f"duplicates={result.get('duplicates', 0)}, "
                    f"ignored={result.get('ignored', 0)}"
                ],
            )
            return 0

        if args.command == "process":
            result = process_queue(
                cfg=cfg,
                limit=args.limit,
                dry_run=args.dry_run,
                retry_failed=args.retry_failed,
                re_extract=args.force,
            )
            _emit(
                result,
                args.json_output,
                [
                    f"Process complete (dry_run={args.dry_run}): "
                    f"selected={result.get('selected', 0)}, "
                    f"processed={result.get('processed', 0)}, "
                    f"skipped={result.get('skipped', 0)}, "
                    f"failed={result.get('failed', 0)}"
                ],
            )
            return 0 if result.get("failed", 0) == 0 else 1

        if args.command == "reprocess":
            if not args.shortcode and not args.all:
                parser.error("reprocess requires either a <shortcode> or --all.")
            result = reprocess(
                cfg=cfg,
                shortcodes=[args.shortcode] if args.shortcode else None,
                all_items=args.all,
            )
            _emit(
                result,
                args.json_output,
                [
                    f"Reprocess complete (dry_run={args.dry_run}): "
                    f"reprocessed={result.get('reprocessed', 0)}, "
                    f"skipped={result.get('skipped', 0)}, "
                    f"failed={result.get('failed', 0)}"
                ],
            )
            return 0

        if args.command == "stats":
            result = queue_stats(vault=cfg.vault_path)
            counts = result.get("counts", {})
            _emit(
                result,
                args.json_output,
                [
                    f"Vault: {result.get('vault_path')}",
                    f"Index total: {result.get('total_indexed', 0)} | "
                    f"pending={counts.get('pending', 0)}, "
                    f"processing={counts.get('processing', 0)}, "
                    f"processed={counts.get('processed', 0)}, "
                    f"skipped={counts.get('skipped', 0)}, "
                    f"failed={counts.get('failed', 0)}",
                    f"Stored artifacts: {result.get('artifacts_count', 0)}",
                ],
            )
            return 0

        if args.command == "doctor":
            result = run_doctor(cfg)
            _emit(
                result,
                args.json_output,
                [
                    f"Python:   {result['python']['version']} ({'ok' if result['python']['ok'] else 'fail'})",
                    f"ffmpeg:   {result['ffmpeg']['path'] or 'missing (optional unless audio/vision fallback runs)'}",
                    f"Cookies:  {'ok' if result['cookies']['ok'] else 'missing (set cookies_from_browser or cookies_file)'}",
                    f"API keys: primary={result['api_keys']['primary_provider']} ({'ok' if result['api_keys']['ok'] else 'missing'})",
                    f"Vault:    {result['vault']['path']} ({'writable' if result['vault']['writable'] else 'not writable/missing'})",
                ],
            )
            return 0 if result["ok"] else 1

        if args.command == "telegram":
            run_telegram_bot(cfg=cfg)
            return 0

        if args.command == "mcp":
            run_mcp_server(cfg=cfg)
            return 0

        parser.error(f"Unknown command: {args.command}")
        return 2
    except Exception as exc:
        if args.json_output:
            print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        logger.debug("CLI failure", exc_info=exc)
        return 1


def mcp_main() -> int:
    """Entry point for `reels-wiki-mcp` script."""
    cfg = load_config()
    run_mcp_server(cfg=cfg)
    return 0


def telegram_main() -> int:
    """Entry point for `reels-wiki-telegram` script."""
    cfg = load_config()
    run_telegram_bot(cfg=cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
