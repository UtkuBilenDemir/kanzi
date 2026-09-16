var KindleZoteroImporter = {
  id: "kindle-zotero-importer@utkubilen.de",
  menuItems: [],
  defaultProjectDir:
    "/home/user/Library/Mobile Documents/iCloud~md~obsidian/Documents/rhizome/06_projects/UTI/kindle-zotero-importer",
  defaultClippingsPath:
    "/home/user/Library/Mobile Documents/com~apple~CloudDocs/Projects/test/My Clippings.txt",
  prefBranch: "extensions.kindleZoteroImporter.",
  rootURI: null,
  managerWindow: null,
  chromeHandle: null,

  async startup(data) {
    this.rootURI = data.rootURI;
    const addonManagerStartup = Cc["@mozilla.org/addons/addon-manager-startup;1"].getService(
      Ci.amIAddonManagerStartup
    );
    this.chromeHandle = addonManagerStartup.registerChrome(
      Services.io.newURI(this.rootURI + "manifest.json"),
      [["content", "kindle-zotero-importer", ""]]
    );
    await Zotero.initializationPromise;
    this.addToAllWindows();
  },

  shutdown() {
    this.removeMenuItems();
    if (this.managerWindow && !this.managerWindow.closed) {
      this.managerWindow.close();
    }
    this.managerWindow = null;
    if (this.chromeHandle) {
      this.chromeHandle.destruct();
      this.chromeHandle = null;
    }
  },

  onMainWindowLoad(win) {
    this.addMenuItems(win);
  },

  onMainWindowUnload(_win) {
    this.menuItems = [];
  },

  addMenuItems(win) {
    win = win || Zotero.getMainWindow();
    if (!win || !win.document) {
      return;
    }

    const doc = win.document;
    if (doc.getElementById("kindle-zotero-importer-manager")) {
      return;
    }

    const popup = doc.getElementById("menu_ToolsPopup");
    if (!popup) {
      Zotero.debug("Kindle Zotero Importer: Tools menu not found");
      return;
    }

    const managerItem = doc.createXULElement("menuitem");
    managerItem.setAttribute("id", "kindle-zotero-importer-manager");
    managerItem.setAttribute("label", "Kindle Zotero Importer...");
    managerItem.addEventListener("command", () => this.openManager());
    popup.appendChild(managerItem);
    this.menuItems.push(managerItem);

  },

  addToAllWindows() {
    const windows = Zotero.getMainWindows ? Zotero.getMainWindows() : [Zotero.getMainWindow()];
    for (const win of windows) {
      if (win && win.ZoteroPane) {
        this.addMenuItems(win);
      }
    }
  },

  removeMenuItems() {
    for (const item of this.menuItems) {
      if (item && item.parentNode) {
        item.parentNode.removeChild(item);
      }
    }
    this.menuItems = [];
  },

  getPref(name, fallback) {
    try {
      return Services.prefs.getCharPref(this.prefBranch + name);
    } catch (_error) {
      return fallback;
    }
  },

  setPref(name, value) {
    Services.prefs.setCharPref(this.prefBranch + name, String(value));
  },

  getProjectDir() {
    return this.getPref("projectDir", this.defaultProjectDir);
  },

  getPythonPath() {
    return this.getPref("pythonPath", "/opt/homebrew/bin/python3");
  },

  getZoteroDbPath() {
    return this.getPref("zoteroDbPath", "/home/user/Zotero/zotero.sqlite");
  },

  getZoteroStorageRoot() {
    return this.getPref("zoteroStorageRoot", "/home/user/Zotero/storage");
  },

  getConfigPath() {
    return this.getProjectDir() + "/plugin-config.json";
  },

  artifactPath(relativePath) {
    return this.getProjectDir() + "/" + relativePath;
  },

  async openArtifact(relativePath) {
    const path = this.artifactPath(relativePath);
    try {
      await Zotero.File.getContentsAsync(path);
      this.revealFile(path);
    } catch (_error) {
      this.alert(
        "Kindle Zotero Importer",
        `File not found yet:\n${path}\n\nRun Import Kindle Clippings first to generate review artifacts.`
      );
    }
  },

  async getRuntimeSettings() {
    const settings = {
      projectDir: this.getProjectDir(),
      pythonPath: this.getPythonPath(),
      zoteroDbPath: this.getZoteroDbPath(),
      zoteroStorageRoot: this.getZoteroStorageRoot(),
    };
    try {
      const text = await Zotero.File.getContentsAsync(this.getConfigPath());
      const parsed = JSON.parse(text);
      for (const key of Object.keys(settings)) {
        if (parsed[key]) {
          settings[key] = parsed[key];
        }
      }
    } catch (_error) {
      // The config file is optional; defaults/preferences are enough for first run.
    }
    return settings;
  },

  getMainWindow() {
    return Zotero.getMainWindow();
  },

  getPickerWindow() {
    return Services.wm.getMostRecentWindow("navigator:browser") || this.getMainWindow();
  },

  alert(title, message) {
    Services.prompt.alert(this.getMainWindow(), title, message);
  },

  notify(message, success) {
    try {
      const progressWindow = new Zotero.ProgressWindow({ closeOnClick: true });
      progressWindow.changeHeadline("Kindle Zotero Importer");
      const icon = success ? "chrome://zotero/skin/tick.png" : "chrome://zotero/skin/cross.png";
      const item = new progressWindow.ItemProgress(icon, message);
      item.setProgress(100);
      progressWindow.show();
      progressWindow.startCloseTimer(success ? 5000 : 10000);
      return progressWindow;
    } catch (_error) {
      return null;
    }
  },

  createProgress(message) {
    try {
      const progressWindow = new Zotero.ProgressWindow({ closeOnClick: false });
      progressWindow.changeHeadline("Kindle Zotero Importer");
      progressWindow.progress = new progressWindow.ItemProgress(
        "chrome://zotero/skin/treesource-collection.png",
        message
      );
      progressWindow.progress.setProgress(0);
      progressWindow.show();
      return progressWindow;
    } catch (_error) {
      return null;
    }
  },

  promptForPath(title, message, fallback) {
    const value = { value: fallback || "" };
    const ok = Services.prompt.prompt(this.getMainWindow(), title, message, value, null, {});
    return ok && value.value ? value.value : null;
  },

  async configure() {
    const current = {
      projectDir: this.getProjectDir(),
      pythonPath: this.getPythonPath(),
      zoteroDbPath: this.getZoteroDbPath(),
      zoteroStorageRoot: this.getZoteroStorageRoot(),
    };
    try {
      const configPath = this.getConfigPath();
      await Zotero.File.putContentsAsync(configPath, JSON.stringify(current, null, 2) + "\n");
      this.alert(
        "Kindle Zotero Importer Configuration",
        `Configuration file written to:\n${configPath}\n\nEdit this file to change paths. The import dialog will show the active settings before running.`
      );
      this.revealFile(configPath);
    } catch (error) {
      Zotero.logError(error);
      this.alert("Kindle Zotero Importer Failed", String(error && error.stack ? error.stack : error));
    }
  },

  async openManager() {
    if (this.managerWindow && !this.managerWindow.closed) {
      this.managerWindow.focus();
      return;
    }
    const settings = await this.getRuntimeSettings();
    const data = await this.loadManagerData();
    const io = { plugin: this, settings, data };
    this.managerWindow = this.getMainWindow().openDialog(
      "chrome://kindle-zotero-importer/content/manager.html",
      "kindle-zotero-importer-manager-window",
      "chrome,centerscreen,resizable",
      io
    );
  },

  async loadManagerData() {
    return {
      matches: await this.readJsonArtifact("matches.json"),
      generatedOverrides: await this.readJsonArtifact("match-overrides.generated.json"),
      positionedPlan: await this.readJsonArtifact("import-plan.positioned.json"),
      finalPlan: await this.readJsonArtifact("import-plan.final.json"),
      summary: await this.readJsonArtifact("plugin-summary.json"),
      persistentOverrides: await this.readJsonArtifact("match-overrides.json"),
    };
  },

  async openStaticDashboard() {
    const settings = await this.getRuntimeSettings();
    const data = {
      matches: await this.readJsonArtifact("matches.json"),
      generatedOverrides: await this.readJsonArtifact("match-overrides.generated.json"),
      positionedPlan: await this.readJsonArtifact("import-plan.positioned.json"),
      finalPlan: await this.readJsonArtifact("import-plan.final.json"),
      summary: await this.readJsonArtifact("plugin-summary.json"),
      persistentOverrides: await this.readJsonArtifact("match-overrides.json"),
    };
    const outputPath = this.artifactPath("kindle-import-manager.html");
    await Zotero.File.putContentsAsync(outputPath, this.buildManagerHtml(settings, data));
    this.openFile(outputPath);
  },

  async loadOverridesFile() {
    const path = this.artifactPath("match-overrides.json");
    try {
      return JSON.parse(await Zotero.File.getContentsAsync(path));
    } catch (_error) {
      return { format: "kindle-zotero-importer.match-overrides.v1", overrides: [] };
    }
  },

  async saveOverride(resolution) {
    if (!resolution || !resolution.clipping_title) {
      throw new Error("Missing clipping title for override");
    }
    const payload = await this.loadOverridesFile();
    if (!Array.isArray(payload.overrides)) {
      payload.overrides = [];
    }
    const index = payload.overrides.findIndex(
      (entry) => entry.clipping_title === resolution.clipping_title
    );
    const nowIso = new Date().toISOString();
    const entry = {
      clipping_title: resolution.clipping_title,
      resolution: resolution.resolution,
      review: resolution.review || { status: "manager", clipping_count: resolution.clipping_count || 0 },
      created_at: nowIso,
      updated_at: nowIso,
    };
    if (index >= 0) {
      const prev = payload.overrides[index];
      entry.created_at = prev.created_at || prev.updated_at || nowIso;
      entry.updated_at = nowIso;
      payload.overrides[index] = entry;
    } else {
      payload.overrides.push(entry);
    }
    payload.overrides.sort((a, b) => (b.updated_at || b.created_at || "").localeCompare(a.updated_at || a.created_at || "") || a.clipping_title.localeCompare(b.clipping_title));
    await Zotero.File.putContentsAsync(
      this.artifactPath("match-overrides.json"),
      JSON.stringify(payload, null, 2) + "\n"
    );
    return entry;
  },

  async deleteOverride(clippingTitle) {
    if (!clippingTitle) {
      throw new Error("Missing clipping title for delete");
    }
    const payload = await this.loadOverridesFile();
    const before = payload.overrides.length;
    payload.overrides = payload.overrides.filter((e) => e.clipping_title !== clippingTitle);
    if (payload.overrides.length === before) {
      throw new Error(`No override found for: ${clippingTitle}`);
    }
    await Zotero.File.putContentsAsync(
      this.artifactPath("match-overrides.json"),
      JSON.stringify(payload, null, 2) + "\n"
    );
    return true;
  },

  async saveSettingsFromManager(newSettings) {
    const toSave = {
      projectDir: newSettings.projectDir || this.getProjectDir(),
      pythonPath: newSettings.pythonPath || this.getPythonPath(),
      zoteroDbPath: newSettings.zoteroDbPath || this.getZoteroDbPath(),
      zoteroStorageRoot: newSettings.zoteroStorageRoot || this.getZoteroStorageRoot(),
    };
    for (const [key, value] of Object.entries(toSave)) {
      this.setPref(key, value);
    }
    await Zotero.File.putContentsAsync(
      this.getConfigPath(),
      JSON.stringify(toSave, null, 2) + "\n"
    );
    return toSave;
  },

  async readJsonArtifact(relativePath) {
    try {
      return JSON.parse(await Zotero.File.getContentsAsync(this.artifactPath(relativePath)));
    } catch (_error) {
      return null;
    }
  },

  escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  },

  fileHref(path) {
    return "file://" + encodeURI(path).replaceAll("#", "%23");
  },

  artifactLink(label, relativePath) {
    const path = this.artifactPath(relativePath);
    return `<a href="${this.escapeHtml(this.fileHref(path))}">${this.escapeHtml(label)}</a>`;
  },

  countStatuses(items, key = "status") {
    const counts = {};
    for (const item of items || []) {
      const status = item[key] || "unknown";
      counts[status] = (counts[status] || 0) + 1;
    }
    return counts;
  },

  statusCards(counts) {
    return Object.entries(counts || {})
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([status, count]) => `<div class="card"><strong>${this.escapeHtml(count)}</strong><span>${this.escapeHtml(status)}</span></div>`)
      .join("\n");
  },

  conflictRows(data) {
    const rows = [];
    for (const match of data.matches?.matches || []) {
      if (["matched", "ignored"].includes(match.status)) {
        continue;
      }
      const candidates = (match.candidates || [])
        .slice(0, 3)
        .map((candidate) => `${candidate.citation_key || candidate.key || candidate.item_id}: ${candidate.title || ""}`)
        .join("; ");
      rows.push({
        type: "title-match",
        status: match.status,
        title: match.clipping_title,
        count: match.clipping_count,
        detail: candidates || "No candidates",
        snippet: this.overrideSnippet(match.clipping_title, match.clipping_count, match.status, match.candidates?.[0]),
      });
    }

    for (const override of data.generatedOverrides?.overrides || []) {
      const candidateText = (override.candidates || [])
        .slice(0, 3)
        .map((candidate) => `${candidate.citation_key || candidate.key || candidate.item_id}: ${candidate.title || ""}`)
        .join("; ");
      rows.push({
        type: "override-suggestion",
        status: override.review?.status || "review",
        title: override.clipping_title,
        count: override.review?.clipping_count || "",
        detail: candidateText || override.notes || "Needs override decision",
        snippet: JSON.stringify({
          clipping_title: override.clipping_title,
          resolution: override.resolution || { ignore: false, citation_key: "" },
          review: override.review,
        }, null, 2),
      });
    }

    for (const item of data.positionedPlan?.items || []) {
      const status = item.status || "unknown";
      if (["positioned", "ignored-title"].includes(status)) {
        continue;
      }
      rows.push({
        type: "positioning/import-plan",
        status,
        title: item.clipping?.title || "(missing clipping title)",
        count: 1,
        detail: (item.problems || []).join("; ") || item.annotation?.text || "Needs review",
        snippet: "Fix source data, attachment availability, or matching override; then rerun Import Kindle Clippings.",
      });
    }

    return rows;
  },

  overrideSnippet(title, clippingCount, status, candidate) {
    const resolution = candidate?.citation_key
      ? { ignore: false, citation_key: candidate.citation_key }
      : { ignore: true };
    return JSON.stringify({
      clipping_title: title,
      resolution,
      review: {
        status,
        clipping_count: clippingCount,
      },
    }, null, 2);
  },

  groupedRows(rows) {
    const groups = {
      "Title Matching": [],
      "Override Suggestions": [],
      "Attachment / Positioning": [],
    };
    for (const row of rows) {
      if (row.type === "title-match") {
        groups["Title Matching"].push(row);
      } else if (row.type === "override-suggestion") {
        groups["Override Suggestions"].push(row);
      } else {
        groups["Attachment / Positioning"].push(row);
      }
    }
    return groups;
  },

  tableRows(rows, limit = 200) {
    if (!rows.length) {
      return '<tr><td colspan="6">No conflicts found in this group.</td></tr>';
    }
    return rows.slice(0, limit).map((row) => `
      <tr data-search="${this.escapeHtml(`${row.type} ${row.status} ${row.title} ${row.detail}`.toLowerCase())}">
        <td>${this.escapeHtml(row.type)}</td>
        <td><span class="pill">${this.escapeHtml(row.status)}</span></td>
        <td>${this.escapeHtml(row.count)}</td>
        <td>${this.escapeHtml(row.title)}</td>
        <td>${this.escapeHtml(row.detail)}</td>
        <td><pre>${this.escapeHtml(row.snippet || "")}</pre></td>
      </tr>`).join("\n");
  },

  conflictTables(rows) {
    const groups = this.groupedRows(rows);
    return Object.entries(groups).map(([label, groupRows]) => `
      <section class="panel">
        <h3>${this.escapeHtml(label)} <span class="muted">${this.escapeHtml(groupRows.length)} rows</span></h3>
        <table>
          <thead><tr><th>Type</th><th>Status</th><th>Count</th><th>Kindle Title</th><th>Details / Candidate Differences</th><th>Override / Fix Snippet</th></tr></thead>
          <tbody>${this.tableRows(groupRows)}</tbody>
        </table>
      </section>`).join("\n");
  },

  buildManagerHtml(settings, data) {
    const matchCounts = this.countStatuses(data.matches?.matches || []);
    const planCounts = data.positionedPlan?.status_counts || this.countStatuses(data.positionedPlan?.items || []);
    const finalCount = data.finalPlan?.annotation_count || 0;
    const skippedCounts = data.finalPlan?.skipped_counts || {};
    const conflicts = this.conflictRows(data);
    const generatedAt = new Date().toLocaleString();
    return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Kindle Zotero Importer Manager</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 28px; color: #202124; background: #f6f4ef; }
    h1 { margin: 0 0 4px; font-size: 30px; }
    h2 { margin-top: 28px; border-bottom: 1px solid #d8d0c2; padding-bottom: 6px; }
    h3 { margin-top: 18px; }
    code, pre { background: #eee7dc; border-radius: 6px; padding: 2px 5px; }
    pre { white-space: pre-wrap; max-width: 360px; font-size: 12px; }
    .meta { color: #6b6258; margin-bottom: 24px; }
    .nav { display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0; }
    .nav a { background: #263238; color: white; text-decoration: none; padding: 7px 10px; border-radius: 999px; font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .card { background: white; border: 1px solid #ded6c9; border-radius: 12px; padding: 14px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
    .card strong { display: block; font-size: 24px; }
    .card span { color: #6b6258; }
    table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #ded6c9; }
    th, td { text-align: left; vertical-align: top; border-bottom: 1px solid #eee7dc; padding: 8px; }
    th { background: #eee7dc; position: sticky; top: 0; }
    .pill { display: inline-block; background: #263238; color: white; border-radius: 999px; padding: 2px 8px; font-size: 12px; }
    .paths li { margin: 6px 0; }
    .notice { background: #fff8d6; border: 1px solid #ead37a; border-radius: 10px; padding: 12px; }
    .panel { margin: 18px 0 28px; }
    .muted { color: #6b6258; font-weight: normal; font-size: 13px; }
    .search { width: 100%; box-sizing: border-box; font-size: 16px; padding: 10px; border: 1px solid #d8d0c2; border-radius: 10px; margin: 10px 0 16px; }
    .todo { background: #e8f1ff; border: 1px solid #a7c7ef; border-radius: 10px; padding: 12px; }
  </style>
  <script>
    function filterRows() {
      const needle = document.getElementById('conflict-search').value.toLowerCase();
      for (const row of document.querySelectorAll('tbody tr[data-search]')) {
        row.style.display = row.dataset.search.includes(needle) ? '' : 'none';
      }
    }
  </script>
</head>
<body>
  <h1>Kindle Zotero Importer Manager</h1>
  <div class="meta">Generated ${this.escapeHtml(generatedAt)} from <code>${this.escapeHtml(settings.projectDir)}</code></div>

  <div class="nav">
    <a href="#settings">Settings</a>
    <a href="#run">Run Import</a>
    <a href="#statuses">Statuses</a>
    <a href="#artifacts">Artifacts</a>
    <a href="#conflicts">Conflicts</a>
  </div>

  <div class="notice">
    This dashboard is generated from importer artifacts. Copy override snippets into <code>match-overrides.json</code> for now, then rerun Import Kindle Clippings. Direct in-dashboard editing is the next step.
  </div>

  <h2 id="settings">Settings</h2>
  <ul class="paths">
    <li><strong>Project directory:</strong> <code>${this.escapeHtml(settings.projectDir)}</code></li>
    <li><strong>Python:</strong> <code>${this.escapeHtml(settings.pythonPath)}</code></li>
    <li><strong>Zotero DB:</strong> <code>${this.escapeHtml(settings.zoteroDbPath)}</code></li>
    <li><strong>Zotero storage:</strong> <code>${this.escapeHtml(settings.zoteroStorageRoot)}</code></li>
    <li><strong>Config:</strong> <code>${this.escapeHtml(this.getConfigPath())}</code></li>
  </ul>

  <h2 id="run">Run Import</h2>
  <div class="todo">
    Run from Zotero: <strong>Tools > Import Kindle Clippings...</strong>. The import now shows preflight settings, progress, final counts, existing-comment updates, existing-sort-order repairs, and any guarded delete/recreate confirmations for <code>kindle-import</code> annotations.
  </div>

  <h2>Import Summary</h2>
  <div class="grid">
    <div class="card"><strong>${this.escapeHtml(data.summary?.counts?.clippings || "-")}</strong><span>clippings</span></div>
    <div class="card"><strong>${this.escapeHtml(data.summary?.counts?.unique_titles || "-")}</strong><span>unique titles</span></div>
    <div class="card"><strong>${this.escapeHtml(finalCount)}</strong><span>final annotations</span></div>
    <div class="card"><strong>${this.escapeHtml(conflicts.length)}</strong><span>conflict rows</span></div>
  </div>

  <h2 id="statuses">Match Statuses</h2>
  <div class="grid">${this.statusCards(matchCounts) || '<div class="card">No match data yet</div>'}</div>

  <h2>Plan Statuses</h2>
  <div class="grid">${this.statusCards(planCounts) || '<div class="card">No plan data yet</div>'}</div>

  <h2>Final Plan Skips</h2>
  <div class="grid">${this.statusCards(skippedCounts) || '<div class="card">No skipped final annotations</div>'}</div>

  <h2 id="artifacts">Artifacts</h2>
  <ul>
    <li>${this.artifactLink("Mismatch review", "docs/mismatch-review.md")}</li>
    <li>${this.artifactLink("Persistent overrides", "match-overrides.json")}</li>
    <li>${this.artifactLink("Generated override suggestions", "match-overrides.generated.json")}</li>
    <li>${this.artifactLink("Positioned plan", "import-plan.positioned.json")}</li>
    <li>${this.artifactLink("Final writer plan", "import-plan.final.json")}</li>
    <li>${this.artifactLink("Plugin summary", "plugin-summary.json")}</li>
  </ul>

  <h2 id="conflicts">Conflicts and Exceptions</h2>
  <p>Rows include unresolved title matches, generated override suggestions, attachment problems, and positioning failures. Use search to filter titles, statuses, citekeys, and candidate text. Showing first 200 rows per group.</p>
  <input id="conflict-search" class="search" type="search" oninput="filterRows()" placeholder="Filter conflicts by title, status, candidate, citekey...">
  ${this.conflictTables(conflicts)}
</body>
</html>`;
  },

  async importClippings() {
    let progressWindow = null;
    try {
      const clippingsPath = await this.pickFile("Select Kindle My Clippings.txt", "*.txt");
      if (!clippingsPath) {
        return;
      }

      const settings = await this.getRuntimeSettings();
      const settingsMessage = [
        "Run Kindle import pipeline with these settings?",
        "",
        `Clippings: ${clippingsPath}`,
        `Project directory: ${settings.projectDir}`,
        `Python: ${settings.pythonPath}`,
        `Zotero DB: ${settings.zoteroDbPath}`,
        `Zotero storage: ${settings.zoteroStorageRoot}`,
        `Config file: ${this.getConfigPath()}`,
        "",
        "This first creates/updates review files. You can choose whether to import annotations after the summary.",
      ].join("\n");
      if (!Services.prompt.confirm(this.getMainWindow(), "Kindle Zotero Importer", settingsMessage)) {
        return;
      }

      progressWindow = this.createProgress("Starting Kindle import...");
      if (progressWindow) {
        progressWindow.changeHeadline("Kindle Zotero Importer: reading clippings");
      }
      const summary = await this.runPipeline(clippingsPath, settings);
      if (progressWindow && progressWindow.progress) {
        progressWindow.progress.setProgress(100);
        progressWindow.changeHeadline("Kindle Zotero Importer: pipeline complete");
      }
      const finalPlanPath = summary.outputs.final_plan;
      const finalPlan = JSON.parse(await Zotero.File.getContentsAsync(finalPlanPath));
      this.notify(
        `Pipeline completed. ${summary.counts.final_annotations || 0} final annotations ready.`,
        true
      );

      const decision = this.confirmImport(summary);
      if (decision === "review") {
        this.revealFile(summary.outputs.mismatch_review);
        return;
      }
      if (decision !== "import") {
        return;
      }

      if (progressWindow) {
        progressWindow.changeHeadline("Kindle Zotero Importer: writing annotations");
      }
      const results = await this.writeAnnotations(finalPlan, false);
      this.notify(
        `Import finished. Created ${results.created}; skipped ${results.skippedExisting}; updated order ${results.updatedSortIndex}; recreated ${results.recreatedForSortIndex}; failed ${results.failed.length}.`,
        results.failed.length === 0
      );
      this.alert("Kindle Zotero Importer", this.formatWriterResults(results));
    } catch (error) {
      Zotero.logError(error);
      this.notify("Import failed. See the error dialog for details.", false);
      this.alert("Kindle Zotero Importer Failed", String(error && error.stack ? error.stack : error));
    } finally {
      if (progressWindow && progressWindow.startCloseTimer) {
        progressWindow.startCloseTimer(1000);
      }
    }
  },

  async pickFile(title, filter) {
    try {
      const pickerModule = ChromeUtils.importESModule(
        "chrome://zotero/content/modules/filePicker.mjs"
      );
      const FilePicker = pickerModule.FilePicker;
      if (typeof FilePicker !== "function") {
        throw new Error(`Zotero FilePicker module did not export a constructor: ${Object.keys(pickerModule)}`);
      }
      const fp = new FilePicker();
      fp.init(this.getPickerWindow(), title, fp.modeOpen);
      if (filter) {
        fp.appendFilter("Kindle clippings", filter);
      }
      fp.appendFilters(fp.filterAll);

      const result = await fp.show();
      if (result !== fp.returnOK) {
        return null;
      }
      return fp.file;
    } catch (error) {
      Zotero.logError(error);
      return this.promptForPath(
        "Kindle Zotero Importer",
        "File picker failed. Enter the full path to My Clippings.txt:",
        this.defaultClippingsPath
      );
    }
  },

  async pickDirectory(title) {
    try {
      const pickerModule = ChromeUtils.importESModule(
        "chrome://zotero/content/modules/filePicker.mjs"
      );
      const FilePicker = pickerModule.FilePicker;
      if (typeof FilePicker !== "function") {
        throw new Error(`Zotero FilePicker module did not export a constructor: ${Object.keys(pickerModule)}`);
      }
      const fp = new FilePicker();
      fp.init(this.getPickerWindow(), title, fp.modeGetFolder);

      const result = await fp.show();
      if (result !== fp.returnOK) {
        return null;
      }
      return fp.file;
    } catch (error) {
      Zotero.logError(error);
      return this.promptForPath(
        "Kindle Zotero Importer",
        "Folder picker failed. Enter the full project directory path:",
        this.defaultProjectDir
      );
    }
  },

  async runPipeline(clippingsPath, settings, isFull = false) {
    const python = settings.pythonPath;
    const projectDir = settings.projectDir;
    const runner = projectDir + "/plugin_runner.py";
    const summaryOutput = projectDir + "/plugin-summary.json";
    const progressOutput = projectDir + "/plugin-progress.json";
    const args = [
      runner,
      "run",
      clippingsPath,
      "--workdir",
      projectDir,
      "--db",
      settings.zoteroDbPath,
      "--storage-root",
      settings.zoteroStorageRoot,
      "--overrides",
      "match-overrides.json",
      "--summary-output",
      summaryOutput,
      "--progress-output",
      progressOutput,
      "--pretty",
    ];
    if (isFull) {
      args.push("--full");
    }

    await this.exec(python, args);
    return JSON.parse(await Zotero.File.getContentsAsync(summaryOutput));
  },

  async runManagedImport(manager) {
    const clippingsPath = await this.pickFile("Select Kindle My Clippings.txt", "*.txt");
    if (!clippingsPath) {
      return;
    }
    const isFull = manager.getFullReimport ? manager.getFullReimport() : false;
    await this.runManagedImportWithPath(manager, clippingsPath, isFull);
  },

  async runManagedImportWithPath(manager, clippingsPath, isFullOverride) {
    try {
      if (!clippingsPath) {
        throw new Error("No clippings file selected");
      }
      const settings = await this.getRuntimeSettings();
      const progressPath = settings.projectDir + "/plugin-progress.json";
      // Determine full vs incremental from explicit arg or manager checkbox
      const isFull = typeof isFullOverride === "boolean" ? isFullOverride : (manager.getFullReimport ? manager.getFullReimport() : false);
      manager.beginRun(clippingsPath);
      try {
        await Zotero.File.removeIfExists(progressPath);
      } catch (_error) {}

      let polling = true;
      const poll = async () => {
        while (polling) {
          try {
            const progress = JSON.parse(await Zotero.File.getContentsAsync(progressPath));
            manager.updateProgress(progress.percent, progress.stage, progress.detail);
          } catch (_error) {}
          await Zotero.Promise.delay(500);
        }
      };
      const pollPromise = poll();
      let summary;
      try {
        summary = await this.runPipeline(clippingsPath, settings, isFull);
      } finally {
        polling = false;
        await pollPromise;
      }

      const finalPlan = JSON.parse(
        await Zotero.File.getContentsAsync(summary.outputs.final_plan)
      );
      manager.updateProgress(96, "Writing annotations", "Saving annotations in Zotero");
      const results = await this.writeAnnotations(finalPlan, false, (completed, total) => {
        const percent = total ? 96 + Math.floor((completed / total) * 4) : 100;
        manager.updateProgress(percent, "Writing annotations", `${completed} of ${total} checked`);
      });
      const data = await this.loadManagerData();
      manager.completeRun(summary, results, data);
    } catch (error) {
      Zotero.logError(error);
      manager.failRun(String(error && error.stack ? error.stack : error));
    }
  },

  async exec(command, args) {
    if (!Zotero.Utilities || !Zotero.Utilities.Internal || !Zotero.Utilities.Internal.exec) {
      throw new Error("Zotero.Utilities.Internal.exec is unavailable in this Zotero build");
    }
    return Zotero.Utilities.Internal.exec(command, args);
  },

  confirmImport(summary) {
    const counts = summary.counts || {};
    const planStatuses = counts.plan_statuses || {};
    const matchStatuses = counts.match_statuses || {};
    const unresolved =
      (matchStatuses.unmatched || 0) +
      (matchStatuses.ambiguous || 0) +
      (planStatuses["matched-title-no-attachment"] || 0) +
      (planStatuses["matched-title-ambiguous-attachment"] || 0);
    const positioned = planStatuses.positioned || 0;

    const message = [
      "Pipeline completed.",
      "",
      `Clippings: ${counts.clippings || 0}`,
      `Unique Kindle titles: ${counts.unique_titles || 0}`,
      `Positioned annotations ready: ${positioned}`,
      `Final annotations to check/import: ${counts.final_annotations || 0}`,
      `Unresolved or ambiguous cases: ${unresolved}`,
      "",
      "Import positioned annotations now, open the mismatch review, or cancel?",
    ].join("\n");

    const choice = Services.prompt.confirmEx(
      this.getMainWindow(),
      "Kindle Zotero Importer",
      message,
      Services.prompt.BUTTON_POS_0 * Services.prompt.BUTTON_TITLE_IS_STRING +
        Services.prompt.BUTTON_POS_1 * Services.prompt.BUTTON_TITLE_IS_STRING +
        Services.prompt.BUTTON_POS_2 * Services.prompt.BUTTON_TITLE_CANCEL,
      "Import",
      "Open Review",
      null,
      null,
      {}
    );

    if (choice === 0) {
      return "import";
    }
    if (choice === 1) {
      return "review";
    }
    return "cancel";
  },

  normalizePosition(position) {
    if (!position) {
      return "";
    }
    if (typeof position === "string") {
      try {
        return JSON.stringify(JSON.parse(position));
      } catch (_error) {
        return position;
      }
    }
    return JSON.stringify(position);
  },

  annotationFingerprint(annotation) {
    return `${annotation.text || ""}\u0000${this.normalizePosition(annotation.position)}`;
  },

  existingAnnotationFingerprint(annotation) {
    return `${annotation.annotationText || ""}\u0000${this.normalizePosition(annotation.annotationPosition)}`;
  },

  mergeComments(existingComment, newComment) {
    const seen = new Set();
    const merged = [];
    for (const comment of [existingComment, newComment]) {
      for (const part of String(comment || "").split(/\n\s*\n/)) {
        const cleaned = part.trim();
        if (!cleaned || seen.has(cleaned)) {
          continue;
        }
        seen.add(cleaned);
        merged.push(cleaned);
      }
    }
    return merged.join("\n\n");
  },

  existingSortIndex(annotation) {
    return annotation.annotationSortIndex || annotation._annotationSortIndex || annotation.sortIndex || "";
  },

  existingTags(annotation) {
    try {
      if (annotation.getTags) {
        return annotation.getTags().map((tag) => tag.tag || tag.name || String(tag));
      }
    } catch (_error) {
      // Fall through to property checks below.
    }
    const tags = annotation.annotationTags || annotation.tags || [];
    if (!Array.isArray(tags)) {
      return [];
    }
    return tags.map((tag) => tag.tag || tag.name || String(tag));
  },

  hasKindleImportTag(annotation) {
    return this.existingTags(annotation).includes("kindle-import");
  },

  confirmRecreateForSortIndex(entry, existingAnnotation, oldSortIndex, newSortIndex) {
    const tags = this.existingTags(existingAnnotation).join(", ") || "(none)";
    const message = [
      "Zotero could not update an existing annotation's sort order in place.",
      "",
      "The plugin can delete and recreate this annotation to fix ordering, but only because it has the kindle-import tag.",
      "",
      `Title: ${entry.clipping_title}`,
      `Attachment item: ${entry.attachment_item_id}`,
      `Current sortIndex: ${oldSortIndex || "(empty)"}`,
      `New sortIndex: ${newSortIndex}`,
      `Tags: ${tags}`,
      "",
      "Text, comment, color, tags, and position will be preserved from the import plan.",
      "",
      "Delete and recreate this kindle-import annotation?",
    ].join("\n");
    return Services.prompt.confirm(
      this.getMainWindow(),
      "Kindle Zotero Importer: Recreate Annotation?",
      message
    );
  },

  async saveExistingAnnotation(existingAnnotation) {
    if (existingAnnotation.saveTx) {
      await existingAnnotation.saveTx();
      return;
    }
    if (existingAnnotation.save) {
      await existingAnnotation.save();
      return;
    }
    throw new Error("Existing annotation cannot be saved by this Zotero build");
  },

  async writeAnnotations(plan, dryRun, onProgress) {
    if (plan.format !== "kindle-zotero-importer.zotero-writer-plan.v1") {
      throw new Error(`Unsupported plan format: ${plan.format}`);
    }

    const results = {
      dryRun,
      total: plan.annotations.length,
      created: 0,
      skippedExisting: 0,
      updatedComments: 0,
      updatedSortIndex: 0,
      recreatedForSortIndex: 0,
      blockedRecreateMissingTag: 0,
      recreateDeclined: 0,
      removedDuplicates: 0,
      deletedForIncremental: 0,
      failed: [],
    };
    // Incremental deletions: remove annotations whose clipping_id is no longer present
    if (!dryRun && plan.deletions && plan.deletions.length) {
      const deletionIds = new Set(plan.deletions);
      try {
        // Find all annotations with kindle-id tag
        const allAnnotations = [];
        // Collect via attachments to be safe
        const allItems = Zotero.Items.getAll ? await Zotero.Items.getAll() : [];
        for (const item of allItems) {
          if (item.isAnnotation && item.isAnnotation()) {
            allAnnotations.push(item);
          } else if (item.getAnnotations) {
            const anns = item.getAnnotations();
            for (const a of anns) allAnnotations.push(a);
          }
        }
        // Deduplicate
        const seen = new Set();
        for (const ann of allAnnotations) {
          if (!ann || seen.has(ann.id)) continue;
          seen.add(ann.id);
          const tags = this.existingTags(ann);
          for (const tag of tags) {
            if (tag.startsWith("kindle-id:")) {
              const id = tag.substring("kindle-id:".length);
              if (deletionIds.has(id)) {
                await ann.eraseTx();
                results.deletedForIncremental += 1;
                break;
              }
            }
          }
        }
      } catch (e) {
        Zotero.logError(e);
      }
    }
    const existingByAttachment = new Map();

    const getExistingAnnotations = async (attachment) => {
      if (!existingByAttachment.has(attachment.id)) {
        const annotations = attachment.getAnnotations ? attachment.getAnnotations() : [];
        const byFingerprint = new Map();

        for (const annotation of annotations) {
          const fingerprint = this.existingAnnotationFingerprint(annotation);
          const kept = byFingerprint.get(fingerprint);
          if (!kept) {
            byFingerprint.set(fingerprint, annotation);
            continue;
          }

          const keptHasComment = Boolean(kept.annotationComment);
          const currentHasComment = Boolean(annotation.annotationComment);
          const duplicate = keptHasComment || !currentHasComment ? annotation : kept;
          const replacement = duplicate === annotation ? kept : annotation;

          byFingerprint.set(fingerprint, replacement);
          if (!dryRun) {
            await duplicate.eraseTx();
          }
          results.removedDuplicates += 1;
        }

        existingByAttachment.set(attachment.id, byFingerprint);
      }
      return existingByAttachment.get(attachment.id);
    };

    let completed = 0;
    for (const entry of plan.annotations) {
      try {
        const attachment = Zotero.Items.get(entry.attachment_item_id);
        if (!attachment) {
          throw new Error(`Attachment not found: ${entry.attachment_item_id}`);
        }

        const annotation = {
          key: Zotero.DataObjectUtilities.generateKey(),
          ...entry.annotation,
        };
        if (!annotation.sortIndex) {
          delete annotation.sortIndex;
        }

        const existingAnnotations = await getExistingAnnotations(attachment);
        const fingerprint = this.annotationFingerprint(annotation);
        const existingAnnotation = existingAnnotations.get(fingerprint);
        if (existingAnnotation) {
          const mergedComment = this.mergeComments(
            existingAnnotation.annotationComment,
            annotation.comment
          );
          let changed = false;
          if (mergedComment && existingAnnotation.annotationComment !== mergedComment) {
            existingAnnotation.annotationComment = mergedComment;
            changed = true;
            results.updatedComments += 1;
          }

          const oldSortIndex = this.existingSortIndex(existingAnnotation);
          const newSortIndex = annotation.sortIndex || "";
          const sortIndexChanged = Boolean(newSortIndex) && oldSortIndex !== newSortIndex;
          if (sortIndexChanged) {
            existingAnnotation.annotationSortIndex = newSortIndex;
            changed = true;
          }

          if (changed && !dryRun) {
            try {
              await this.saveExistingAnnotation(existingAnnotation);
              if (sortIndexChanged) {
                results.updatedSortIndex += 1;
              }
            } catch (error) {
              if (!sortIndexChanged) {
                throw error;
              }
              if (!this.hasKindleImportTag(existingAnnotation)) {
                results.blockedRecreateMissingTag += 1;
                throw new Error(
                  `Could not update sortIndex and existing annotation is not tagged kindle-import: ${error}`
                );
              }
              if (!this.confirmRecreateForSortIndex(entry, existingAnnotation, oldSortIndex, newSortIndex)) {
                results.recreateDeclined += 1;
                results.skippedExisting += 1;
                continue;
              }
              await existingAnnotation.eraseTx();
              await Zotero.Annotations.saveFromJSON(attachment, annotation);
              existingAnnotations.set(fingerprint, {
                annotationComment: annotation.comment || "",
                annotationPosition: annotation.position,
                annotationSortIndex: annotation.sortIndex || "",
                annotationTags: annotation.tags || [],
                annotationText: annotation.text || "",
              });
              results.recreatedForSortIndex += 1;
              results.skippedExisting += 1;
              continue;
            }
          } else if (sortIndexChanged && dryRun) {
            results.updatedSortIndex += 1;
          }
          results.skippedExisting += 1;
          continue;
        }

        if (!dryRun) {
          await Zotero.Annotations.saveFromJSON(attachment, annotation);
        }
        existingAnnotations.set(fingerprint, {
          annotationComment: annotation.comment || "",
          annotationPosition: annotation.position,
          annotationSortIndex: annotation.sortIndex || "",
          annotationTags: annotation.tags || [],
          annotationText: annotation.text || "",
        });
        results.created += 1;
      } catch (error) {
        results.failed.push({
          clipping_id: entry.clipping_id,
          attachment_item_id: entry.attachment_item_id,
          message: String(error),
        });
      } finally {
        completed += 1;
        if (onProgress) {
          onProgress(completed, plan.annotations.length);
        }
      }
    }

    return results;
  },

  formatWriterResults(results) {
    const lines = [
      "Import finished.",
      "",
      `Annotations in final plan: ${results.total}`,
      `Created: ${results.created}`,
      `Skipped existing: ${results.skippedExisting}`,
      `Updated comments: ${results.updatedComments}`,
      `Updated sort order: ${results.updatedSortIndex}`,
      `Recreated for sort order: ${results.recreatedForSortIndex}`,
      `Recreate blocked (missing kindle-import tag): ${results.blockedRecreateMissingTag}`,
      `Recreate declined: ${results.recreateDeclined}`,
      `Removed exact duplicates: ${results.removedDuplicates}`,
      `Failed: ${results.failed.length}`,
    ];
    if (results.failed.length) {
      lines.push("", "First failures:");
      for (const failure of results.failed.slice(0, 5)) {
        lines.push(`- ${failure.clipping_id}: ${failure.message}`);
      }
    }
    return lines.join("\n");
  },

  revealFile(path) {
    try {
      if (Zotero.File && Zotero.File.reveal) {
        Zotero.File.reveal(path);
        return;
      }
      const file = Components.classes["@mozilla.org/file/local;1"].createInstance(
        Components.interfaces.nsIFile
      );
      file.initWithPath(path);
      file.reveal();
    } catch (error) {
      this.alert("Kindle Zotero Importer", `Review file written to:\n${path}\n\n${error}`);
    }
  },

  openFile(path) {
    try {
      const file = Components.classes["@mozilla.org/file/local;1"].createInstance(
        Components.interfaces.nsIFile
      );
      file.initWithPath(path);
      if (file.exists() && file.isFile()) {
        file.launch();
        return;
      }
      this.revealFile(path);
    } catch (error) {
      Zotero.logError(error);
      this.revealFile(path);
    }
  },
};

function install(_data, _reason) {}

function uninstall(_data, _reason) {}

async function startup(data, _reason) {
  try {
    await KindleZoteroImporter.startup(data);
  } catch (error) {
    Zotero.logError(error);
  }
}

function shutdown(_data, _reason) {
  try {
    KindleZoteroImporter.shutdown();
  } catch (error) {
    Zotero.logError(error);
  }
}

function onMainWindowLoad({ window }) {
  try {
    KindleZoteroImporter.onMainWindowLoad(window);
  } catch (error) {
    Zotero.logError(error);
  }
}

function onMainWindowUnload({ window }) {
  try {
    KindleZoteroImporter.onMainWindowUnload(window);
  } catch (error) {
    Zotero.logError(error);
  }
}
