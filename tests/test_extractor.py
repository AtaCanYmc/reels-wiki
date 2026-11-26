from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from reels_wiki.core.config import Config, ExtractionConfig
from reels_wiki.pipeline.extractor import extract_reel


def _cfg(tmp_path: Path, **ext_kwargs) -> Config:
    return Config(vault_path=tmp_path, extraction=ExtractionConfig(**ext_kwargs))


def test_extract_reel_long_caption_skips_whisper_and_vision(tmp_path: Path) -> None:
    long_caption = "A" * 160
    info = {
        "description": long_caption,
        "uploader": "creator_one",
        "title": "Long caption reel",
        "duration": 22,
        "upload_date": "20261124",
    }

    with (
        patch("reels_wiki.pipeline.extractor._fetch_metadata", return_value=info),
        patch("reels_wiki.pipeline.extractor._fetch_subtitles", return_value=""),
        patch("reels_wiki.pipeline.extractor._transcribe") as mock_transcribe,
        patch("reels_wiki.pipeline.extractor._vision_notes") as mock_vision,
    ):
        art = extract_reel("https://www.instagram.com/reel/DAbCdEfGhIj/", "DAbCdEfGhIj", _cfg(tmp_path))

    assert art.steps_used == ["metadata"]
    assert art.caption == long_caption
    assert art.creator == "creator_one"
    mock_transcribe.assert_not_called()
    mock_vision.assert_not_called()


def test_extract_reel_short_caption_triggers_whisper(tmp_path: Path) -> None:
    info = {"description": "Short caption", "uploader": "creator_two"}
    transcript = "Spoken technical explanation exceeding forty characters easily."

    with (
        patch("reels_wiki.pipeline.extractor._fetch_metadata", return_value=info),
        patch("reels_wiki.pipeline.extractor._fetch_subtitles", return_value=""),
        patch("reels_wiki.pipeline.extractor._transcribe", return_value=(transcript, "groq")) as mock_transcribe,
        patch("reels_wiki.pipeline.extractor._vision_notes") as mock_vision,
    ):
        art = extract_reel("https://www.instagram.com/reel/DAbCdEfGhIj/", "DAbCdEfGhIj", _cfg(tmp_path))

    assert art.transcript == transcript
    assert art.transcript_source == "groq"
    assert art.steps_used == ["metadata", "whisper:groq"]
    mock_transcribe.assert_called_once()
    mock_vision.assert_not_called()


def test_extract_reel_thin_caption_and_transcript_triggers_vision(tmp_path: Path) -> None:
    info = {"description": "Watch this", "uploader": "creator_three", "duration": 15}

    with (
        patch("reels_wiki.pipeline.extractor._fetch_metadata", return_value=info),
        patch("reels_wiki.pipeline.extractor._fetch_subtitles", return_value=""),
        patch("reels_wiki.pipeline.extractor._transcribe", return_value=("", "groq")) as mock_transcribe,
        patch("reels_wiki.pipeline.extractor._vision_notes", return_value="On-screen CLI flags") as mock_vision,
    ):
        art = extract_reel("https://www.instagram.com/reel/DAbCdEfGhIj/", "DAbCdEfGhIj", _cfg(tmp_path))

    assert art.visual_notes == "On-screen CLI flags"
    assert art.steps_used == ["metadata", "vision:gemini"]
    assert len(art.warnings) == 1
    mock_transcribe.assert_called_once()
    mock_vision.assert_called_once()


def test_extract_reel_whisper_failure_degrades_gracefully_to_vision(tmp_path: Path) -> None:
    info = {"description": "Hi", "uploader": "creator_four", "duration": 12}

    with (
        patch("reels_wiki.pipeline.extractor._fetch_metadata", return_value=info),
        patch("reels_wiki.pipeline.extractor._fetch_subtitles", return_value=""),
        patch("reels_wiki.pipeline.extractor._transcribe", side_effect=RuntimeError("Groq down")),
        patch("reels_wiki.pipeline.extractor._vision_notes", return_value="Slide text") as mock_vision,
    ):
        art = extract_reel("https://www.instagram.com/reel/DAbCdEfGhIj/", "DAbCdEfGhIj", _cfg(tmp_path))

    assert art.visual_notes == "Slide text"
    assert art.steps_used == ["metadata", "vision:gemini"]
    assert any("audio transcription failed: RuntimeError: Groq down" in w for w in art.warnings)
    mock_vision.assert_called_once()
