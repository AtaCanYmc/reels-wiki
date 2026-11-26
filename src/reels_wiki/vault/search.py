"""Local hybrid keyword + optional embedding search indexed in ``sources/.embeddings.sqlite``."""
from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Any

import frontmatter
import httpx

INDEX_DB_REL = "sources/.embeddings.sqlite"
_SKIP_DIRS = {"sources", "inbox"}
_SKIP_FILES = {"_index.md", "_log.md", "_CLAUDE.md"}


def _iter_vault_notes(root: Path) -> list[tuple[str, float, str, str]]:
    notes: list[tuple[str, float, str, str]] = []
    for path in sorted(root.rglob("*.md")):
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        if (
            rel.parts[0] in _SKIP_DIRS
            or any(p.startswith(".") for p in rel.parts)
            or resolved.name in _SKIP_FILES
        ):
            continue
        try:
            text = resolved.read_text(encoding="utf-8", errors="ignore")
            mtime = resolved.stat().st_mtime
        except OSError:
            continue
        title = resolved.stem
        try:
            meta_title = frontmatter.loads(text).metadata.get("title")
            if isinstance(meta_title, str) and meta_title.strip():
                title = meta_title.strip()
        except Exception:  # noqa: BLE001
            pass
        notes.append((rel.as_posix(), mtime, title, text))
    return notes


def embed_text(
    text: str,
    *,
    backend: str = "none",
    ollama_url: str = "http://localhost:11434",
    model: str = "nomic-embed-text",
) -> list[float] | None:
    """Return a local embedding vector via Ollama or fastembed, else ``None``."""
    clean = (text or "").strip()[:8000]
    if backend == "none" or not clean:
        return None
    if backend == "ollama":
        try:
            resp = httpx.post(
                f"{ollama_url.rstrip('/')}/api/embeddings",
                json={"model": model, "prompt": clean},
                timeout=15.0,
            )
            resp.raise_for_status()
            vec = resp.json().get("embedding")
            return [float(x) for x in vec] if isinstance(vec, list) and vec else None
        except Exception:  # noqa: BLE001
            return None
    if backend == "fastembed":
        try:
            from fastembed import TextEmbedding

            embedder = TextEmbedding(model_name=model)
            vec = next(iter(embedder.embed([clean])), None)
            return [float(x) for x in vec] if vec is not None else None
        except Exception:  # noqa: BLE001
            return None
    return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na > 0.0 and nb > 0.0 else 0.0


def _keyword_score(query: str, title: str, content: str) -> float:
    needle = query.strip().lower()
    if not needle:
        return 0.0
    title_l = title.lower()
    body_l = content.lower()
    if needle in body_l or needle in title_l:
        return 1.0 if needle in title_l else 0.7
    tokens = [t for t in re.split(r"\W+", needle) if len(t) > 1]
    if not tokens:
        return 0.0
    hits = sum(1 for tok in tokens if tok in title_l or tok in body_l)
    return 0.5 * (hits / len(tokens))


def _snippet(content: str, query: str) -> str:
    needle = query.strip().lower()
    idx = content.lower().find(needle) if needle else -1
    if idx != -1:
        start = max(0, idx - 60)
        return " ".join(content[start : idx + len(needle) + 120].split())
    return " ".join(content[:180].split())


def index_vault(
    vault: Path,
    *,
    backend: str = "none",
    ollama_url: str = "http://localhost:11434",
    embed_model: str = "nomic-embed-text",
    reindex: bool = False,
) -> dict[str, Any]:
    """Sync vault Markdown notes into ``sources/.embeddings.sqlite``."""
    root = Path(vault).expanduser().resolve()
    db_path = root / INDEX_DB_REL
    db_path.parent.mkdir(parents=True, exist_ok=True)
    disk_notes = _iter_vault_notes(root) if root.is_dir() else []

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS notes ("
            "path TEXT PRIMARY KEY, mtime REAL NOT NULL, title TEXT NOT NULL, "
            "content TEXT NOT NULL, embedding TEXT)"
        )
        existing = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT path, mtime, embedding FROM notes")}
        current_paths = {n[0] for n in disk_notes}
        for stale in set(existing) - current_paths:
            conn.execute("DELETE FROM notes WHERE path = ?", (stale,))

        embedded = 0
        for rel, mtime, title, text in disk_notes:
            prev = existing.get(rel)
            changed = prev is None or abs(prev[0] - mtime) > 1e-6 or reindex
            emb_json = prev[1] if (prev and not changed) else None
            if backend != "none" and (changed or emb_json is None):
                vec = embed_text(f"{title}\n{text}", backend=backend, ollama_url=ollama_url, model=embed_model)
                if vec is not None:
                    emb_json = json.dumps(vec)
                    embedded += 1
            if changed or (emb_json is not None and (prev is None or prev[1] is None)):
                conn.execute(
                    "INSERT INTO notes (path, mtime, title, content, embedding) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, title=excluded.title, "
                    "content=excluded.content, embedding=COALESCE(excluded.embedding, notes.embedding)",
                    (rel, mtime, title, text, emb_json),
                )
        conn.commit()
    finally:
        conn.close()
    return {"db_path": str(db_path), "total_notes": len(disk_notes), "embedded": embedded}


def search_vault(
    vault: Path,
    query: str,
    *,
    limit: int = 10,
    backend: str = "none",
    ollama_url: str = "http://localhost:11434",
    embed_model: str = "nomic-embed-text",
    reindex: bool = False,
) -> dict[str, Any]:
    """Search Markdown notes with hybrid keyword + optional cosine similarity ranking."""
    root = Path(vault).expanduser().resolve()
    needle = query.strip()
    if not needle or not root.is_dir():
        return {"query": query, "backend": backend, "count": 0, "matches": []}

    index_vault(root, backend=backend, ollama_url=ollama_url, embed_model=embed_model, reindex=reindex)
    q_vec = embed_text(needle, backend=backend, ollama_url=ollama_url, model=embed_model) if backend != "none" else None

    conn = sqlite3.connect(root / INDEX_DB_REL)
    try:
        rows = conn.execute("SELECT path, title, content, embedding FROM notes").fetchall()
    finally:
        conn.close()

    scored: list[dict[str, Any]] = []
    for rel, title, content, emb_raw in rows:
        kw = _keyword_score(needle, title, content)
        vec_score = 0.0
        if q_vec is not None and emb_raw:
            try:
                vec_score = max(0.0, _cosine_similarity(q_vec, json.loads(emb_raw)))
            except (ValueError, TypeError):
                vec_score = 0.0
        if kw <= 0.0 and vec_score <= 0.1:
            continue
        score = (0.45 * kw + 0.55 * vec_score) if q_vec is not None else kw
        scored.append({"path": rel, "title": title, "score": round(score, 4), "snippet": _snippet(content, needle)})

    scored.sort(key=lambda item: (-item["score"], item["path"]))
    matches = scored[: max(limit, 1)]
    return {"query": query, "backend": backend, "count": len(matches), "matches": matches}
