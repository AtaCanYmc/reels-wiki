"""LLM structured synthesis (Groq or Gemini) with validation-repair retries and provider fallback."""
from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Callable

import httpx
from pydantic import ValidationError

from ..core.config import Config, ConfigError
from ..core.models import AtomicNoteSynthesis, RawReelArtifact
from ..core.utils import slugify
from ..prompts import render_prompt
from ..vault.context import VaultContext


class SynthesisError(RuntimeError):
    """All providers/retries exhausted."""


SYSTEM_PROMPT = render_prompt("synthesis_system.j2")


def _schema_text() -> str:
    return json.dumps(AtomicNoteSynthesis.model_json_schema(), ensure_ascii=False, indent=1)


def build_user_prompt(artifact: RawReelArtifact, ctx: VaultContext, max_chars: int) -> str:
    raw_sections = [
        ("Caption", artifact.caption),
        ("Subtitles / audio transcript", artifact.transcript),
        ("On-screen text & visuals (OCR/VLM)", artifact.visual_notes),
    ]
    budget = max_chars
    sections: list[tuple[str, str]] = []
    for label, text in raw_sections:
        text = (text or "").strip()
        if not text:
            continue
        text = text[: max(budget, 0)]
        budget -= len(text)
        sections.append((label, text))
    return render_prompt(
        "synthesis_user.j2",
        vault_block=ctx.prompt_block(),
        schema_text=_schema_text(),
        creator=artifact.creator or "unknown",
        url=artifact.url,
        duration=artifact.duration or "unknown",
        upload_date=artifact.upload_date or "unknown",
        sections=sections,
    )


# ---------------------------------------------------------------------- providers
class BaseProvider(ABC):
    """Abstract base class for LLM synthesis providers."""

    name: str

    @abstractmethod
    def complete(self, system: str, user: str, cfg: Config) -> str:
        """Send system and user prompts and return the raw model response text."""

    def __call__(self, system: str, user: str, cfg: Config) -> str:
        return self.complete(system, user, cfg)


class GroqProvider(BaseProvider):
    """Groq chat-completions synthesis provider."""

    name = "groq"

    def complete(self, system: str, user: str, cfg: Config) -> str:
        from groq import Groq

        client = Groq(api_key=cfg.require_key("groq"))
        resp = client.chat.completions.create(
            model=cfg.synthesis.groq_model,
            temperature=cfg.synthesis.temperature,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""


class GeminiProvider(BaseProvider):
    """Google Gemini structured-output synthesis provider."""

    name = "gemini"

    def complete(self, system: str, user: str, cfg: Config) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=cfg.require_key("gemini"))
        kwargs: dict[str, Any] = dict(
            system_instruction=system,
            temperature=cfg.synthesis.temperature,
            response_mime_type="application/json",
        )
        try:  # JSON-schema-constrained decoding when the installed SDK supports it
            config = types.GenerateContentConfig(**kwargs, response_json_schema=AtomicNoteSynthesis.model_json_schema())
        except (TypeError, ValidationError):
            config = types.GenerateContentConfig(**kwargs)
        resp = client.models.generate_content(model=cfg.synthesis.gemini_model, contents=user, config=config)
        return resp.text or ""


class OllamaProvider(BaseProvider):
    """Local OpenAI-compatible (Ollama) synthesis provider."""

    name = "ollama"

    def complete(self, system: str, user: str, cfg: Config) -> str:
        url = f"{cfg.synthesis.ollama_base_url.rstrip('/')}/chat/completions"
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {cfg.synthesis.ollama_api_key}"},
            json={
                "model": cfg.synthesis.ollama_model,
                "temperature": cfg.synthesis.temperature,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"].get("content") or "").strip()


PROVIDERS: dict[str, BaseProvider | Callable[[str, str, Config], str]] = {
    "groq": GroqProvider(),
    "gemini": GeminiProvider(),
    "ollama": OllamaProvider(),
}


def register_provider(provider: BaseProvider) -> None:
    """Register a custom ``BaseProvider`` implementation by its ``name``."""
    PROVIDERS[provider.name] = provider


def parse_json_object(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    return json.loads(text[start : end + 1])


def _run_provider(provider: str, user: str, cfg: Config) -> AtomicNoteSynthesis:
    cfg.require_key(provider)
    prompt: str = user
    last_err: Exception | None = None
    for attempt in range(1, cfg.synthesis.max_retries + 1):
        try:
            raw = PROVIDERS[provider](SYSTEM_PROMPT, prompt, cfg)
            return AtomicNoteSynthesis.model_validate(parse_json_object(raw))
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_err = exc  # model produced bad JSON: tell it what was wrong and retry
            prompt = f"{user}\n\nYour previous reply was invalid ({str(exc)[:400]}). Return corrected JSON only."
        except ConfigError:
            raise
        except Exception as exc:  # noqa: BLE001 - network/rate-limit/provider errors
            last_err = exc
            if attempt < cfg.synthesis.max_retries:
                time.sleep(min(2 ** attempt, 20))
    raise SynthesisError(f"{provider} failed after {cfg.synthesis.max_retries} attempts: {last_err}")


# ---------------------------------------------------------------------- normalisation
def normalize_synthesis(syn: AtomicNoteSynthesis, ctx: VaultContext, artifact: RawReelArtifact) -> AtomicNoteSynthesis:
    """Enforce vault rules on whatever the model returned (valid folder, ASCII slug, clean tags)."""
    if not syn.should_keep:
        return syn
    slug = slugify(syn.slug) or slugify(syn.title) or f"reel-{artifact.shortcode.lower()}"
    folder = ctx.resolve_folder(syn.target_folder) or ctx.default_folder
    tags: list[str] = []
    for tag in syn.tags:
        clean = slugify(tag.lstrip("#").replace("/", "-"))
        if clean and clean not in tags:
            tags.append(clean)
    existing, unknown = ctx.resolve_wikilinks(syn.related_wikilinks)
    # Unknown names are kept; the writer re-resolves them and renders them as plain-text "new candidates".
    return syn.model_copy(
        update={
            "slug": slug,
            "target_folder": folder,
            "tags": tags[:8],
            "related_wikilinks": existing + unknown,
            "for_future_agent": [b.strip() for b in syn.for_future_agent if b.strip()],
        }
    )


def synthesize(artifact: RawReelArtifact, ctx: VaultContext, cfg: Config) -> AtomicNoteSynthesis:
    """Return a normalised synthesis. Content-free artifacts are skipped without spending an LLM call."""
    if not artifact.has_content():
        return AtomicNoteSynthesis(should_keep=False, skip_reason="No extractable content (empty caption, transcript and visuals)")
    user = build_user_prompt(artifact, ctx, cfg.synthesis.max_input_chars)
    providers = [cfg.synthesis.provider]
    if cfg.synthesis.fallback_provider and cfg.synthesis.fallback_provider != cfg.synthesis.provider:
        providers.append(cfg.synthesis.fallback_provider)
    errors: list[str] = []
    for provider in providers:
        try:
            return normalize_synthesis(_run_provider(provider, user, cfg), ctx, artifact)
        except (SynthesisError, ConfigError) as exc:
            errors.append(str(exc))
    raise SynthesisError(" | ".join(errors))
