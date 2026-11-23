# Roadmap

## v0.1.0 (Current)

- Instagram Reel extraction via `yt-dlp` and Instagram data export ingestion (`reels_wiki.ig_export`).
- Audio transcription and synthesis pipeline (`reels_wiki.synthesizer`, `reels_wiki.pipeline`).
- Atomic Markdown note generation with frontmatter for Obsidian vaults (`reels_wiki.writer`).
- CLI (`reels-sync`), MCP server (`reels-wiki-mcp`), and Telegram bot (`reels-wiki-telegram`) entry points.

## v0.2.0

- CI test matrix across Python 3.10, 3.11, and 3.12.
- Expanded unit test coverage for `extractor`, `pipeline`, and `mcp_server`.
- Automated release tagging via Conventional Commits.
