const urlInput = document.getElementById("url");
const endpointInput = document.getElementById("endpoint");
const tokenInput = document.getElementById("token");
const saveBtn = document.getElementById("saveBtn");
const processBtn = document.getElementById("processBtn");
const statusEl = document.getElementById("status");
const healthBadge = document.getElementById("healthBadge");
const pendingBar = document.getElementById("pendingBar");
const pendingCount = document.getElementById("pendingCount");
const syncBtn = document.getElementById("syncBtn");
const exportBtn = document.getElementById("exportBtn");

const MEDIA_URL_RE = /^https?:\/\/(?:www\.|m\.)?(?:instagram\.com|instagr\.am|youtube\.com|youtu\.be|tiktok\.com)\//i;

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = cls || "";
}

function cleanEndpoint() {
  return endpointInput.value.trim().replace(/\/+$/, "");
}

async function renderPending() {
  const { pendingQueue = [] } = await chrome.storage.local.get(["pendingQueue"]);
  pendingBar.hidden = pendingQueue.length === 0;
  pendingCount.textContent = `Offline queue: ${pendingQueue.length}`;
  return pendingQueue;
}

async function queueOffline(url) {
  const { pendingQueue = [] } = await chrome.storage.local.get(["pendingQueue"]);
  if (!pendingQueue.includes(url)) {
    pendingQueue.push(url);
    await chrome.storage.local.set({ pendingQueue });
  }
  await renderPending();
  return pendingQueue.length;
}

async function checkHealth(endpoint) {
  try {
    const resp = await fetch(`${endpoint}/health`);
    if (resp.ok) {
      healthBadge.textContent = "online";
      healthBadge.className = "pill pill-on";
      return true;
    }
  } catch {
    // ignore connection errors; badge reports offline
  }
  healthBadge.textContent = "offline";
  healthBadge.className = "pill pill-off";
  return false;
}

function jsonHeaders(token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function sendUrl(endpoint, token, url) {
  const resp = await fetch(`${endpoint}/ingest`, {
    method: "POST",
    headers: jsonHeaders(token),
    body: JSON.stringify({ url, source: "extension" }),
  });
  const data = await resp.json();
  return { resp, data };
}

async function init() {
  const stored = await chrome.storage.local.get(["endpoint", "token"]);
  if (stored.endpoint) endpointInput.value = stored.endpoint;
  if (stored.token) tokenInput.value = stored.token;
  checkHealth(cleanEndpoint());
  renderPending();

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  urlInput.value = (tab && tab.url) || "";
}

endpointInput.addEventListener("change", () => {
  checkHealth(cleanEndpoint());
});

saveBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  const endpoint = cleanEndpoint();
  const token = tokenInput.value.trim();
  if (!url || !MEDIA_URL_RE.test(url)) {
    setStatus("Enter an Instagram, YouTube Shorts, or TikTok URL.", "err");
    return;
  }

  saveBtn.disabled = true;
  setStatus("Sending...", "");
  await chrome.storage.local.set({ endpoint, token });

  try {
    const { resp, data } = await sendUrl(endpoint, token, url);
    if (!resp.ok) {
      setStatus(data.error || `Error ${resp.status}`, "err");
    } else if (data.result === "enqueued") {
      setStatus(`ENQUEUED [${data.shortcode}]`, "ok");
    } else {
      setStatus(`SKIPPED (${data.result || "duplicate"}) [${data.shortcode}]`, "warn");
    }
    checkHealth(endpoint);
  } catch {
    const count = await queueOffline(url);
    setStatus(`SAVED OFFLINE (${count} queued). Use Sync or Export JSON later.`, "warn");
    healthBadge.textContent = "offline";
    healthBadge.className = "pill pill-off";
  } finally {
    saveBtn.disabled = false;
  }
});

processBtn.addEventListener("click", async () => {
  const endpoint = cleanEndpoint();
  const token = tokenInput.value.trim();

  processBtn.disabled = true;
  setStatus("Processing queue...", "");
  await chrome.storage.local.set({ endpoint, token });

  try {
    const resp = await fetch(`${endpoint}/process`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify({ limit: 10 }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      setStatus(data.error || `Error ${resp.status}`, "err");
    } else if (data.error) {
      setStatus(data.error, "warn");
    } else {
      setStatus(
        `PROCESSED ${data.processed} (skipped ${data.skipped}, failed ${data.failed})`,
        data.failed ? "warn" : "ok"
      );
    }
  } catch {
    setStatus("Server unreachable. Start reels-sync serve first.", "err");
  } finally {
    processBtn.disabled = false;
    checkHealth(endpoint);
  }
});

syncBtn.addEventListener("click", async () => {
  const queue = await renderPending();
  if (!queue.length) return;
  const endpoint = cleanEndpoint();
  const token = tokenInput.value.trim();

  syncBtn.disabled = true;
  setStatus("Syncing offline queue...", "");
  const remaining = [];
  let sent = 0;

  for (const url of queue) {
    try {
      const { resp } = await sendUrl(endpoint, token, url);
      if (resp.ok || resp.status === 400) {
        sent += 1;
      } else {
        remaining.push(url);
      }
    } catch {
      remaining.push(url);
    }
  }

  await chrome.storage.local.set({ pendingQueue: remaining });
  await renderPending();
  checkHealth(endpoint);
  setStatus(
    remaining.length
      ? `Synced ${sent}; ${remaining.length} still pending (check server/token).`
      : `Synced ${sent} queued item(s).`,
    remaining.length ? "warn" : "ok"
  );
  syncBtn.disabled = false;
});

exportBtn.addEventListener("click", async () => {
  const queue = await renderPending();
  if (!queue.length) return;
  const payload = {
    saved_saved_media: queue.map((href) => ({
      string_map_data: { "Saved on": { href } },
    })),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = "reels-wiki-saved.json";
  link.click();
  URL.revokeObjectURL(objectUrl);
  setStatus(`Exported ${queue.length} URL(s). Run: reels-sync import-ig ~/Downloads/reels-wiki-saved.json`, "ok");
});

init();
