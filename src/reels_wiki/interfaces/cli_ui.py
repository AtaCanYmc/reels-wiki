"""Rich terminal UI helpers for ``reels-sync``. Zero business logic; skipped when ``--json`` is active."""
from __future__ import annotations

from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_STATUS_STYLE: dict[str, str] = {
    "processed": "bold green",
    "enqueued": "bold green",
    "pass": "bold green",
    "pending": "cyan",
    "processing": "yellow",
    "skipped": "yellow",
    "warn": "bold yellow",
    "failed": "bold red",
    "fail": "bold red",
}


def get_console(*, stderr: bool = False) -> Console:
    """Create a Console bound to the current stdout/stderr stream."""
    return Console(stderr=stderr, highlight=False, soft_wrap=True)


def _badge(label: str, style: str | None = None) -> Text:
    resolved = style or _STATUS_STYLE.get(label.lower(), "white")
    return Text(label.upper(), style=resolved)


def render_ingest(result: dict[str, Any], url: str, console: Console | None = None) -> None:
    con = console or get_console()
    enqueued = bool(result.get("enqueued"))
    status_label = "ENQUEUED" if enqueued else f"SKIPPED ({result.get('reason', 'duplicate')})"
    border = "green" if enqueued else "yellow"
    sc = str(result.get("shortcode", "?"))
    canon = str(result.get("url", url))

    body = Text()
    body.append_text(_badge(status_label, "bold green" if enqueued else "bold yellow"))
    body.append(f"  [{sc}]\n", style="bold cyan")
    body.append(canon, style="dim")
    con.print(Panel(body, title="Ingest", border_style=border, expand=False))


def render_import_ig(result: dict[str, Any], console: Console | None = None) -> None:
    con = console or get_console()
    table = Table(title="Instagram Export Import", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    for label, key, style in (
        ("Found URLs", "found", "white"),
        ("Enqueued", "enqueued", "green"),
        ("Duplicates", "duplicates", "yellow"),
        ("Ignored", "ignored", "dim"),
    ):
        table.add_row(label, Text(str(result.get(key, 0)), style=style))

    con.print(table)


def render_stats(result: dict[str, Any], console: Console | None = None) -> None:
    con = console or get_console()
    counts = result.get("counts", {})

    table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=False)
    table.add_column("Queue State", style="bold")
    table.add_column("Count", justify="right")

    for state in ("pending", "processing", "processed", "skipped", "failed"):
        val = str(counts.get(state, 0))
        table.add_row(state.capitalize(), Text(val, style=_STATUS_STYLE.get(state, "white")))

    table.add_section()
    table.add_row("Total Indexed", Text(str(result.get("total_indexed", 0)), style="bold"))
    table.add_row("Stored Artifacts", Text(str(result.get("artifacts_count", 0)), style="bold cyan"))

    vault = str(result.get("vault_path", ""))
    con.print(Panel(table, title="reels-wiki Vault Stats", subtitle=vault, border_style="cyan", expand=False))


def render_doctor(result: dict[str, Any], console: Console | None = None) -> None:
    con = console or get_console()
    table = Table(title="reels-wiki Diagnostics", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Detail")
    table.add_column("Action", style="dim")

    py = result["python"]
    ff = result["ffmpeg"]
    ck = result["cookies"]
    ak = result["api_keys"]
    vl = result["vault"]

    cookie_detail = (
        f"browser={ck['cookies_from_browser']}"
        if ck.get("cookies_from_browser")
        else (str(ck["cookies_file"]) if ck.get("cookies_file") else "not configured")
    )
    rows = [
        (
            "Python",
            "PASS" if py["ok"] else "FAIL",
            f"v{py['version']}",
            "" if py["ok"] else "Upgrade to Python >= 3.10",
        ),
        (
            "ffmpeg",
            "PASS" if ff["ok"] else "WARN",
            ff["path"] or "not found",
            "" if ff["ok"] else "Install ffmpeg for audio/vision fallback",
        ),
        (
            "Cookies",
            "PASS" if ck["ok"] else "WARN",
            cookie_detail,
            "" if ck["ok"] else "Set cookies_from_browser or cookies_file in config.yaml",
        ),
        (
            "API Keys",
            "PASS" if ak["ok"] else "FAIL",
            f"primary={ak['primary_provider']} (groq={ak['groq_configured']}, gemini={ak['gemini_configured']})",
            "" if ak["ok"] else "Set GROQ_API_KEY or GEMINI_API_KEY in .env",
        ),
        (
            "Vault",
            "PASS" if vl["ok"] else "FAIL",
            f"{vl['path']} ({'writable' if vl['writable'] else 'not writable/missing'})",
            "" if vl["ok"] else "Verify vault_path exists and is writable",
        ),
    ]

    for check, status, detail, action in rows:
        table.add_row(check, _badge(status), detail, action)

    con.print(table)
    overall = "All required checks passed." if result.get("ok") else "One or more required checks failed."
    con.print(overall, style="bold green" if result.get("ok") else "bold red")


def render_process_summary(
    result: dict[str, Any],
    *,
    title: str = "Process Summary",
    dry_run: bool = False,
    console: Console | None = None,
) -> None:
    con = console or get_console()

    if result.get("error"):
        con.print(Panel(str(result["error"]), title=title, border_style="red", expand=False))
        return

    mode = " (dry-run)" if dry_run else ""
    summary_line = (
        f"selected={result.get('selected', 0)}  "
        f"processed={result.get('processed', 0)}  "
        f"skipped={result.get('skipped', 0)}  "
        f"failed={result.get('failed', 0)}"
    )
    if result.get("recovered_stale"):
        summary_line += f"  recovered_stale={result['recovered_stale']}"

    results: list[dict[str, Any]] = result.get("results") or []
    if not results:
        con.print(Panel(summary_line, title=f"{title}{mode}", border_style="cyan", expand=False))
        return

    table = Table(title=f"{title}{mode}", caption=summary_line, show_header=True, header_style="bold cyan")
    table.add_column("Shortcode", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")

    for row in results:
        sc = str(row.get("shortcode", "?"))
        st = str(row.get("status", "unknown"))
        detail = str(
            row.get("note_path")
            or row.get("skip_reason")
            or row.get("reason")
            or row.get("error")
            or row.get("url")
            or ""
        )
        table.add_row(sc, _badge(st), detail)

    con.print(table)


def make_progress_callback(console: Console | None = None) -> Callable[[dict[str, Any]], None]:
    """Return an ``on_event`` callback that streams live per-item status to the terminal."""
    con = console or get_console()

    def _on_event(item: dict[str, Any]) -> None:
        sc = str(item.get("shortcode", "?"))
        st = str(item.get("status", "unknown"))
        detail = str(item.get("note_path") or item.get("skip_reason") or item.get("error") or "")
        line = Text("  ")
        line.append_text(_badge(st))
        line.append(f"  {sc}", style="bold cyan")
        if detail:
            line.append(f"  {detail}", style="dim")
        con.print(line)

    return _on_event


def render_error(exc: Exception, console: Console | None = None) -> None:
    con = console or get_console(stderr=True)
    con.print(Panel(f"{type(exc).__name__}: {exc}", title="Error", border_style="red", expand=False))
