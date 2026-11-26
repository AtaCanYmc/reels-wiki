# Roadmap

Product and engineering milestones for `reels-wiki`, grouped by SemVer releases managed via `release-please`. Each milestone lists concrete module deliverables and verification gates.

## Milestone Overview

| Version | Focus | Status |
| :--- | :--- | :--- |
| `v0.1.0` | Core pipeline, 5 interfaces, governance, release automation | Completed |
| `v0.2.0` | Reliability, static analysis, coverage gates, `init` wizard, PyPI publishing | Completed |
| `v0.3.0` | Extraction fidelity, local LLM synthesis, observability | Completed |
| `v0.4.0` | Background scheduling, container packaging, ecosystem distribution | Completed |
| `v1.0.0` | Frozen schemas, public SDK contract, E2E fixture suite | Future |

## v0.1.0 (Completed)

- **Core Pipeline (`src/reels_wiki/`)**: URL normalization, append-only queue (`inbox/reels-queue.jsonl`) with O(1) index (`sources/.reels_index.json`), crash recovery, 3-stage waterfall extraction (`extractor.py`), LLM synthesis with noise filtering (`synthesizer.py`), and atomic vault updates (`writer.py`, `vault_context.py`).
- **Interfaces**: Python SDK (`reels_wiki`), CLI (`reels-sync`), MCP server (`reels-wiki-mcp`), Telegram capture bot (`reels-wiki-telegram`), and Agent Skill (`SKILL.md`).
- **Engineering Governance**: CI matrix across Python 3.10, 3.11, and 3.12, `release-please` automation with wheel/sdist/SHA256 release artifacts, Dependabot, Issue/PR templates, `Makefile`, and technical guides in `docs/`.

## v0.2.0 (Completed - Reliability, Quality Gates, and Packaging)

Focus: Turn the repository into a strictly verified package with zero broken entry points, static analysis gates, and automated PyPI releases.

- [x] **Entrypoint Smoke Verification**: Lock `reels-sync`, `reels-wiki-mcp`, and `reels-wiki-telegram` console scripts in `pyproject.toml` and run `--help` smoke tests in `.github/workflows/ci.yml`.
- [x] **Expanded Unit Coverage**: Add mocked-boundary tests for `extractor.py` (3-stage fallback branching), `pipeline.py` (crash reset and lock contention), and `mcp_server.py` (tool schemas and JSON outputs).
- [x] **Coverage Enforcement**: Add `pytest-cov` reporting and minimum coverage thresholds to `Makefile` and `.github/workflows/ci.yml`.
- [x] **Static Analysis Gates**: Add `ruff` (lint and formatting) and `mypy` (strict typing on `src/reels_wiki/`) to `pyproject.toml`, `Makefile`, and CI.
- [x] **Configuration & Diagnostics**:
  - Add `.env.example` with sanitized placeholders for all supported keys.
  - Implement `reels-sync doctor` to validate Python version, `ffmpeg`, cookie configuration, API key presence, and vault write permissions.
  - Implement `reels-sync init` interactive setup wizard for `config.yaml` and `.env` with automatic `doctor` verification.
  - Add `docs/troubleshooting.md`, `docs/saved-posts-workflow.md`, and `docs/telegram-bot.md`.
- [x] **PyPI Trusted Publishing**: Extend `.github/workflows/release-please.yml` to publish tagged wheels and sdists to PyPI via OIDC after checksum generation.

**Exit Criteria**: `make verify` passes `ruff`, `mypy`, `check-docs`, `check-release`, and `pytest` across Python 3.10 to 3.12, and all CLI entry points execute cleanly in CI.

## v0.3.0 (Completed - Extraction Fidelity and Local-First Providers)

Focus: Reduce failed extractions on edge-case Instagram posts, enable 100% offline synthesis, and expose cost/stage metrics.

- [x] **Instagram Edge Cases (`ingestion/queue_manager.py`, `pipeline/extractor.py`)**:
  - Resolve `/share/...` redirect URLs before shortcode extraction.
  - Handle image-only `/p/` carousel posts by routing downloaded frames to Gemini Vision when `yt-dlp` finds no video stream.
- [x] **Offline LLM Synthesis (`synthesizer.py`, `config.py`, `cli.py`)**:
  - Add an `ollama` / OpenAI-compatible local provider option alongside `groq` and `gemini` so audio (`faster-whisper`) and synthesis run completely offline.
- [x] **Stage & Token Observability (`pipeline/runner.py`, `pipeline/synthesizer.py`, `ingestion/queue_manager.py`)**:
  - Track waterfall stage counts (`metadata`, `subtitles`, `whisper`, `vision`) and LLM token/retry counts (`prompt_tokens`, `completion_tokens`, `total_tokens`, `retries`) in `sources/reels/<shortcode>.json` and `reels-sync --json stats`.
- [x] **Content-Hash Reprocessing (`vault/writer.py`)**:
  - Skip rewriting identical notes during `reels-sync reprocess --all` unless synthesized content or frontmatter actually changed.

**Exit Criteria**: A sample batch can run end-to-end offline using `faster-whisper` + local LLM without external API calls, and stage metrics appear in `reels-sync --json stats`.

## v0.4.0 (Completed - Automation, Scheduling, and Ecosystem)

Focus: Unattended background execution, containerized deployment, and broader package distribution.

- [x] **Unattended Scheduling & Containers**:
  - Ship copy-pasteable macOS `launchd` plist and Linux `systemd` user timer examples in `docs/deployment.md` for scheduled `reels-sync process` and `reels-sync telegram` execution.
  - Add a minimal `Dockerfile` and `docker-compose.yml` bundling Python and `ffmpeg` for headless server runs.
- [x] **Custom Note Templates & Vault Profiles (`vault/writer.py`, `core/config.py`)**:
  - Support an optional `template_path` in `config.yaml` while preserving required frontmatter (`status`, `created`) and `_index.md` / `_log.md` invariants.
- [x] **Package Manager Distribution**:
  - Publish a Homebrew formula and verify `pipx install` / `uv tool install` workflows in `docs/deployment.md`.
- [x] **MCP Server Expansion (`interfaces/mcp_server.py`)**:
  - Expose `reprocess_reel` and `search_vault_notes` tools so MCP agents can inspect existing vault notes and trigger targeted re-synthesis.

**Exit Criteria**: Containerized `reels-sync process` and `launchd`/`systemd` schedules run unattended against a mounted vault with zero manual intervention.

## v1.0.0 (Stable Contract)

Focus: Guarantee backward compatibility for configuration, on-disk vault artifacts, and Python SDK consumers.

- **Frozen Contracts**:
  - Lock `config.yaml` v1 schema with explicit deprecation warnings before removing any key.
  - Freeze `sources/reels/<shortcode>.json` and `inbox/reels-queue.jsonl` schemas so stored artifacts remain reprocessable across minor upgrades.
  - Stabilize the public Python SDK exports in `reels_wiki.__all__`.
- **E2E Fixture Vault Suite**:
  - Run automated end-to-end integration tests against a reference 3-layer Obsidian vault fixture verifying folder routing, tag normalization, wikilink preservation, `_index.md` idempotency, and `_log.md` formatting.
- **Migration Policy**:
  - Document version upgrade notes and schema migration procedures in `CHANGELOG.md` and `docs/`.

## Non-Goals

To keep `reels-wiki` predictable and local-first, the project explicitly avoids:

- **Hosted SaaS Backend**: Processing, keys, and vault state remain on the user's machine.
- **Instagram Anti-Bot Bypass**: The pipeline relies on standard `yt-dlp` sessions and user-supplied browser cookies rather than automated login or CAPTCHA solving.
- **Media Archival in Obsidian**: Video and audio files stay in temporary directories and are never copied into the Obsidian vault; only structured JSON artifacts and Markdown notes persist.
