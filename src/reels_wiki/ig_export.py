"""Parser for Instagram's official data export (``saved_posts.json``)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from .queue_manager import QueueManager, _resolve_vault, parse_instagram_url


def _find_saved_file(path: Path) -> Path:
    if path.is_file():
        return path
    if path.is_dir():
        hits = sorted(path.rglob("saved_posts.json"))
        if hits:
            return hits[0]
    raise FileNotFoundError(f"saved_posts.json not found at {path}")


def _walk_hrefs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        href = node.get("href")
        if isinstance(href, str):
            yield href
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from _walk_hrefs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_hrefs(value)


def _entry_hrefs(entry: Any) -> list[str]:
    """``string_map_data -> 'Saved on' -> href`` first; any other href inside the entry as fallback."""
    if not isinstance(entry, dict):
        return []
    smd = entry.get("string_map_data")
    if isinstance(smd, dict):
        saved_on = smd.get("Saved on")
        if isinstance(saved_on, dict) and isinstance(saved_on.get("href"), str):
            return [saved_on["href"]]
    return list(_walk_hrefs(entry))


def parse_export(json_path: Path | str) -> list[str]:
    """Return every href found in the export, in file order (not yet filtered)."""
    path = _find_saved_file(Path(json_path).expanduser())
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("saved_saved_media") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        entries = [data]
    hrefs: list[str] = []
    for entry in entries:
        hrefs.extend(_entry_hrefs(entry))
    return hrefs


def import_ig_export(
    json_path: Path | str,
    *,
    vault: Path | str | None = None,
    force: bool = False,
    include_posts: bool = True,
) -> dict:
    """Bulk-enqueue reel/post URLs from an Instagram export with ``source="ig_export"``."""
    hrefs = parse_export(json_path)
    wanted: list[str] = []
    ignored = 0
    for href in hrefs:
        parsed = parse_instagram_url(href)
        if not parsed or (parsed[0] == "post" and not include_posts):
            ignored += 1
            continue
        wanted.append(href)
    summary = QueueManager(_resolve_vault(vault)).enqueue_many(wanted, source="ig_export", force=force)
    return {
        "file": str(json_path),
        "total_links": len(hrefs),
        "instagram_media_links": len(wanted),
        "ignored_links": ignored,
        "enqueued": summary["enqueued"],
        "duplicates": summary["duplicates"],
        "invalid": summary["invalid"],
    }
