const DEFAULT_ENDPOINT = "http://127.0.0.1:8765";
const AUTOSYNC_ALARM = "reels-wiki-autosync";

function setup() {
  chrome.contextMenus.create(
    {
      id: "save-to-reels-wiki",
      title: "Save to reels-wiki",
      contexts: ["page", "link"],
      documentUrlPatterns: [
        "*://*.instagram.com/*",
        "*://*.youtube.com/*",
        "*://*.tiktok.com/*",
      ],
    },
    () => chrome.runtime.lastError
  );
  chrome.alarms.create(AUTOSYNC_ALARM, { periodInMinutes: 5 });
}

chrome.runtime.onInstalled.addListener(setup);
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(AUTOSYNC_ALARM, { periodInMinutes: 5 });
  flushOfflineQueue();
});

function setBadge(text, color, tabId) {
  chrome.action.setBadgeText({ text, tabId });
  chrome.action.setBadgeBackgroundColor({ color, tabId });
  setTimeout(() => chrome.action.setBadgeText({ text: "", tabId }), 2500);
}

async function queueOffline(url) {
  const { pendingQueue = [] } = await chrome.storage.local.get(["pendingQueue"]);
  if (!pendingQueue.includes(url)) {
    pendingQueue.push(url);
    await chrome.storage.local.set({ pendingQueue });
  }
  return pendingQueue.length;
}

async function flushOfflineQueue() {
  const stored = await chrome.storage.local.get(["endpoint", "token", "pendingQueue"]);
  const queue = stored.pendingQueue || [];
  if (!queue.length) return;
  const endpoint = (stored.endpoint || DEFAULT_ENDPOINT).replace(/\/+$/, "");

  try {
    const health = await fetch(`${endpoint}/health`);
    if (!health.ok) return;
  } catch {
    return;
  }

  const headers = { "Content-Type": "application/json" };
  if (stored.token) headers.Authorization = `Bearer ${stored.token}`;
  const remaining = [];
  for (const url of queue) {
    try {
      const resp = await fetch(`${endpoint}/ingest`, {
        method: "POST",
        headers,
        body: JSON.stringify({ url, source: "extension" }),
      });
      if (!resp.ok && resp.status !== 400) remaining.push(url);
    } catch {
      remaining.push(url);
    }
  }
  await chrome.storage.local.set({ pendingQueue: remaining });
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === AUTOSYNC_ALARM) flushOfflineQueue();
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "save-to-reels-wiki") return;
  const targetUrl = info.linkUrl || (tab && tab.url) || "";
  const tabId = tab ? tab.id : undefined;
  if (!targetUrl) return;

  const stored = await chrome.storage.local.get(["endpoint", "token"]);
  const endpoint = (stored.endpoint || DEFAULT_ENDPOINT).replace(/\/+$/, "");
  const headers = { "Content-Type": "application/json" };
  if (stored.token) headers.Authorization = `Bearer ${stored.token}`;

  try {
    const resp = await fetch(`${endpoint}/ingest`, {
      method: "POST",
      headers,
      body: JSON.stringify({ url: targetUrl, source: "extension" }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      setBadge("ERR", "#ef4444", tabId);
    } else if (data.result === "enqueued") {
      setBadge("OK", "#16a34a", tabId);
    } else {
      setBadge("DUP", "#f59e0b", tabId);
    }
  } catch {
    await queueOffline(targetUrl);
    setBadge("SAVED", "#f59e0b", tabId);
  }
});
