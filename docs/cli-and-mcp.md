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
| `stats` | Show index counts by status and artifact count | — |
| `telegram` | Start long-polling Telegram share capture bot | — |
| `mcp` | Start MCP server over stdio | — |

## MCP Server (`reels-wiki-mcp`)

Run via `reels-wiki-mcp` or `reels-sync mcp` over `stdio` transport.

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `enqueue_reel` | `url`, `source="mcp"`, `force=False`, `vault_path=None` | Enqueue URL with shortcode deduplication |
| `import_ig_export` | `export_path`, `reels_only=False`, `force=False`, `vault_path=None` | Bulk-import Instagram data export |
| `process_reels_queue` | `limit=10`, `dry_run=False`, `retry_failed=False`, `force=False`, `vault_path=None` | Process pending queue items |
| `get_queue_stats` | `vault_path=None` | Return index status counts and artifact count |
