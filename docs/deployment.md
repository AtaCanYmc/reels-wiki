[Back to Documentation](README.md)

# Deployment and Unattended Scheduling

Run `reels-wiki` unattended using Docker, macOS `launchd`, or Linux `systemd` user timers, or install globally via `pipx`, `uv`, or Homebrew.

---

## 1. Docker (Headless Server)

The repository ships a minimal `Dockerfile` (`python:3.12-slim` + `ffmpeg` + non-root `appuser`) and `docker-compose.yml` mounting `config.yaml` read-only and your vault at `/vault`.

```bash
cp config.example.yaml config.yaml
cp .env.example .env
# Set VAULT_PATH=/path/to/ObsidianVault in your environment or .env
docker compose build
docker compose run --rm reels-process
```

Run the Telegram capture bot persistently in the background:

```bash
docker compose up -d reels-telegram
```

Schedule `docker compose run --rm reels-process` from host `cron` or a systemd timer to digest queued items periodically.

---

## 2. Package Managers (`pipx`, `uv`, Homebrew)

```bash
# pipx
pipx install reels-wiki

# uv
uv tool install reels-wiki

# Homebrew (personal tap)
brew install atacanymc/tap/reels-wiki
```

After installation, run `reels-sync init` to create `~/.config/reels-wiki/config.yaml` and `.env`, then verify with `reels-sync doctor`.

---

## 3. macOS `launchd` Schedules

Save the plist files under `~/Library/LaunchAgents/` and replace `/path/to/reels-secretary` and `/Users/you` with your absolute paths.

### Periodic Queue Processor (`~/Library/LaunchAgents/com.reelswiki.process.plist`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.reelswiki.process</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/reels-secretary/.venv/bin/reels-sync</string>
    <string>process</string>
    <string>--limit</string>
    <string>10</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/reels-secretary</string>
  <key>StartInterval</key>
  <integer>1800</integer>
  <key>StandardOutPath</key>
  <string>/tmp/reels-wiki-process.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/reels-wiki-process.err</string>
</dict>
</plist>
```

### Always-On Telegram Capture Bot (`~/Library/LaunchAgents/com.reelswiki.telegram.plist`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.reelswiki.telegram</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/reels-secretary/.venv/bin/reels-sync</string>
    <string>telegram</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/reels-secretary</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/reels-wiki-telegram.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/reels-wiki-telegram.err</string>
</dict>
</plist>
```

Load both agents:

```bash
launchctl load ~/Library/LaunchAgents/com.reelswiki.process.plist
launchctl load ~/Library/LaunchAgents/com.reelswiki.telegram.plist
```

---

## 4. Linux `systemd` User Units

Save these unit files under `~/.config/systemd/user/`.

### `reels-wiki-process.service`

```ini
[Unit]
Description=Process queued Instagram Reels into Obsidian notes

[Service]
Type=oneshot
WorkingDirectory=%h/reels-secretary
ExecStart=%h/reels-secretary/.venv/bin/reels-sync process --limit 10
```

### `reels-wiki-process.timer`

```ini
[Unit]
Description=Run reels-wiki processor every 30 minutes

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

### `reels-wiki-telegram.service`

```ini
[Unit]
Description=reels-wiki Telegram Capture Bot
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/reels-secretary
ExecStart=%h/reels-secretary/.venv/bin/reels-sync telegram
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Enable and start them:

```bash
systemctl --user daemon-reload
systemctl --user enable --now reels-wiki-process.timer reels-wiki-telegram.service
```

---

## 5. Custom Note Templates (`template_path`)

Set `template_path` in `config.yaml` to customize the Markdown body rendered inside `<folder>/<slug>.md`. Required YAML frontmatter (`status`, `created`, `shortcode`, `source_url`, `tags`), `_index.md`, and `_log.md` invariants remain managed by `writer.py`, and templates execute inside a sandboxed Jinja2 environment.

```yaml
vault_path: ~/Documents/ObsidianVault
template_path: ~/.config/reels-wiki/note-template.j2
```

Available template variables: `title`, `core_insight`, `for_future_agent`, `actionable_next_step`, `related_links`, `candidate_links`, `tags`, `artifact`, `syn`.
