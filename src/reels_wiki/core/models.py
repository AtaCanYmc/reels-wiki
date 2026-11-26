"""Pydantic schemas: queue items, raw extraction artifacts, and the LLM synthesis contract."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QueueStatus = Literal["pending", "processing", "processed", "skipped", "failed"]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class QueueItem(BaseModel):
    """One line (state snapshot) of ``inbox/reels-queue.jsonl``. Latest line per shortcode wins."""

    shortcode: str
    url: str
    source: str = "manual"
    status: QueueStatus = "pending"
    enqueued_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    note_path: str | None = None
    skip_reason: str | None = None
    error: str | None = None
    attempts: int = 0


class RawReelArtifact(BaseModel):
    """Everything extracted for a reel; stored at ``sources/reels/<shortcode>.json``."""

    shortcode: str
    url: str
    creator: str | None = None
    title: str | None = None
    caption: str = ""
    duration: float | None = None
    upload_date: str | None = None
    subtitles: str = ""
    transcript: str = ""
    transcript_source: str = "none"  # none | subtitles | groq | faster-whisper
    visual_notes: str = ""
    steps_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extracted_at: str = Field(default_factory=utcnow_iso)

    def has_content(self) -> bool:
        return bool(
            (self.caption or "").strip() or (self.transcript or "").strip() or (self.visual_notes or "").strip()
        )


class AtomicNoteSynthesis(BaseModel):
    """Structured-output contract for the synthesis LLM."""

    should_keep: bool = Field(description="False for entertainment/memes/thirst traps or content with no actionable insight.")
    skip_reason: str | None = Field(default=None, description="Concise reason when should_keep is false.")
    title: str = Field(default="", description="Clear, concise title (Turkish or technical English, matching the content).")
    slug: str = Field(default="", description="ASCII kebab-case filename slug.")
    target_folder: str = Field(default="", description="One of the vault's allowed folders.")
    tags: list[str] = Field(default_factory=list, description="Lowercase tags aligned with existing vault tags.")
    core_insight: str = Field(default="", description="2-4 sentences distilling the core idea, tool, workflow or mental model.")
    for_future_agent: list[str] = Field(
        default_factory=list,
        description="Bullets: constraints, architecture patterns, context for future AI agents.",
    )
    actionable_next_step: str = Field(default="", description="One concrete next action or experiment.")
    related_wikilinks: list[str] = Field(default_factory=list, description="Existing note names (no brackets).")

    @model_validator(mode="after")
    def _require_fields_when_kept(self) -> "AtomicNoteSynthesis":
        if self.should_keep:
            missing = [n for n in ("title", "core_insight") if not getattr(self, n).strip()]
            if missing:
                raise ValueError(f"should_keep is true but these fields are empty: {', '.join(missing)}")
        elif not (self.skip_reason or "").strip():
            self.skip_reason = "Not worth keeping (no reason given by model)"
        return self
