# Architecture

`reels-wiki` is a local-first pipeline that ingests saved Instagram Reels, YouTube Shorts, and TikTok videos, extracts text through a 3-stage waterfall, synthesizes atomic notes via LLM, and updates a 3-layer Obsidian LLM Wiki vault.

## Data Flow

![reels-wiki Core Pipeline Architecture](../assets/architecture-diagram.svg)

## Vault Layout

| Path | Purpose |
| :--- | :--- |
| `inbox/reels-queue.jsonl` | Append-only queue of ingested Instagram URLs |
| `sources/.reels_index.json` | Shortcode-keyed state index (`pending`, `processing`, `processed`, `skipped`, `failed`) |
| `sources/reels/<code>.json` | Raw extracted metadata, caption, transcript, and vision notes |
| `<folder>/<slug>.md` | Synthesized atomic Markdown note with YAML frontmatter |
| `_index.md` | Idempotent vault index updated on each kept note |
| `_log.md` | Append-only processing log |
| `_CLAUDE.md` | Vault-level conventions, allowed folders, and tag rules |

## Design Guarantees

- **Multi-Platform ID Deduplication**: Instagram `/reel/`, `/reels/`, `/p/`, `/tv/`, and `/share/...` URLs normalize to 11-character shortcodes, YouTube Shorts normalize to `yt_<id>`, and TikTok video URLs normalize to `tt_<id>` (`https://www.tiktok.com/@_/video/<id>`).
- **Frozen v1 Contracts**: `sources/reels/<code>.json`, `inbox/reels-queue.jsonl`, and `config.yaml` carry `schema_version: 1` with backward/forward-compatible `extra="ignore"` loading for persisted queue and artifact data. See [Migration Policy](migration.md).
- **No Media Stored**: Downloaded audio and video frames are deleted after extraction; only `sources/reels/<code>.json` persists.
- **Re-synthesizable Artifacts**: `reels-sync reprocess` re-runs LLM synthesis from `sources/reels/<code>.json` without re-downloading media.

## Examples

### Stored Raw Artifact (`sources/reels/ABC12345678.json`)

```json
{
  "schema_version": 1,
  "shortcode": "ABC12345678",
  "url": "https://www.instagram.com/reel/ABC12345678/",
  "creator": "example_creator",
  "caption": "Three habits for local-first note taking.",
  "transcript": "Keep raw sources separate from synthesized atomic notes...",
  "visual_notes": "",
  "steps_used": ["metadata", "whisper:groq"]
}
```

### Synthesized Atomic Note (`ideas/local-first-note-taking.md`)

```markdown
---
title: Local-First Note Taking
source_url: https://www.instagram.com/reel/ABC12345678/
shortcode: ABC12345678
tags: [pkm, obsidian]
status: inbox
created: 2026-11-24
---

Separate raw captured sources from synthesized atomic notes so prompts can evolve without re-downloading media.
```

