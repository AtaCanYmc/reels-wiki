const urlInput = document.getElementById("url");
const endpointInput = document.getElementById("endpoint");
const tokenInput = document.getElementById("token");
const saveBtn = document.getElementById("saveBtn");
const statusEl = document.getElementById("status");
const healthBadge = document.getElementById("healthBadge");

const IG_URL_RE = /^https?:\/\/(?:www\.|m\.)?(?:instagram\.com|instagr\.am)\//i;

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = cls || "";
}

async function checkHealth(endpoint) {
  try {
    const resp = await fetch(`${endpoint}/health`);
    if (resp.ok) {
      healthBadge.textContent = "online";
      healthBadge.className = "pill pill-on";
      return;
    }
  } catch {
    // ignore connection errors; badge reports offline
  }
  healthBadge.textContent = "offline";
  healthBadge.className = "pill pill-off";
}

async function init() {
  const stored = await chrome.storage.local.get(["endpoint", "token"]);
  if (stored.endpoint) endpointInput.value = stored.endpoint;
  if (stored.token) tokenInput.value = stored.token;
  const endpoint = endpointInput.value.trim().replace(/\/+$/, "");
  checkHealth(endpoint);

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  urlInput.value = (tab && tab.url) || "";
}

endpointInput.addEventListener("change", () => {
  checkHealth(endpointInput.value.trim().replace(/\/+$/, ""));
});

saveBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  const endpoint = endpointInput.value.trim().replace(/\/+$/, "");
  const token = tokenInput.value.trim();
  if (!url || !IG_URL_RE.test(url)) {
    setStatus("Enter a valid Instagram URL.", "err");
    return;
  }

  saveBtn.disabled = true;
  setStatus("Sending...", "");
  await chrome.storage.local.set({ endpoint, token });

  try {
    const headers = { "Content-Type": "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;

    const resp = await fetch(`${endpoint}/ingest`, {
      method: "POST",
      headers,
      body: JSON.stringify({ url, source: "extension" }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      setStatus(data.error || `Error ${resp.status}`, "err");
    } else if (data.result === "enqueued") {
      setStatus(`ENQUEUED [${data.shortcode}]`, "ok");
    } else {
      setStatus(`SKIPPED (${data.result || "duplicate"}) [${data.shortcode}]`, "warn");
    }
    checkHealth(endpoint);
  } catch (err) {
    setStatus(`Connection failed: ${err.message}. Run 'reels-sync serve'.`, "err");
    healthBadge.textContent = "offline";
    healthBadge.className = "pill pill-off";
  } finally {
    saveBtn.disabled = false;
  }
});

init();
