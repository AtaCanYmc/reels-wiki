[Back to Documentation](README.md)

# Apple Shortcuts & Browser Extension

Capture Instagram Reels directly into your `reels-wiki` queue without opening Telegram:

- **iOS / macOS Apple Shortcuts**: Share from the Instagram app Share Sheet via HTTP.
- **Chrome / Firefox Extension**: One-click capture from the active desktop browser tab (`extension/`).

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
| `/ingest` | `POST` | JSON `{"url": "...", "source": "shortcut"}` + optional `Authorization: Bearer <token>` | Deduplicates and enqueues shortcode |

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

### Chrome / Edge / Brave / Arc

1. Open `chrome://extensions` and enable **Developer mode**.
2. Click **Load unpacked** and select the `extension/` folder in this repository.
3. Open any Instagram Reel or post, click the **reels-wiki Capture** icon, and click **Save to Queue**.

### Firefox

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on...** and select `extension/manifest.json`.
3. Click the extension icon on any Instagram tab to enqueue the URL.

> **Note:** Make sure `reels-sync serve` is running while capturing.
