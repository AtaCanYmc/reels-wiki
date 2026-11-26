from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest

import reels_wiki
from reels_wiki import enqueue, load_config, process_queue, reprocess
from reels_wiki.core.config import CONFIG_SCHEMA_VERSION, DEPRECATED_CONFIG_KEYS, Config, ConfigError
from reels_wiki.core.models import (
    ARTIFACT_SCHEMA_VERSION,
    QUEUE_SCHEMA_VERSION,
    QueueItem,
    RawReelArtifact,
)
from reels_wiki.pipeline.synthesizer import PROVIDERS

EXPECTED_PUBLIC_EXPORTS = {
    "Config",
    "ConfigError",
    "QueueManager",
    "enqueue",
    "extract_shortcode",
    "import_ig_export",
    "load_config",
    "normalize_url",
    "process_queue",
    "queue_stats",
    "reprocess",
}

CLAUDE_MD = """# Vault Rules
Write atomic notes under `ideas/`, `tools/`, or `learning/`.
Never place notes in `sources/` or `inbox/`.
Preferred tags: #ai-agents #automation #devtools
"""

INDEX_MD = """# Vault Index

## 🛠 Tools
- [[docker-setup|Docker Setup]] — Local container baseline

## Ideas
- [[obsidian-mcp|Obsidian MCP]] — Expose vault search over stdio

## Learning
"""

LOG_MD = """# Log

## [2026-11-20] create | Docker Setup
- Source: manual
- Note: [[docker-setup]]
"""


@pytest.fixture
def ref_vault(tmp_path: Path) -> Path:
    (tmp_path / "_CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    (tmp_path / "_index.md").write_text(INDEX_MD, encoding="utf-8")
    (tmp_path / "_log.md").write_text(LOG_MD, encoding="utf-8")
    for folder, slug, title in (
        ("tools", "docker-setup", "Docker Setup"),
        ("ideas", "obsidian-mcp", "Obsidian MCP"),
    ):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        (tmp_path / folder / f"{slug}.md").write_text(
            f"---\ntitle: {title}\ntags: [devtools]\n---\nBody\n",
            encoding="utf-8",
        )
    (tmp_path / "learning").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_sdk_public_exports_contract() -> None:
    assert set(reels_wiki.__all__) == EXPECTED_PUBLIC_EXPORTS
    for name in EXPECTED_PUBLIC_EXPORTS:
        assert getattr(reels_wiki, name) is not None


def test_config_v1_schema_and_deprecation_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg_file = tmp_path / "config.yaml"

    cfg_file.write_text(f"vault_path: {vault}\n", encoding="utf-8")
    defaulted = load_config(cfg_file)
    assert defaulted.schema_version == CONFIG_SCHEMA_VERSION == 1

    cfg_file.write_text(f"schema_version: 1\nvault_path: {vault}\ndelay_seconds: 1.0\n", encoding="utf-8")
    monkeypatch.setitem(DEPRECATED_CONFIG_KEYS, "delay_seconds", "moved in v2")
    with pytest.warns(DeprecationWarning, match="delay_seconds"):
        warned = load_config(cfg_file)
    assert warned.delay_seconds == 1.0

    cfg_file.write_text(f"schema_version: 2\nvault_path: {vault}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="schema_version"):
        load_config(cfg_file)


def test_artifact_and_queue_forward_backward_compat(ref_vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        PROVIDERS,
        "ollama",
        lambda _sys, _usr, _cfg: json.dumps({
            "should_keep": True,
            "title": "Reprocessed Stored Note",
            "slug": "reprocessed-stored-note",
            "target_folder": "tools",
            "tags": ["devtools"],
            "core_insight": "Stored artifacts stay valid across minor schema additions.",
            "for_future_agent": ["Additive fields ignored cleanly"],
            "actionable_next_step": "Reprocess offline",
            "related_wikilinks": ["Docker Setup"],
        }),
    )

    legacy_item = QueueItem.model_validate({"shortcode": "DLegacy1234", "url": "https://www.instagram.com/reel/DLegacy1234/"})
    future_item = QueueItem.model_validate({
        "schema_version": 2,
        "shortcode": "DFuture1234",
        "url": "https://www.instagram.com/reel/DFuture1234/",
        "future_flag": True,
    })
    assert legacy_item.schema_version == QUEUE_SCHEMA_VERSION
    assert future_item.schema_version == 2

    inbox = ref_vault / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "reels-queue.jsonl").write_text(
        json.dumps({"shortcode": "DLegacy1234", "url": "https://www.instagram.com/reel/DLegacy1234/", "status": "processed"})
        + "\n"
        + json.dumps({
            "schema_version": 2,
            "shortcode": "DFuture1234",
            "url": "https://www.instagram.com/reel/DFuture1234/",
            "status": "processed",
            "future_metadata": {"origin": "mobile"},
        })
        + "\n",
        encoding="utf-8",
    )

    reels_dir = ref_vault / "sources" / "reels"
    reels_dir.mkdir(parents=True, exist_ok=True)
    (reels_dir / "DLegacy1234.json").write_text(
        json.dumps({
            "shortcode": "DLegacy1234",
            "url": "https://www.instagram.com/reel/DLegacy1234/",
            "caption": "Legacy pre-schema artifact " * 10,
            "steps_used": ["metadata"],
        }),
        encoding="utf-8",
    )
    (reels_dir / "DFuture1234.json").write_text(
        json.dumps({
            "schema_version": 2,
            "shortcode": "DFuture1234",
            "url": "https://www.instagram.com/reel/DFuture1234/",
            "caption": "Future minor-version artifact " * 10,
            "steps_used": ["metadata"],
            "extra_v1_minor_field": {"nested": True},
        }),
        encoding="utf-8",
    )
    loaded = RawReelArtifact.model_validate_json((reels_dir / "DLegacy1234.json").read_text(encoding="utf-8"))
    assert loaded.schema_version == ARTIFACT_SCHEMA_VERSION

    cfg = Config(vault_path=ref_vault, synthesis={"provider": "ollama"})
    res = reprocess(cfg, ["DLegacy1234", "DFuture1234"])
    assert res["processed"] == 2 and res["failed"] == 0


def test_e2e_reference_vault_routing_tags_wikilinks_and_idempotency(
    ref_vault: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = Config(vault_path=ref_vault, default_folder="ideas", synthesis={"provider": "ollama"})

    enqueue("https://www.instagram.com/reel/DToolValid1/", "cli", vault=ref_vault)
    enqueue("https://www.youtube.com/shorts/VpW4T7e34EI", "extension", vault=ref_vault)

    def _fake_extract(url: str, shortcode: str, _cfg: Config) -> RawReelArtifact:
        return RawReelArtifact(
            shortcode=shortcode,
            url=url,
            creator="tester",
            caption=f"Detailed architectural notes for {shortcode}. " * 6,
            steps_used=["metadata"],
        )

    responses = {
        "DToolValid1": {
            "should_keep": True,
            "title": "MCP Server Tooling",
            "slug": "mcp-server-tooling",
            "target_folder": "Tools",
            "tags": ["#AI-Agents", "Automation/CLI", "ai-agents"],
            "core_insight": "MCP servers expose typed tools to agents cleanly.",
            "for_future_agent": ["Read _CLAUDE.md before writing"],
            "actionable_next_step": "Add one tool endpoint",
            "related_wikilinks": ["Docker Setup", "Unknown Future Note"],
        },
        "yt_VpW4T7e34EI": {
            "should_keep": True,
            "title": "Disallowed Folder Fallback",
            "slug": "disallowed-folder-fallback",
            "target_folder": "not-an-allowed-folder",
            "tags": ["#DevTools"],
            "core_insight": "Disallowed folders route to default_folder.",
            "for_future_agent": ["Enforce folder whitelist"],
            "actionable_next_step": "Verify fallback folder",
            "related_wikilinks": ["[[Obsidian MCP]]"],
        },
    }

    def _fake_llm(_sys: str, user: str, _cfg: Config) -> str:
        key = "DToolValid1" if "DToolValid1" in user else "yt_VpW4T7e34EI"
        return json.dumps(responses[key])

    monkeypatch.setitem(PROVIDERS, "ollama", _fake_llm)
    with patch("reels_wiki.pipeline.runner.extract_reel", side_effect=_fake_extract):
        summary = process_queue(cfg, limit=10)

    assert summary["processed"] == 2 and summary["failed"] == 0

    tool_note = ref_vault / "tools" / "mcp-server-tooling.md"
    fallback_note = ref_vault / "ideas" / "disallowed-folder-fallback.md"
    assert tool_note.is_file()
    assert fallback_note.is_file()

    tool_post = frontmatter.load(tool_note)
    assert tool_post["tags"] == ["ai-agents", "automation-cli"]
    assert "- [[docker-setup]]" in tool_post.content
    assert "- (new note candidate) Unknown Future Note" in tool_post.content

    fallback_post = frontmatter.load(fallback_note)
    assert "- [[obsidian-mcp]]" in fallback_post.content

    index_before = (ref_vault / "_index.md").read_text(encoding="utf-8")
    assert index_before.count("[[mcp-server-tooling|") == 1
    assert index_before.count("[[disallowed-folder-fallback|") == 1

    log_text = (ref_vault / "_log.md").read_text(encoding="utf-8")
    assert "## [" in log_text and "- Note: [[mcp-server-tooling]]" in log_text

    # Simulate human curation before offline reprocess: edits to status and created must survive.
    tool_post["status"] = "reviewed"
    tool_post["created"] = "2025-01-15"
    tool_note.write_text(frontmatter.dumps(tool_post, sort_keys=False).rstrip("\n") + "\n", encoding="utf-8")

    responses["DToolValid1"]["core_insight"] = "Updated core insight after offline reprocess."
    reproc = reprocess(cfg, ["DToolValid1"])
    assert reproc["processed"] == 1 and reproc["results"][0]["updated_existing"] is True

    updated_post = frontmatter.load(tool_note)
    assert updated_post["status"] == "reviewed"
    assert updated_post["created"] == "2025-01-15"
    assert "Updated core insight after offline reprocess." in updated_post.content

    index_after = (ref_vault / "_index.md").read_text(encoding="utf-8")
    assert index_after.count("[[mcp-server-tooling|") == 1
    assert "] update | MCP Server Tooling" in (ref_vault / "_log.md").read_text(encoding="utf-8")
