# Example Walkthrough

Step-by-step walkthroughs of processing real Instagram Reels through `reels-wiki`.

## Example 1: Long Caption (Stage 1 Sufficient) - `Df44o7WhunQ`

URL: `https://www.instagram.com/p/Df44o7WhunQ/?hl=tr`

### Step 1: URL Normalization and Enqueue

Enqueue the post URL:

```bash
reels-sync ingest "https://www.instagram.com/p/Df44o7WhunQ/?hl=tr"
```

`reels-wiki` performs three operations during enqueue:

1. Extracts the 11-character shortcode `Df44o7WhunQ` and normalizes `/p/Df44o7WhunQ/?hl=tr` to `https://www.instagram.com/reel/Df44o7WhunQ/`.
2. Checks `sources/.reels_index.json` to ensure `Df44o7WhunQ` is not already tracked.
3. Appends a `pending` snapshot to `inbox/reels-queue.jsonl` and updates `sources/.reels_index.json`.

### Step 2: Dry-Run Queue Check

Preview pending items without calling `yt-dlp`, Whisper, or the synthesis LLM:

```bash
reels-sync process --dry-run
```

### Step 3: Stage 1 Metadata Extraction

When `process` runs (or when invoking `extract_reel` directly via the Python SDK), Stage 1 calls `yt_dlp` with `extract_info(download=False)`:

```python
from reels_wiki.core.config import Config, ExtractionConfig
from reels_wiki.pipeline.extractor import extract_reel

cfg = Config(
    vault_path="/path/to/ObsidianVault",
    extraction=ExtractionConfig(
        enable_whisper_fallback=False,
        enable_vision_fallback=False,
    ),
)
result = extract_reel("https://www.instagram.com/p/Df44o7WhunQ/?hl=tr", "Df44o7WhunQ", cfg)
print(result.model_dump_json(indent=2))
```

Observed output from `Df44o7WhunQ`:

```json
{
  "shortcode": "Df44o7WhunQ",
  "url": "https://www.instagram.com/p/Df44o7WhunQ/?hl=tr",
  "creator": "Atalay KARAHAN",
  "title": "Video by krhnatalay",
  "caption": "Claude limitin bitiyorsa bu 2 skill’i kur: RTK ve Caveman. 20 dolarlık abonelik su gibi bitiyorsa ikisini Claude Code’a ekle, token harcamasını azaltsın.\n\nYayının tamamı YouTube’da: @krhnatalay\n\n#claude #claudecode #yapayzeka #yazılım",
  "duration": null,
  "upload_date": "20261118",
  "subtitles": "",
  "transcript": "",
  "transcript_source": "none",
  "visual_notes": "",
  "steps_used": [
    "metadata"
  ],
  "warnings": [],
  "extracted_at": "2026-11-23T22:51:35+00:00"
}
```

Why Stage 2 and Stage 3 do not run here:

- The extracted caption exceeds `min_caption_chars` (`150` by default).
- Because the text threshold is met at Stage 1, `reels-wiki` skips audio download/Whisper transcription (Stage 2) and `ffmpeg` frame extraction/Gemini OCR (Stage 3).
- During a queue run, this payload is persisted to `sources/reels/Df44o7WhunQ.json`.

### Step 4: LLM Synthesis and Vault Write

Run the full pipeline for one pending item:

```bash
reels-sync process --limit 1
```

During synthesis and writing:

1. **Vault context discovery**: Reads `_CLAUDE.md` and `_index.md` to collect allowed target folders, existing `#tags`, and existing note titles.
2. **LLM synthesis**: Evaluates `AtomicNoteSynthesis` (`should_keep`, folder, ASCII/Turkish-transliterated slug, summary, tags, and related wikilinks).
3. **Atomic write**: Writes the note to `<folder>/<slug>.md` inside the vault using `python-frontmatter`. Any `related_wikilinks` without an existing target note are written as plain text `(new note candidate) ...`.
4. **Index and log update**: Adds the note under the matching folder heading in `_index.md` and appends an entry to `_log.md`.

### Step 5: Reprocess Without Re-Downloading

To regenerate the note after changing prompts, models, or vault folder structure, reprocess directly from `sources/reels/Df44o7WhunQ.json`:

```bash
reels-sync reprocess Df44o7WhunQ
```

This skips Instagram extraction and reuses the stored JSON artifact.

---

## Example 2: Short Caption (Triggers Audio/Vision Fallbacks) - `Df2jr_RN9gb`

URL: `https://www.instagram.com/p/Df2jr_RN9gb/?hl=tr`

### Step 1: Enqueue

```bash
reels-sync ingest "https://www.instagram.com/p/Df2jr_RN9gb/?hl=tr"
```

The URL is normalized to `https://www.instagram.com/reel/Df2jr_RN9gb/` and queued under shortcode `Df2jr_RN9gb`.

### Step 2: Stage 1 Metadata Extraction

Observed output from Stage 1 (`yt_dlp` metadata only):

```json
{
  "shortcode": "Df2jr_RN9gb",
  "url": "https://www.instagram.com/p/Df2jr_RN9gb/?hl=tr",
  "creator": "Ahmet Demirci",
  "title": "Video by ahmetbuilder",
  "caption": "juri yaz sana bağlantıyı göndereyim",
  "duration": null,
  "upload_date": "20261117",
  "subtitles": "",
  "transcript": "",
  "transcript_source": "none",
  "visual_notes": "",
  "steps_used": [
    "metadata"
  ],
  "warnings": [],
  "extracted_at": "2026-11-23T22:57:10+00:00"
}
```

### Step 3: Why Stage 2 and Stage 3 Trigger

- The extracted caption is only 35 characters (`"juri yaz sana bağlantıyı göndereyim"`), which is below `min_caption_chars` (`150`), and `subtitles` is empty.
- With default settings (`enable_whisper_fallback: true`), `reels-wiki` downloads the audio to a temporary directory and transcribes it using Groq `whisper-large-v3-turbo` or local `faster-whisper`.
- If the resulting transcript is still shorter than `min_transcript_chars` (`40`) and `enable_vision_fallback: true`, Stage 3 extracts `vision_frames` (`4`) evenly spaced frames via `ffmpeg` and reads on-screen text with `gemini-2.5-flash`.

### Step 4: Synthesis or Noise Filtering

Once extraction completes and `sources/reels/Df2jr_RN9gb.json` is saved, LLM synthesis evaluates `AtomicNoteSynthesis`:

- If the spoken transcript or on-screen frames contain actionable ideas, a note is written to the vault.
- If the Reel is purely a short call-to-action without standalone insight, `should_keep` evaluates to `false` and the item is marked `skipped` with `skip_reason` in `sources/.reels_index.json`.

---

## Example 3: Concise Headline Caption (Triggers Audio Fallback for Details) - `DdYn6ekug5W`

URL: `https://www.instagram.com/p/DdYn6ekug5W/?hl=tr`

### Step 1: Enqueue

```bash
reels-sync ingest "https://www.instagram.com/p/DdYn6ekug5W/?hl=tr"
```

The URL is normalized to `https://www.instagram.com/reel/DdYn6ekug5W/` and queued under shortcode `DdYn6ekug5W`.

### Step 2: Stage 1 Metadata Extraction

Observed output from Stage 1 (`yt_dlp` metadata only):

```json
{
  "shortcode": "DdYn6ekug5W",
  "url": "https://www.instagram.com/p/DdYn6ekug5W/?hl=tr",
  "creator": "Bartın Taha Bakıcı",
  "title": "Video by beathabest.tech",
  "caption": "Bir Türk’ün 170 bin yıldızlı reposu: 2169 hazır promt! #ai #github #chatgpt #developer",
  "duration": null,
  "upload_date": "20260917",
  "subtitles": "",
  "transcript": "",
  "transcript_source": "none",
  "visual_notes": "",
  "steps_used": [
    "metadata"
  ],
  "warnings": [],
  "extracted_at": "2026-11-23T22:59:10+00:00"
}
```

### Step 3: Stage 2 Fallback Behavior

- The caption is 85 characters (below `min_caption_chars: 150`) and gives only a headline without naming the GitHub repository.
- Stage 2 downloads the audio and transcribes it with Whisper so the synthesis step receives the repository name and spoken details.

### Step 4: Synthesis and Vault Write

- The extracted artifact is saved to `sources/reels/DdYn6ekug5W.json`.
- LLM synthesis generates an atomic note with a Turkish title and ASCII-transliterated slug, then updates `_index.md` and `_log.md`.

---

## Example 4: Long Caption (Stage 1 Sufficient) - `DgNTHLDg9X5`

URL: `https://www.instagram.com/p/DgNTHLDg9X5/?hl=tr`

### Step 1: URL Normalization and Enqueue

```bash
reels-sync ingest "https://www.instagram.com/p/DgNTHLDg9X5/?hl=tr"
```

- Parsed as `('post', 'DgNTHLDg9X5')` and normalized to `https://www.instagram.com/reel/DgNTHLDg9X5/`.

### Step 2: Stage 1 Metadata Extraction

Observed output from `extract_reel`:

```json
{
  "shortcode": "DgNTHLDg9X5",
  "url": "https://www.instagram.com/p/DgNTHLDg9X5/?hl=tr",
  "creator": "Copy Paste AI | Tested Prompts",
  "title": "Video by ai.copypaste",
  "caption": "Comment COPY and I’ll DM you the install prompt for all 10 tools (follow first, or the DM won’t arrive).\n\nYour Claude is running on empty. 10 free, open-source tools Claude Code installs for you:\nVoice: Kokoro, faster-whisper, DeepFilterNet\nCut: yt-dlp, FFmpeg, auto-editor, OBS\nDesign: HyperFrames, rembg, ImageMagick\n\nAll run on a normal laptop. Start with the one you pay for now.\n(Claude Code needs a paid Claude plan.)",
  "duration": null,
  "upload_date": "20261126",
  "subtitles": "",
  "transcript": "",
  "transcript_source": "none",
  "visual_notes": "",
  "steps_used": [
    "metadata"
  ],
  "warnings": [],
  "synthesis_metrics": null,
  "extracted_at": "2026-11-26T16:06:58+00:00"
}
```

### Step 3: Decision Gate

- `len(caption)` is 438 characters (`>= min_caption_chars: 150`), so Stage 2 (Whisper) and Stage 3 (Vision) are skipped.
- `steps_used` contains `["metadata"]` with zero `warnings`.

---

## End-to-End Groq Run Summary (All 4 Examples)

Verified full pipeline run (`whisper_provider: groq` with `whisper-large-v3-turbo`, `synthesis.provider: groq` with `openai/gpt-oss-120b`, `enable_vision_fallback: false`):

| Shortcode | `steps_used` | Generated Note Path | Tokens (Prompt / Completion / Total) | Retries |
| :--- | :--- | :--- | :--- | :--- |
| `Df44o7WhunQ` | `["metadata"]` | `tools/claude-token-azaltma-rtk-caveman.md` | `1182 / 590 / 1772` | `0` |
| `Df2jr_RN9gb` | `["metadata", "whisper:groq"]` | `tools/awards-cloud-skill-otomatik-odul-sitesi.md` | `1338 / 775 / 2113` | `0` |
| `DdYn6ekug5W` | `["metadata", "whisper:groq"]` | `tools/prompt-chat-turkish-repo.md` | `1482 / 787 / 2269` | `0` |
| `DgNTHLDg9X5` | `["metadata"]` | `tools/claude-code-10-tools-install.md` | `1258 / 704 / 1962` | `0` |

Observed `reels-sync --json stats` output totals from the run:

```json
{
  "total": 4,
  "processed": 4,
  "skipped": 0,
  "failed": 0,
  "artifacts_count": 4,
  "stages": {
    "metadata": 4,
    "subtitles": 0,
    "whisper": 2,
    "vision": 0
  },
  "llm_usage": {
    "prompt_tokens": 5260,
    "completion_tokens": 2856,
    "total_tokens": 8116,
    "retries": 0
  }
}
```
