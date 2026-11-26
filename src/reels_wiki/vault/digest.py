"""Weekly digest generator grouping recent atomic Obsidian notes by tag and folder."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import frontmatter

from ..core.utils import atomic_write_text

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
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Scan recent vault notes from the last ``days`` days and write ``digests/<YYYY-MM-DD>-digest.md``."""
    root = Path(vault).expanduser().resolve()
    ref_day = (now or datetime.now()).date()
    cutoff = ref_day - timedelta(days=max(days, 1) - 1)

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
        entry = {"slug": path.stem, "title": title, "path": rel.as_posix(), "created": created.isoformat()}
        notes.append({**entry, "tags": tags})
        for tag in tags or ["untagged"]:
            by_tag[tag].append(entry)

    out_rel = f"digests/{ref_day.isoformat()}-digest.md"
    if not dry_run and notes:
        lines = [
            f"---\ntitle: Weekly Digest ({cutoff.isoformat()} to {ref_day.isoformat()})\n"
            f"created: {ref_day.isoformat()}\ntype: digest\ntags: [digest, weekly]\n---\n",
            f"# Weekly Knowledge Digest ({cutoff.isoformat()} to {ref_day.isoformat()})\n",
            f"Total notes: {len(notes)}\n",
        ]
        for tag in sorted(by_tag):
            lines.append(f"\n## #{tag}\n")
            for item in by_tag[tag]:
                lines.append(f"- [[{item['slug']}|{item['title']}]] ({item['created']})")
        atomic_write_text(root / out_rel, "\n".join(lines) + "\n")

    return {
        "vault": str(root),
        "days": days,
        "from_date": cutoff.isoformat(),
        "to_date": ref_day.isoformat(),
        "notes_count": len(notes),
        "tags": sorted(t for t in by_tag if t != "untagged"),
        "digest_path": out_rel if notes else None,
        "dry_run": dry_run,
    }
