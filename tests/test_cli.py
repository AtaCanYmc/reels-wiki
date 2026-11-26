from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from reels_wiki.interfaces import cli


def _fake_cfg(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(vault_path=tmp_path, config_path=None)


def test_cli_ingest_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _fake_cfg(tmp_path)
    expected = {"enqueued": True, "shortcode": "ABC12345678", "url": "https://www.instagram.com/reel/ABC12345678/"}

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch("reels_wiki.interfaces.cli.enqueue", return_value=expected) as mock_enq,
    ):
        rc = cli.main(["--json", "ingest", "https://www.instagram.com/reel/ABC12345678/?igsh=1"])

    assert rc == 0
    mock_enq.assert_called_once()
    out = json.loads(capsys.readouterr().out)
    assert out["enqueued"] is True
    assert out["shortcode"] == "ABC12345678"


def test_cli_stats_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _fake_cfg(tmp_path)
    expected = {
        "vault_path": str(tmp_path),
        "total_indexed": 3,
        "counts": {"pending": 1, "processing": 0, "processed": 2, "skipped": 0, "failed": 0},
        "artifacts_count": 2,
    }

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch("reels_wiki.interfaces.cli.queue_stats", return_value=expected),
    ):
        rc = cli.main(["--json", "stats"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_indexed"] == 3
    assert out["counts"]["processed"] == 2


def test_cli_process_returns_nonzero_on_failures(tmp_path: Path) -> None:
    cfg = _fake_cfg(tmp_path)
    expected = {"selected": 2, "processed": 1, "skipped": 0, "failed": 1}

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch("reels_wiki.interfaces.cli.process_queue", return_value=expected),
    ):
        rc = cli.main(["process", "--limit", "2"])

    assert rc == 1


def test_cli_reprocess_requires_target(tmp_path: Path) -> None:
    cfg = _fake_cfg(tmp_path)
    with patch("reels_wiki.interfaces.cli.load_config", return_value=cfg):
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["reprocess"])
    assert exc_info.value.code == 2


def test_cli_doctor_json_reports_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    cfg = SimpleNamespace(
        vault_path=tmp_path,
        config_path=tmp_path / "config.yaml",
        extraction=SimpleNamespace(ffmpeg_path="ffmpeg", cookies_from_browser=None, cookies_file=cookies),
        synthesis=SimpleNamespace(provider="groq", fallback_provider="gemini"),
        groq_api_key="gsk_secret_test",
        gemini_api_key="gem_secret_test",
    )
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_test")

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch("reels_wiki.interfaces.cli.shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
    ):
        rc = cli.main(["--json", "doctor"])

    assert rc == 0
    raw_out = capsys.readouterr().out
    assert "gsk_secret_test" not in raw_out
    assert "gem_secret_test" not in raw_out
    out = json.loads(raw_out)
    assert set(["python", "ffmpeg", "cookies", "api_keys", "vault", "ok"]).issubset(out.keys())
    assert out["ok"] is True
    assert out["python"]["ok"] is True
    assert out["ffmpeg"]["ok"] is True
    assert out["cookies"]["ok"] is True
    assert out["api_keys"]["ok"] is True
    assert out["vault"]["ok"] is True
    assert out["vault"]["writable"] is True


def test_cli_doctor_returns_nonzero_when_vault_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_vault = tmp_path / "nonexistent-vault"
    cfg = SimpleNamespace(
        vault_path=missing_vault,
        config_path=None,
        extraction=SimpleNamespace(ffmpeg_path="ffmpeg", cookies_from_browser=None, cookies_file=None),
        synthesis=SimpleNamespace(provider="groq", fallback_provider=None),
        groq_api_key=None,
        gemini_api_key=None,
    )

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch("reels_wiki.interfaces.cli.shutil.which", return_value=None),
    ):
        rc = cli.main(["doctor"])

    assert rc == 1
    out = capsys.readouterr().out
    assert "vault" in out.lower()


def test_cli_rich_human_ui_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = SimpleNamespace(
        vault_path=tmp_path,
        config_path=None,
        extraction=SimpleNamespace(ffmpeg_path="ffmpeg", cookies_from_browser="chrome", cookies_file=None),
        synthesis=SimpleNamespace(provider="groq", fallback_provider=None),
        groq_api_key="gsk_secret_hidden",
        gemini_api_key=None,
    )

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch(
            "reels_wiki.interfaces.cli.enqueue",
            return_value={"enqueued": True, "shortcode": "DAbCdEfGhIj", "url": "https://www.instagram.com/reel/DAbCdEfGhIj/"},
        ),
    ):
        assert cli.main(["ingest", "https://www.instagram.com/reel/DAbCdEfGhIj/"]) == 0
    ingest_out = capsys.readouterr().out
    assert "ENQUEUED" in ingest_out
    assert "DAbCdEfGhIj" in ingest_out

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch(
            "reels_wiki.interfaces.cli.queue_stats",
            return_value={
                "vault_path": str(tmp_path),
                "total_indexed": 4,
                "counts": {"pending": 1, "processing": 0, "processed": 2, "skipped": 1, "failed": 0},
                "artifacts_count": 3,
            },
        ),
    ):
        assert cli.main(["stats"]) == 0
    stats_out = capsys.readouterr().out
    assert "Vault Stats" in stats_out
    assert "Processed" in stats_out

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch(
            "reels_wiki.interfaces.cli.process_queue",
            return_value={
                "selected": 1,
                "processed": 1,
                "skipped": 0,
                "failed": 0,
                "results": [{"shortcode": "DAbCdEfGhIj", "status": "processed", "note_path": "ideas/test.md"}],
            },
        ),
    ):
        assert cli.main(["process", "--limit", "1"]) == 0
    proc_out = capsys.readouterr().out
    assert "Process Summary" in proc_out
    assert "ideas/test.md" in proc_out

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch("reels_wiki.interfaces.cli.shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
    ):
        assert cli.main(["doctor"]) == 0
    doc_out = capsys.readouterr().out
    assert "Diagnostics" in doc_out
    assert "PASS" in doc_out
    assert "gsk_secret_hidden" not in doc_out


def test_cli_init_creates_config_and_env(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    prompt_answers = iter([str(vault), "chrome", "groq", "gsk_test_123", ""])
    with (
        patch("reels_wiki.interfaces.cli.Prompt.ask", side_effect=lambda *a, **kw: next(prompt_answers)),
        patch("reels_wiki.interfaces.cli.Confirm.ask", return_value=False),
        patch("reels_wiki.interfaces.cli.shutil.which", return_value="/usr/bin/ffmpeg"),
    ):
        rc = cli.main(["--config", str(cfg_path), "init", "--env-path", str(env_path)])

    assert rc == 0
    assert cfg_path.is_file()
    assert env_path.is_file()
    assert (env_path.stat().st_mode & 0o777) == 0o600
    cfg_text = cfg_path.read_text(encoding="utf-8")
    assert str(vault) in cfg_text
    assert "cookies_from_browser: chrome" in cfg_text
    env_text = env_path.read_text(encoding="utf-8")
    assert "GROQ_API_KEY=gsk_test_123" in env_text
    assert "GEMINI_API_KEY=your_gemini_api_key" in env_text


def test_cli_init_respects_existing_without_force(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    cfg_path.write_text("vault_path: /existing\n", encoding="utf-8")

    with patch("reels_wiki.interfaces.cli.Confirm.ask", return_value=False):
        rc = cli.main(["--config", str(cfg_path), "init", "--env-path", str(env_path)])

    assert rc == 0
    assert cfg_path.read_text(encoding="utf-8") == "vault_path: /existing\n"
    assert not env_path.exists()


def test_cli_doctor_passes_with_ollama_without_cloud_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = SimpleNamespace(
        vault_path=tmp_path,
        config_path=tmp_path / "config.yaml",
        extraction=SimpleNamespace(ffmpeg_path="ffmpeg", cookies_from_browser="chrome", cookies_file=None),
        synthesis=SimpleNamespace(provider="ollama", fallback_provider=None),
        groq_api_key=None,
        gemini_api_key=None,
    )

    with (
        patch("reels_wiki.interfaces.cli.load_config", return_value=cfg),
        patch("reels_wiki.interfaces.cli.shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
    ):
        rc = cli.main(["--json", "doctor"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["api_keys"]["ok"] is True
    assert out["api_keys"]["primary_provider"] == "ollama"


def test_cli_digest_writes_weekly_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from datetime import date

    today = date.today().isoformat()
    ideas = tmp_path / "ideas"
    ideas.mkdir()
    (ideas / "note-one.md").write_text(
        f"---\ntitle: First Idea\ncreated: {today}\ntags: [cli, local]\n---\nBody\n",
        encoding="utf-8",
    )
    cfg = _fake_cfg(tmp_path)
    with patch("reels_wiki.interfaces.cli.load_config", return_value=cfg):
        rc = cli.main(["--json", "digest", "--days", "7"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["notes_count"] == 1
    assert out["tags"] == ["cli", "local"]
    digest_file = tmp_path / out["digest_path"]
    assert digest_file.is_file()
    assert "[[note-one|First Idea]]" in digest_file.read_text(encoding="utf-8")


def test_cli_digest_scoped_by_tag_and_review_actions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from datetime import date

    from reels_wiki.vault.writer import apply_review_action, list_inbox_notes

    today = date.today().isoformat()
    tools = tmp_path / "tools"
    ideas = tmp_path / "ideas"
    tools.mkdir()
    ideas.mkdir()
    note_a = tools / "tool-note.md"
    note_b = ideas / "idea-note.md"
    note_a.write_text(
        f"---\ntitle: CLI Tool Note\ncreated: '{today}'\nstatus: inbox\ntags: [cli, local]\n---\nTool body\n",
        encoding="utf-8",
    )
    note_b.write_text(
        f"---\ntitle: Design Idea\ncreated: '{today}'\nstatus: inbox\ntags: [design]\n---\nIdea body\n",
        encoding="utf-8",
    )
    (tmp_path / "_index.md").write_text("# Index\n\n## Tools\n- [[tool-note|CLI Tool Note]] - summary\n", encoding="utf-8")

    cfg = _fake_cfg(tmp_path)
    with patch("reels_wiki.interfaces.cli.load_config", return_value=cfg):
        assert cli.main(["--json", "digest", "--days", "30", "--tag", "cli"]) == 0
    digest_out = json.loads(capsys.readouterr().out)
    assert digest_out["tag"] == "cli"
    assert digest_out["notes_count"] == 1
    assert digest_out["digest_path"].endswith("-cli-digest.md")

    with patch("reels_wiki.interfaces.cli.load_config", return_value=cfg):
        assert cli.main(["--json", "review", "--limit", "5"]) == 0
    review_json = json.loads(capsys.readouterr().out)
    assert review_json["count"] == 2
    assert len(list_inbox_notes(tmp_path)) == 2

    promo = apply_review_action(tmp_path, note_a, "promote")
    assert promo["status"] == "evergreen" and promo["index_updated"] is False
    retagged = apply_review_action(tmp_path, note_b, "retag", new_tags=["#New Tag", "design"])
    assert retagged["tags"] == ["new-tag", "design"]
    archived = apply_review_action(tmp_path, note_b, "archive")
    assert archived["status"] == "archived"
    assert len(list_inbox_notes(tmp_path)) == 0
    assert (tmp_path / "_index.md").read_text(encoding="utf-8").count("[[tool-note|") == 1
