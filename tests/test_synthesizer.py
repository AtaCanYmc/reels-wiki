import json

import pytest

from reels_wiki import synthesizer
from reels_wiki.config import Config
from reels_wiki.models import AtomicNoteSynthesis, RawReelArtifact
from reels_wiki.synthesizer import SynthesisError, normalize_synthesis, parse_json_object, synthesize
from reels_wiki.utils import slugify
from reels_wiki.vault_context import VaultContext


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "_CLAUDE.md").write_text("Folders: `ideas/`, `tools/`. Tags: #ai", encoding="utf-8")
    (tmp_path / "ideas").mkdir()
    (tmp_path / "ideas" / "Known Note.md").write_text("x", encoding="utf-8")
    return VaultContext.load(tmp_path)


@pytest.fixture
def cfg(tmp_path):
    return Config(vault_path=tmp_path, groq_api_key="k", gemini_api_key="k")


ART = RawReelArtifact(shortcode="DAbCdEfGhIj", url="https://www.instagram.com/reel/DAbCdEfGhIj/", caption="Some content")


def test_slugify_turkish_and_symbols():
    assert slugify("Çalışma Şekli: Öğrenme & Güçlü İdeas!") == "calisma-sekli-ogrenme-guclu-ideas"
    assert slugify("") == "" and slugify("***") == ""


def test_parse_json_object_handles_fences_and_chatter():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Here you go: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}
    with pytest.raises(json.JSONDecodeError):
        parse_json_object("no json here")


def test_normalize_enforces_vault_rules(ctx):
    raw = AtomicNoteSynthesis(
        should_keep=True, title="Başlık", slug="Başlık Örnek!!", target_folder="Nonexistent",
        tags=["#AI", "ai", "Büyük Dil/Modeli"], core_insight="x", related_wikilinks=["known note", "Ghost"],
    )
    out = normalize_synthesis(raw, ctx, ART)
    assert out.slug == "baslik-ornek" and out.target_folder == ctx.default_folder
    assert out.tags == ["ai", "buyuk-dil-modeli"]
    assert out.related_wikilinks == ["Known Note", "Ghost"]


def test_empty_artifact_skips_without_llm_call(ctx, cfg, monkeypatch):
    monkeypatch.setitem(synthesizer.PROVIDERS, "groq", lambda *a: pytest.fail("LLM must not be called"))
    out = synthesize(RawReelArtifact(shortcode="X" * 11, url="u"), ctx, cfg)
    assert out.should_keep is False and "No extractable content" in out.skip_reason


def test_retry_repairs_invalid_json(ctx, cfg, monkeypatch):
    calls = []
    good = json.dumps({"should_keep": True, "title": "T", "slug": "t", "target_folder": "tools", "core_insight": "c"})

    def fake(system, user, cfg):
        calls.append(user)
        return "not json" if len(calls) == 1 else good

    monkeypatch.setitem(synthesizer.PROVIDERS, "groq", fake)
    out = synthesize(ART, ctx, cfg)
    assert out.title == "T" and out.target_folder == "tools"
    assert len(calls) == 2 and "previous reply was invalid" in calls[1]


def test_fallback_provider_used_when_primary_fails(ctx, tmp_path, monkeypatch):
    cfg = Config(vault_path=tmp_path, groq_api_key="k", gemini_api_key="k",
                 synthesis={"provider": "groq", "fallback_provider": "gemini", "max_retries": 2})
    monkeypatch.setattr(synthesizer.time, "sleep", lambda s: None)

    def boom(*a):
        raise RuntimeError("rate limited")

    monkeypatch.setitem(synthesizer.PROVIDERS, "groq", boom)
    monkeypatch.setitem(synthesizer.PROVIDERS, "gemini",
                        lambda *a: json.dumps({"should_keep": False, "skip_reason": "meme"}))
    out = synthesize(ART, ctx, cfg)
    assert out.should_keep is False and out.skip_reason == "meme"


def test_all_providers_failing_raises(ctx, cfg, monkeypatch):
    monkeypatch.setattr(synthesizer.time, "sleep", lambda s: None)
    monkeypatch.setitem(synthesizer.PROVIDERS, "groq", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(SynthesisError):
        synthesize(ART, ctx, cfg)


def test_kept_note_requires_title_and_insight():
    with pytest.raises(ValueError):
        AtomicNoteSynthesis(should_keep=True, title="", core_insight="")


def test_ollama_provider_synthesizes_offline(tmp_path, ctx, monkeypatch):
    from reels_wiki.config import Config

    cfg = Config(vault_path=tmp_path, synthesis={"provider": "ollama", "ollama_model": "llama3.1:8b"})
    payload = {
        "should_keep": True,
        "title": "Offline Synthesis",
        "slug": "offline-synthesis",
        "target_folder": "concepts",
        "tags": ["local-llm"],
        "core_insight": "Ollama synthesizes notes locally via OpenAI-compatible chat completions.",
        "for_future_agent": ["No cloud API keys required."],
        "actionable_next_step": "Run ollama serve.",
        "related_wikilinks": [],
    }

    class _FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    captured = {}

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return _FakeResp()

    monkeypatch.setattr(synthesizer.httpx, "post", _fake_post)
    out = synthesize(ART, ctx, cfg)
    assert out.should_keep is True
    assert out.title == "Offline Synthesis"
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["json"]["model"] == "llama3.1:8b"
