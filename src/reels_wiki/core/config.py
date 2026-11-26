"""YAML + .env configuration loader with validation."""
from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Literal

import yaml
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

CONFIG_SCHEMA_VERSION = 1
DEPRECATED_CONFIG_KEYS: dict[str, str] = {}


class ConfigError(RuntimeError):
    """Raised for missing/invalid configuration or secrets."""


class ExtractionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_caption_chars: int = Field(150, ge=0)
    min_transcript_chars: int = Field(40, ge=0)
    enable_whisper_fallback: bool = True
    whisper_provider: Literal["groq", "local"] = "groq"
    groq_whisper_model: str = "whisper-large-v3-turbo"
    local_whisper_model: str = "small"
    whisper_language: str | None = None
    enable_vision_fallback: bool = True
    vision_frames: int = Field(4, ge=1, le=12)
    vision_model: str = "gemini-2.5-flash"
    cookies_file: Path | None = None
    cookies_from_browser: str | None = None
    ffmpeg_path: str = "ffmpeg"

    @field_validator("cookies_file")
    @classmethod
    def _expand_cookies(cls, v: Path | None) -> Path | None:
        return v.expanduser() if v else v


class SynthesisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["groq", "gemini", "ollama"] = "groq"
    groq_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1:8b"
    ollama_api_key: str = "ollama"
    fallback_provider: Literal["groq", "gemini", "ollama"] | None = None
    max_retries: int = Field(3, ge=1, le=8)
    temperature: float = Field(0.2, ge=0, le=2)
    max_input_chars: int = Field(12000, ge=1000)


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    vault_path: Path
    template_path: Path | None = None
    allowed_folders: list[str] | None = None
    default_folder: str | None = None
    delay_seconds: float = Field(2.0, ge=0)
    extraction: ExtractionConfig = Field(default_factory=lambda: ExtractionConfig())
    synthesis: SynthesisConfig = Field(default_factory=lambda: SynthesisConfig())

    # Secrets: populated from the environment / .env, never required in YAML.
    groq_api_key: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    telegram_bot_token: str | None = Field(default=None, repr=False)
    telegram_allowed_chat_id: int | None = None

    @field_validator("vault_path")
    @classmethod
    def _expand_vault(cls, v: Path) -> Path:
        return v.expanduser().resolve()

    @field_validator("template_path")
    @classmethod
    def _expand_template(cls, v: Path | None) -> Path | None:
        return v.expanduser().resolve() if v else v

    def require_key(self, provider: str) -> str:
        if provider == "ollama":
            return self.synthesis.ollama_api_key
        key = {"groq": self.groq_api_key, "gemini": self.gemini_api_key}.get(provider)
        if not key:
            env = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]
            raise ConfigError(f"{env} is not set (add it to .env or the environment)")
        return key


def _candidate_paths(explicit: Path | None) -> list[Path]:
    out: list[Path] = []
    if explicit:
        out.append(Path(explicit).expanduser())
    if os.environ.get("REELS_WIKI_CONFIG"):
        out.append(Path(os.environ["REELS_WIKI_CONFIG"]).expanduser())
    out.append(Path.cwd() / "config.yaml")
    out.append(Path.home() / ".config" / "reels-wiki" / "config.yaml")
    return out


def _has_dotted_key(data: dict, dotted: str) -> bool:
    cur: object = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def _warn_deprecated_keys(data: dict) -> None:
    for key, hint in DEPRECATED_CONFIG_KEYS.items():
        if _has_dotted_key(data, key):
            warnings.warn(
                f"Config key '{key}' is deprecated and will be removed in a future release: {hint}",
                DeprecationWarning,
                stacklevel=3,
            )


def load_config(
    path: Path | str | None = None,
    *,
    vault_override: Path | str | None = None,
    require_vault: bool = True,
) -> Config:
    """Load config from YAML (first of: explicit path, $REELS_WIKI_CONFIG, ./config.yaml, ~/.config/...) + env."""
    load_dotenv(find_dotenv(usecwd=True), override=False)

    explicit = Path(path) if path else None
    if explicit and not explicit.expanduser().is_file():
        raise ConfigError(f"Config file not found: {explicit}")

    data: dict = {}
    for cand in _candidate_paths(explicit):
        if cand.is_file():
            try:
                data = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise ConfigError(f"Invalid YAML in {cand}: {exc}") from exc
            if not isinstance(data, dict):
                raise ConfigError(f"{cand} must contain a YAML mapping at the top level")
            break

    vault = vault_override or os.environ.get("REELS_WIKI_VAULT") or data.get("vault_path")
    if not vault:
        raise ConfigError("No vault configured: set vault_path in config.yaml, REELS_WIKI_VAULT, or pass --vault")
    data["vault_path"] = str(vault)

    for key, env in (
        ("groq_api_key", "GROQ_API_KEY"),
        ("gemini_api_key", "GEMINI_API_KEY"),
        ("telegram_bot_token", "TELEGRAM_BOT_TOKEN"),
    ):
        if os.environ.get(env):
            data[key] = os.environ[env]
    chat = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    if chat:
        try:
            data["telegram_allowed_chat_id"] = int(chat)
        except ValueError as exc:
            raise ConfigError("TELEGRAM_ALLOWED_CHAT_ID must be an integer") from exc

    try:
        _warn_deprecated_keys(data)
        cfg = Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration:\n{exc}") from exc

    if require_vault and not cfg.vault_path.is_dir():
        raise ConfigError(f"Vault directory does not exist: {cfg.vault_path}")
    return cfg
