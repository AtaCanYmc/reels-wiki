# reels-wiki

Local-first pipeline that turns **saved Instagram Reels** into **atomic idea notes** inside an existing 3-layer Obsidian LLM Wiki vault (`sources/` → atomic note → `_index.md` / `_log.md`), without duplicates and without breaking the vault's conventions.

```
 Telegram share ─┐
 IG data export ─┼─► inbox/reels-queue.jsonl ─► waterfall extraction ─► LLM synthesis ─► <folder>/<slug>.md
 CLI / MCP / SDK ┘   sources/.reels_index.json   1 yt-dlp metadata        (noise filter)    _index.md + _log.md
                     (dedupe by shortcode)       2 audio → Whisper                         sources/reels/<code>.json
                                                 3 frames → Gemini OCR                     (re-synthesizable raw data)
```

Surfaces: **SDK** (`import reels_wiki`), **CLI** (`reels-sync`), **MCP server** (`reels-wiki-mcp`), **Agent Skill** (`SKILL.md`), **Telegram capture bot** (`reels-wiki-telegram`).

## Install

Requires Python ≥ 3.10 and `ffmpeg` on your PATH (only used by the audio/vision fallbacks).

```bash
git clone <this repo> && cd reels-to-obsidian
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # add ".[local]" for offline faster-whisper
cp config.example.yaml config.yaml # set vault_path
cp .env.example .env               # GROQ_API_KEY / GEMINI_API_KEY (+ Telegram vars if used)
reels-sync stats                   # sanity check
```

Config lookup order: `--config`, `$REELS_WIKI_CONFIG`, `./config.yaml`, `~/.config/reels-wiki/config.yaml`. `--vault` / `$REELS_WIKI_VAULT` override `vault_path`. Unknown keys in `config.yaml` are rejected (typo protection).

### Instagram authentication

Instagram blocks anonymous scraping. Configure **one** of (under `extraction:`):

- `cookies_from_browser: chrome` (or `firefox`, `"chrome:Profile 1"`) — yt-dlp reads your logged-in browser session, or
- `cookies_file: ~/cookies.txt` — a Netscape-format export.

Use a secondary account if you are cautious; keep `delay_seconds` ≥ 2 and process in batches. Keep yt-dlp current (`pip install -U yt-dlp`): Instagram changes often.

## Usage

```bash
reels-sync ingest "https://www.instagram.com/reel/DAbCdEfGhIj/?igsh=xyz"   # dedupes by shortcode
reels-sync import-ig ~/Downloads/instagram-export/                          # saved_posts.json or its folder
reels-sync process --limit 10          # extract → synthesize → write
reels-sync process --dry-run           # what would run
reels-sync process --retry-failed
reels-sync reprocess DAbCdEfGhIj       # re-synthesize from stored artifact (no download, no Whisper)
reels-sync reprocess --all
reels-sync stats
reels-sync telegram                    # long-polling share bot
reels-sync mcp                         # MCP server on stdio
reels-sync --json stats                # JSON for agents/scripts (global flag goes before the subcommand)
```

**Instagram export**: Instagram → Accounts Center → *Your information and permissions* → *Export your information* → choose **JSON** and include saved items. The file is `saved_posts.json` (`saved_saved_media → string_map_data → "Saved on" → href`).

**Telegram**: create a bot with @BotFather, put `TELEGRAM_BOT_TOKEN` and your numeric `TELEGRAM_ALLOWED_CHAT_ID` (ask @userinfobot) in `.env`, run `reels-sync telegram`, then use *Share → Telegram → your bot* on a Reel. The bot ignores every other chat and refuses to start without an allowed chat id. It only enqueues; run `reels-sync process` (cron/launchd) to digest.

**MCP** (Claude Desktop / Claude Code):
```json
{ "mcpServers": { "reels-wiki": { "command": "/path/to/.venv/bin/reels-wiki-mcp",
                                   "env": { "REELS_WIKI_CONFIG": "/path/to/config.yaml" } } } }
```
Tools: `enqueue_reel`, `import_ig_export`, `process_reels_queue`, `get_queue_stats`.

**SDK**:
```python
from reels_wiki import load_config, enqueue, process_queue
cfg = load_config()
enqueue("https://www.instagram.com/reel/DAbCdEfGhIj/", "script", vault=cfg.vault_path)
process_queue(cfg, limit=3)
```

## How it works

**Deduplication.** Every URL form (`/reel/`, `/reels/`, `/p/`, `/tv/`, optional `/<user>/`, tracking params) is reduced to the 11-character shortcode and normalized to `https://www.instagram.com/reel/<shortcode>/`. `sources/.reels_index.json` (`shortcode → {status, url, note_path, updated_at}`) is the O(1) gate; nothing known is enqueued without `--force`. The queue (`inbox/reels-queue.jsonl`) is append-only: each state change appends a snapshot and the last line per shortcode wins. If the index is lost or corrupt it is rebuilt from the queue. Writes are atomic and guarded by a file lock; one `process` run per vault at a time, and items stuck in `processing` after a crash are reset automatically. A forced re-run keeps the previous `note_path`, so it **overwrites that note rather than creating a second one** (your edits to `status`/`created` survive).

**Waterfall (cost-aware).**
1. *Metadata* via the `yt_dlp` Python API (`extract_info(download=False)`): caption, creator, duration, date, subtitles if any. Free.
2. *Audio → text* only if the caption is shorter than `min_caption_chars` (150) and no usable subtitles exist: audio is downloaded to a temp dir and transcribed with Groq `whisper-large-v3-turbo` or local `faster-whisper`.
3. *Frames → Gemini* only if caption **and** transcript are both thin (`min_caption_chars` / `min_transcript_chars`): `vision_frames` (4) evenly spaced frames via ffmpeg are sent to `gemini-2.5-flash` to read on-screen text/code/diagrams.

Step failures never abort the reel; they are recorded in the artifact's `warnings`. Reels with no text at all are skipped without spending an LLM call. Everything is saved to `sources/reels/<shortcode>.json`; no media ever touches the vault.

**Vault compliance.** Before synthesis the vault is read: allowed folders (backticked `` `folder/` `` tokens in `_CLAUDE.md`/`_index.md`, else top-level directories; `sources/` and `inbox/` are never targets; `allowed_folders` in config overrides), tag taxonomy (`#tags` in those files plus note frontmatter), and existing note names/titles. The model's output is then *enforced*, not trusted: folder must be allowed (else `default_folder`), slug is re-slugified to ASCII (Turkish transliterated), tags are normalized, and `related_wikilinks` that don't match a real note are written as plain `(new note candidate) …` text, never as dangling links. Notes are written with `python-frontmatter`; the target path is checked to stay inside the vault. `_log.md` entries follow the style already in the file (`## [YYYY-MM-DD] ingest | …` or a bullet line); `_index.md` entries go under the heading matching the folder (created if missing) and are idempotent.

**Noise filtering.** The synthesis schema (`AtomicNoteSynthesis`) has `should_keep`; memes, trends and insight-free content become `skipped` (with `skip_reason` in the index) and produce no note. Invalid JSON triggers repair retries, then the optional `fallback_provider`.

## Layout

`src/reels_wiki/` implements the modules in the spec plus two small shared ones: `pipeline.py` (orchestration used by CLI/MCP) and `utils.py` (atomic writes, slugify). Tests are in `tests/` (`pytest`): queue/URL parsing/dedupe, IG export parsing, writer/vault-context behaviour, and synthesizer normalization/retry logic. Network and LLM calls are never made in tests.

## Notes & limits

- Shortcodes are validated as exactly 11 characters (`[A-Za-z0-9_-]`); Instagram `/share/...` redirect links are not resolved: open them once and copy the real URL.
- Carousel/photo posts (`/p/`) are accepted; yt-dlp may fail on image-only posts, which are then marked `failed` with the reason (use `import-ig --reels-only` to skip them up front).
- Titles are generated in Turkish for Turkish content and technical English otherwise.
- Provider SDK surfaces (Groq, google-genai, yt-dlp) move quickly; if a call signature changes, the isolated provider functions in `extractor.py` / `synthesizer.py` are the only places to touch.
