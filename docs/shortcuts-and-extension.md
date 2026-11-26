[Back to Documentation](README.md)

# Apple Shortcuts & Browser Extension

Capture Instagram Reels/posts, YouTube Shorts, and TikTok videos directly into your `reels-wiki` queue without opening Telegram:

- **iOS / macOS Apple Shortcuts**: Share from mobile or desktop apps via the Share Sheet over HTTP.
- **Chrome / Firefox Extension**: One-click popup and right-click context menu capture (`extension/`), with automatic offline queueing when the local server is asleep.

Both interfaces connect to the built-in `reels-sync serve` HTTP ingest endpoint.

---

## 1. Start the Local HTTP Server (`reels-sync serve`)

Run the server locally on loopback (`127.0.0.1:8765`):

```bash
reels-sync serve
```

### LAN / Tailscale Access (Required for iPhone Share Sheet)

When binding to a non-loopback address (for example `0.0.0.0` over Tailscale or home LAN), `reels-sync serve` requires `REELS_WIKI_HTTP_TOKEN` in `.env` or your environment:

```env
REELS_WIKI_HTTP_TOKEN=your_random_secret_token
```

```bash
reels-sync serve --host 0.0.0.0 --port 8765
```

| Endpoint | Method | Body / Headers | Effect |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | None | Returns `{"ok": true}` |
| `/stats` | `GET` | Optional `Authorization: Bearer <token>` | Returns queue counts and extracted artifact metrics |
| `/ingest` | `POST` | JSON `{"url": "...", "source": "shortcut"}` + optional Bearer token | Deduplicates and enqueues shortcode |
| `/reprocess` | `POST` | JSON `{"shortcode": "..."}` or `{"all": true}` + optional Bearer token | Re-synthesizes stored JSON artifact offline |
| `/digest` | `POST` | JSON `{"days": 7, "tag": null, "dry_run": false}` + optional Bearer token | Generates weekly or topic-scoped digest note |

---

## 2. iOS / macOS Apple Shortcuts Setup

1. Open the **Shortcuts** app on iPhone or Mac and tap **+**.
2. Open shortcut details (`i`) and enable **Show in Share Sheet** (accept **URLs** and **Text**).
3. Add **Get Contents of URL**:
   - **URL**: `http://<mac-ip-or-tailscale-host>:8765/ingest`
   - **Method**: `POST`
   - **Headers**:
     - `Content-Type`: `application/json`
     - `Authorization`: `Bearer <your_REELS_WIKI_HTTP_TOKEN>`
   - **Request Body** (JSON):
     - `url`: `Shortcut Input`
     - `source`: `shortcut`
4. Optional: add **Show Notification** displaying `Contents of URL` so you see `enqueued` or `duplicate` immediately.

Now tap **Share > More > Save to reels-wiki** from any Instagram Reel on iOS or macOS.

---

## 3. Chrome & Firefox Extension (`extension/`)

Supports **Instagram** (Reels and posts), **YouTube Shorts**, and **TikTok** URLs via either the toolbar popup (`Alt+Shift+S`) or the right-click context menu (**Save to reels-wiki**).

### Chrome / Edge / Brave / Arc

1. Open `chrome://extensions` and enable **Developer mode**.
2. Click **Load unpacked** and select the `extension/` folder in this repository.
3. Open any Instagram, YouTube Shorts, or TikTok tab, click the **reels-wiki Capture** icon (or right-click the page/link), and choose **Save to Queue**.

### Firefox

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on...** and select `extension/manifest.json`.
3. Click the extension icon on any supported tab to enqueue the URL.

### Safari (macOS + Xcode)

Since `extension/` targets Manifest V3, generate a local Safari Web Extension Xcode project under `dist/safari-extension` via `make`:

```bash
make build-safari-extension
```

Or invoke Apple's converter directly:

```bash
xcrun safari-web-extension-converter extension/ \
  --project-location dist/safari-extension \
  --app-name "reels-wiki Capture" \
  --bundle-identifier com.atacanymc.reels-wiki \
  --macos-only --force --no-open --no-prompt
```

1. Open the generated Xcode project and build/run once (**Run** / `Cmd+R`).
2. In Safari, enable **Settings > Developer > Allow unsigned extensions** (App Store distribution requires an Apple Developer account).
3. Enable **reels-wiki Capture** under **Settings > Extensions** and grant access for `127.0.0.1` / `localhost`.

> Without Xcode, use **Apple Shortcuts** (Section 2) from the Safari Share menu on macOS and iOS.

### Offline Queue & Automatic Background Sync

If `reels-sync serve` is unreachable when you capture a URL, the extension stores it locally in `pendingQueue` (`chrome.storage.local`) instead of failing:

- **Automatic retry**: `background.js` runs a `chrome.alarms` schedule every 5 minutes (plus on browser startup) that probes `GET /health` and flushes queued URLs automatically once `reels-sync serve` comes online.
- **Manual controls**: When queued items exist offline, the popup reveals **Sync** (flush immediately) and **Export JSON** (download pending items).

### Store Packaging & Privacy

- Chrome Web Store submission copy and permissions justification: [`extension/STORE_LISTING.md`](../extension/STORE_LISTING.md)
- Extension privacy policy (zero remote data collection): [`site/privacy.html`](../site/privacy.html)

---

## 4. Native Obsidian Community Plugin (`obsidian-plugin/`)

Control your local `reels-wiki` pipeline directly inside an Obsidian sidebar view backed by `reels-sync serve`:

1. Run `make build-obsidian-plugin` (or copy `manifest.json`, `main.js`, and `styles.css` from `obsidian-plugin/`) into `<YourVault>/.obsidian/plugins/reels-wiki/`.
2. Start `reels-sync serve`.
3. Enable **reels-wiki** in Obsidian under **Settings > Community plugins**, open the sidebar via the film ribbon icon, and trigger queue health checks, URL ingest, active-note reprocessing, or 7-day digests.
