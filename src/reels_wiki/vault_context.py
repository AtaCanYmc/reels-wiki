"""Read ``_CLAUDE.md`` / ``_index.md`` (and the vault itself) to learn folders, tags and existing notes."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

EXCLUDED_TOP_DIRS = {
    "sources", "inbox", "attachments", "assets", "templates", "template", "raw", "archive",
    "node_modules", "site-packages",
}
FALLBACK_FOLDER = "ideas"
MAX_SCAN_NOTES = 5000

_FOLDER_TOKEN_RE = re.compile(r"`([A-Za-z0-9_\-. ]+(?:/[A-Za-z0-9_\-. ]+)*)/`")
_TAG_RE = re.compile(r"(?<![\w/&#])#([A-Za-z\u00C0-\u024F][\w/\-\u00C0-\u024F]*)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _skip_dir(name: str) -> bool:
    return name.startswith((".", "_")) or name.lower() in EXCLUDED_TOP_DIRS


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _frontmatter_head(path: Path) -> dict:
    """Cheap YAML front-matter read (first 4 KB) without loading the whole note."""
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(4096)
    except (OSError, UnicodeDecodeError):
        return {}
    if not head.startswith("---"):
        return {}
    end = head.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(head[3:end])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class VaultContext:
    root: Path
    claude_md: str = ""
    index_md: str = ""
    allowed_folders: list[str] = field(default_factory=list)
    default_folder: str = FALLBACK_FOLDER
    tag_counts: Counter = field(default_factory=Counter)
    note_names: dict[str, str] = field(default_factory=dict)  # lower(name or title) -> canonical file stem
    note_paths: dict[str, Path] = field(default_factory=dict)  # canonical stem -> path
    index_headings: list[tuple[int, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(
        cls,
        root: Path | str,
        *,
        allowed_override: list[str] | None = None,
        default_folder: str | None = None,
    ) -> "VaultContext":
        root = Path(root).expanduser().resolve()
        ctx = cls(root=root)
        claude_path = next((root / n for n in ("_CLAUDE.md", "CLAUDE.md") if (root / n).is_file()), None)
        if claude_path:
            ctx.claude_md = _read(claude_path)
        else:
            ctx.warnings.append("_CLAUDE.md not found; using folder/tag discovery from the vault tree")
        index_path = root / "_index.md"
        if index_path.is_file():
            ctx.index_md = _read(index_path)
        else:
            ctx.warnings.append("_index.md not found; it will be created on first write")

        ctx._scan_notes()
        ctx._discover_folders(allowed_override)
        ctx._discover_tags()
        ctx._parse_index()
        wanted = (default_folder or "").strip("/ ")
        ctx.default_folder = ctx.resolve_folder(wanted) or (ctx.allowed_folders[0] if ctx.allowed_folders else FALLBACK_FOLDER)
        return ctx

    def _scan_notes(self) -> None:
        count = 0
        for path in sorted(self.root.rglob("*.md")):
            rel = path.relative_to(self.root)
            if any(_skip_dir(part) for part in rel.parts[:-1]) or rel.name.startswith("_"):
                continue
            count += 1
            if count > MAX_SCAN_NOTES:
                self.warnings.append(f"vault scan capped at {MAX_SCAN_NOTES} notes")
                break
            stem = path.stem
            self.note_names[stem.lower()] = stem
            self.note_paths[stem] = path
            fm = _frontmatter_head(path)
            title = fm.get("title")
            if isinstance(title, str) and title.strip():
                self.note_names.setdefault(title.strip().lower(), stem)
            tags = fm.get("tags")
            if isinstance(tags, str):
                tags = re.split(r"[,\s]+", tags)
            if isinstance(tags, list):
                for t in tags:
                    if isinstance(t, str) and t.strip():
                        self.tag_counts[t.strip().lstrip("#").lower()] += 1
        for name in _WIKILINK_RE.findall(self.index_md):
            name = name.strip()
            self.note_names.setdefault(name.lower(), name)

    def _discover_folders(self, override: list[str] | None) -> None:
        if override:
            self.allowed_folders = [f.strip("/ ") for f in override if f.strip("/ ")]
            return
        found: list[str] = []
        for text in (self.claude_md, self.index_md):
            for token in _FOLDER_TOKEN_RE.findall(text):
                token = token.strip("/ ")
                first = token.split("/")[0]
                if not token or ".." in token or _skip_dir(first) or token in found:
                    continue
                found.append(token)
        if found:
            self.allowed_folders = found  # documented order; missing directories are created on first write
            return
        dirs = sorted(p.name for p in self.root.iterdir() if p.is_dir() and not _skip_dir(p.name))
        self.allowed_folders = dirs or [FALLBACK_FOLDER]
        self.warnings.append("No folders documented in _CLAUDE.md/_index.md; using top-level vault directories")

    def _discover_tags(self) -> None:
        for text in (self.claude_md, self.index_md):
            for tag in _TAG_RE.findall(text):
                self.tag_counts[tag.lower()] += 1

    def _parse_index(self) -> None:
        for line in self.index_md.splitlines():
            m = _HEADING_RE.match(line)
            if m:
                self.index_headings.append((len(m.group(1)), m.group(2)))

    # ------------------------------------------------------------------ lookups
    def resolve_folder(self, name: str | None) -> str | None:
        """Map an LLM-supplied folder onto an allowed one (case-insensitive; trailing slash/last segment tolerant)."""
        if not name:
            return None
        key = name.strip().strip("/").lower()
        for folder in self.allowed_folders:
            if folder.lower() == key:
                return folder
        for folder in self.allowed_folders:
            if folder.lower().split("/")[-1] == key.split("/")[-1]:
                return folder
        return None

    def resolve_wikilinks(self, names: list[str]) -> tuple[list[str], list[str]]:
        """Split proposed links into (existing canonical names, unknown 'new note candidates')."""
        existing: list[str] = []
        unknown: list[str] = []
        for raw in names:
            name = re.sub(r"^\[\[|\]\]$", "", raw.strip()).split("|")[0].strip()
            if not name:
                continue
            canon = self.note_names.get(name.lower())
            bucket, value = (existing, canon) if canon else (unknown, name)
            if value not in existing and value not in unknown:
                bucket.append(value)
        return existing, unknown

    def note_exists(self, stem: str) -> bool:
        return stem.lower() in self.note_names

    def top_tags(self, n: int = 80) -> list[str]:
        return [t for t, _ in self.tag_counts.most_common(n)]

    def prompt_block(self, max_claude_chars: int = 6000, max_notes: int = 400) -> str:
        notes = sorted({v for v in self.note_names.values()})[:max_notes]
        claude = self.claude_md.strip()
        if len(claude) > max_claude_chars:
            claude = claude[:max_claude_chars] + "\n…[truncated]"
        return (
            "## Vault conventions (from _CLAUDE.md)\n"
            f"{claude or '(none provided)'}\n\n"
            f"## Allowed target folders (choose exactly one)\n{', '.join(self.allowed_folders)}\n\n"
            f"## Existing tags (prefer these; lowercase)\n{', '.join(self.top_tags()) or '(none yet)'}\n\n"
            f"## Existing note names (related_wikilinks must come from this list)\n{', '.join(notes) or '(none yet)'}\n"
        )
