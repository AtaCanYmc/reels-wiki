from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from filelock import FileLock

from reels_wiki.config import Config
from reels_wiki.models import AtomicNoteSynthesis, RawReelArtifact
from reels_wiki.pipeline import process_item, process_queue
from reels_wiki.queue_manager import QueueManager


def test_process_queue_lock_contention_returns_error(tmp_path: Path) -> None:
    cfg = Config(vault_path=tmp_path)
    lock_path = tmp_path / "inbox" / ".reels-process.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    external_lock = FileLock(str(lock_path))

    with external_lock:
        res = process_queue(cfg, limit=5)

    assert res["processed"] == 0
    assert "already running" in res["error"]


def test_process_queue_recovers_stale_processing_and_dry_run(tmp_path: Path) -> None:
    cfg = Config(vault_path=tmp_path)
    queue = QueueManager(tmp_path)
    queue.enqueue("https://www.instagram.com/reel/DAbCdEfGhIj/", source="cli")
    queue.update_status("DAbCdEfGhIj", "processing")

    res = process_queue(cfg, dry_run=True)

    assert res["dry_run"] is True
    assert res["recovered_stale"] == 1
    assert res["selected"] == 1
    assert res["results"][0]["shortcode"] == "DAbCdEfGhIj"
    assert res["results"][0]["status"] == "pending"


def test_process_item_happy_path_and_failure_recording(tmp_path: Path) -> None:
    cfg = Config(vault_path=tmp_path)
    queue = QueueManager(tmp_path)
    queue.enqueue("https://www.instagram.com/reel/DAbCdEfGhIj/", source="cli")
    item = queue.pending()[0]

    fake_artifact = RawReelArtifact(
        shortcode="DAbCdEfGhIj",
        url=item.url,
        caption="A" * 200,
        steps_used=["metadata"],
    )
    fake_syn = AtomicNoteSynthesis(
        should_keep=True,
        title="Test Note",
        slug="test-note",
        target_folder="ideas",
        core_insight="Insight",
        actionable_next_step="Step",
    )
    expected_write = {"status": "processed", "shortcode": "DAbCdEfGhIj", "note_path": "ideas/test-note.md"}

    with (
        patch("reels_wiki.pipeline.extract_reel", return_value=fake_artifact),
        patch("reels_wiki.pipeline.save_artifact"),
        patch("reels_wiki.pipeline._ctx"),
        patch("reels_wiki.pipeline.synthesize", return_value=fake_syn),
        patch("reels_wiki.pipeline.write_synthesis", return_value=dict(expected_write)),
    ):
        ok_res = process_item(cfg, queue, item)

    assert ok_res["status"] == "processed"
    assert ok_res["downloaded"] is True
    assert ok_res["steps"] == ["metadata"]

    queue.enqueue("https://www.instagram.com/reel/XyZ987LmNoP/", source="cli")
    bad_item = queue.pending()[0]
    with patch("reels_wiki.pipeline.extract_reel", side_effect=RuntimeError("yt-dlp blocked")):
        fail_res = process_item(cfg, queue, bad_item)

    assert fail_res["status"] == "failed"
    assert "RuntimeError: yt-dlp blocked" in fail_res["error"]
