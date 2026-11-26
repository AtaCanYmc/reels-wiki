from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from reels_wiki.core.config import Config
from reels_wiki.interfaces.cli import main
from reels_wiki.interfaces.mcp_server import create_mcp_server
from reels_wiki.vault.search import INDEX_DB_REL, search_vault


def _seed_vault(vault: Path) -> None:
    (vault / "tools").mkdir(parents=True, exist_ok=True)
    (vault / "ideas").mkdir(parents=True, exist_ok=True)
    (vault / "sources").mkdir(parents=True, exist_ok=True)
    (vault / "inbox").mkdir(parents=True, exist_ok=True)
    (vault / "tools" / "ffmpeg-clips.md").write_text(
        "---\ntitle: FFmpeg Video Clipping\ntags: [cli, media]\n---\n\nTrim frames quickly with ffmpeg.\n",
        encoding="utf-8",
    )
    (vault / "ideas" / "vector-notes.md").write_text(
        "---\ntitle: Semantic Note Graph\ntags: [obsidian]\n---\n\nConnect related atomic ideas offline.\n",
        encoding="utf-8",
    )
    (vault / "sources" / "raw.md").write_text("Trim frames quickly with ffmpeg.\n", encoding="utf-8")
    (vault / "_index.md").write_text("# Index\nTrim frames quickly with ffmpeg.\n", encoding="utf-8")


def test_keyword_search_excludes_system_files_and_writes_sqlite(tmp_path: Path) -> None:
    _seed_vault(tmp_path)
    res = search_vault(tmp_path, "ffmpeg")
    assert res["count"] == 1
    assert res["matches"][0]["path"] == "tools/ffmpeg-clips.md"
    assert res["matches"][0]["title"] == "FFmpeg Video Clipping"
    assert (tmp_path / INDEX_DB_REL).is_file()


def test_hybrid_embedding_search_with_mocked_ollama(tmp_path: Path) -> None:
    _seed_vault(tmp_path)

    class _FakeResp:
        def __init__(self, embedding: list[float]) -> None:
            self._embedding = embedding

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"embedding": self._embedding}

    def _fake_post(_url: str, *, json: dict, timeout: float) -> _FakeResp:
        prompt = json["prompt"]
        if "Semantic" in prompt or "knowledge linking" in prompt:
            return _FakeResp([1.0, 0.0])
        return _FakeResp([0.0, 1.0])

    with patch("reels_wiki.vault.search.httpx.post", side_effect=_fake_post):
        res = search_vault(tmp_path, "knowledge linking", backend="ollama")

    assert res["count"] == 1
    assert res["matches"][0]["path"] == "ideas/vector-notes.md"
    assert res["matches"][0]["score"] > 0.5


def test_cli_search_and_mcp_search_vault_notes(tmp_path: Path, capsys) -> None:
    _seed_vault(tmp_path)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"vault_path: {tmp_path}\n", encoding="utf-8")

    rc = main(["--config", str(cfg_file), "--json", "search", "atomic ideas"])
    assert rc == 0
    cli_data = json.loads(capsys.readouterr().out)
    assert cli_data["count"] == 1
    assert cli_data["matches"][0]["path"] == "ideas/vector-notes.md"

    server = create_mcp_server(Config(vault_path=tmp_path))
    raw = asyncio.run(server.call_tool("search_vault_notes", {"query": "atomic ideas"}))
    contents = raw.content if hasattr(raw, "content") else raw[0]
    mcp_data = json.loads(contents[0].text)
    assert mcp_data["count"] == 1
    assert mcp_data["matches"][0]["path"] == "ideas/vector-notes.md"
