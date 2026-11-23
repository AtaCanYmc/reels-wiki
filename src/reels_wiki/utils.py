"""Small filesystem/text helpers shared across modules."""
from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from pathlib import Path

_TR_MAP = str.maketrans(
    {
        "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "I": "i",
        "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
    }
)


def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file + fsync + os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def slugify(text: str, max_len: int = 80) -> str:
    """ASCII kebab-case slug; transliterates Turkish characters."""
    text = (text or "").translate(_TR_MAP)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(text) > max_len:
        cut = text[:max_len]
        text = (cut.rsplit("-", 1)[0] if "-" in cut else cut).strip("-")
    return text


def normalize_key(text: str) -> str:
    """Lowercase alphanumerics only (emoji/punctuation/spaces dropped) for fuzzy heading matches."""
    return slugify(text, max_len=200).replace("-", "")


def one_line(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
