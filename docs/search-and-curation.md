[Back to Documentation](README.md)

# Search, Curation & Digests

Guides covering `v1.1.0` and `v1.2.0` local-first vault recall, interactive curation, topic-scoped digests, backlinks, and bounded worker concurrency.

---

## 1. Local Hybrid Semantic Search (`reels-sync search`)

`reels-wiki` maintains an optional local search index inside `sources/.embeddings.sqlite` (rebuildable from Markdown notes, excluding `sources/`, `inbox/`, dot-directories, `_index.md`, `_log.md`, and `_CLAUDE.md`).

| Flag | Default | Description |
| :--- | :--- | :--- |
| `<query>` | Required | Search phrase or semantic topic |
| `--limit N` | `10` | Maximum number of ranked matches returned |
| `--backend` | `none` | `none` (keyword only), `ollama` (`/api/embeddings`), or `fastembed` |
| `--reindex` | `false` | Recompute stored vectors in `sources/.embeddings.sqlite` |

```bash
# Keyword-only search (zero external dependencies)
reels-sync search "ffmpeg framing"

# Hybrid keyword + local Ollama embeddings (uses synthesis.ollama_base_url)
reels-sync --json search "knowledge graph linking" --backend ollama --limit 5

# Rebuild SQLite embeddings after bulk edits
reels-sync search "mcp tools" --backend ollama --reindex
```

The MCP tool `search_vault_notes(query, limit=10, backend="none", vault_path=None)` uses the same hybrid search engine (`sources/.embeddings.sqlite`). If the chosen embedding backend is unreachable, `search_vault` falls back cleanly to keyword scoring.

---

## 2. Interactive Inbox Review (`reels-sync review`)

Step through synthesized notes carrying `status: inbox` without duplicating entries in `_index.md`:

```bash
reels-sync review --limit 10
```

| Key | Action | Result |
| :--- | :--- | :--- |
| `p` | Promote | Sets `status: evergreen`, ensures `_index.md` entry once, logs `review:promote` to `_log.md` |
| `t` | Retag | Replaces `tags` with normalized kebab-case slugs, logs `review:retag` |
| `a` | Archive | Sets `status: archived`, logs `review:archive` |
| `s` | Skip | Leaves file unchanged |
| `q` | Quit | Exits review loop |

For scripting or agent preflight inspection, pass `--json` before `review` to list inbox notes without waiting on stdin:

```bash
reels-sync --json review --limit 20
```

---

## 3. Weekly & Topic-Scoped Digests (`reels-sync digest`)

Generate Markdown summary notes grouped by tag across a configurable lookback window:

```bash
# Weekly digest across all notes from the past 7 days -> digests/<YYYY-MM-DD>-digest.md
reels-sync digest --days 7

# Monthly topic-scoped digest -> digests/<YYYY-MM-DD>-ai-agents-digest.md
reels-sync digest --days 30 --tag ai-agents

# Preview matching note count without writing files
reels-sync digest --days 30 --tag ai-agents --dry-run
```

---

## 4. Bidirectional Backlinks & Folder Prompt Profiles

Add optional graph enrichment and per-folder synthesis instructions in `config.yaml`:

```yaml
enable_backlinks: true

synthesis:
  provider: groq
  folder_prompts:
    tools: "Emphasize exact CLI commands, config keys, and constraints."
    learning: "Emphasize core mental models and trade-offs."
```

- When `enable_backlinks: true`, matched `[[Existing Note]]` links receive `- [[source_slug|source_title]]` under `## Related Links` idempotently without changing human prose or frontmatter (`status`, `created`).
- Entries under `synthesis.folder_prompts` append a `## Folder-specific guidance` section to each synthesis prompt.

---

## 5. Bounded Worker Concurrency (`--workers`)

Speed up multi-item batches safely across LLM/synthesis stages:

```bash
reels-sync process --limit 20 --workers 4
```

Execution stays split into three safe phases under a single vault `FileLock`:

1. **Extraction (serial)**: honors `delay_seconds` per host between `yt-dlp` downloads.
2. **Synthesis (concurrent)**: runs LLM synthesis across up to `--workers` threads using thread-local usage tracking.
3. **Vault writes (serial)**: commits notes, `_index.md`, `_log.md`, and `inbox/reels-queue.jsonl` sequentially on the main thread with zero write races.
