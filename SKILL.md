---
name: reels-wiki
description: Operate the reels-wiki pipeline (CLI `reels-sync`) that turns saved Instagram Reels into atomic notes in a 3-layer Obsidian LLM Wiki vault. Use when the user shares Instagram reel/post links, wants their Instagram saved posts imported, asks to process or check the reels queue, wants a reel note re-synthesized, or reports a failed/skipped reel.
---

# reels-wiki

Local-first pipeline: **Instagram URL → queue → metadata/caption → (audio transcript) → (frame OCR) → LLM synthesis → atomic note in the vault**. Notes land in the vault's own folders; `_index.md` and `_log.md` are updated; duplicates are impossible by design (dedupe on the 11-char shortcode).

## Ground rules

1. **Always pass `--json`** (before the subcommand) so output is machine-readable: `reels-sync --json stats`.
2. **Never edit** `inbox/reels-queue.jsonl`, `sources/.reels_index.json` or `sources/reels/*.json` by hand. Use the CLI/MCP tools. (If the index is lost it rebuilds itself from the queue.)
3. **Never create notes by hand for a reel** that exists in the index. Use `reprocess` so the existing note is updated in place.
4. **Process in small batches** (`--limit 5`). Each reel may cost a transcription and/or vision call and Instagram rate-limits aggressive scraping.
5. Do not use `--force` unless the user explicitly asks to redo a reel.
6. Never print or log API keys, cookies, or the Telegram token.

## Preflight (once per session)

```bash
reels-sync --json stats          # fails with a config error if vault/config is wrong
```
Required: `config.yaml` (or `REELS_WIKI_VAULT`), `GROQ_API_KEY` and/or `GEMINI_API_KEY` in `.env`. `ffmpeg` on PATH for audio/vision fallbacks. Instagram usually needs `extraction.cookies_file` or `extraction.cookies_from_browser`.

## Workflows

**User pastes link(s)**
```bash
reels-sync --json ingest "<url>" ["<url2>" ...]     # result per URL: enqueued | duplicate | invalid
reels-sync --json process --limit 5
```
Tell the user the note path(s) from `results[].note_path`, or the `skip_reason` if skipped. For `duplicate`, report the existing `status`/`note_path` instead of reprocessing.

**Bulk import from Instagram data export**
```bash
reels-sync --json import-ig /path/to/saved_posts.json    # or the export folder
reels-sync --json stats
reels-sync --json process --limit 10                       # repeat until pending == 0
```

**Checking progress**: `reels-sync --json stats` → `pending / processing / processed / skipped / failed`.

**Failures**: statuses and reasons are in `results[]` of `process` (`error`) and in `sources/.reels_index.json` (`error`).
- "login required / cookies / rate-limit" → ask the user to configure Instagram cookies; then `process --retry-failed --limit 5`.
- "ffmpeg not found" → ask the user to install ffmpeg.
- "No stored artifact" on reprocess → the reel was never extracted; use `process`.

**Improve or redo a note without re-downloading** (e.g. after changing the vault's `_CLAUDE.md`, folders or tags):
```bash
reels-sync --json reprocess <shortcode> [<shortcode> ...]
reels-sync --json reprocess --all          # re-synthesizes everything that has a stored artifact
```
Raw material is in `sources/reels/<shortcode>.json` (caption, transcript, on-screen text). Human edits to `status` and `created` in an existing note's frontmatter are preserved.

**Skipped items**: `should_keep=false` means the model judged the reel to be entertainment/low-signal. If the user disagrees, read `sources/reels/<shortcode>.json`, then tell them; they can ask for a re-run with `reprocess` after you adjust vault conventions.

## MCP tools (if the `reels-wiki` MCP server is connected)

`enqueue_reel(url, source, force)`, `import_ig_export(json_path, force, include_posts)`, `process_reels_queue(limit, retry_failed, dry_run)`, `get_queue_stats()`. Same semantics and rules as the CLI.

## What the pipeline guarantees (so you don't need to re-check)

- Folder, tags and wikilinks come from the vault's `_CLAUDE.md` / `_index.md`; links only point at existing notes, unknown ones are written as plain-text "new note candidates".
- Frontmatter is generated with python-frontmatter (always valid YAML, Turkish characters OK).
- `_index.md` insertion and `_log.md` appends are idempotent per note.
- Notes can only be written inside the vault.

## Repository map

`src/reels_wiki/`: `queue_manager.py` (dedupe/queue/state) · `ig_export.py` · `extractor.py` (yt-dlp → Groq/faster-whisper → ffmpeg+Gemini) · `vault_context.py` · `synthesizer.py` · `writer.py` · `pipeline.py` (orchestration) · `cli.py` · `mcp_server.py` · `telegram_bot.py`. Tests: `pytest`.
