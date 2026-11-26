# Changelog

For frozen v1 schemas (`config.yaml`, `sources/reels/<shortcode>.json`, `inbox/reels-queue.jsonl`, `reels_wiki.__all__`), deprecation notices, and upgrade/rollback procedures, see [Migration & Backward-Compatibility Policy](docs/migration.md).

## [0.1.5](https://github.com/AtaCanYmc/reels-wiki/compare/v0.1.4...v0.1.5) (2026-11-26)


### Features

* add build target for generating Safari Web Extension and update documentation ([a391826](https://github.com/AtaCanYmc/reels-wiki/commit/a3918266ae6326c5a0614aca53c6dbf91671d482))
* add HTTP endpoint tests for health check, stats, and ingesting social media content ([0a82945](https://github.com/AtaCanYmc/reels-wiki/commit/0a82945498dde50fbab5723f3ceb48c8efeba3cb))
* add HTTP endpoints for listing queue items and searching vault notes ([956796c](https://github.com/AtaCanYmc/reels-wiki/commit/956796cb3f0f060281aa67b4545cebfca3a3dd2c))
* add instructions for converting extension to Safari Web Extension using Xcode ([9e4c489](https://github.com/AtaCanYmc/reels-wiki/commit/9e4c489552101bb58ccb8d909d1deb829dd78192))
* add Obsidian Community Plugin Store submission details to roadmap ([1cfed8e](https://github.com/AtaCanYmc/reels-wiki/commit/1cfed8e55a784108586e0a791dba5071f01af26c))
* add process queue endpoint with dry run capability and HTTP access logging ([6bec390](https://github.com/AtaCanYmc/reels-wiki/commit/6bec3908e01d4ed1a4906ea7b5767f1c7da72911))
* add zero-cost hosting and tunneling patterns to deployment documentation ([99714ba](https://github.com/AtaCanYmc/reels-wiki/commit/99714ba0f458bd98be189dc93c49d038e4818647))
* enhance CLI setup wizard with additional configuration options and improve HTTP server shutdown message ([15061e7](https://github.com/AtaCanYmc/reels-wiki/commit/15061e7a4c8b26aec3fda19acee5c329a46764eb))
* update CLI and documentation for enhanced HTTP server with 8 endpoints and improved initialization process ([acc2b87](https://github.com/AtaCanYmc/reels-wiki/commit/acc2b878669e3a87c3b39c0fd8fc0de5c289c141))
* update README with additional badges for PyPI downloads, website, Obsidian plugin, browser extension, MCP server, Ruff, mypy, and API tests ([21ba412](https://github.com/AtaCanYmc/reels-wiki/commit/21ba41272ae492696da1a63a1a4f7188a213a647))

## [0.1.4](https://github.com/AtaCanYmc/reels-wiki/compare/v0.1.3...v0.1.4) (2026-11-26)


### Features

* add architecture diagram SVG and update references in HTML and README ([762cce4](https://github.com/AtaCanYmc/reels-wiki/commit/762cce4bd8df7892605bce8380c83c734e3e87d0))
* add documentation section with guides and references; update index and sitemap ([40f99ce](https://github.com/AtaCanYmc/reels-wiki/commit/40f99ce6cc41d3bd26c79a99980d1b4808a8da4e))
* add interactive review command for inbox notes; implement tagging and promotion actions ([b1d3eda](https://github.com/AtaCanYmc/reels-wiki/commit/b1d3eda1b0b76de5ec7d070a0b7a8f4d7545e899))
* add language selection feature; implement i18n support and update navigation links ([0d1ee9f](https://github.com/AtaCanYmc/reels-wiki/commit/0d1ee9f76b216108d51c2559a4d5aab253c54d8f))
* add privacy policy and Chrome Web Store submission documentation for reels-wiki Capture ([dde0f59](https://github.com/AtaCanYmc/reels-wiki/commit/dde0f5914a2c05cb917fe4d98369e04db0a9a9ec))
* add support for YouTube Shorts and TikTok URLs; implement weekly digest generation ([c16fa3c](https://github.com/AtaCanYmc/reels-wiki/commit/c16fa3c998d93f0b6d2720a91afd54745beeaca4))
* enhance architecture documentation for multi-platform URL normalization; update CLI commands and configuration details ([218c003](https://github.com/AtaCanYmc/reels-wiki/commit/218c003450b39693117163c0fbe3bf55817aebd6))
* enhance example walkthrough and documentation for YouTube Shorts and TikTok support; update normalization and enqueue logic ([6542100](https://github.com/AtaCanYmc/reels-wiki/commit/65421002a0108a67e04dee83ebe1d91f11cb1507))
* enhance Makefile with new commands for local server, Docker processes, and site validation ([bf0119a](https://github.com/AtaCanYmc/reels-wiki/commit/bf0119aad918cf11a6ee4bdff3c5f4e64ddf87c4))
* enhance search and curation features; add local hybrid search, interactive inbox review, and update documentation ([9e00c39](https://github.com/AtaCanYmc/reels-wiki/commit/9e00c39a728f7c0d9ab1b8602d7aae29742da969))
* enhance share URL resolution to safely handle redirects and reject offhost URLs ([dd6f97a](https://github.com/AtaCanYmc/reels-wiki/commit/dd6f97af4641cc1105e181b648f5f959fc39c7c4))
* implement HTTP ingest server and browser extension for capturing Instagram Reels ([9ee1380](https://github.com/AtaCanYmc/reels-wiki/commit/9ee1380b4f849c440232f794392c1a6da7557773))
* implement local semantic search with hybrid keyword and embedding support; add CLI and MCP commands for searching vault notes ([63278a0](https://github.com/AtaCanYmc/reels-wiki/commit/63278a062af390904ed6e5eef53e3e3c28488087))
* implement migration policy and deprecation warnings for configuration; enhance changelog and documentation ([f035a1a](https://github.com/AtaCanYmc/reels-wiki/commit/f035a1a6ec5457620eac103be72afb4672a6baa2))
* implement Obsidian plugin with sidebar view; add health check, URL enqueueing, reprocessing, and digest generation features ([2afb4e7](https://github.com/AtaCanYmc/reels-wiki/commit/2afb4e71915c2a428658debbf1684cbba27660d5))
* implement offline queue for saving Instagram URLs and enhance popup UI for syncing and exporting ([e8faa46](https://github.com/AtaCanYmc/reels-wiki/commit/e8faa460dc7f89967517b434561618b98b3fbc6e))
* update architecture documentation and add diagram for core pipeline; enhance README with visual representation ([1c83534](https://github.com/AtaCanYmc/reels-wiki/commit/1c835344b991f6c64323281ebc3adddf647f886d))
* update metadata and documentation to support YouTube Shorts and TikTok; add weekly digest feature ([fd2b8de](https://github.com/AtaCanYmc/reels-wiki/commit/fd2b8dea4c4d1412a86c1f7efcbb022fef5888cc))
* update README with demo video and local HTTP ingest details; add brag-output to .gitignore ([aaed360](https://github.com/AtaCanYmc/reels-wiki/commit/aaed360048703c353d20786da89308056422bfed))
* update roadmap for v0.5.0 with multi-platform support, weekly digest, and extension auto-sync plans ([d50f3e0](https://github.com/AtaCanYmc/reels-wiki/commit/d50f3e01bc6d27981b486eb29492868372a84521))
* update roadmap with planned features for multi-vault profiles, long-form chunking, and near-duplicate concept deduplication ([1e5b0ec](https://github.com/AtaCanYmc/reels-wiki/commit/1e5b0ecc2f65f399295cc93ad05560200fca7ff4))
* update roadmap with planned features for v1.1.0, v1.2.0, and v1.3.0; enhance exit criteria and focus areas ([f90e2b6](https://github.com/AtaCanYmc/reels-wiki/commit/f90e2b6ebd06509be51b4023c77031fea3963806))


### Bug Fixes

* **security:** eliminate polynomial regex in share URL parser ([3cbfd5c](https://github.com/AtaCanYmc/reels-wiki/commit/3cbfd5cf7a0d5e8f473f0750588aa22419c4a0da))

## [0.1.3](https://github.com/AtaCanYmc/reels-wiki/compare/v0.1.2...v0.1.3) (2026-11-26)


### Features

* add CSS styles for theming and layout, implement JavaScript for color scheme toggle and interactive features ([66ba631](https://github.com/AtaCanYmc/reels-wiki/commit/66ba631e9f589a898ee5877c3920b7fc5f2cb205))
* add favicon and apple-touch-icon links to enhance site branding ([91e84f3](https://github.com/AtaCanYmc/reels-wiki/commit/91e84f3cf9afaea35adba918518e862e9a999ab3))
* add interactive setup wizard for config and environment files in CLI ([9136c2a](https://github.com/AtaCanYmc/reels-wiki/commit/9136c2a96e9f23907d08c4012a399c8bdc3cb461))
* add support for custom note templates and enhance deployment documentation ([1ebd987](https://github.com/AtaCanYmc/reels-wiki/commit/1ebd987f51bc8955d888584e5fbbc93097758779))
* add support for Ollama as a primary LLM provider in CLI and configuration ([8196363](https://github.com/AtaCanYmc/reels-wiki/commit/81963638a710b67804524d395d9b1adbef1303bb))
* enhance documentation for multi-provider synthesis and unattended deployment, update tool references ([007d35c](https://github.com/AtaCanYmc/reels-wiki/commit/007d35c7759444bfcc979797796b03dc3eed527d))
* enhance stats command to include artifact counts, extraction stages, and LLM usage metrics ([c496f4a](https://github.com/AtaCanYmc/reels-wiki/commit/c496f4adc38ab13e09883a6f445889501b5cc300))
* implement Jinja2 prompt rendering for synthesizer and add new templates ([0cf8aa8](https://github.com/AtaCanYmc/reels-wiki/commit/0cf8aa824c324ff007c271058a5d2e9c50fcb4f4))
* refactor module structure and update imports for ingestion and interfaces ([faab430](https://github.com/AtaCanYmc/reels-wiki/commit/faab430f465e069ba9ded0bdf155e1deaf94d292))
* remove logo bg ([b80d2f6](https://github.com/AtaCanYmc/reels-wiki/commit/b80d2f685ccd245e8d242846d22ec7b23f311cf8))
* resolve Instagram share URLs and enhance image extraction for posts without video ([8ec254b](https://github.com/AtaCanYmc/reels-wiki/commit/8ec254bc05139dc1f57d8baf71beb70031cf5dea))
* update Groq model configuration to use openai/gpt-oss-120b and add providers guide ([b37b84a](https://github.com/AtaCanYmc/reels-wiki/commit/b37b84a623839354516b216330c7c377ecbc6e39))
* update roadmap to mark v0.3.0 as completed and enhance content hash reprocessing logic ([3f9e736](https://github.com/AtaCanYmc/reels-wiki/commit/3f9e7360cc92b7d269e730f034695349ba73af54))


### Documentation

* add saved posts workflow guide and sync repository layout ([64abc00](https://github.com/AtaCanYmc/reels-wiki/commit/64abc009f5e3e1834c7ec48e8dccaa56643f6a91))

## [0.1.2](https://github.com/AtaCanYmc/reels-wiki/compare/v0.1.1...v0.1.2) (2026-11-23)


### Features

* enhance CLI output with Rich UI for various commands and add JSON mode support ([8ed0f13](https://github.com/AtaCanYmc/reels-wiki/commit/8ed0f133d186a0b3a6ff0f17a54678d44a88a3d3))
* implement v0.2.0 quality gates, doctor CLI, tests, and troubleshooting docs ([0d1f3b6](https://github.com/AtaCanYmc/reels-wiki/commit/0d1f3b65300b8f7b80b2d33c9481fc2755464a02))

## [0.1.1](https://github.com/AtaCanYmc/reels-wiki/compare/v0.1.0...v0.1.1) (2026-11-23)


### Features

* add initial HTML structure and GitHub Pages deployment workflow ([886868c](https://github.com/AtaCanYmc/reels-wiki/commit/886868cc356aacf5dbacb7839e5b15e722fb51b8))
* enhance error handling and redact sensitive information in Telegram bot ([55e4af8](https://github.com/AtaCanYmc/reels-wiki/commit/55e4af86fdf9d69311478ed3608503422188fb50))
* update project metadata and add PyPI publishing workflow ([23887b9](https://github.com/AtaCanYmc/reels-wiki/commit/23887b919460608ca88bb4923539fd938804e221))


### Code Refactoring

* rename enqueue_url to enqueue and get_stats to queue_stats in CLI and Telegram bot tests ([736a64c](https://github.com/AtaCanYmc/reels-wiki/commit/736a64cf17e10efbb7b3f17162c8c1e74be926ba))
* update function names and improve config handling in CLI and server modules ([6616b6d](https://github.com/AtaCanYmc/reels-wiki/commit/6616b6d003fe2696a880a8da671f5b6b139779f0))


### Documentation

* add architecture and configuration documentation for reels-wiki ([ec038e4](https://github.com/AtaCanYmc/reels-wiki/commit/ec038e47813c3e1ce7c031ac7bfa8cf4d73710de))
* add example walkthrough and step-by-step guide to documentation ([f7fd7ca](https://github.com/AtaCanYmc/reels-wiki/commit/f7fd7cac6b3f81702a700d2af19f8d2bcab5d7ab))
* add examples for CLI commands and configuration in documentation ([1e2f44a](https://github.com/AtaCanYmc/reels-wiki/commit/1e2f44af34ec89d7e6e3d1e0abf05312c62db211))
* add logo to README for branding ([85f3081](https://github.com/AtaCanYmc/reels-wiki/commit/85f3081dbb9425f15109c4fd2e3a071155f86431))
* enhance README with detailed setup instructions and usage examples ([62cf4eb](https://github.com/AtaCanYmc/reels-wiki/commit/62cf4ebc05f254636aabf9202f17e7aa0e38d5f0))
