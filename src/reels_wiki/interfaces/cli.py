from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from rich.prompt import Confirm, Prompt

from ..core.config import Config, load_config
from ..core.utils import atomic_write_text
from ..ingestion.ig_export import import_ig_export
from ..ingestion.queue_manager import enqueue, queue_stats
from ..pipeline.runner import process_queue, reprocess
from ..vault.digest import generate_digest
from ..vault.search import search_vault
from ..vault.writer import apply_review_action, list_inbox_notes
from .cli_ui import (
    get_console,
    make_progress_callback,
    render_doctor,
    render_error,
    render_import_ig,
    render_ingest,
    render_process_summary,
    render_review_card,
    render_stats,
)
from .http_server import run_http_server
from .mcp_server import run_mcp_server
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


def _emit_json(payload: dict[str, Any]) -> None:
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
    p_process.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent workers for Whisper/LLM synthesis (extraction remains serial).",
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

    # init
    p_init = subparsers.add_parser("init", help="Interactive setup wizard for config.yaml and .env.")
    p_init.add_argument(
        "--env-path",
        type=Path,
        default=None,
        help="Path to .env file (default: <config_dir>/.env).",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config.yaml and .env without confirmation.",
    )

    # telegram
    subparsers.add_parser("telegram", help="Run long-polling Telegram share capture bot.")

    # mcp
    subparsers.add_parser("mcp", help="Run MCP server over stdio.")

    # serve
    p_serve = subparsers.add_parser(
        "serve",
        help="Run local HTTP ingest server for Apple Shortcuts and browser extensions.",
    )
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    p_serve.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765).")

    # digest
    p_digest = subparsers.add_parser("digest", help="Generate a weekly digest note grouping recent vault notes by tag.")
    p_digest.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7).")
    p_digest.add_argument("--tag", default=None, help="Scope digest to notes matching this tag.")
    p_digest.add_argument("--dry-run", action="store_true", help="Preview matched notes without writing a digest file.")

    # search
    p_search = subparsers.add_parser("search", help="Search vault notes via keyword and optional local embeddings.")
    p_search.add_argument("query", help="Search query string.")
    p_search.add_argument("--limit", type=int, default=10, help="Maximum matches to return (default: 10).")
    p_search.add_argument(
        "--backend",
        choices=["none", "ollama", "fastembed"],
        default="none",
        help="Optional embedding backend (default: none).",
    )
    p_search.add_argument("--reindex", action="store_true", help="Rebuild embeddings in sources/.embeddings.sqlite.")

    # review
    p_review = subparsers.add_parser("review", help="Interactively curate status: inbox notes (promote, retag, archive).")
    p_review.add_argument("--limit", type=int, default=None, help="Maximum inbox notes to review.")

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
    api_ok = bool((primary == "groq" and groq_set) or (primary == "gemini" and gemini_set) or primary == "ollama")

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


def run_init(
    config_path: Path,
    env_path: Path,
    *,
    vault_default: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Interactively create config.yaml and .env across a 4-step setup wizard, then run diagnostics."""
    if config_path.exists() and not force:
        if not Confirm.ask(f"{config_path} already exists. Overwrite?", default=False):
            return {"written": False, "config_path": str(config_path), "env_path": str(env_path)}

    con = get_console()

    # Step 1: Obsidian Vault & Folders
    con.print("\n[bold cyan][1/4] Obsidian Vault & Folders[/bold cyan]")
    con.print("[dim]Notes save to <vault_path>/<folder>/<slug>.md with _index.md and _log.md at the vault root.[/dim]")
    vault_str = Prompt.ask(
        "Obsidian vault path",
        default=str(vault_default) if vault_default else "~/Documents/ObsidianVault",
    )
    raw_folders = Prompt.ask(
        "Allowed folders (comma-separated, blank for auto-discovery)",
        default="",
    )
    allowed_folders = [f.strip() for f in raw_folders.split(",") if f.strip()]
    default_folder_hint = allowed_folders[0] if allowed_folders else ""
    default_folder = Prompt.ask(
        "Default fallback folder (blank for auto)",
        default=default_folder_hint,
    ).strip()
    enable_backlinks = Confirm.ask("Enable automatic backlinks in existing notes?", default=False)

    # Step 2: Instagram Extraction & Fallbacks
    con.print("\n[bold cyan][2/4] Instagram Extraction & Fallbacks[/bold cyan]")
    cookie_mode = Prompt.ask(
        "Instagram cookies source",
        choices=["chrome", "firefox", "safari", "file", "skip"],
        default="chrome",
    )
    extraction_cfg: dict[str, Any] = {}
    if cookie_mode in ("chrome", "firefox", "safari"):
        extraction_cfg["cookies_from_browser"] = cookie_mode
    elif cookie_mode == "file":
        extraction_cfg["cookies_file"] = Prompt.ask("Netscape cookies file path", default="~/cookies.txt")

    whisper_mode = Prompt.ask(
        "Audio transcript fallback (Whisper)",
        choices=["groq", "local", "off"],
        default="groq",
    )
    if whisper_mode == "off":
        extraction_cfg["enable_whisper_fallback"] = False
    else:
        extraction_cfg["enable_whisper_fallback"] = True
        extraction_cfg["whisper_provider"] = whisper_mode
        whisper_lang = Prompt.ask("Whisper language (e.g. tr, en, blank for auto)", default="").strip()
        if whisper_lang:
            extraction_cfg["whisper_language"] = whisper_lang

    enable_vision = Confirm.ask("Enable Gemini vision fallback for visual-only Reels?", default=True)
    extraction_cfg["enable_vision_fallback"] = enable_vision

    # Step 3: LLM Synthesis & API Keys
    con.print("\n[bold cyan][3/4] LLM Synthesis & API Keys[/bold cyan]")
    provider = Prompt.ask("Primary LLM provider", choices=["groq", "gemini", "ollama"], default="groq")
    synthesis_cfg: dict[str, Any] = {"provider": provider}
    if provider == "ollama":
        synthesis_cfg["ollama_base_url"] = Prompt.ask("Ollama base URL", default="http://localhost:11434/v1")
        synthesis_cfg["ollama_model"] = Prompt.ask("Ollama model", default="llama3.1:8b")

    fallback = Prompt.ask(
        "Fallback LLM provider",
        choices=["none", "groq", "gemini", "ollama"],
        default="gemini" if provider == "groq" else "none",
    )
    synthesis_cfg["fallback_provider"] = None if fallback == "none" else fallback
    groq_key = Prompt.ask("GROQ_API_KEY (leave blank to skip)", password=True, default="")
    gemini_key = Prompt.ask("GEMINI_API_KEY (leave blank to skip)", password=True, default="")

    # Step 4: Optional Capture & Diagnostics
    con.print("\n[bold cyan][4/4] Optional Capture & Diagnostics[/bold cyan]")
    tg_token = ""
    tg_chat_id = ""
    if Confirm.ask("Configure Telegram capture bot?", default=False):
        tg_token = Prompt.ask("TELEGRAM_BOT_TOKEN", password=True, default="")
        tg_chat_id = Prompt.ask("TELEGRAM_ALLOWED_CHAT_ID", default="")

    cfg_data: dict[str, Any] = {"vault_path": vault_str}
    if allowed_folders:
        cfg_data["allowed_folders"] = allowed_folders
    if default_folder:
        cfg_data["default_folder"] = default_folder
    if enable_backlinks:
        cfg_data["enable_backlinks"] = True
    cfg_data["extraction"] = extraction_cfg
    cfg_data["synthesis"] = synthesis_cfg

    atomic_write_text(config_path, yaml.safe_dump(cfg_data, sort_keys=False))

    if not env_path.exists() or force or Confirm.ask(f"{env_path} already exists. Overwrite?", default=False):
        env_lines = [
            f"GROQ_API_KEY={groq_key or 'your_groq_api_key'}",
            f"GEMINI_API_KEY={gemini_key or 'your_gemini_api_key'}",
            f"TELEGRAM_BOT_TOKEN={tg_token or 'your_telegram_bot_token'}",
        ]
        if tg_chat_id.strip():
            env_lines.append(f"TELEGRAM_ALLOWED_CHAT_ID={tg_chat_id.strip()}")
        else:
            env_lines.append("# TELEGRAM_ALLOWED_CHAT_ID=123456789")
        atomic_write_text(env_path, "\n".join(env_lines) + "\n")
        os.chmod(env_path, 0o600)

    load_dotenv(env_path, override=True)
    cfg = load_config(path=config_path, require_vault=False)
    doctor_res = run_doctor(cfg)
    return {
        "written": True,
        "config_path": str(config_path),
        "env_path": str(env_path),
        "doctor": doctor_res,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(verbose=args.verbose, json_mode=args.json_output)

    try:
        if args.command == "init":
            cfg_path = args.config.expanduser() if args.config else Path.cwd() / "config.yaml"
            env_path = args.env_path.expanduser() if args.env_path else cfg_path.parent / ".env"
            result = run_init(cfg_path, env_path, vault_default=args.vault, force=args.force)
            if args.json_output:
                _emit_json(result)
            elif result.get("doctor"):
                render_doctor(result["doctor"])
            return 0

        cfg = load_config(path=args.config, vault_override=args.vault)

        if args.command == "ingest":
            result = enqueue(
                url=args.url,
                source=args.source,
                vault=cfg.vault_path,
                force=args.force,
            )
            if args.json_output:
                _emit_json(result)
            else:
                render_ingest(result, args.url)
            return 0

        if args.command == "import-ig":
            result = import_ig_export(
                args.export_path,
                vault=cfg.vault_path,
                force=args.force,
                include_posts=not args.reels_only,
            )
            if args.json_output:
                _emit_json(result)
            else:
                render_import_ig(result)
            return 0

        if args.command == "process":
            progress_cb = None if (args.json_output or args.dry_run) else make_progress_callback()
            result = process_queue(
                cfg=cfg,
                limit=args.limit,
                dry_run=args.dry_run,
                retry_failed=args.retry_failed,
                re_extract=args.force,
                workers=args.workers,
                on_event=progress_cb,
            )
            if args.json_output:
                _emit_json(result)
            else:
                render_process_summary(result, title="Process Summary", dry_run=args.dry_run)
            return 0 if result.get("failed", 0) == 0 else 1

        if args.command == "reprocess":
            if not args.shortcode and not args.all:
                parser.error("reprocess requires either a <shortcode> or --all.")
            progress_cb = None if args.json_output else make_progress_callback()
            result = reprocess(
                cfg=cfg,
                shortcodes=[args.shortcode] if args.shortcode else None,
                all_items=args.all,
                on_event=progress_cb,
            )
            if args.json_output:
                _emit_json(result)
            else:
                render_process_summary(result, title="Reprocess Summary", dry_run=args.dry_run)
            return 0 if result.get("failed", 0) == 0 else 1

        if args.command == "stats":
            result = queue_stats(vault=cfg.vault_path)
            if args.json_output:
                _emit_json(result)
            else:
                render_stats(result)
            return 0

        if args.command == "doctor":
            result = run_doctor(cfg)
            if args.json_output:
                _emit_json(result)
            else:
                render_doctor(result)
            return 0 if result["ok"] else 1

        if args.command == "telegram":
            run_telegram_bot(cfg=cfg)
            return 0

        if args.command == "mcp":
            run_mcp_server(cfg=cfg)
            return 0

        if args.command == "serve":
            run_http_server(cfg=cfg, host=args.host, port=args.port)
            return 0

        if args.command == "digest":
            result = generate_digest(cfg.vault_path, days=args.days, tag=args.tag, dry_run=args.dry_run)
            if args.json_output:
                _emit_json(result)
            else:
                print(f"Digest ({result['notes_count']} notes): {result['digest_path'] or 'none'}")
            return 0

        if args.command == "review":
            import frontmatter as _fm

            inbox_paths = list_inbox_notes(cfg.vault_path)
            if args.limit is not None:
                inbox_paths = inbox_paths[: max(args.limit, 0)]
            notes_meta: list[dict[str, Any]] = []
            for p in inbox_paths:
                post = _fm.load(p)
                raw_tags = post.metadata.get("tags")
                tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
                notes_meta.append({
                    "path": p.relative_to(cfg.vault_path).as_posix(),
                    "abs_path": p,
                    "title": str(post.metadata.get("title") or p.stem),
                    "tags": tags,
                    "excerpt": " ".join(post.content.split())[:240],
                })
            if args.json_output:
                payload = [{k: v for k, v in n.items() if k != "abs_path"} for n in notes_meta]
                _emit_json({"count": len(notes_meta), "notes": payload})
                return 0
            for idx, info in enumerate(notes_meta, 1):
                render_review_card(info, idx, len(notes_meta))
                choice = Prompt.ask(
                    "Action [p]romote / [t]ags / [a]rchive / [s]kip / [q]uit",
                    choices=["p", "t", "a", "s", "q"],
                    default="s",
                )
                if choice == "q":
                    break
                if choice == "p":
                    apply_review_action(cfg.vault_path, info["abs_path"], "promote")
                elif choice == "a":
                    apply_review_action(cfg.vault_path, info["abs_path"], "archive")
                elif choice == "t":
                    raw = Prompt.ask("Tags (comma-separated)", default=",".join(info["tags"]))
                    tags_in = [t.strip() for t in raw.split(",") if t.strip()]
                    apply_review_action(cfg.vault_path, info["abs_path"], "retag", new_tags=tags_in)
            return 0

        if args.command == "search":
            result = search_vault(
                cfg.vault_path,
                args.query,
                limit=args.limit,
                backend=args.backend,
                ollama_url=cfg.synthesis.ollama_base_url,
                reindex=args.reindex,
            )
            if args.json_output:
                _emit_json(result)
            else:
                print(f"Matches ({result['count']}):")
                for item in result["matches"]:
                    print(f"- {item['path']} ({item['score']}): {item['snippet']}")
            return 0

        parser.error(f"Unknown command: {args.command}")
        return 2
    except Exception as exc:
        if args.json_output:
            print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False))
        else:
            render_error(exc)
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
