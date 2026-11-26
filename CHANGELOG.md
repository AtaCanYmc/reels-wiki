# Changelog

For frozen v1 schemas (`config.yaml`, `sources/reels/<shortcode>.json`, `inbox/reels-queue.jsonl`, `reels_wiki.__all__`), deprecation notices, and upgrade/rollback procedures, see [Migration & Backward-Compatibility Policy](docs/migration.md).

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
