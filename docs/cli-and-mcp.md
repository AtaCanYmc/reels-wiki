# CLI and MCP Reference

## CLI (`reels-sync`)

Global flags must appear **before** the subcommand:

```bash
reels-sync [--config PATH] [--vault PATH] [--json] [-v] <subcommand>
```

| Flag | Description |
| :--- | :--- |
| `--config PATH` | Path to `config.yaml` |
| `--vault PATH` | Override Obsidian vault path |
| `--json` | Emit machine-readable JSON to stdout (logs go to stderr) |
| `-v`, `--verbose` | Enable debug logging |

### Subcommands

| Command | Description | Key Flags |
| :--- | :--- | :--- |
| `ingest <url>` | Enqueue an Instagram, YouTube Shorts, or TikTok URL | `--source`, `--force` |
| `import-ig <path>` | Bulk-import from `saved_posts.json` or export folder | `--reels-only`, `--force` |
| `process` | Run waterfall extraction, synthesis, and note writing | `--limit N`, `--dry-run`, `--retry-failed`, `--force`, `--workers N` |
| `reprocess [shortcode]` | Re-synthesize from `sources/reels/<code>.json` | `--all`, `--dry-run` |
| `stats` | Show queue counts, artifact count, extraction `stages`, and `llm_usage` token/retry metrics | None |
| `doctor` | Verify Python, `ffmpeg`, cookies, API keys, and vault permissions | None |
| `init` | Run 4-step wizard (vault/folders, extraction/fallbacks, synthesis/keys, Telegram) and `doctor` | `--env-path PATH`, `--force` |
| `telegram` | Start long-polling Telegram share capture bot | None |
| `mcp` | Start MCP server over stdio | None |
| `serve` | Start 8-endpoint HTTP server (`/health`, `/stats`, `/queue`, `/search`, `/ingest` with optional `process: true`, `/process`, `/reprocess`, `/digest`) | `--host`, `--port` |
| `digest` | Generate summary note grouping recent vault notes by tag | `--days N`, `--tag TAG`, `--dry-run` |
| `search <query>` | Search vault notes via hybrid keyword + local embeddings (`sources/.embeddings.sqlite`) | `--limit N`, `--backend`, `--reindex` |
| `review` | Interactively promote, retag, or archive `status: inbox` vault notes | `--limit N` |

### Output Modes

- **Default (Terminal UI)**: Renders Rich panels, tables, and live per-item progress rows during `process` and `reprocess`.
- **Machine-Readable (`--json`)**: Emits pure JSON to stdout and sends logs to stderr, bypassing Rich formatting.

### Examples

```bash
# Enqueue a single Reel URL
reels-sync ingest "https://www.instagram.com/reel/ABC12345678/?igsh=xyz"

# Import saved posts from Instagram export (Reels only)
reels-sync import-ig ~/Downloads/instagram-export/saved_posts.json --reels-only

# Preview next 5 queued items without writing notes
reels-sync process --limit 5 --dry-run

# Process up to 10 items and retry previously failed ones
reels-sync --json process --limit 10 --retry-failed

# Re-synthesize a single stored artifact without re-downloading
reels-sync reprocess ABC12345678

# Check queue and index stats as JSON
reels-sync --json stats

# Run runtime diagnostics in human-readable or JSON format
reels-sync doctor
reels-sync --json doctor

# Start local HTTP ingest server for Shortcuts and browser extensions
reels-sync serve

# Generate weekly summary note for notes from the past 7 days
reels-sync digest --days 7

# Generate topic-scoped summary note across the last 30 days
reels-sync digest --days 30 --tag ai-agents

# Interactively curate inbox notes (promote to evergreen, retag, or archive)
reels-sync review --limit 10

# Search vault notes via keyword or local Ollama/fastembed index
reels-sync search "ffmpeg framing" --backend ollama
```

## MCP Server (`reels-wiki-mcp`)

Run via `reels-wiki-mcp` or `reels-sync mcp` over `stdio` transport.

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `enqueue_reel` | `url`, `source="mcp"`, `force=False`, `vault_path=None` | Enqueue URL with shortcode deduplication |
| `import_ig_export` | `export_path`, `reels_only=False`, `force=False`, `vault_path=None` | Bulk-import Instagram data export |
| `process_reels_queue` | `limit=10`, `dry_run=False`, `retry_failed=False`, `force=False`, `vault_path=None` | Process pending queue items |
| `get_queue_stats` | `vault_path=None` | Return index status counts and artifact count |
| `reprocess_reel` | `shortcode=None`, `all_items=False`, `vault_path=None` | Re-synthesize from stored `sources/reels/<code>.json` artifacts |
| `search_vault_notes` | `query`, `limit=10`, `backend="none"`, `vault_path=None` | Search Markdown notes inside the vault via hybrid keyword + local embedding index |
