"""Safe Obsidian writer: valid YAML frontmatter, idempotent ``_index.md`` updates, ``_log.md`` entries."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter

from .models import AtomicNoteSynthesis, RawReelArtifact
from .queue_manager import QueueManager
from .utils import atomic_write_text, normalize_key, one_line
from .vault_context import VaultContext

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LOG_HEADING_STYLE_RE = re.compile(r"^##\s+\[\d{4}-\d{2}-\d{2}\]", re.M)


class WriterError(RuntimeError):
    """The note could not be written safely."""


# ---------------------------------------------------------------------- note rendering
def _quote(text: str) -> str:
    text = text.strip().replace("</details>", "&lt;/details&gt;")
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines())


def render_body(
    artifact: RawReelArtifact,
    syn: AtomicNoteSynthesis,
    existing_links: list[str],
    candidates: list[str],
) -> str:
    creator = f"@{artifact.creator.lstrip('@')}" if artifact.creator else "unknown creator"
    agent = "\n".join(f"- {b}" for b in syn.for_future_agent) or "- (no extra context captured)"
    links = [f"- [[{name}]]" for name in existing_links]
    links += [f"- (new note candidate) {name}" for name in candidates]
    links.append(f"- Source: [Instagram Reel by {creator}]({artifact.url})")

    raw_parts: list[str] = []
    if artifact.caption.strip():
        raw_parts.append(f"**Caption**\n\n{_quote(artifact.caption)}")
    if artifact.transcript.strip():
        raw_parts.append(f"**Transcript** ({artifact.transcript_source})\n\n{_quote(artifact.transcript)}")
    if artifact.visual_notes.strip():
        raw_parts.append(f"**On-screen text / visuals**\n\n{_quote(artifact.visual_notes)}")
    raw = "\n\n".join(raw_parts) or "_(no raw text captured)_"

    return (
        f"## For Future Agent\n{agent}\n\n"
        f"## Core Insight\n{syn.core_insight.strip()}\n\n"
        f"## Actionable Next Step\n{syn.actionable_next_step.strip() or '_(none)_'}\n\n"
        f"## Related Links\n" + "\n".join(links) + "\n\n"
        f"<details>\n<summary>Raw source (caption / transcript)</summary>\n\n{raw}\n\n</details>\n"
    )


def _read_post(path: Path) -> frontmatter.Post | None:
    try:
        return frontmatter.load(path)
    except Exception:  # noqa: BLE001 - unreadable/foreign file: treat as "not ours"
        return None


def _choose_path(ctx: VaultContext, syn: AtomicNoteSynthesis, artifact: RawReelArtifact, overwrite: str | Path | None) -> Path:
    root = ctx.root.resolve()

    def _ensure_in_vault(resolved: Path) -> Path:
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise WriterError(f"Refusing to write outside the vault: {resolved}") from exc
        return resolved

    def safe(folder: str, slug: str) -> Path:
        return _ensure_in_vault((root / folder / f"{slug}.md").resolve())

    if overwrite:
        p = Path(overwrite)
        resolved = _ensure_in_vault((p if p.is_absolute() else root / p).resolve())
        if resolved.is_file():
            return resolved
    target = safe(syn.target_folder or ctx.default_folder, syn.slug)
    if target.exists():
        post = _read_post(target)
        if post is not None and post.metadata.get("shortcode") == artifact.shortcode:
            return target  # same reel: update in place
        target = safe(syn.target_folder or ctx.default_folder, f"{syn.slug}-{artifact.shortcode.lower()}")
    return target


# ---------------------------------------------------------------------- _log.md / _index.md
def append_log(vault: Path, *, slug: str, title: str, artifact: RawReelArtifact, action: str, now: datetime) -> None:
    """Append one chronological entry, matching the vault's existing log style when it has one."""
    path = Path(vault) / "_log.md"
    exists = path.exists()
    existing = path.read_text(encoding="utf-8") if exists else "# Log\n\n"
    if _LOG_HEADING_STYLE_RE.search(existing):  # vault already uses "## [YYYY-MM-DD] verb | title" entries
        entry = (f"\n## [{now:%Y-%m-%d}] {action} | {title}\n"
                 f"- Source: reels/{artifact.shortcode} ({artifact.url})\n- Note: [[{slug}]]\n")
    else:
        entry = f"- {now:%Y-%m-%d %H:%M} — reels-sync {action}: [[{slug}]] — {one_line(title, 100)} (`{artifact.shortcode}`)\n"
    if not exists:
        atomic_write_text(path, existing + entry.lstrip("\n"))
        return
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(("" if existing.endswith("\n") else "\n") + entry)


def _section_bounds(lines: list[str], folder: str) -> tuple[int, int] | None:
    fkey = normalize_key(folder.split("/")[-1])
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        hkey = normalize_key(re.sub(r"[(\[].*?[)\]]", "", m.group(2)))
        if hkey and (hkey == fkey or hkey.rstrip("s") == fkey.rstrip("s")):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if _HEADING_RE.match(lines[j]):
                    end = j
                    break
            return i, end
    return None


def update_index(vault: Path, folder: str, slug: str, title: str, summary: str) -> bool:
    """Insert ``- [[slug|Title]] — summary`` under the heading matching ``folder``. Returns False if already present."""
    path = Path(vault) / "_index.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Index\n"
    if re.search(r"\[\[" + re.escape(slug) + r"(?:\|[^\]]*)?\]\]", text):
        return False
    entry = f"- [[{slug}|{title}]] — {one_line(summary, 140)}"
    lines = text.splitlines()
    bounds = _section_bounds(lines, folder)
    if bounds:
        start, end = bounds
        last = start
        for k in range(start + 1, end):
            if lines[k].strip():
                last = k
        if last == start:  # empty section
            lines[start + 1 : start + 1] = ["", entry]
        else:
            lines.insert(last + 1, entry)
    else:
        label = folder.split("/")[-1].replace("-", " ").replace("_", " ").title()
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"## {label}", "", entry]
    atomic_write_text(path, "\n".join(lines) + "\n")
    return True


# ---------------------------------------------------------------------- main entry point
def write_synthesis(
    queue: QueueManager,
    ctx: VaultContext,
    artifact: RawReelArtifact,
    syn: AtomicNoteSynthesis,
    *,
    overwrite_path: str | Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Apply a synthesis: skip (status only) or write note + log + index + status. Idempotent."""
    now = now or datetime.now()
    sc = artifact.shortcode

    if not syn.should_keep:
        reason = (syn.skip_reason or "Not worth keeping").strip()
        queue.update_status(sc, "skipped", skip_reason=reason)
        return {"status": "skipped", "shortcode": sc, "skip_reason": reason, "note_path": None}

    path = _choose_path(ctx, syn, artifact, overwrite_path)
    existing_links, candidates = ctx.resolve_wikilinks(syn.related_wikilinks)
    existing_links = [n for n in existing_links if n != path.stem]
    updating = path.exists()

    created, status = f"{now:%Y-%m-%d}", "inbox"
    if updating:
        old = _read_post(path)
        if old is not None:  # preserve what the human may have changed
            created = str(old.metadata.get("created") or created)
            status = str(old.metadata.get("status") or status)

    meta: dict[str, Any] = {
        "title": syn.title.strip(),
        "source_url": artifact.url,
        "creator": f"@{artifact.creator.lstrip('@')}" if artifact.creator else None,
        "shortcode": sc,
        "created": created,
        "type": "atomic-idea",
        "status": status,
        "tags": list(syn.tags),
    }
    post = frontmatter.Post(render_body(artifact, syn, existing_links, candidates), **meta)
    atomic_write_text(path, frontmatter.dumps(post, sort_keys=False).rstrip("\n") + "\n")

    rel = path.relative_to(ctx.root).as_posix()
    folder = path.parent.relative_to(ctx.root).as_posix()
    action = "update" if updating else "ingest"
    append_log(ctx.root, slug=path.stem, title=syn.title.strip(), artifact=artifact, action=action, now=now)
    index_updated = update_index(ctx.root, folder, path.stem, syn.title.strip(), syn.core_insight)
    queue.update_status(sc, "processed", note_path=rel)
    return {"status": "processed", "shortcode": sc, "note_path": rel, "index_updated": index_updated, "updated_existing": updating}
