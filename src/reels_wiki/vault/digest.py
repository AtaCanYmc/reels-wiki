"""Weekly digest generator grouping recent atomic Obsidian notes by tag and folder."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import frontmatter

from ..core.utils import atomic_write_text, slugify

_SKIP_DIRS = {"sources", "inbox", "digests"}
_SKIP_FILES = {"_index.md", "_log.md", "_CLAUDE.md"}


def _note_date(post: frontmatter.Post, path: Path) -> date:
    raw = str(post.metadata.get("created") or "").strip()[:10]
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def generate_digest(
    vault: Path,
    *,
    days: int = 7,
    tag: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Scan recent vault notes from the last ``days`` days and write a digest note grouped by tag."""
    root = Path(vault).expanduser().resolve()
    ref_day = (now or datetime.now()).date()
    cutoff = ref_day - timedelta(days=max(days, 1) - 1)
    tag_filter = (slugify(tag.lstrip("#")) or tag.strip().lower()) if tag and tag.strip() else None

    by_tag: dict[str, list[dict[str, str]]] = defaultdict(list)
    notes: list[dict[str, Any]] = []

    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if rel.name in _SKIP_FILES or rel.parts[0] in _SKIP_DIRS or any(p.startswith(".") for p in rel.parts):
            continue
        try:
            post = frontmatter.load(path)
        except Exception:  # noqa: BLE001 - skip malformed markdown files
            continue
        created = _note_date(post, path)
        if created < cutoff or created > ref_day:
            continue
        title = str(post.metadata.get("title") or path.stem)
        raw_tags = post.metadata.get("tags")
        tags = [str(t) for t in raw_tags if str(t).strip()] if isinstance(raw_tags, list) else []
        norm_tags = [slugify(t.lstrip("#")) or t.strip().lower() for t in tags]
        if tag_filter and tag_filter not in norm_tags:
            continue
        entry = {"slug": path.stem, "title": title, "path": rel.as_posix(), "created": created.isoformat()}
        notes.append({**entry, "tags": tags})
        for note_tag in tags or ["untagged"]:
            by_tag[note_tag].append(entry)

    out_rel = f"digests/{ref_day.isoformat()}-{tag_filter}-digest.md" if tag_filter else f"digests/{ref_day.isoformat()}-digest.md"
    heading_label = f"Topic Digest (#{tag_filter})" if tag_filter else "Weekly Knowledge Digest"
    fm_tags = f"[digest, {tag_filter}]" if tag_filter else "[digest, weekly]"
    if not dry_run and notes:
        lines = [
            f"---\ntitle: {heading_label} ({cutoff.isoformat()} to {ref_day.isoformat()})\n"
            f"created: {ref_day.isoformat()}\ntype: digest\ntags: {fm_tags}\n---\n",
            f"# {heading_label} ({cutoff.isoformat()} to {ref_day.isoformat()})\n",
            f"Total notes: {len(notes)}\n",
        ]
        for group_tag in sorted(by_tag):
            lines.append(f"\n## #{group_tag}\n")
            for item in by_tag[group_tag]:
                lines.append(f"- [[{item['slug']}|{item['title']}]] ({item['created']})")
        atomic_write_text(root / out_rel, "\n".join(lines) + "\n")

    return {
        "vault": str(root),
        "days": days,
        "tag": tag_filter,
        "from_date": cutoff.isoformat(),
        "to_date": ref_day.isoformat(),
        "notes_count": len(notes),
        "tags": sorted(t for t in by_tag if t != "untagged"),
        "digest_path": out_rel if notes else None,
        "dry_run": dry_run,
    }
