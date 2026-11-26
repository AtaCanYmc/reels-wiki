import json

import pytest

from reels_wiki.ingestion.queue_manager import QueueManager, enqueue, extract_shortcode, normalize_url

SC = "DAbCdEfGhIj"  # 11 chars
CANON = f"https://www.instagram.com/reel/{SC}/"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.instagram.com/reel/{SC}/",
        f"https://www.instagram.com/reel/{SC}",
        f"https://instagram.com/reels/{SC}/",
        f"https://www.instagram.com/p/{SC}/",
        f"https://www.instagram.com/tv/{SC}/",
        f"https://www.instagram.com/reel/{SC}/?igsh=MWQ1ZGUxMzBkMg==",
        f"https://www.instagram.com/reel/{SC}/?utm_source=ig_web_copy_link&igsh=abc",
        f"https://www.instagram.com/some.user_1/reel/{SC}/",
        f"https://m.instagram.com/reel/{SC}/#frag",
        f"www.instagram.com/reel/{SC}/",
        f"  https://www.instagram.com/reel/{SC}/  ",
    ],
)
def test_extract_shortcode_variants(url):
    assert extract_shortcode(url) == SC


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        f"https://example.com/reel/{SC}/",
        f"https://notinstagram.com/reel/{SC}/",
        "https://www.instagram.com/reel/short/",
        "https://www.instagram.com/explore/",
        "https://www.instagram.com/someuser/",
        "https://www.instagram.com/reel/DAbCdEfGhIjKL/",  # 13 chars: not an 11-char shortcode
        None,
    ],
)
def test_extract_shortcode_rejects(url):
    assert extract_shortcode(url) is None


def test_normalize_url():
    assert normalize_url(f"https://www.instagram.com/p/{SC}/?igsh=x") == CANON
    assert normalize_url(SC) == CANON


def test_enqueue_writes_queue_and_index(tmp_path):
    res = enqueue(f"https://www.instagram.com/reels/{SC}/?igsh=zz", "telegram", vault=tmp_path)
    assert res["result"] == "enqueued" and res["shortcode"] == SC and res["url"] == CANON

    lines = (tmp_path / "inbox" / "reels-queue.jsonl").read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["status"] == "pending" and row["source"] == "telegram" and row["url"] == CANON

    index = json.loads((tmp_path / "sources" / ".reels_index.json").read_text())
    assert set(index[SC]) >= {"status", "url", "note_path", "updated_at"}
    assert index[SC]["status"] == "pending" and index[SC]["note_path"] is None


def test_duplicate_is_not_enqueued_unless_forced(tmp_path):
    q = QueueManager(tmp_path)
    assert q.enqueue(CANON)["result"] == "enqueued"
    dup = q.enqueue(f"https://www.instagram.com/p/{SC}/")
    assert dup["result"] == "duplicate" and dup["status"] == "pending"
    assert len((tmp_path / "inbox" / "reels-queue.jsonl").read_text().splitlines()) == 1

    forced = q.enqueue(CANON, force=True)
    assert forced["result"] == "enqueued"
    assert len((tmp_path / "inbox" / "reels-queue.jsonl").read_text().splitlines()) == 2
    assert len(q.read_queue()) == 1  # still one logical item


def test_processed_items_are_never_requeued(tmp_path):
    q = QueueManager(tmp_path)
    q.enqueue(CANON)
    q.update_status(SC, "processed", note_path="ideas/x.md")
    assert q.enqueue(CANON)["result"] == "duplicate"
    forced = q.enqueue(CANON, force=True)
    assert forced["result"] == "enqueued"
    assert q.load_index()[SC]["note_path"] == "ideas/x.md"  # kept so a re-run overwrites instead of duplicating


def test_invalid_url(tmp_path):
    res = enqueue("https://example.com/video/1", vault=tmp_path)
    assert res["result"] == "invalid" and res["ok"] is False
    assert not (tmp_path / "inbox" / "reels-queue.jsonl").exists()


def test_status_transitions_and_stats(tmp_path):
    q = QueueManager(tmp_path)
    q.enqueue(CANON, source="manual")
    q.enqueue("https://www.instagram.com/reel/AAAAAAAAAAA/", source="ig_export")
    q.enqueue("https://www.instagram.com/reel/BBBBBBBBBBB/", source="ig_export")
    q.update_status(SC, "processed", note_path="tools/a.md")
    q.update_status("AAAAAAAAAAA", "skipped", skip_reason="meme")
    q.update_status("BBBBBBBBBBB", "failed", error="boom")

    index = q.load_index()
    assert index[SC] == {**index[SC], "status": "processed", "note_path": "tools/a.md"}
    assert index["AAAAAAAAAAA"]["skip_reason"] == "meme"
    assert index["BBBBBBBBBBB"]["error"] == "boom"

    stats = q.stats()
    assert stats["total"] == 3 and stats["processed"] == 1 and stats["skipped"] == 1 and stats["failed"] == 1
    assert stats["pending"] == 0 and stats["by_source"] == {"manual": 1, "ig_export": 2}


def test_pending_order_and_retry_failed(tmp_path):
    q = QueueManager(tmp_path)
    ids = ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"]
    for sc in ids:
        q.enqueue(f"https://www.instagram.com/reel/{sc}/")
    q.update_status("BBBBBBBBBBB", "failed", error="x")
    assert [i.shortcode for i in q.pending()] == ["AAAAAAAAAAA", "CCCCCCCCCCC"]
    assert [i.shortcode for i in q.pending(retry_failed=True)] == ids


def test_reset_stale_processing(tmp_path):
    q = QueueManager(tmp_path)
    q.enqueue(CANON)
    q.update_status(SC, "processing", count_attempt=True)
    assert q.reset_stale_processing() == 1
    assert q.get_item(SC).status == "pending" and q.get_item(SC).attempts == 1


def test_enqueue_many_dedupes_within_batch(tmp_path):
    q = QueueManager(tmp_path)
    res = q.enqueue_many(
        [CANON, f"https://www.instagram.com/p/{SC}/?igsh=1", "https://www.instagram.com/reel/AAAAAAAAAAA/", "garbage"],
        source="ig_export",
    )
    assert res["enqueued"] == 2 and res["duplicates"] == 1 and res["invalid"] == 1
    assert len(q.read_queue()) == 2


def test_index_is_rebuilt_from_queue_if_lost(tmp_path):
    q = QueueManager(tmp_path)
    q.enqueue(CANON)
    q.update_status(SC, "processed", note_path="ideas/x.md")
    q.index_path.unlink()
    assert q.enqueue(CANON)["result"] == "duplicate"  # dedupe survives index loss
    assert q.load_index()[SC]["status"] == "processed"

    q.index_path.write_text("{not json")
    assert q.load_index()[SC]["note_path"] == "ideas/x.md"


def test_corrupt_queue_line_is_ignored(tmp_path):
    q = QueueManager(tmp_path)
    q.enqueue(CANON)
    with open(q.queue_path, "a", encoding="utf-8") as fh:
        fh.write('{"shortcode": "truncated\n')
    assert list(q.read_queue()) == [SC]
