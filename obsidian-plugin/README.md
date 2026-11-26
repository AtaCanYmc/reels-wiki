# reels-wiki Obsidian Plugin

Official Obsidian desktop plugin connecting your vault sidebar directly to your local `reels-sync serve` daemon.

## Features

- Sidebar health check and live queue counters (`GET /health`, `GET /stats`).
- One-click URL enqueueing for Instagram Reels, YouTube Shorts, and TikTok (`POST /ingest`).
- Targeted reprocess on the active note using its `shortcode` frontmatter (`POST /reprocess`).
- 7-day knowledge digest generation and automatic note opening (`POST /digest`).

## Local Installation

1. Build or copy `manifest.json`, `main.js`, and `styles.css` into `<YourVault>/.obsidian/plugins/reels-wiki/` (or unzip `dist/reels-wiki-obsidian-plugin.zip`).
2. Start the local server:

```bash
reels-sync serve
```

3. Enable **reels-wiki** under **Settings > Community plugins** in Obsidian, then click the film ribbon icon.
