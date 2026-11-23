"""Waterfall extraction: yt-dlp metadata -> audio transcript (Groq / faster-whisper) -> frame OCR (Gemini).

Media is only ever written to a ``TemporaryDirectory``; the vault receives just the JSON artifact.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from .config import Config, ConfigError, ExtractionConfig
from .models import RawReelArtifact
from .utils import atomic_write_text

GROQ_MAX_BYTES = 24 * 1024 * 1024
_AUTH_HINTS = ("login", "log in", "cookies", "rate-limit", "rate limit", "empty media response", "private", "403", "401")
_LOCAL_MODELS: dict[str, Any] = {}


class ExtractionError(RuntimeError):
    """Step 1 (metadata) failed; nothing useful can be extracted."""


# ---------------------------------------------------------------------- artifact persistence
def artifact_path(vault: Path, shortcode: str) -> Path:
    return Path(vault) / "sources" / "reels" / f"{shortcode}.json"


def save_artifact(vault: Path, artifact: RawReelArtifact) -> Path:
    path = artifact_path(vault, artifact.shortcode)
    atomic_write_text(path, artifact.model_dump_json(indent=2) + "\n")
    return path


def load_artifact(vault: Path, shortcode: str) -> RawReelArtifact | None:
    path = artifact_path(vault, shortcode)
    if not path.is_file():
        return None
    return RawReelArtifact.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- yt-dlp helpers
def _browser_tuple(spec: str) -> tuple[str, ...]:
    return tuple(p for p in spec.split(":", 1) if p)


def _ydl_opts(cfg: ExtractionConfig, **extra: Any) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "noplaylist": True,
        "playlist_items": "1",
    }
    if cfg.cookies_file:
        opts["cookiefile"] = str(cfg.cookies_file)
    elif cfg.cookies_from_browser:
        opts["cookiesfrombrowser"] = _browser_tuple(cfg.cookies_from_browser)
    opts.update(extra)
    return opts


def _flatten_info(info: dict[str, Any]) -> dict[str, Any]:
    """Carousels/multi-item posts come back as a playlist; merge the first entry over the parent."""
    entries = info.get("entries")
    if not entries:
        return info
    first = next((e for e in entries if e), None) or {}
    merged = {**first}
    for key in ("description", "uploader", "channel", "title"):
        if info.get(key) and not merged.get(key):
            merged[key] = info[key]
    return merged


def _fetch_metadata(url: str, cfg: ExtractionConfig) -> dict[str, Any]:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    try:
        with YoutubeDL(_ydl_opts(cfg, skip_download=True)) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        msg = str(exc)
        hint = ""
        if any(h in msg.lower() for h in _AUTH_HINTS):
            hint = (" Instagram likely requires a logged-in session: set extraction.cookies_file or "
                    "extraction.cookies_from_browser in config.yaml.")
        raise ExtractionError(f"yt-dlp could not read {url}: {msg[:300]}{hint}") from exc
    if not info:
        raise ExtractionError(f"yt-dlp returned no data for {url}")
    return _flatten_info(info)


def _download(url: str, outdir: Path, fmt: str, cfg: ExtractionConfig) -> Path:
    from yt_dlp import YoutubeDL

    opts = _ydl_opts(cfg, format=fmt, outtmpl=str(outdir / "%(id)s.%(ext)s"))
    with YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
    files = [p for p in outdir.iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
    if not files:
        raise ExtractionError("yt-dlp downloaded no media file")
    return max(files, key=lambda p: p.stat().st_size)


# ---------------------------------------------------------------------- subtitles
_VTT_TAG = re.compile(r"<[^>]+>")


def subtitle_to_text(raw: str) -> str:
    """Strip WEBVTT/SRT headers, cue numbers, timestamps and markup; collapse repeated lines."""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or line.startswith(("NOTE", "Kind:", "Language:")):
            continue
        if "-->" in line or line.isdigit():
            continue
        line = _VTT_TAG.sub("", line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return " ".join(lines)


def _fetch_subtitles(info: dict[str, Any]) -> str:
    pools = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
    for pool in pools:
        langs = [lang for lang in ("tr", "en") if lang in pool] + [lang for lang in pool if lang not in ("tr", "en")]
        for lang in langs:
            for fmt in pool[lang]:
                if fmt.get("ext") in ("vtt", "srt") and fmt.get("url"):
                    try:
                        resp = httpx.get(fmt["url"], timeout=20, follow_redirects=True)
                        resp.raise_for_status()
                        return subtitle_to_text(resp.text)
                    except httpx.HTTPError:
                        continue
    return ""


# ---------------------------------------------------------------------- ffmpeg
def _ffmpeg(cfg: ExtractionConfig) -> str:
    path = shutil.which(cfg.ffmpeg_path)
    if not path:
        raise ExtractionError(f"ffmpeg not found ('{cfg.ffmpeg_path}'); install it or set extraction.ffmpeg_path")
    return path


def _compress_audio(src: Path, outdir: Path, cfg: ExtractionConfig) -> Path:
    dst = outdir / "audio_small.mp3"
    subprocess.run(
        [_ffmpeg(cfg), "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(dst)],
        check=True, timeout=300,
    )
    return dst


def extract_frames(video: Path, outdir: Path, n: int, duration: float | None, cfg: ExtractionConfig) -> list[Path]:
    """``n`` evenly spaced JPEG frames (at the centre of ``n`` equal slices of the video)."""
    ffmpeg = _ffmpeg(cfg)
    total = duration if duration and duration > 0 else _probe_duration(video, ffmpeg)
    stamps = [total * (i + 0.5) / n for i in range(n)] if total else [0.0]
    frames: list[Path] = []
    for i, ts in enumerate(stamps):
        out = outdir / f"frame_{i:02d}.jpg"
        proc = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{ts:.2f}", "-i", str(video),
             "-frames:v", "1", "-vf", "scale='min(960,iw)':-2", "-q:v", "3", str(out)],
            capture_output=True, timeout=120,
        )
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
            frames.append(out)
    return frames


def _probe_duration(video: Path, ffmpeg: str) -> float | None:
    probe = shutil.which("ffprobe") or str(Path(ffmpeg).with_name("ffprobe"))
    try:
        out = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video)],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return float(out) if out else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------------- transcription
def _transcribe_groq(path: Path, cfg: ExtractionConfig, api_key: str) -> str:
    from groq import Groq

    kwargs: dict[str, Any] = {
        "file": (path.name, path.read_bytes()),
        "model": cfg.groq_whisper_model,
        "response_format": "json",
        "temperature": 0.0,
    }
    if cfg.whisper_language:
        kwargs["language"] = cfg.whisper_language
    resp = Groq(api_key=api_key).audio.transcriptions.create(**kwargs)
    return (getattr(resp, "text", None) or (resp if isinstance(resp, str) else "")).strip()


def _transcribe_local(path: Path, cfg: ExtractionConfig) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ConfigError('faster-whisper is not installed: pip install "reels-wiki[local]"') from exc
    model = _LOCAL_MODELS.get(cfg.local_whisper_model)
    if model is None:
        model = _LOCAL_MODELS[cfg.local_whisper_model] = WhisperModel(cfg.local_whisper_model, device="auto", compute_type="int8")
    segments, _info = model.transcribe(str(path), language=cfg.whisper_language, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()


def _transcribe(url: str, tmp: Path, cfg: Config) -> tuple[str, str]:
    ecfg = cfg.extraction
    audio = _download(url, tmp, "bestaudio[ext=m4a]/bestaudio/best", ecfg)
    if ecfg.whisper_provider == "groq":
        if audio.stat().st_size > GROQ_MAX_BYTES:
            audio = _compress_audio(audio, tmp, ecfg)
        return _transcribe_groq(audio, ecfg, cfg.require_key("groq")), "groq"
    return _transcribe_local(audio, ecfg), "faster-whisper"


# ---------------------------------------------------------------------- vision
_VISION_PROMPT = (
    "These are {n} evenly spaced frames from one Instagram Reel, in order. Extract ALL legible on-screen text "
    "verbatim (captions, slides, code, terminal commands, UI labels, diagrams' text), then add a brief factual "
    "description of what is shown that matters for the knowledge content (tools, interfaces, steps, charts). "
    "Do not invent anything that is not visible. Answer in the language of the on-screen text. "
    "Plain text only, no preamble."
)


def _vision_notes(url: str, tmp: Path, duration: float | None, cfg: Config) -> str:
    from google import genai
    from google.genai import types

    ecfg = cfg.extraction
    video = _download(url, tmp, "best[height<=720][ext=mp4]/best[height<=720]/best", ecfg)
    frames = extract_frames(video, tmp, ecfg.vision_frames, duration, ecfg)
    if not frames:
        raise ExtractionError("ffmpeg produced no frames")
    parts: list[Any] = [types.Part.from_bytes(data=f.read_bytes(), mime_type="image/jpeg") for f in frames]
    parts.append(_VISION_PROMPT.format(n=len(frames)))
    client = genai.Client(api_key=cfg.require_key("gemini"))
    resp = client.models.generate_content(model=ecfg.vision_model, contents=parts)
    return (resp.text or "").strip()


# ---------------------------------------------------------------------- public API
def extract_reel(url: str, shortcode: str, cfg: Config) -> RawReelArtifact:
    """Run the cost-aware waterfall and return a :class:`RawReelArtifact` (not yet persisted)."""
    ecfg = cfg.extraction

    # Step 1: metadata & caption (free, no media download)
    info = _fetch_metadata(url, ecfg)
    caption = (info.get("description") or "").strip()
    art = RawReelArtifact(
        shortcode=shortcode,
        url=url,
        creator=info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        title=info.get("title"),
        caption=caption,
        duration=float(info["duration"]) if info.get("duration") else None,
        upload_date=info.get("upload_date"),
        steps_used=["metadata"],
    )
    subs = _fetch_subtitles(info)
    if subs:
        art.subtitles = subs
        art.transcript, art.transcript_source = subs, "subtitles"
        art.steps_used.append("subtitles")

    # Step 2: audio transcript when the caption is thin and no usable subtitles exist
    if len(caption) < ecfg.min_caption_chars and len(art.transcript) < ecfg.min_caption_chars and ecfg.enable_whisper_fallback:
        try:
            with tempfile.TemporaryDirectory(prefix="reels-audio-") as tmp:
                text, source = _transcribe(url, Path(tmp), cfg)
            if text:
                art.transcript, art.transcript_source = text, source
                art.steps_used.append(f"whisper:{source}")
            else:
                art.warnings.append("Whisper returned an empty transcript (silent or music-only audio?)")
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, keep going to step 3
            art.warnings.append(f"audio transcription failed: {type(exc).__name__}: {str(exc)[:200]}")

    # Step 3: frame OCR/VLM when neither caption nor transcript carries enough text
    if (len(caption) < ecfg.min_caption_chars and len(art.transcript) < ecfg.min_transcript_chars
            and ecfg.enable_vision_fallback):
        try:
            with tempfile.TemporaryDirectory(prefix="reels-video-") as tmp:
                notes = _vision_notes(url, Path(tmp), art.duration, cfg)
            if notes:
                art.visual_notes = notes
                art.steps_used.append("vision:gemini")
        except Exception as exc:  # noqa: BLE001
            art.warnings.append(f"vision fallback failed: {type(exc).__name__}: {str(exc)[:200]}")

    return art
