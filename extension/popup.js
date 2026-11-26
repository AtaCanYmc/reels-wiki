const urlInput = document.getElementById("url");
const endpointInput = document.getElementById("endpoint");
const tokenInput = document.getElementById("token");
const autoProcessInput = document.getElementById("autoProcess");
const saveBtn = document.getElementById("saveBtn");
const processBtn = document.getElementById("processBtn");
const retryBtn = document.getElementById("retryBtn");
const statusEl = document.getElementById("status");
const healthBadge = document.getElementById("healthBadge");
const statsBar = document.getElementById("statsBar");
const statsText = document.getElementById("statsText");
const pendingBar = document.getElementById("pendingBar");
const pendingCount = document.getElementById("pendingCount");
const syncBtn = document.getElementById("syncBtn");
const exportBtn = document.getElementById("exportBtn");
const searchInput = document.getElementById("searchInput");
const searchResults = document.getElementById("searchResults");

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

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function jsonHeaders(token) {
  return { "Content-Type": "application/json", ...authHeaders(token) };
}

async function refreshStats(endpoint, token) {
  try {
    const resp = await fetch(`${endpoint}/stats`, { headers: authHeaders(token) });
    if (!resp.ok) {
      statsBar.hidden = true;
      retryBtn.hidden = true;
      return;
    }
    const data = await resp.json();
    statsText.textContent = `pending: ${data.pending} | processed: ${data.processed} | failed: ${data.failed}`;
    statsBar.hidden = false;
    retryBtn.hidden = !(data.failed > 0);
  } catch {
    statsBar.hidden = true;
    retryBtn.hidden = true;
  }
}

async function sendUrl(endpoint, token, url, process = false) {
  const resp = await fetch(`${endpoint}/ingest`, {
    method: "POST",
    headers: jsonHeaders(token),
    body: JSON.stringify({ url, source: "extension", process }),
  });
  const data = await resp.json();
  return { resp, data };
}

async function init() {
  const stored = await chrome.storage.local.get(["endpoint", "token", "autoProcess"]);
  if (stored.endpoint) endpointInput.value = stored.endpoint;
  if (stored.token) tokenInput.value = stored.token;
  if (typeof stored.autoProcess === "boolean") autoProcessInput.checked = stored.autoProcess;
  const endpoint = cleanEndpoint();
  const token = tokenInput.value.trim();
  checkHealth(endpoint);
  refreshStats(endpoint, token);
  renderPending();

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  urlInput.value = (tab && tab.url) || "";
}

endpointInput.addEventListener("change", () => {
  checkHealth(cleanEndpoint());
  refreshStats(cleanEndpoint(), tokenInput.value.trim());
});

tokenInput.addEventListener("change", () => {
  refreshStats(cleanEndpoint(), tokenInput.value.trim());
});

autoProcessInput.addEventListener("change", () => {
  chrome.storage.local.set({ autoProcess: autoProcessInput.checked });
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
  await chrome.storage.local.set({ endpoint, token, autoProcess: autoProcessInput.checked });

  try {
    const { resp, data } = await sendUrl(endpoint, token, url, autoProcessInput.checked);
    if (!resp.ok) {
      setStatus(data.error || `Error ${resp.status}`, "err");
    } else if (data.result === "enqueued") {
      if (data.process) {
        const p = data.process;
        setStatus(
          p.error
            ? `ENQUEUED [${data.shortcode}] (${p.error})`
            : `ENQUEUED [${data.shortcode}] -> processed ${p.processed}, failed ${p.failed}`,
          p.error || p.failed ? "warn" : "ok"
        );
      } else {
        setStatus(`ENQUEUED [${data.shortcode}]`, "ok");
      }
    } else {
      setStatus(`SKIPPED (${data.result || "duplicate"}) [${data.shortcode}]`, "warn");
    }
    checkHealth(endpoint);
    refreshStats(endpoint, token);
  } catch {
    const count = await queueOffline(url);
    setStatus(`SAVED OFFLINE (${count} queued). Use Sync or Export JSON later.`, "warn");
    healthBadge.textContent = "offline";
    healthBadge.className = "pill pill-off";
  } finally {
    saveBtn.disabled = false;
  }
});

async function runProcess(payload, btn, busyText) {
  const endpoint = cleanEndpoint();
  const token = tokenInput.value.trim();

  btn.disabled = true;
  setStatus(busyText, "");
  await chrome.storage.local.set({ endpoint, token });

  try {
    const resp = await fetch(`${endpoint}/process`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
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
    btn.disabled = false;
    checkHealth(endpoint);
    refreshStats(endpoint, token);
  }
}

processBtn.addEventListener("click", () => {
  runProcess({ limit: 10 }, processBtn, "Processing queue...");
});

retryBtn.addEventListener("click", () => {
  runProcess({ retry_failed: true, limit: 10 }, retryBtn, "Retrying failed items...");
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
  refreshStats(endpoint, token);
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

searchInput.addEventListener("keydown", async (event) => {
  if (event.key !== "Enter") return;
  const q = searchInput.value.trim();
  searchResults.replaceChildren();
  if (!q) return;

  const endpoint = cleanEndpoint();
  const token = tokenInput.value.trim();
  try {
    const resp = await fetch(`${endpoint}/search?q=${encodeURIComponent(q)}&limit=5`, {
      headers: authHeaders(token),
    });
    const data = await resp.json();
    if (!resp.ok) {
      setStatus(data.error || `Search error ${resp.status}`, "err");
      return;
    }
    if (!data.matches || data.matches.length === 0) {
      const empty = document.createElement("li");
      empty.className = "res-path";
      empty.textContent = "No matching notes.";
      searchResults.appendChild(empty);
      return;
    }
    for (const item of data.matches) {
      const li = document.createElement("li");
      const title = document.createElement("span");
      title.className = "res-title";
      title.textContent = item.title || item.path;
      const rel = document.createElement("span");
      rel.className = "res-path";
      rel.textContent = item.path;
      li.append(title, rel);
      searchResults.appendChild(li);
    }
  } catch {
    setStatus("Server unreachable. Start reels-sync serve first.", "err");
  }
});

init();
