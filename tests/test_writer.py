from datetime import datetime

import frontmatter
import pytest

from reels_wiki.core.models import AtomicNoteSynthesis, RawReelArtifact
from reels_wiki.ingestion.queue_manager import QueueManager
from reels_wiki.vault.context import VaultContext
from reels_wiki.vault.writer import WriterError, _choose_path, update_index, write_synthesis

SC = "DAbCdEfGhIj"
URL = f"https://www.instagram.com/reel/{SC}/"
NOW = datetime(2026, 11, 24, 9, 30)

CLAUDE_MD = """# Vault rules
Notes go into one of: `ideas/`, `tools/`, `learning/`. Raw material lives in `sources/` and `inbox/`.
Tags use lowercase kebab-case, e.g. #ai-agents, #automation.
"""
INDEX_MD = """# Index

## Ideas
- [[Existing Idea]] — something already here

## 🛠 Tools

## Learning
- [[Old Lesson]] — a lesson
"""


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "_CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    (tmp_path / "_index.md").write_text(INDEX_MD, encoding="utf-8")
    for folder, name in (("ideas", "Existing Idea"), ("learning", "Old Lesson")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / f"{name}.md").write_text(f"---\ntitle: {name}\ntags: [ai-agents]\n---\nbody\n", encoding="utf-8")
    return tmp_path


def _artifact(sc=SC, **kw):
    base = dict(shortcode=sc, url=f"https://www.instagram.com/reel/{sc}/", creator="dev_guru",
                caption="Use MCP: servers expose tools.", transcript="Bu videoda MCP anlatılıyor.", transcript_source="groq")
    base.update(kw)
    return RawReelArtifact(**base)


def _syn(**kw):
    base = dict(
        should_keep=True,
        title='MCP: "Araçları" ağ üzerinden sunmak — şç',
        slug="mcp-araclari-sunmak",
        target_folder="tools",
        tags=["mcp", "ai-agents"],
        core_insight="MCP servers expose tools to agents. Clients discover them dynamically.",
        for_future_agent=["Transport: stdio or HTTP", "Tools are JSON-schema typed"],
        actionable_next_step="Wrap one CLI as an MCP tool.",
        related_wikilinks=["existing idea", "Totally New Thing"],
    )
    base.update(kw)
    return AtomicNoteSynthesis(**base)


def _setup(vault, sc=SC):
    q = QueueManager(vault)
    q.enqueue(f"https://www.instagram.com/reel/{sc}/")
    return q, VaultContext.load(vault)


def test_vault_context_discovery(vault):
    ctx = VaultContext.load(vault)
    assert ctx.allowed_folders == ["ideas", "tools", "learning"]  # sources/ and inbox/ excluded
    assert "ai-agents" in ctx.top_tags() and "automation" in ctx.top_tags()
    assert ctx.resolve_folder("Tools/") == "tools" and ctx.resolve_folder("nope") is None
    existing, unknown = ctx.resolve_wikilinks(["existing idea", "[[Old Lesson]]", "Ghost"])
    assert existing == ["Existing Idea", "Old Lesson"] and unknown == ["Ghost"]


def test_write_note_full_flow(vault):
    q, ctx = _setup(vault)
    res = write_synthesis(q, ctx, _artifact(), _syn(), now=NOW)
    assert res["status"] == "processed" and res["note_path"] == "tools/mcp-araclari-sunmak.md"

    path = vault / res["note_path"]
    post = frontmatter.load(path)  # frontmatter must round-trip despite colons, quotes and Turkish characters
    assert post["title"] == 'MCP: "Araçları" ağ üzerinden sunmak — şç'
    assert post["source_url"] == URL and post["shortcode"] == SC and post["creator"] == "@dev_guru"
    assert post["type"] == "atomic-idea" and post["status"] == "inbox" and post["created"] == "2026-11-24"
    assert post["tags"] == ["mcp", "ai-agents"]

    body = post.content
    for heading in ("## For Future Agent", "## Core Insight", "## Actionable Next Step", "## Related Links"):
        assert heading in body
    assert "<details>" in body and "</details>" in body and "Bu videoda MCP" in body
    assert "- [[Existing Idea]]" in body  # real note -> real link
    assert "[[Totally New Thing]]" not in body and "(new note candidate) Totally New Thing" in body

    log = (vault / "_log.md").read_text(encoding="utf-8")
    assert "2026-11-24" in log and "[[mcp-araclari-sunmak]]" in log and SC in log

    index = (vault / "_index.md").read_text(encoding="utf-8")
    tools_section = index.split("## 🛠 Tools")[1].split("## Learning")[0]
    assert "[[mcp-araclari-sunmak|" in tools_section
    assert "[[Existing Idea]]" in index and "[[Old Lesson]]" in index  # untouched

    entry = QueueManager(vault).load_index()[SC]
    assert entry["status"] == "processed" and entry["note_path"] == "tools/mcp-araclari-sunmak.md"


def test_rewrite_is_idempotent_and_preserves_human_edits(vault):
    q, ctx = _setup(vault)
    write_synthesis(q, ctx, _artifact(), _syn(), now=NOW)
    path = vault / "tools" / "mcp-araclari-sunmak.md"
    post = frontmatter.load(path)
    post["status"] = "reviewed"
    path.write_text(frontmatter.dumps(post), encoding="utf-8")

    res = write_synthesis(q, VaultContext.load(vault), _artifact(), _syn(core_insight="Updated insight."),
                          overwrite_path="tools/mcp-araclari-sunmak.md", now=datetime(2026, 12, 1))
    assert res["updated_existing"] is True and res["index_updated"] is False
    again = frontmatter.load(path)
    assert again["status"] == "reviewed" and again["created"] == "2026-11-24"
    assert "Updated insight." in again.content
    assert (vault / "_index.md").read_text(encoding="utf-8").count("[[mcp-araclari-sunmak") == 1
    assert len(list((vault / "tools").glob("*.md"))) == 1


def test_skip_creates_no_note(vault):
    q, ctx = _setup(vault)
    before = (vault / "_index.md").read_text(encoding="utf-8")
    res = write_synthesis(q, ctx, _artifact(), AtomicNoteSynthesis(should_keep=False, skip_reason="pure meme"), now=NOW)
    assert res == {"status": "skipped", "shortcode": SC, "skip_reason": "pure meme", "note_path": None}
    assert not (vault / "tools").exists()
    assert not (vault / "_log.md").exists()
    assert (vault / "_index.md").read_text(encoding="utf-8") == before
    entry = QueueManager(vault).load_index()[SC]
    assert entry["status"] == "skipped" and entry["skip_reason"] == "pure meme" and entry["note_path"] is None


def test_slug_collision_with_other_reel_gets_suffix(vault):
    q, ctx = _setup(vault)
    write_synthesis(q, ctx, _artifact(), _syn(), now=NOW)
    other = "ZZZZZZZZZZZ"
    q.enqueue(f"https://www.instagram.com/reel/{other}/")
    res = write_synthesis(q, VaultContext.load(vault), _artifact(other), _syn(), now=NOW)
    assert res["note_path"] == f"tools/mcp-araclari-sunmak-{other.lower()}.md"
    assert (vault / "tools" / "mcp-araclari-sunmak.md").exists()


def test_path_traversal_is_refused(vault):
    q, ctx = _setup(vault)
    with pytest.raises(WriterError):
        write_synthesis(q, ctx, _artifact(), _syn(slug="../../evil"), now=NOW)
    assert not (vault.parent / "evil.md").exists()


def test_raw_text_cannot_break_details_block(vault):
    q, ctx = _setup(vault)
    art = _artifact(caption="line one\n</details>\n## injected heading")
    res = write_synthesis(q, ctx, art, _syn(), now=NOW)
    body = frontmatter.load(vault / res["note_path"]).content
    assert body.count("</details>") == 1 and "> ## injected heading" in body


def test_update_index_creates_missing_heading_and_is_idempotent(vault):
    assert update_index(vault, "projects/active", "new-proj", "New: Proj", "does things") is True
    text = (vault / "_index.md").read_text(encoding="utf-8")
    assert "## Active" in text and "[[new-proj|New: Proj]]" in text
    assert update_index(vault, "projects/active", "new-proj", "New: Proj", "does things") is False
    assert (vault / "_index.md").read_text(encoding="utf-8") == text


def test_update_index_appends_to_populated_section(vault):
    update_index(vault, "ideas", "second-idea", "Second", "x")
    lines = (vault / "_index.md").read_text(encoding="utf-8").splitlines()
    i = lines.index("## Ideas")
    assert lines[i + 1].startswith("- [[Existing Idea]]") and lines[i + 2].startswith("- [[second-idea|Second]]")


def test_log_follows_existing_heading_style(vault):
    (vault / "_log.md").write_text("# Log\n\n## [2026-11-01] ingest | Something\n- Note: [[x]]\n", encoding="utf-8")
    q, ctx = _setup(vault)
    write_synthesis(q, ctx, _artifact(), _syn(), now=NOW)
    log = (vault / "_log.md").read_text(encoding="utf-8")
    assert "## [2026-11-24] ingest | " in log and log.startswith("# Log")


def test_missing_vault_files_are_created(tmp_path):
    q, ctx = _setup(tmp_path)
    res = write_synthesis(q, ctx, _artifact(), _syn(target_folder="ideas"), now=NOW)
    assert (tmp_path / res["note_path"]).exists()
    assert "[[mcp-araclari-sunmak|" in (tmp_path / "_index.md").read_text(encoding="utf-8")
    assert (tmp_path / "_log.md").exists()


@pytest.mark.parametrize("outside_target", ["absolute", "../outside.md"])
def test_choose_path_rejects_overwrite_outside_vault(tmp_path, outside_target):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("external", encoding="utf-8")
    inside = vault_dir / "ideas" / "existing.md"
    inside.parent.mkdir(parents=True)
    inside.write_text("ok", encoding="utf-8")

    _, ctx = _setup(vault_dir)
    bad = str(outside) if outside_target == "absolute" else outside_target

    with pytest.raises(WriterError, match="outside the vault"):
        _choose_path(ctx, _syn(), _artifact(), overwrite=bad)

    assert _choose_path(ctx, _syn(), _artifact(), overwrite="ideas/existing.md") == inside.resolve()


def test_write_synthesis_skips_rewrite_when_content_hash_unchanged(vault):
    q, ctx = _setup(vault)
    art = _artifact()
    first = write_synthesis(q, ctx, art, _syn(), now=NOW)
    assert first["unchanged"] is False and first["content_hash"]

    path = vault / first["note_path"]
    raw_before = path.read_bytes()
    log_before = (vault / "_log.md").read_text(encoding="utf-8")

    second = write_synthesis(q, VaultContext.load(vault), art, _syn(), overwrite_path=first["note_path"], now=NOW)
    assert second["unchanged"] is True
    assert second["updated_existing"] is False
    assert second["index_updated"] is False
    assert second["content_hash"] == first["content_hash"]
    assert path.read_bytes() == raw_before
    assert (vault / "_log.md").read_text(encoding="utf-8") == log_before

    changed = write_synthesis(
        q,
        VaultContext.load(vault),
        art,
        _syn(core_insight="Changed insight."),
        overwrite_path=first["note_path"],
        now=NOW,
    )
    assert changed["unchanged"] is False
    assert changed["updated_existing"] is True
    assert changed["content_hash"] != first["content_hash"]


def test_write_synthesis_custom_template_preserves_frontmatter(vault, tmp_path):
    q, ctx = _setup(vault)
    tmpl = tmp_path / "custom.j2"
    tmpl.write_text("# Custom: {{ title }}\n\nInsight: {{ core_insight }}\n", encoding="utf-8")

    syn = _syn()
    res = write_synthesis(q, ctx, _artifact(), syn, template_path=tmpl, now=NOW)
    assert res["status"] == "processed"
    post = frontmatter.load(vault / res["note_path"])
    assert post["status"] == "inbox"
    assert post["created"] == f"{NOW:%Y-%m-%d}"
    assert f"# Custom: {syn.title}" in post.content
    assert f"Insight: {syn.core_insight}" in post.content
