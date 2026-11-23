from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from reels_wiki import cli


def _fake_cfg(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(vault_path=tmp_path, config_path=None)


def test_cli_ingest_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _fake_cfg(tmp_path)
    expected = {"enqueued": True, "shortcode": "ABC12345678", "url": "https://www.instagram.com/reel/ABC12345678/"}

    with (
        patch("reels_wiki.cli.load_config", return_value=cfg),
        patch("reels_wiki.cli.enqueue", return_value=expected) as mock_enq,
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
        patch("reels_wiki.cli.load_config", return_value=cfg),
        patch("reels_wiki.cli.queue_stats", return_value=expected),
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
        patch("reels_wiki.cli.load_config", return_value=cfg),
        patch("reels_wiki.cli.process_queue", return_value=expected),
    ):
        rc = cli.main(["process", "--limit", "2"])

    assert rc == 1


def test_cli_reprocess_requires_target(tmp_path: Path) -> None:
    cfg = _fake_cfg(tmp_path)
    with patch("reels_wiki.cli.load_config", return_value=cfg):
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["reprocess"])
    assert exc_info.value.code == 2
