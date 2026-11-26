[Back to Documentation](README.md)

# Migration & Backward-Compatibility Policy

`reels-wiki` follows strict v1 backward-compatibility guarantees for configuration files, stored vault artifacts, and the Python SDK surface so upgrades do not break existing Obsidian vaults or offline reprocessing.

---

## Frozen v1 Contracts

| Surface | Schema / Location | Stability Guarantee |
| :--- | :--- | :--- |
| Configuration | `config.yaml` (`schema_version: 1`, optional) | Unknown keys rejected (`extra="forbid"`); deprecated v1 keys emit `DeprecationWarning` for at least one minor release before removal |
| Extracted Artifacts | `sources/reels/<shortcode>.json` (`schema_version: 1`) | Loaded with `extra="ignore"`; older artifacts without `schema_version` and newer additive fields remain reprocessable offline |
| Queue Log | `inbox/reels-queue.jsonl` (`schema_version: 1`) | Append-only JSONL snapshots loaded with `extra="ignore"`; corrupted or lost `sources/.reels_index.json` rebuilds from this log |
| Public Python SDK | `reels_wiki.__all__` (`11` symbols) | Locked exports: `Config`, `ConfigError`, `QueueManager`, `enqueue`, `extract_shortcode`, `import_ig_export`, `load_config`, `normalize_url`, `process_queue`, `queue_stats`, `reprocess` |

---

## Deprecation Policy

- Before any `config.yaml` key is removed or renamed across minor versions, it is registered in `DEPRECATED_CONFIG_KEYS` (`src/reels_wiki/core/config.py`) and remains functional while emitting a Python `DeprecationWarning` from `load_config()`.
- Unsupported major `schema_version` values raise `ConfigError` loudly at startup instead of silently ignoring configuration intent.
- Existing Markdown notes inside your vault never have human-edited `status` or `created` frontmatter fields overwritten during `reels-sync reprocess` or `reels-sync process --force`.

---

## Upgrading Safely

1. Update the package and extraction backend:

```bash
pip install -U reels-wiki yt-dlp
```

2. Back up your vault directory (or commit to git) before running bulk synthesis changes.
3. Verify dependencies, cookies, API keys, and `config.yaml` validation:

```bash
reels-sync doctor
```

4. Re-synthesize stored artifacts without touching upstream social platforms or Whisper:

```bash
reels-sync reprocess --all
```

Unchanged rendered notes (identical SHA-256 content hash) are skipped automatically without rewriting `_index.md` or appending `_log.md`.

---

## Recovery & Rollback

| Scenario | Recovery Action |
| :--- | :--- |
| Index cache corrupted or deleted (`sources/.reels_index.json`) | Automatically rebuilt from `inbox/reels-queue.jsonl` on next queue operation (`QueueManager.rebuild_index()`) |
| Crash during processing (`status: "processing"`) | Stale `processing` items automatically reset to `pending` at the start of `reels-sync process` |
| Downgrading to an earlier patch/minor release | Existing v1 artifacts and queue lines with additive keys remain readable via `extra="ignore"` |
