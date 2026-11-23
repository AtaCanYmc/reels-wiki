---
name: reels-wiki
description: Turn saved Instagram Reels into deduplicated atomic idea notes inside an Obsidian 3-layer LLM Wiki vault using the reels-sync CLI or reels-wiki MCP tools.
---

# reels-wiki Skill

Use this skill when ingesting Instagram Reels URLs or `saved_posts.json` exports, inspecting queue/index state, processing the waterfall extraction and LLM synthesis pipeline, or re-synthesizing stored raw artifacts into an Obsidian LLM Wiki vault.

## Core Principles

- **Shortcode Deduplication First:** Every Instagram URL (`/reel/`, `/reels/`, `/p/`, `/tv/`, optional `/<user>/`, query params stripped) maps to an 11-character shortcode and canonical URL `https://www.instagram.com/reel/<shortcode>/`. Never bypass deduplication unless `--force` or `force=True` is explicitly requested.
- **No Media in Vault:** Raw metadata, captions, transcripts, and vision notes live in `sources/reels/<shortcode>.json`. Temporary audio/frame files are cleaned up automatically.
- **Vault Conventions Are Authoritative:** Before synthesizing a note, read `_CLAUDE.md` and `_index.md` in the vault root to respect allowed target folders, tag conventions, and existing note titles for `[[wikilinks]]`.
- **Filter Out Noise:** Drop memes, trends, and insight-free clips (`should_keep=false` -> `skipped`) instead of creating low-value notes.
- **Keep Wiki Indexes in Sync:** Valid notes write `<folder>/<slug>.md` with frontmatter, append to `_log.md`, and idempotently update `_index.md`.

## CLI Workflow (`reels-sync`)

Place `--json` before the subcommand when machine-readable output is needed:

- **Ingest a URL:**
  `reels-sync --json ingest "https://www.instagram.com/reel/<shortcode>/?igsh=..."`
- **Import Instagram export (`saved_posts.json` or folder):**
  `reels-sync --json import-ig ~/Downloads/instagram-export/ --reels-only`
- **Inspect queue & index stats:**
  `reels-sync --json stats`
- **Preview processing:**
  `reels-sync process --limit 10 --dry-run`
- **Process queue (optionally retry failed items):**
  `reels-sync --json process --limit 10 --retry-failed`
- **Re-synthesize from stored artifact (no re-download or Whisper):**
  `reels-sync --json reprocess <shortcode>` or `reels-sync --json reprocess --all`
- **Run long-polling Telegram capture bot:**
  `reels-sync telegram`
- **Run MCP server over stdio:**
  `reels-sync mcp`

## MCP Tools (`reels-wiki-mcp`)

When connected to the `reels-wiki` MCP server, prefer these tools:

1. `enqueue_reel(url, source="mcp", force=False, vault_path=None)` — Add a single URL to the queue.
2. `import_ig_export(export_path, reels_only=False, force=False, vault_path=None)` — Bulk-import from `saved_posts.json` or an export directory.
3. `process_reels_queue(limit=10, dry_run=False, retry_failed=False, force=False, vault_path=None)` — Run extraction, synthesis, and note writing.
4. `get_queue_stats(vault_path=None)` — Inspect counts by status and stored raw artifacts.

## Guardrails

- Instagram `/share/...` redirect links are not resolved automatically; ask the user to open the link once and provide the canonical `/reel/` or `/p/` URL if needed.
- Never overwrite existing user edits to `status` or `created` frontmatter fields on forced re-runs of an existing note (`note_path`).
