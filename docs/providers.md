[Back to Documentation](README.md)

# Providers Guide (Groq, Gemini, Ollama)

How to obtain API keys, discover supported models, and configure extraction and synthesis providers in `reels-wiki`.

## Overview

| Provider | Used For | Env Variable | Default Models |
| :--- | :--- | :--- | :--- |
| `groq` | Audio transcription + LLM synthesis | `GROQ_API_KEY` | `whisper-large-v3-turbo`, `openai/gpt-oss-120b` |
| `gemini` | Frame OCR (Vision) + LLM synthesis | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| `ollama` | Offline LLM synthesis | None (local HTTP) | `llama3.1:8b` |

---

## 1. Groq

Groq runs Whisper audio transcription (`Stage 2`) and fast structured-output LLM synthesis.

### Get an API key

1. Sign in at `https://console.groq.com/keys`.
2. Click **Create API Key**, copy the generated key, and store it in `.env` (or run `reels-sync init`):

   ```env
   GROQ_API_KEY=your_groq_api_key
   ```

### Find available models

- **Docs**: Check the current model catalog at `https://console.groq.com/docs/models`.
- **Live query from your environment** (shows models enabled on your account):

  ```bash
  python -c 'import os; from dotenv import load_dotenv; from groq import Groq; load_dotenv(".env"); print(sorted(m.id for m in Groq(api_key=os.environ["GROQ_API_KEY"]).models.list().data))'
  ```

### Configure in `config.yaml`

```yaml
extraction:
  whisper_provider: groq
  groq_whisper_model: whisper-large-v3-turbo

synthesis:
  provider: groq
  groq_model: openai/gpt-oss-120b
```

---

## 2. Google Gemini

Gemini powers frame OCR (`Stage 3` Vision fallback for text-on-screen Reels and image-only `/p/` carousels) and structured JSON synthesis.

### Get an API key

1. Open Google AI Studio at `https://aistudio.google.com/apikey`.
2. Click **Create API key**, select or create a Google Cloud project, and store the key in `.env`:

   ```env
   GEMINI_API_KEY=your_gemini_api_key
   ```

### Find available models

- **Docs**: Check supported models at `https://ai.google.dev/gemini-api/docs/models`.
- **Live query from your environment**:

  ```bash
  python -c 'import os; from dotenv import load_dotenv; from google import genai; load_dotenv(".env"); print(sorted(m.name for m in genai.Client(api_key=os.environ["GEMINI_API_KEY"]).models.list()))'
  ```

### Configure in `config.yaml`

```yaml
extraction:
  enable_vision_fallback: true
  vision_model: gemini-2.5-flash

synthesis:
  provider: gemini
  gemini_model: gemini-2.5-flash
```

You can also mix providers, such as `provider: groq` with `fallback_provider: gemini` (or vice versa).

---

## 3. Local Offline (Ollama)

To synthesize notes completely offline without cloud API keys, pull a local model in Ollama and pair it with `whisper_provider: local`:

```bash
ollama pull llama3.1:8b
```

```yaml
extraction:
  whisper_provider: local
  local_whisper_model: small
  enable_vision_fallback: false

synthesis:
  provider: ollama
  ollama_base_url: http://localhost:11434/v1
  ollama_model: llama3.1:8b
  fallback_provider: null
```

---

## 4. Verify Configuration

Validate API key presence, vault permissions, `ffmpeg`, and Instagram cookies:

```bash
reels-sync doctor
reels-sync --json doctor
```
