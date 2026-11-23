import json

import pytest

from reels_wiki.ig_export import import_ig_export, parse_export
from reels_wiki.queue_manager import QueueManager

A, B, C = "AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"


def _entry(href, user="someone"):
    return {"title": user, "string_map_data": {"Saved on": {"href": href, "timestamp": 1730000000}}}


@pytest.fixture
def export_file(tmp_path):
    data = {
        "saved_saved_media": [
            _entry(f"https://www.instagram.com/reel/{A}/"),
            _entry(f"https://www.instagram.com/p/{B}/?igsh=xyz"),
            _entry(f"https://www.instagram.com/reel/{A}/?igsh=dup"),  # duplicate of A
            _entry("https://www.instagram.com/explore/tags/python/"),  # not a media link
            _entry("https://example.com/whatever"),
            {"title": "no-links", "string_map_data": {}},
        ]
    }
    path = tmp_path / "saved_posts.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_parse_export_reads_saved_on_href(export_file):
    hrefs = parse_export(export_file)
    assert len(hrefs) == 5 and hrefs[0].endswith(f"/reel/{A}/")


def test_import_enqueues_deduplicated_with_ig_export_source(tmp_path, export_file):
    vault = tmp_path / "vault"
    res = import_ig_export(export_file, vault=vault)
    assert res["enqueued"] == 2 and res["duplicates"] == 1 and res["ignored_links"] == 2
    queue = QueueManager(vault).read_queue()
    assert set(queue) == {A, B}
    assert all(i.source == "ig_export" and i.status == "pending" for i in queue.values())
    assert queue[B].url == f"https://www.instagram.com/reel/{B}/"


def test_second_import_is_all_duplicates_unless_forced(tmp_path, export_file):
    vault = tmp_path / "vault"
    import_ig_export(export_file, vault=vault)
    again = import_ig_export(export_file, vault=vault)
    assert again["enqueued"] == 0 and again["duplicates"] == 3
    forced = import_ig_export(export_file, vault=vault, force=True)
    assert forced["enqueued"] == 2


def test_already_processed_items_are_skipped_on_import(tmp_path, export_file):
    vault = tmp_path / "vault"
    q = QueueManager(vault)
    q.enqueue(f"https://www.instagram.com/reel/{A}/")
    q.update_status(A, "processed", note_path="ideas/a.md")
    res = import_ig_export(export_file, vault=vault)
    assert res["enqueued"] == 1  # only B
    assert q.load_index()[A]["status"] == "processed"


def test_reels_only_filter(tmp_path, export_file):
    res = import_ig_export(export_file, vault=tmp_path / "v", include_posts=False)
    assert res["enqueued"] == 1 and set(QueueManager(tmp_path / "v").read_queue()) == {A}


def test_accepts_export_directory(tmp_path, export_file):
    nested = tmp_path / "export" / "your_instagram_activity" / "saved"
    nested.mkdir(parents=True)
    (nested / "saved_posts.json").write_text(export_file.read_text(), encoding="utf-8")
    res = import_ig_export(tmp_path / "export", vault=tmp_path / "v")
    assert res["enqueued"] == 2


def test_fallback_for_unexpected_structure(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps([{"media": [{"href": f"https://www.instagram.com/reel/{C}/"}]}]), encoding="utf-8")
    assert import_ig_export(path, vault=tmp_path / "v")["enqueued"] == 1


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_ig_export(tmp_path / "nope", vault=tmp_path / "v")
