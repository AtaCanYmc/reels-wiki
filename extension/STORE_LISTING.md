# Chrome Web Store Submission Pack

Copy-paste fields for the [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole).

## 1. Store Listing

- **Name**: `reels-wiki Capture`
- **Short Summary (max 132 chars)**: `Send Instagram Reels or posts to your local reels-wiki Obsidian queue in one click.`
- **Category**: `Productivity`
- **Language**: `English`
- **Official URL / Homepage**: `https://atacanymc.github.io/reels-wiki/`
- **Support URL**: `https://github.com/AtaCanYmc/reels-wiki/issues`

### Detailed Description

```text
reels-wiki Capture connects your browser directly to your local reels-wiki pipeline (reels-sync serve) so you can queue saved Instagram Reels and posts for Obsidian without copying URLs manually.

Features:
- One-click popup capture for the active tab URL with live server health indicator
- Right-click context menu ("Save to reels-wiki") on Instagram pages and links with badge confirmation (OK / DUP / ERR)
- Keyboard shortcut (Alt+Shift+S)
- Local-only execution: connects strictly to your local endpoint (http://127.0.0.1:8765 by default) with optional Bearer token authentication

Prerequisites:
Run `reels-sync serve` locally from https://github.com/AtaCanYmc/reels-wiki before saving.
```

---

## 2. Privacy Practices Tab

- **Single Purpose Description**:
  `Sends the active Instagram Reel or post URL to the user's local reels-wiki HTTP queue server on explicit user click or context menu action.`

- **Permission Justifications**:
  - **`activeTab`**: `Reads the active tab's URL only when the user opens the popup or triggers "Save to reels-wiki" so the Instagram URL can be queued.`
  - **`storage`**: `Persists the user's local reels-wiki server endpoint URL and optional authentication token in chrome.storage.local.`
  - **`contextMenus`**: `Adds a "Save to reels-wiki" option to the right-click menu on Instagram pages and links.`
  - **`host_permissions` (`http://127.0.0.1/*`, `http://localhost/*`)**: `Allows the popup and service worker to send POST /ingest and GET /health requests to the user's local reels-sync serve daemon.`
  - **Remote Code**: `No, I am not using Remote code.`

- **Privacy Policy URL**: `https://atacanymc.github.io/reels-wiki/privacy.html`
- **Data Usage Certifications**:
  - Does not collect or transmit any user data to developer or third-party servers.
  - Check all three Chrome Web Store limited-use certifications (`do not sell`, `do not use for unrelated purposes`, `do not use for creditworthiness`).

---

## 3. Store Assets & Packaging

- **Store Icon (128x128)**: Upload `extension/icons/icon-128.png`.
- **Screenshot (1280x800 or 640x400)**: Open the extension popup on an Instagram tab and capture a screenshot (no personal secrets visible).
- **Upload ZIP**: `dist/reels-wiki-extension-v0.2.0.zip`

Rebuild the upload ZIP cleanly at any time:

```bash
mkdir -p dist && cd extension && zip -r ../dist/reels-wiki-extension-v0.2.0.zip manifest.json background.js popup.html popup.css popup.js icons/
```
