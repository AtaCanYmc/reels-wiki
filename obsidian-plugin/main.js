const { ItemView, Notice, Plugin, PluginSettingTab, Setting, requestUrl } = require("obsidian");

const VIEW_TYPE = "reels-wiki-sidebar";
const DEFAULT_SETTINGS = {
  endpoint: "http://127.0.0.1:8765",
  token: "",
};

class ReelsWikiView extends ItemView {
  constructor(leaf, plugin) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType() {
    return VIEW_TYPE;
  }

  getDisplayText() {
    return "reels-wiki";
  }

  getIcon() {
    return "film";
  }

  async onOpen() {
    const root = this.contentEl;
    root.empty();
    root.addClass("reels-wiki-pane");

    root.createEl("h4", { text: "reels-wiki Vault Control" });
    this.healthEl = root.createDiv({ cls: "reels-wiki-status", text: "Checking server..." });
    this.statsEl = root.createDiv({ cls: "reels-wiki-stats", text: "" });

    const refreshBtn = root.createEl("button", { text: "Refresh Queue Health", cls: "mod-cta" });
    refreshBtn.addEventListener("click", () => this.refreshHealth());

    root.createEl("h5", { text: "Enqueue URL" });
    const urlInput = root.createEl("input", {
      type: "url",
      placeholder: "Instagram, Shorts, or TikTok URL",
      cls: "reels-wiki-input",
    });
    const ingestBtn = root.createEl("button", { text: "Save to Queue" });
    ingestBtn.addEventListener("click", async () => {
      const url = urlInput.value.trim();
      if (!url) {
        new Notice("Enter a valid Reels, Shorts, or TikTok URL.");
        return;
      }
      const res = await this.plugin.ingestUrl(url);
      if (res && res.ok) {
        urlInput.value = "";
        this.refreshHealth();
      }
    });

    root.createEl("h5", { text: "Actions" });
    const actionsRow = root.createDiv({ cls: "reels-wiki-actions" });

    const reprocessBtn = actionsRow.createEl("button", { text: "Reprocess Active Note" });
    reprocessBtn.addEventListener("click", () => this.plugin.reprocessActiveNote());

    const digestBtn = actionsRow.createEl("button", { text: "Generate 7-Day Digest" });
    digestBtn.addEventListener("click", () => this.plugin.triggerDigest());

    await this.refreshHealth();
  }

  async refreshHealth() {
    try {
      const health = await this.plugin.apiRequest("/health", "GET");
      const stats = await this.plugin.apiRequest("/stats", "GET");
      this.healthEl.setText(health.ok ? "Server online" : "Server degraded");
      this.statsEl.setText(
        `pending: ${stats.pending || 0} | processed: ${stats.processed || 0} | skipped: ${stats.skipped || 0} | failed: ${stats.failed || 0}`
      );
    } catch (err) {
      this.healthEl.setText("Offline (start `reels-sync serve`)");
      this.statsEl.setText(String(err.message || err));
    }
  }
}

class ReelsWikiSettingTab extends PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display() {
    const { containerEl } = this;
    containerEl.empty();

    new Setting(containerEl)
      .setName("Server Endpoint")
      .setDesc("Local reels-sync serve URL (default http://127.0.0.1:8765).")
      .addText((text) =>
        text
          .setPlaceholder(DEFAULT_SETTINGS.endpoint)
          .setValue(this.plugin.settings.endpoint)
          .onChange(async (val) => {
            this.plugin.settings.endpoint = val.trim() || DEFAULT_SETTINGS.endpoint;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Bearer Token (optional)")
      .setDesc("REELS_WIKI_HTTP_TOKEN when binding to non-loopback hosts.")
      .addText((text) =>
        text
          .setPlaceholder("REELS_WIKI_HTTP_TOKEN")
          .setValue(this.plugin.settings.token)
          .onChange(async (val) => {
            this.plugin.settings.token = val.trim();
            await this.plugin.saveSettings();
          })
      );
  }
}

class ReelsWikiPlugin extends Plugin {
  async onload() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    this.registerView(VIEW_TYPE, (leaf) => new ReelsWikiView(leaf, this));
    this.addRibbonIcon("film", "Open reels-wiki sidebar", () => this.activateView());
    this.addSettingTab(new ReelsWikiSettingTab(this.app, this));

    this.addCommand({
      id: "open-sidebar",
      name: "Open reels-wiki sidebar",
      callback: () => this.activateView(),
    });
    this.addCommand({
      id: "reprocess-active-note",
      name: "Reprocess active reels-wiki note",
      callback: () => this.reprocessActiveNote(),
    });
    this.addCommand({
      id: "generate-weekly-digest",
      name: "Generate 7-day knowledge digest",
      callback: () => this.triggerDigest(),
    });
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async activateView() {
    let leaf = this.app.workspace.getLeavesOfType(VIEW_TYPE)[0];
    if (!leaf) {
      leaf = this.app.workspace.getRightLeaf(false);
      await leaf.setViewState({ type: VIEW_TYPE, active: true });
    }
    this.app.workspace.revealLeaf(leaf);
  }

  async apiRequest(path, method = "GET", payload = null) {
    const base = (this.settings.endpoint || DEFAULT_SETTINGS.endpoint).replace(/\/+$/, "");
    const headers = { "Content-Type": "application/json" };
    if (this.settings.token) {
      headers.Authorization = `Bearer ${this.settings.token}`;
    }
    const resp = await requestUrl({
      url: `${base}${path}`,
      method,
      headers,
      body: payload !== null ? JSON.stringify(payload) : undefined,
      throw: false,
    });
    const data = resp.json || {};
    if (resp.status >= 400) {
      throw new Error(data.error || data.message || `HTTP ${resp.status}`);
    }
    return data;
  }

  async ingestUrl(url) {
    try {
      const res = await this.apiRequest("/ingest", "POST", { url, source: "obsidian" });
      new Notice(`reels-wiki: ${res.result} [${res.shortcode || "?"}]`);
      return res;
    } catch (err) {
      new Notice(`reels-wiki error: ${err.message}`);
      return null;
    }
  }

  async reprocessActiveNote() {
    const file = this.app.workspace.getActiveFile();
    if (!file) {
      new Notice("Open a reels-wiki note first.");
      return;
    }
    const cache = this.app.metadataCache.getFileCache(file);
    const shortcode = cache && cache.frontmatter ? cache.frontmatter.shortcode : null;
    if (!shortcode) {
      new Notice("Active note has no 'shortcode' frontmatter field.");
      return;
    }
    try {
      const res = await this.apiRequest("/reprocess", "POST", { shortcode: String(shortcode) });
      new Notice(`Reprocessed [${shortcode}]: processed=${res.processed || 0}`);
    } catch (err) {
      new Notice(`Reprocess failed: ${err.message}`);
    }
  }

  async triggerDigest() {
    try {
      const res = await this.apiRequest("/digest", "POST", { days: 7 });
      if (res.digest_path) {
        new Notice(`Digest updated: ${res.digest_path} (${res.notes_count} notes)`);
        const file = this.app.vault.getAbstractFileByPath(res.digest_path);
        if (file) await this.app.workspace.getLeaf(false).openFile(file);
      } else {
        new Notice("No recent notes found for 7-day digest.");
      }
    } catch (err) {
      new Notice(`Digest failed: ${err.message}`);
    }
  }
}

module.exports = ReelsWikiPlugin;
