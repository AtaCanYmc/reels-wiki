"""LLM structured synthesis (Groq or Gemini) with validation-repair retries and provider fallback."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

import httpx
from pydantic import ValidationError

from .config import Config, ConfigError
from .models import AtomicNoteSynthesis, RawReelArtifact
from .utils import slugify
from .vault_context import VaultContext


class SynthesisError(RuntimeError):
    """All providers/retries exhausted."""


SYSTEM_PROMPT = """You are the curator of a personal knowledge base (an Obsidian "LLM Wiki"). You receive the raw \
extraction of one saved Instagram Reel (caption, audio transcript, on-screen text) and decide whether it deserves \
an atomic note, and if so write it.

Rules:
- should_keep=false for pure entertainment, memes, trends, thirst traps, vague motivation, ads without substance, or \
anything lacking an actionable insight or reusable knowledge. Give a concise skip_reason.
- When keeping: be faithful to the source. Never invent tools, numbers, or steps that are not in it. If the source is \
thin, say so in the core_insight rather than padding.
- title: concise; write it in Turkish if the content is Turkish, otherwise technical English. No clickbait.
- slug: ASCII kebab-case (no Turkish characters), at most 8 words.
- target_folder: EXACTLY one of the allowed folders given below.
- tags: lowercase, kebab-case, 2-6 items. Reuse existing tags whenever one fits; invent new ones sparingly.
- core_insight: 2-4 sentences distilling the idea, tool, workflow or mental model (same language as the title).
- for_future_agent: 2-6 terse bullets of technical constraints, architecture patterns, commands, or context that a \
future AI agent would need to act on this knowledge.
- actionable_next_step: ONE concrete next action or experiment.
- related_wikilinks: only names from the "Existing note names" list, without brackets. Empty list if nothing fits.
- Respond with a single JSON object matching the schema. No markdown fences, no commentary."""


def _schema_text() -> str:
    return json.dumps(AtomicNoteSynthesis.model_json_schema(), ensure_ascii=False, indent=1)


def build_user_prompt(artifact: RawReelArtifact, ctx: VaultContext, max_chars: int) -> str:
    sections = [
        ("Caption", artifact.caption),
        ("Subtitles / audio transcript", artifact.transcript),
        ("On-screen text & visuals (OCR/VLM)", artifact.visual_notes),
    ]
    budget = max_chars
    body: list[str] = []
    for label, text in sections:
        text = (text or "").strip()
        if not text:
            continue
        text = text[: max(budget, 0)]
        budget -= len(text)
        body.append(f"### {label}\n{text}")
    meta = (
        f"creator: {artifact.creator or 'unknown'}\nurl: {artifact.url}\n"
        f"duration_seconds: {artifact.duration or 'unknown'}\nupload_date: {artifact.upload_date or 'unknown'}"
    )
    return (
        f"{ctx.prompt_block()}\n## JSON schema\n{_schema_text()}\n\n"
        f"## Reel metadata\n{meta}\n\n## Reel content\n" + ("\n\n".join(body) or "(empty)")
    )


# ---------------------------------------------------------------------- providers
def _call_groq(system: str, user: str, cfg: Config) -> str:
    from groq import Groq

    client = Groq(api_key=cfg.require_key("groq"))
    resp = client.chat.completions.create(
        model=cfg.synthesis.groq_model,
        temperature=cfg.synthesis.temperature,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content or ""


def _call_gemini(system: str, user: str, cfg: Config) -> str:
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


def _call_ollama(system: str, user: str, cfg: Config) -> str:
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


PROVIDERS: dict[str, Callable[[str, str, Config], str]] = {
    "groq": _call_groq,
    "gemini": _call_gemini,
    "ollama": _call_ollama,
}


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
