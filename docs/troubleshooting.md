# Troubleshooting

Diagnostics and recovery procedures for common runtime issues in `reels-wiki`.

First run `reels-sync doctor` to verify Python version, `ffmpeg`, cookie configuration, API key presence, and vault write permissions.

## 1. Instagram Authentication and Cookie Expiration

**Symptoms:** `yt-dlp` fails with login required, rate-limit, or empty metadata errors.

1. Confirm one cookie source is set under `extraction:` in `config.yaml`:
   - `cookies_from_browser: chrome` (or `firefox`, `"chrome:Profile 1"`)
   - `cookies_file: ~/cookies.txt` (Netscape format)
2. Ensure the selected browser profile is actively logged into Instagram, or re-export `cookies.txt`.
3. Keep `delay_seconds` at `2.0` or higher and process queues in smaller batches (`reels-sync process --limit 10`).

## 2. Outdated `yt-dlp` Extractor

**Symptoms:** `yt-dlp` fails to parse Instagram endpoints that worked previously.

Update `yt-dlp` inside your virtual environment:

```bash
make update-yt-dlp
```

Then retry failed items:

```bash
reels-sync process --retry-failed
```

## 3. Missing `ffmpeg` Binary

**Symptoms:** Audio compression or Stage 3 frame extraction logs `ffmpeg not found` in `warnings`.

- **macOS (Homebrew):** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt install ffmpeg`

If `ffmpeg` is installed in a non-standard directory, set `extraction.ffmpeg_path` in `config.yaml` to the full binary path.

## 4. Queue Lock Contention and Crash Recovery

**Symptoms:** `process_queue` reports `another reels-sync process is already running for this vault` or items remain in `processing`.

- Only one `reels-sync process` run may operate on a vault at a time (`inbox/.reels-process.lock`).
- If a prior run terminated unexpectedly, the next `reels-sync process` execution automatically resets items stuck in `processing` back to `pending`.
- If `inbox/.reels-process.lock` remains stale after confirming no `reels-sync` process is active, remove the lock file and run `reels-sync stats`.
- If `sources/.reels_index.json` is lost or corrupted, it rebuilds automatically from `inbox/reels-queue.jsonl` on the next run.

## 5. LLM JSON Output Failures

**Symptoms:** Synthesis fails with JSON validation or provider errors.

- Check `GROQ_API_KEY` and `GEMINI_API_KEY` via `reels-sync doctor`.
- Configure `synthesis.fallback_provider` in `config.yaml` so malformed outputs automatically fall back to the secondary provider after `max_retries`.
- Once fixed, regenerate notes without re-downloading media via `reels-sync reprocess <shortcode>`.
