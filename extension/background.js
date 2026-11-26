const DEFAULT_ENDPOINT = "http://127.0.0.1:8765";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "save-to-reels-wiki",
    title: "Save to reels-wiki",
    contexts: ["page", "link"],
    documentUrlPatterns: ["*://*.instagram.com/*"],
  });
});

function setBadge(text, color, tabId) {
  chrome.action.setBadgeText({ text, tabId });
  chrome.action.setBadgeBackgroundColor({ color, tabId });
  setTimeout(() => chrome.action.setBadgeText({ text: "", tabId }), 2500);
}

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
    setBadge("OFF", "#ef4444", tabId);
  }
});
