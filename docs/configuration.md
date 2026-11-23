# Configuration

## Config File Lookup

`reels-wiki` searches for `config.yaml` in this order:

1. `--config <path>` CLI flag
2. `$REELS_WIKI_CONFIG` environment variable
3. `./config.yaml` in the current working directory
4. `~/.config/reels-wiki/config.yaml`

Unknown keys in `config.yaml` are rejected at load time.

## Vault Path Override

`--vault <path>` and `$REELS_WIKI_VAULT` override `vault_path` from `config.yaml`.

## Environment Variables

| Variable | Required For | Description |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Whisper / Groq LLM | API key for Groq transcription and synthesis |
| `GEMINI_API_KEY` | Gemini Vision / LLM | API key for frame OCR and Gemini synthesis |
| `TELEGRAM_BOT_TOKEN` | `reels-sync telegram` | Bot token from `@BotFather` |
| `TELEGRAM_ALLOWED_CHAT_ID` | `reels-sync telegram` | Numeric Telegram chat ID; bot refuses to start if missing or non-numeric |
| `REELS_WIKI_CONFIG` | Optional | Path to `config.yaml` |
| `REELS_WIKI_VAULT` | Optional | Override `vault_path` |

## Telegram Capture Bot

The Telegram bot (`reels-sync telegram` or `reels-wiki-telegram`) only enqueues Instagram URLs from `TELEGRAM_ALLOWED_CHAT_ID` with `source="telegram"`. Messages from any other chat ID are ignored. It does not trigger `process`.

## Examples

### Minimal `config.yaml`

```yaml
vault_path: /Users/you/Documents/ObsidianVault
llm_provider: groq
whisper_provider: groq
```

### Minimal `.env`

```dotenv
GROQ_API_KEY=gsk_your_groq_key_here
GEMINI_API_KEY=AIza_your_gemini_key_here
TELEGRAM_BOT_TOKEN=123456:ABC-DEF_your_bot_token
TELEGRAM_ALLOWED_CHAT_ID=987654321
```

### Override Config and Vault at Runtime

```bash
REELS_WIKI_VAULT=/tmp/test-vault reels-sync --config ./config.yaml stats
```

