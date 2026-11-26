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
| `ingest <url>` | Enqueue a single Instagram URL | `--source`, `--force` |
| `import-ig <path>` | Bulk-import from `saved_posts.json` or export folder | `--reels-only`, `--force` |
| `process` | Run waterfall extraction, synthesis, and note writing | `--limit N`, `--dry-run`, `--retry-failed`, `--force` |
| `reprocess [shortcode]` | Re-synthesize from `sources/reels/<code>.json` | `--all`, `--dry-run` |
| `stats` | Show queue counts, artifact count, extraction `stages`, and `llm_usage` token/retry metrics | None |
| `doctor` | Verify Python, `ffmpeg`, cookies, API keys, and vault permissions | None |
| `init` | Interactively scaffold `config.yaml`, `.env`, and run `doctor` | `--env-path PATH`, `--force` |
| `telegram` | Start long-polling Telegram share capture bot | None |
| `mcp` | Start MCP server over stdio | None |

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
| `search_vault_notes` | `query`, `limit=10`, `vault_path=None` | Search Markdown notes inside the vault (excluding `sources/` and `inbox/`) |
