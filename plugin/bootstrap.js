var Kanzi = {
  id: "kindle-zotero-importer@utkubilen.de",
  menuItems: [],
  runtimeProjectDir: "",
  defaultProjectDir: "",
  defaultClippingsPath: "",
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
      [["content", "kanzi", ""]]
    );
    await Zotero.initializationPromise;
    await this.ensureRuntime();
    this.addToAllWindows();
  },

  async ensureRuntime() {
    const runtimeDir = PathUtils.join(PathUtils.profileDir, "kanzi-runtime");
    const files = [
      "plugin_runner.py",
      "src/kindle_zotero_importer/__init__.py",
      "src/kindle_zotero_importer/__main__.py",
      "src/kindle_zotero_importer/cli.py",
      "src/kindle_zotero_importer/clippings.py",
      "src/kindle_zotero_importer/epub_position.py",
      "src/kindle_zotero_importer/final_plan.py",
      "src/kindle_zotero_importer/import_plan.py",
      "src/kindle_zotero_importer/matcher.py",
      "src/kindle_zotero_importer/mismatch_review.py",
      "src/kindle_zotero_importer/overrides.py",
      "src/kindle_zotero_importer/pdf_position.py",
      "src/kindle_zotero_importer/zotero_index.py",
    ];
    await IOUtils.makeDirectory(runtimeDir, { createAncestors: true, ignoreExisting: true });
    for (const relativePath of files) {
      const destination = PathUtils.join(runtimeDir, ...relativePath.split("/"));
      await IOUtils.makeDirectory(PathUtils.parent(destination), {
        createAncestors: true,
        ignoreExisting: true,
      });
      const response = await fetch(this.rootURI + "runtime/" + relativePath);
      if (!response.ok) throw new Error(`Missing Kanzi runtime file: ${relativePath}`);
      await Zotero.File.putContentsAsync(destination, await response.text());
    }
    this.runtimeProjectDir = runtimeDir;
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
    if (doc.getElementById("kanzi-manager")) {
      return;
    }

    const popup = doc.getElementById("menu_ToolsPopup");
    if (!popup) {
      Zotero.debug("Kanzi: Tools menu not found");
      return;
    }

    const managerItem = doc.createXULElement("menuitem");
    managerItem.setAttribute("id", "kanzi-manager");
    managerItem.setAttribute("label", "Kanzi...");
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
      const value = Services.prefs.getCharPref(this.prefBranch + name);
      return value || fallback;
    } catch (_error) {
      return fallback;
    }
  },

  setPref(name, value) {
    Services.prefs.setCharPref(this.prefBranch + name, String(value));
  },

  getProjectDir() {
    return this.getPref("projectDir", this.runtimeProjectDir || this.defaultProjectDir);
  },

  getPythonPath() {
    const fallback = this.getDefaultPython();
    const value = this.getPref("pythonPath", fallback);
    // Existing Windows installs may have "python3" stored from the old
    // Unix-only default; that binary name does not exist on Windows.
    if (this.isWindows() && value === "python3") {
      return "python";
    }
    return value || fallback;
  },

  getZoteroDbPath() {
    const dataDir = Zotero.DataDirectory && Zotero.DataDirectory.dir;
    return this.getPref("zoteroDbPath", dataDir ? PathUtils.join(dataDir, "zotero.sqlite") : "");
  },

  getZoteroStorageRoot() {
    const dataDir = Zotero.DataDirectory && Zotero.DataDirectory.dir;
    return this.getPref("zoteroStorageRoot", dataDir ? PathUtils.join(dataDir, "storage") : "");
  },

  isWindows() {
    try {
      return Services.appinfo.OS === "WINNT";
    } catch (_error) {
      return false;
    }
  },

  getDefaultPython() {
    return this.isWindows() ? "python" : "python3";
  },

  getEnvironmentVariable(name) {
    try {
      return Cc["@mozilla.org/process/environment;1"]
        .getService(Ci.nsIEnvironment)
        .get(name) || "";
    } catch (_error) {
      return "";
    }
  },

  joinWindowsPath(base, ...parts) {
    if (!base) {
      return "";
    }
    return [String(base).replace(/[\\/]+$/, ""), ...parts]
      .map((part, index) => index ? String(part).replace(/^[\\/]+|[\\/]+$/g, "") : part)
      .join("\\");
  },

  getWindowsPythonCandidates(configuredPath) {
    const localAppData = this.getEnvironmentVariable("LOCALAPPDATA");
    const programFiles = this.getEnvironmentVariable("ProgramFiles");
    const programFilesX86 = this.getEnvironmentVariable("ProgramFiles(x86)");
    const userProfile = this.getEnvironmentVariable("USERPROFILE");
    const systemDrive = this.getEnvironmentVariable("SystemDrive") || "C:";
    const versions = ["314", "313", "312", "311"];
    const candidates = [configuredPath];
    for (const version of versions) {
      candidates.push(
        this.joinWindowsPath(localAppData, "Programs", "Python", `Python${version}`, "python.exe"),
        this.joinWindowsPath(programFiles, `Python${version}`, "python.exe"),
        this.joinWindowsPath(programFilesX86, `Python${version}-32`, "python.exe"),
        this.joinWindowsPath(systemDrive, `Python${version}`, "python.exe")
      );
    }
    candidates.push(
      this.joinWindowsPath(localAppData, "Python", "bin", "python.exe"),
      this.joinWindowsPath(userProfile, "scoop", "apps", "python", "current", "python.exe"),
      this.joinWindowsPath(userProfile, "miniconda3", "python.exe"),
      this.joinWindowsPath(userProfile, "anaconda3", "python.exe")
    );
    for (const directory of this.getEnvironmentVariable("PATH").split(";")) {
      const cleanDirectory = directory.trim().replace(/^"|"$/g, "");
      if (cleanDirectory) {
        candidates.push(
          this.joinWindowsPath(cleanDirectory, "python.exe"),
          this.joinWindowsPath(cleanDirectory, "python3.exe")
        );
      }
    }
    return [...new Set(candidates.filter(Boolean))];
  },

  async resolvePythonPath(configuredPath) {
    let candidates;
    if (this.isWindows()) {
      candidates = this.getWindowsPythonCandidates(configuredPath);
    } else if (Services.appinfo.OS === "Darwin") {
      candidates = [configuredPath];
      candidates.push(
        "/opt/homebrew/bin/python3",
        "/opt/homebrew/opt/python@3.14/bin/python3.14",
        "/opt/homebrew/opt/python@3.13/bin/python3.13",
        "/opt/homebrew/opt/python@3.12/bin/python3.12",
        "/opt/homebrew/opt/python@3.11/bin/python3.11",
        "/usr/local/bin/python3",
        "/usr/local/opt/python@3.14/bin/python3.14",
        "/usr/local/opt/python@3.13/bin/python3.13",
        "/usr/local/opt/python@3.12/bin/python3.12",
        "/usr/local/opt/python@3.11/bin/python3.11",
        "/usr/bin/python3"
      );
    } else {
      candidates = [configuredPath, "/usr/bin/python3", "/usr/local/bin/python3"];
    }
    for (const candidate of candidates) {
      if (!candidate || (!candidate.includes("/") && !candidate.includes("\\"))) continue;
      try {
        if (await IOUtils.exists(candidate)) return candidate;
      } catch (_error) {}
    }
    return configuredPath || this.getDefaultPython();
  },

  joinPath(...parts) {
    if (typeof PathUtils !== "undefined" && PathUtils.join) {
      return PathUtils.join(...parts);
    }
    return parts.join("/").replaceAll("//", "/");
  },

  getConfigPath() {
    return this.joinPath(this.getProjectDir(), "plugin-config.json");
  },

  artifactPath(relativePath) {
    return this.joinPath(this.getProjectDir(), ...String(relativePath).split("/"));
  },

  async openArtifact(relativePath) {
    const path = this.artifactPath(relativePath);
    try {
      await Zotero.File.getContentsAsync(path);
      this.revealFile(path);
    } catch (_error) {
      this.alert(
        "Kanzi",
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
      if (parsed.colourMap) settings.colourMap = parsed.colourMap;
      if (parsed.colorMap) settings.colourMap = parsed.colorMap;
      // also check colour-map.json for Python pipeline
      try {
        const cmapText = await Zotero.File.getContentsAsync(this.joinPath(this.getProjectDir(), "colour-map.json"));
        settings.colourMap = JSON.parse(cmapText);
      } catch (_e2) {}
    } catch (_error) {
      // The config file is optional; defaults/preferences are enough for first run.
    }
    settings.pythonPath = await this.resolvePythonPath(settings.pythonPath);
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
      progressWindow.changeHeadline("Kanzi");
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
      progressWindow.changeHeadline("Kanzi");
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

  async openManager() {
    if (this.managerWindow && !this.managerWindow.closed) {
      this.managerWindow.focus();
      return;
    }
    const settings = await this.getRuntimeSettings();
    const data = await this.loadManagerData();
    const io = { plugin: this, settings, data };
    this.managerWindow = this.getMainWindow().openDialog(
      "chrome://kanzi/content/manager.html",
      "kanzi-manager-window",
      "chrome,centerscreen,resizable",
      io
    );
  },

  async loadManagerData() {
    return {
      clippings: await this.readJsonArtifact("clippings.json"),
      matches: await this.readJsonArtifact("matches.json"),
      generatedOverrides: await this.readJsonArtifact("match-overrides.generated.json"),
      positionedPlan: await this.readJsonArtifact("import-plan.positioned.json"),
      finalPlan: await this.readJsonArtifact("import-plan.final.json"),
      summary: await this.readJsonArtifact("plugin-summary.json"),
      persistentOverrides: await this.readJsonArtifact("match-overrides.json"),
    };
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
    const clippings = await this.readJsonArtifact("clippings.json");
    const sourceCount = this.countClippingsForTitle(clippings, resolution.clipping_title);
    const clippingCount = sourceCount || resolution.clipping_count || resolution.review?.clipping_count || 0;
    const nowIso = new Date().toISOString();
    const entry = {
      clipping_title: resolution.clipping_title,
      resolution: resolution.resolution,
      review: {
        ...(resolution.review || { status: "manager" }),
        clipping_count: clippingCount,
      },
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

  countClippingsForTitle(payload, clippingTitle) {
    return (payload?.clippings || []).reduce(
      (count, clipping) => count + (clipping.title === clippingTitle ? 1 : 0),
      0
    );
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

  async discardClip(clippingId) {
    if (!clippingId) {
      throw new Error("Missing clipping id for discard");
    }
    const path = this.artifactPath("import-plan.final.json");
    const plan = JSON.parse(await Zotero.File.getContentsAsync(path));
    const discarded = new Set(plan.discarded_clipping_ids || []);
    discarded.add(clippingId);
    plan.discarded_clipping_ids = [...discarded].sort();
    // Also drop from deferred so it is never re-queued.
    if (Array.isArray(plan.deferred_clipping_ids)) {
      plan.deferred_clipping_ids = plan.deferred_clipping_ids.filter((id) => id !== clippingId);
    }
    await Zotero.File.putContentsAsync(path, JSON.stringify(plan, null, 2) + "\n");
    return true;
  },

  async saveSettingsFromManager(newSettings) {
    const toSave = {
      projectDir: newSettings.projectDir || this.getProjectDir(),
      pythonPath: newSettings.pythonPath || this.getPythonPath(),
      zoteroDbPath: newSettings.zoteroDbPath || this.getZoteroDbPath(),
      zoteroStorageRoot: newSettings.zoteroStorageRoot || this.getZoteroStorageRoot(),
    };
    if (newSettings.colourMap) {
      toSave.colourMap = newSettings.colourMap;
      // also write colour-map.json for Python pipeline (mirrors plugin-config)
      try {
        await Zotero.File.putContentsAsync(
          this.joinPath(this.getProjectDir(), "colour-map.json"),
          JSON.stringify(newSettings.colourMap, null, 2) + "\n"
        );
      } catch (_e) {}
    }
    for (const [key, value] of Object.entries(toSave)) {
      if (key === "colourMap") continue;
      this.setPref(key, value);
    }
    await Zotero.File.putContentsAsync(
      this.getConfigPath(),
      JSON.stringify(toSave, null, 2) + "\n"
    );
    return toSave;
  },

  async loadColourMap() {
    try {
      const text = await Zotero.File.getContentsAsync(this.joinPath(this.getProjectDir(), "colour-map.json"));
      return JSON.parse(text);
    } catch (_e) {}
    try {
      const text = await Zotero.File.getContentsAsync(this.getConfigPath());
      const parsed = JSON.parse(text);
      if (parsed.colourMap) return parsed.colourMap;
      if (parsed.colorMap) return parsed.colorMap;
    } catch (_e) {}
    return null;
  },

  async readJsonArtifact(relativePath) {
    try {
      return JSON.parse(await Zotero.File.getContentsAsync(this.artifactPath(relativePath)));
    } catch (_error) {
      return null;
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
      return this.filePickerResultToPath(fp.file);
    } catch (error) {
      Zotero.logError(error);
      return this.promptForPath(
        "Kanzi",
        "File picker failed. Enter the full path to My Clippings.txt:",
        this.defaultClippingsPath
      );
    }
  },

  filePickerResultToPath(file) {
    if (!file) {
      return null;
    }
    if (typeof file === "string") {
      return file;
    }
    // Mozilla FilePicker returns an nsIFile; Python needs a native string path.
    if (typeof file.path === "string" && file.path) {
      return file.path;
    }
    try {
      const str = String(file);
      if (str && str !== "[object Object]") {
        return str;
      }
    } catch (_error) {}
    return null;
  },

  async runPipeline(clippingsPath, settings, isFull = false, retryUnresolved = false) {
    const python = settings.pythonPath || this.getDefaultPython();
    const projectDir = settings.projectDir;
    const runner = this.joinPath(projectDir, "plugin_runner.py");
    const summaryOutput = this.joinPath(projectDir, "plugin-summary.json");
    const progressOutput = this.joinPath(projectDir, "plugin-progress.json");
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
    if (retryUnresolved) {
      args.push("--retry-unresolved");
    }

    let execResult = null;
    try {
      execResult = await this.exec(python, args);
    } catch (error) {
      const installHint = this.isWindows()
        ? `Install Python 3.11 or newer, fully restart Zotero, and let Kanzi detect python.exe. `
        : `Install Python 3.11 or newer and check the Python path in Kanzi Settings. `;
      throw new Error(
        `Python could not run the Kanzi pipeline (${python}): ${error && error.message ? error.message : error}. ` +
          installHint
      );
    }
    try {
      return JSON.parse(await Zotero.File.getContentsAsync(summaryOutput));
    } catch (error) {
      const detail = execResult ? ` Python output: ${JSON.stringify(execResult).slice(0, 1000)}.` : "";
      throw new Error(
        `Python pipeline did not write ${summaryOutput}.${detail} ` +
          `Python: ${python}. Runner: ${runner}. ` +
          `Make sure Python 3 is installed and reachable, then check the project directory is writable.`
      );
    }
  },

  async runManagedImport(manager) {
    const clippingsPath = await this.pickFile("Select Kindle My Clippings.txt", "*.txt");
    // NOTE: writing now happens only after the user reviews the pending
    // highlights and presses Integrate (see integratePending).
    if (!clippingsPath) {
      return;
    }
    const isFull = manager.getFullReimport ? manager.getFullReimport() : false;
    const retryUnresolved = manager.getRetryUnresolved ? manager.getRetryUnresolved() : false;
    await this.runManagedImportWithPath(manager, clippingsPath, isFull, retryUnresolved);
  },

  async runManagedImportWithPath(manager, clippingsPath, isFullOverride, retryUnresolvedOverride) {
    let previousFinalText = null;
    let previousClippingsText = null;
    let finalPlanPath = null;
    let clippingsArtifactPath = null;
    let safeLedgerWritten = false;
    try {
      clippingsPath = this.filePickerResultToPath(clippingsPath) || clippingsPath;
      if (!clippingsPath) {
        throw new Error("No clippings file selected");
      }
      const settings = await this.getRuntimeSettings();
      const progressPath = this.joinPath(settings.projectDir, "plugin-progress.json");
      // Determine full vs incremental from explicit arg or manager checkbox
      const isFull = typeof isFullOverride === "boolean" ? isFullOverride : (manager.getFullReimport ? manager.getFullReimport() : false);
      const retryUnresolved = typeof retryUnresolvedOverride === "boolean"
        ? retryUnresolvedOverride
        : (manager.getRetryUnresolved ? manager.getRetryUnresolved() : false);
      manager.beginRun(clippingsPath);
      finalPlanPath = this.joinPath(settings.projectDir, "import-plan.final.json");
      clippingsArtifactPath = this.joinPath(settings.projectDir, "clippings.json");
      let previousFinalPlan = null;
      try {
        previousFinalText = await Zotero.File.getContentsAsync(finalPlanPath);
        previousFinalPlan = JSON.parse(previousFinalText);
      } catch (_backupError) {}
      try {
        previousClippingsText = await Zotero.File.getContentsAsync(clippingsArtifactPath);
      } catch (_backupError) {}
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
        summary = await this.runPipeline(clippingsPath, settings, isFull, retryUnresolved);
      } finally {
        polling = false;
        await pollPromise;
      }

      const finalPlan = JSON.parse(
        await Zotero.File.getContentsAsync(summary.outputs.final_plan)
      );
      const generatedDeltaIds = (finalPlan.annotations || []).map((a) => a.clipping_id);
      // The pipeline writes generated artifacts before Zotero review. Replace
      // its final ledger immediately so any later UI/preflight failure remains
      // retryable rather than recording annotations that were never applied.
      const initialDeferredPlan = this.deferPendingPlan(
        previousFinalPlan,
        finalPlan,
        generatedDeltaIds
      );
      await Zotero.File.putContentsAsync(
        summary.outputs.final_plan,
        JSON.stringify(initialDeferredPlan, null, 2) + "\n"
      );
      safeLedgerWritten = true;
      manager.updateProgress(90, "Preparing review", "Comparing the plan with Zotero");
      const reviewModel = await this.buildReviewModel(finalPlan, previousFinalPlan);
      if (!reviewModel.operation_count && !reviewModel.warnings.length) {
        await Zotero.File.putContentsAsync(
          summary.outputs.final_plan,
          JSON.stringify(finalPlan, null, 2) + "\n"
        );
        const emptyResults = this.emptyWriterResults(0);
        emptyResults.noChanges = true;
        const emptyData = await this.loadManagerData();
        await manager.completeRun(summary, emptyResults, emptyData);
        return;
      }
      // Pause before writing: let the user review and select what to integrate.
      const fullDeltaIds = (reviewModel.annotations || []).map((a) => a.clipping_id);
      // The pipeline has already written its generated history. Replace it with
      // a safe ledger until Integrate is pressed, including if the window closes.
      const deferredPlan = this.deferPendingPlan(previousFinalPlan, finalPlan, fullDeltaIds);
      await Zotero.File.putContentsAsync(
        summary.outputs.final_plan,
        JSON.stringify(deferredPlan, null, 2) + "\n"
      );
      this._pending = {
        summary,
        finalPlan,
        finalPlanPath: summary.outputs.final_plan,
        fullDeltaIds,
        previousFinalPlan,
        reviewModel,
      };
      manager.updateProgress(
        90,
        "Review ready",
        `${reviewModel.operation_count} proposed change(s) — review before applying`
      );
      manager.showPendingReview(summary, finalPlan, reviewModel);
    } catch (error) {
      if (!safeLedgerWritten) {
        try {
          if (previousFinalText !== null && finalPlanPath) {
            await Zotero.File.putContentsAsync(finalPlanPath, previousFinalText);
          } else if (finalPlanPath) {
            await Zotero.File.removeIfExists(finalPlanPath);
          }
          if (previousClippingsText !== null && clippingsArtifactPath) {
            await Zotero.File.putContentsAsync(clippingsArtifactPath, previousClippingsText);
          } else if (clippingsArtifactPath) {
            await Zotero.File.removeIfExists(clippingsArtifactPath);
          }
        } catch (restoreError) {
          Zotero.logError(restoreError);
        }
      }
      Zotero.logError(error);
      manager.failRun(String(error && error.stack ? error.stack : error));
    }
  },

  deferPendingPlan(previousPlan, generatedPlan, deferredIds) {
    const plan = previousPlan
      ? { ...previousPlan }
      : {
          ...generatedPlan,
          annotations: [],
          all_annotations: [],
          deletions: [],
          annotation_count: 0,
          delta_annotation_count: 0,
        };
    const deferred = new Set(plan.deferred_clipping_ids || []);
    for (const id of deferredIds || []) deferred.add(id);
    plan.deferred_clipping_ids = [...deferred].sort();
    const pendingCandidates = new Map();
    for (const candidate of [
      ...(plan.pending_deletion_candidates || []),
      ...(plan.deletion_candidates || []),
      ...(generatedPlan.deletion_candidates || []),
    ]) {
      if (candidate?.clipping_id) pendingCandidates.set(candidate.clipping_id, candidate);
    }
    plan.pending_deletion_candidates = [...pendingCandidates.values()];
    return plan;
  },

  // Pure helper (tested): narrow a pipeline plan to the user's selection.
  filterPlanForSelection(
    finalPlan,
    fullDeltaIds,
    selectedIds,
    previousPlan = null,
    selectedDeletionIds = null,
    selectedOperationIDs = null
  ) {
    const selected = new Set(selectedIds || []);
    const selectedOperations = new Set(selectedOperationIDs || []);
    const unselected = new Set(
      (fullDeltaIds || []).filter((id) => !selected.has(id))
    );
    const plan = { ...finalPlan };
    plan.annotations = (finalPlan.annotations || [])
      .filter((a) => selected.has(a.clipping_id))
      .map((entry) => {
        if (
          !selectedOperationIDs ||
          selectedOperations.has(`comment-link:${entry.clipping_id}`)
        ) {
          return entry;
        }
        return {
          ...entry,
          annotation: {
            ...(entry.annotation || {}),
            comment: this.commentWithoutRelationLinks(entry),
          },
        };
      });
    const selectedDeletions = selectedDeletionIds
      ? new Set(selectedDeletionIds)
      : new Set((finalPlan.deletion_candidates || []).map((entry) => entry.clipping_id));
    plan.deletion_candidates = (finalPlan.deletion_candidates || []).filter((candidate) =>
      selectedDeletions.has(candidate.clipping_id) &&
      !candidate.blocked &&
      (!candidate.replacement_clipping_id || selected.has(candidate.replacement_clipping_id))
    );
    plan.deletions = Array.isArray(finalPlan.deletion_candidates)
      ? plan.deletion_candidates.map((candidate) => candidate.clipping_id)
      : (finalPlan.deletions || []).filter((clippingID) => selectedDeletions.has(clippingID));
    const activeDeletionIDs = new Set(
      plan.deletion_candidates.map((candidate) => candidate.clipping_id)
    );
    plan.pending_deletion_candidates = (finalPlan.deletion_candidates || []).filter(
      (candidate) => !activeDeletionIDs.has(candidate.clipping_id)
    );
    const relationEntries = new Set();
    if (selectedOperationIDs) {
      for (const entry of finalPlan.all_annotations || []) {
        if (selectedOperations.has(`comment-link:${entry.clipping_id}`)) {
          relationEntries.add(entry.clipping_id);
          continue;
        }
        if ((entry.related_items || []).some((target) =>
          selectedOperations.has(this.relationOperationID(entry.parent_item_id, target.item_id))
        )) {
          relationEntries.add(entry.clipping_id);
        }
      }
    }
    if (unselected.size && Array.isArray(finalPlan.all_annotations)) {
      plan.all_annotations = finalPlan.all_annotations.filter(
        (a) => !unselected.has(a.clipping_id) || relationEntries.has(a.clipping_id)
      );
      const present = new Set(plan.all_annotations.map((a) => a.clipping_id));
      for (const annotation of previousPlan?.all_annotations || previousPlan?.annotations || []) {
        if (unselected.has(annotation.clipping_id) && !present.has(annotation.clipping_id)) {
          plan.all_annotations.push(annotation);
          present.add(annotation.clipping_id);
        }
      }
    }
    const deferred = new Set(previousPlan?.deferred_clipping_ids || []);
    for (const id of selected) deferred.delete(id);
    for (const id of unselected) deferred.add(id);
    plan.deferred_clipping_ids = [...deferred].sort();
    plan.reconciliation_excluded_ids = [...unselected].sort();
    plan.delta_annotation_count = plan.annotations.length;
    if (Array.isArray(plan.all_annotations)) {
      plan.annotation_count = plan.all_annotations.length;
    }
    return plan;
  },

  async integratePending(manager, selection) {
    const pending = this._pending;
    if (!pending) {
      throw new Error("No pending review to integrate");
    }
    try {
      const selectedIds = Array.isArray(selection)
        ? selection
        : (selection?.clippingIds || []);
      const selectedDeletionIds = Array.isArray(selection)
        ? null
        : (selection?.deletionIds || []);
      const approvedOperationIDs = Array.isArray(selection)
        ? selectedIds.map((id) => `annotation:${id}`)
        : (selection?.operationIds || []);
      const plan = this.filterPlanForSelection(
        pending.finalPlan,
        pending.fullDeltaIds,
        selectedIds,
        pending.previousFinalPlan,
        selectedDeletionIds,
        approvedOperationIDs
      );
      manager.updateProgress(96, "Applying changes", "Saving the approved review in Zotero");
      const results = await this.writeAnnotations(plan, false, (completed, total) => {
        const percent = total ? 96 + Math.floor((completed / total) * 4) : 100;
        manager.updateProgress(percent, "Writing annotations", `${completed} of ${total} checked`);
      }, approvedOperationIDs);
      await this.reconcileWriterState(
        pending.finalPlanPath,
        plan,
        results,
        pending.previousFinalPlan
      );
      this._pending = null;
      const data = await this.loadManagerData();
      await manager.completeRun(pending.summary, results, data);
    } catch (error) {
      Zotero.logError(error);
      manager.failRun(String(error && error.stack ? error.stack : error));
    }
  },

  async cancelPendingReview(manager) {
    // The deferred ledger was written before the review appeared, so closing
    // or cancelling never records pending highlights as integrated.
    this._pending = null;
    manager.hidePendingReview();
    manager.cancelRun("Review cancelled — nothing was written. Run again when ready.");
    try {
      const data = await this.loadManagerData();
      manager.data = data;
      manager.rows = manager.conflictRows();
      manager.refreshRows(true);
      manager.refreshTitleOverview();
      manager.refreshIntegrated(true);
      manager.refreshMappings(true);
    } catch (_reloadError) {}
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
      "Kanzi",
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
        const cleaned = this.stripColourCode(part);
        if (!cleaned) continue;
        const key = cleaned.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        merged.push(cleaned);
      }
    }
    return merged.join("\n\n");
  },

  stripColourCode(value) {
    return String(value || "")
      .replace(/^\s*\[(?:y|yellow|o|orange|r|red|e|grey|gray|g|green|b|blue|bl|p|purple|m|magenta|pink)\]\s*/i, "")
      .trim();
  },

  normalizeAnnotationText(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFKC")
      .replace(/-\s*\n\s*/g, "")
      .replace(/[^\p{L}\p{N}\s]+/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
  },

  annotationPositionAnchor(annotation) {
    const raw = annotation.annotationPosition || annotation.position;
    let position = raw;
    if (typeof raw === "string") {
      try { position = JSON.parse(raw); } catch (_error) { return raw; }
    }
    if (!position || typeof position !== "object") return "";
    if (position.type === "FragmentSelector" && position.value) {
      const value = String(position.value);
      const finalComma = value.lastIndexOf(",");
      return `epub:${finalComma > 0 ? value.slice(0, finalComma) : value}`;
    }
    if (Number.isInteger(position.pageIndex) && Array.isArray(position.rects) && position.rects.length) {
      const rect = position.rects[0] || [];
      const x = Number(rect[0]);
      const y = Number(rect[1]);
      return `pdf:${position.pageIndex}:${x.toFixed(1)}:${y.toFixed(1)}`;
    }
    return this.normalizePosition(position);
  },

  areImportedDuplicates(left, right) {
    const leftAnchor = this.annotationPositionAnchor(left);
    const rightAnchor = this.annotationPositionAnchor(right);
    if (!leftAnchor || leftAnchor !== rightAnchor) return false;
    const leftPosition = this.normalizePosition(left.annotationPosition || left.position);
    const rightPosition = this.normalizePosition(right.annotationPosition || right.position);
    if (leftPosition && leftPosition === rightPosition) return true;
    const leftText = this.normalizeAnnotationText(left.annotationText || left.text);
    const rightText = this.normalizeAnnotationText(right.annotationText || right.text);
    if (!leftText || !rightText) return false;
    if (leftText === rightText) return true;
    const shorter = leftText.length < rightText.length ? leftText : rightText;
    const longer = shorter === leftText ? rightText : leftText;
    return shorter.length >= 20 && longer.startsWith(shorter);
  },

  zoteroItemDescription(itemID, fallback = {}) {
    const item = itemID ? Zotero.Items.get(itemID) : null;
    let title = fallback.title || "Untitled Zotero item";
    if (item) {
      try { title = item.getField ? item.getField("title") || title : item.title || title; } catch (_error) {}
    }
    const libraryID = item?.libraryID ?? fallback.library_id ?? null;
    let libraryName = libraryID ? `Library ${libraryID}` : "Unknown library";
    try {
      const library = libraryID && Zotero.Libraries?.get ? Zotero.Libraries.get(libraryID) : null;
      if (library) {
        libraryName = library.libraryType === "user" || library.libraryID === Zotero.Libraries.userLibraryID
          ? "My Library"
          : library.name || libraryName;
      }
    } catch (_error) {}
    const citationKey = fallback.citation_key || "";
    return {
      itemID: item?.id || itemID || null,
      key: item?.key || fallback.key || "",
      title,
      libraryID,
      libraryName,
      citationKey,
      label: `${title}${citationKey ? ` (@${citationKey})` : ""} · ${libraryName}`,
    };
  },

  findMatchingAnnotation(entry, annotations) {
    const planned = entry.annotation || {};
    const fingerprint = this.annotationFingerprint(planned);
    const matches = (annotations || []).filter((candidate) =>
      this.hasKindleImportTag(candidate) &&
      (this.existingAnnotationFingerprint(candidate) === fingerprint ||
        this.areImportedDuplicates(candidate, planned))
    );
    return matches[0] || null;
  },

  annotationChanges(entry, existingAnnotation) {
    if (!existingAnnotation) return ["annotation"];
    const annotation = entry.annotation || {};
    const changes = [];
    const mergedComment = this.commentForExistingAnnotation(
      existingAnnotation,
      annotation.comment,
      entry.previous_imported_comment
    );
    if (String(existingAnnotation.annotationComment || "") !== mergedComment) changes.push("comment");
    const existingTags = new Set(this.existingTags(existingAnnotation));
    if ((annotation.tags || []).some((tag) => !existingTags.has(tag.name || tag.tag))) changes.push("tags");
    const existingColour = existingAnnotation.annotationColor || existingAnnotation.color || "";
    if (annotation.color && existingColour.toLowerCase() !== annotation.color.toLowerCase()) changes.push("colour");
    if (annotation.sortIndex && this.existingSortIndex(existingAnnotation) !== annotation.sortIndex) changes.push("sort order");
    return changes;
  },

  annotationObjectID(annotation) {
    return String(annotation?.id || annotation?.key || this.existingAnnotationFingerprint(annotation));
  },

  relationOperationID(sourceID, targetID) {
    return `relation:${[Number(sourceID), Number(targetID)].sort((a, b) => a - b).join(":")}`;
  },

  relationCommentBlock(entry) {
    const targets = entry?.related_items || [];
    return targets.length
      ? "Related: " + targets.map(
        (target) => `@${target.citation_key} ${target.link || ""}`.trim()
      ).join(" · ")
      : "";
  },

  commentWithoutRelationLinks(entry) {
    const comment = String(entry?.annotation?.comment || "");
    const block = this.relationCommentBlock(entry);
    return block ? comment.replace(block, "").replace(/\n{3,}/g, "\n\n").trim() : comment;
  },

  planMaintenanceOperations(annotations) {
    const operations = [];
    const byAttachment = new Map();
    for (const annotation of annotations || []) {
      const parentID = annotation.parentItemID || annotation.parentID;
      if (!byAttachment.has(parentID)) byAttachment.set(parentID, []);
      byAttachment.get(parentID).push(annotation);
    }
    for (const group of byAttachment.values()) {
      group.sort((a, b) =>
        this.normalizeAnnotationText(b.annotationText).length -
        this.normalizeAnnotationText(a.annotationText).length
      );
      const kept = [];
      for (const annotation of group) {
        const objectID = this.annotationObjectID(annotation);
        const canonicalComment = this.mergeComments(annotation.annotationComment, "");
        if (String(annotation.annotationComment || "") !== canonicalComment) {
          operations.push({
            operation_id: `maintenance:comment:${objectID}`,
            kind: "maintenance",
            action: "Normalize imported comment",
            text: annotation.annotationText || "",
            parent_item_id: annotation.parentItemID || annotation.parentID,
          });
        }
        const duplicateOf = kept.find((candidate) => this.areImportedDuplicates(candidate, annotation));
        if (!duplicateOf) {
          kept.push(annotation);
          continue;
        }
        operations.push({
          operation_id: `maintenance:duplicate:${objectID}`,
          kind: "maintenance",
          action: "Merge duplicate Kanzi annotation",
          text: annotation.annotationText || "",
          parent_item_id: annotation.parentItemID || annotation.parentID,
        });
      }
    }
    return operations;
  },

  async buildReviewModel(finalPlan, previousPlan = null) {
    const model = {
      annotations: [],
      deletions: [],
      maintenance: [],
      relations: [],
      commentLinks: [],
      warnings: [],
    };
    const currentAnnotationIDs = new Set(
      (finalPlan.annotations || []).map((entry) => entry.clipping_id)
    );
    for (const entry of finalPlan.annotations || []) {
      const reviewEntry = {
        ...entry,
        annotation: {
          ...(entry.annotation || {}),
          comment: this.commentWithoutRelationLinks(entry),
        },
      };
      const attachment = Zotero.Items.get(entry.attachment_item_id);
      const existing = attachment
        ? this.findMatchingAnnotation(reviewEntry, attachment.getAnnotations ? attachment.getAnnotations() : [])
        : null;
      const changes = existing ? this.annotationChanges(reviewEntry, existing) : ["annotation"];
      if (existing && !changes.length) continue;
      model.annotations.push({
        operation_id: `annotation:${entry.clipping_id}`,
        kind: existing ? "update" : "add",
        clipping_id: entry.clipping_id,
        clipping_title: entry.clipping_title,
        text: entry.annotation?.text || "",
        page: entry.annotation?.pageLabel || "",
        color: entry.annotation?.color || "#ffd400",
        changes,
        destination: this.zoteroItemDescription(entry.parent_item_id, {
          title: entry.parent_title,
          key: entry.parent_key,
          citation_key: entry.citation_key,
          library_id: entry.library_id,
        }),
      });
    }

    const previousByID = new Map(
      (previousPlan?.all_annotations || previousPlan?.annotations || []).map(
        (entry) => [entry.clipping_id, entry]
      )
    );
    for (const candidate of finalPlan.deletion_candidates || (finalPlan.deletions || []).map(
      (clippingID) => ({ clipping_id: clippingID, candidate_id: `delete:${clippingID}`, reason: "source-removed" })
    )) {
      const previous = previousByID.get(candidate.clipping_id) || {};
      model.deletions.push({
        ...candidate,
        operation_id: candidate.candidate_id || `delete:${candidate.clipping_id}`,
        kind: "delete",
        text: candidate.text || previous.annotation?.text || "",
        clipping_title: candidate.clipping_title || previous.clipping_title || "",
        destination: this.zoteroItemDescription(candidate.parent_item_id || previous.parent_item_id, {
          title: previous.parent_title,
          key: previous.parent_key,
          citation_key: candidate.citation_key || previous.citation_key,
          library_id: previous.library_id,
        }),
      });
    }

    const imported = await this.collectImportedAnnotations();
    model.maintenance = this.planMaintenanceOperations(imported);
    const relationEntries = finalPlan.all_annotations || finalPlan.annotations || [];
    const seenWarnings = new Set();
    for (const entry of relationEntries) {
      for (const citationKey of entry.ambiguous_citekeys || []) {
        const warningID = `${entry.clipping_id}:${citationKey}`;
        if (seenWarnings.has(warningID)) continue;
        seenWarnings.add(warningID);
        model.warnings.push({
          kind: "warning",
          action: `Ambiguous @${citationKey} reference`,
          text: "More than one Zotero item in the source library has this citation key, so Kanzi did not create a link or relation.",
          clipping_id: entry.clipping_id,
          destination: this.zoteroItemDescription(entry.parent_item_id, {
            title: entry.parent_title,
            key: entry.parent_key,
            citation_key: entry.citation_key,
            library_id: entry.library_id,
          }),
        });
      }
    }
    const seenRelations = new Set();
    for (const entry of relationEntries) {
      for (const targetInfo of entry.related_items || []) {
        const source = Zotero.Items.get(entry.parent_item_id);
        const target = Zotero.Items.get(targetInfo.item_id);
        if (!source || !target || source.id === target.id) continue;
        const operationID = this.relationOperationID(source.id, target.id);
        if (source.libraryID === target.libraryID && !seenRelations.has(operationID)) {
          let exists = false;
          try {
            exists = (source.relatedItems || []).includes(target.key) &&
              (target.relatedItems || []).includes(source.key);
          } catch (_error) {}
          if (!exists) {
            model.relations.push({
              operation_id: operationID,
              kind: "relation",
              action: "Add bidirectional Zotero relation",
              source: this.zoteroItemDescription(source.id, { citation_key: entry.citation_key }),
              target: this.zoteroItemDescription(target.id, targetInfo),
            });
          }
          seenRelations.add(operationID);
        }
      }
      const block = this.relationCommentBlock(entry);
      if (!block || !entry.clipping_id || !entry.attachment_item_id) continue;
      const sourceItem = Zotero.Items.get(entry.parent_item_id);
      const crossLibrary = (entry.related_items || []).some((targetInfo) => {
        const targetItem = Zotero.Items.get(targetInfo.item_id);
        return sourceItem && targetItem && sourceItem.libraryID !== targetItem.libraryID;
      });
      const attachment = Zotero.Items.get(entry.attachment_item_id);
      const tag = `kindle-id:${entry.clipping_id}`;
      const existing = (attachment?.getAnnotations ? attachment.getAnnotations() : []).find(
        (annotation) => this.existingTags(annotation).includes(tag)
      );
      const current = currentAnnotationIDs.has(entry.clipping_id);
      if ((current && !existing) || (existing && !String(existing.annotationComment || "").includes(block))) {
        model.commentLinks.push({
          operation_id: `comment-link:${entry.clipping_id}`,
          kind: "comment-link",
          action: crossLibrary
            ? "Add clickable link (native Zotero relation is unavailable across libraries)"
            : "Append clickable citekey link",
          clipping_id: entry.clipping_id,
          depends_on_clipping_id: current && !existing ? entry.clipping_id : null,
          text: entry.annotation?.text || "",
          block,
          destination: this.zoteroItemDescription(entry.parent_item_id, {
            title: entry.parent_title,
            key: entry.parent_key,
            citation_key: entry.citation_key,
            library_id: entry.library_id,
          }),
        });
      }
    }
    model.operation_count = model.annotations.length + model.deletions.length +
      model.maintenance.length + model.relations.length + model.commentLinks.length;
    return model;
  },

  async collectImportedAnnotations() {
    const annotations = [];
    let allItems = [];
    if (Zotero.DB && Zotero.DB.columnQueryAsync) {
      const ids = await Zotero.DB.columnQueryAsync("SELECT itemID FROM itemAnnotations");
      allItems = Zotero.Items.getAsync ? await Zotero.Items.getAsync(ids) : Zotero.Items.get(ids);
    } else if (Zotero.Items.getAll) {
      allItems = await Zotero.Items.getAll();
    }
    for (const item of allItems || []) {
      if (!item || !item.isAnnotation || !item.isAnnotation()) continue;
      if (this.hasKindleImportTag(item)) annotations.push(item);
    }
    return annotations;
  },

  async maintainImportedAnnotations(annotations, dryRun, results, approvedOperationIDs = null) {
    if (!results.maintenanceDeletedIds) results.maintenanceDeletedIds = [];
    const approved = approvedOperationIDs ? new Set(approvedOperationIDs) : null;
    const isApproved = (operationID) => !approved || approved.has(operationID);
    const byAttachment = new Map();
    for (const annotation of annotations) {
      if (!this.hasKindleImportTag(annotation)) continue;
      const parentID = annotation.parentItemID || annotation.parentID;
      if (!byAttachment.has(parentID)) byAttachment.set(parentID, []);
      byAttachment.get(parentID).push(annotation);
    }

    for (const group of byAttachment.values()) {
      group.sort((a, b) =>
        this.normalizeAnnotationText(b.annotationText).length -
        this.normalizeAnnotationText(a.annotationText).length
      );
      const kept = [];
      for (const annotation of group) {
        const objectID = this.annotationObjectID(annotation);
        const canonicalComment = this.mergeComments(annotation.annotationComment, "");
        const normalizeID = `maintenance:comment:${objectID}`;
        if (
          String(annotation.annotationComment || "") !== canonicalComment &&
          isApproved(normalizeID)
        ) {
          results.updatedComments += 1;
          if (!dryRun) {
            annotation.annotationComment = canonicalComment;
            await this.saveExistingAnnotation(annotation);
          }
        }

        const duplicateOf = kept.find((candidate) => this.areImportedDuplicates(candidate, annotation));
        if (!duplicateOf) {
          kept.push(annotation);
          continue;
        }
        const duplicateID = `maintenance:duplicate:${objectID}`;
        if (!isApproved(duplicateID)) {
          kept.push(annotation);
          continue;
        }
        const mergedComment = this.mergeComments(duplicateOf.annotationComment, annotation.annotationComment);
        if (duplicateOf.annotationComment !== mergedComment) {
          results.updatedComments += 1;
          if (!dryRun) {
            duplicateOf.annotationComment = mergedComment;
            await this.saveExistingAnnotation(duplicateOf);
          }
        }
        if (!dryRun) await annotation.eraseTx();
        const keptClippingIds = new Set(
          this.existingTags(duplicateOf)
            .filter((tag) => tag.startsWith("kindle-id:"))
            .map((tag) => tag.slice("kindle-id:".length))
        );
        for (const tag of this.existingTags(annotation)) {
          const clippingID = tag.startsWith("kindle-id:")
            ? tag.slice("kindle-id:".length)
            : "";
          if (clippingID && !keptClippingIds.has(clippingID)) {
            results.maintenanceDeletedIds.push(clippingID);
          }
        }
        results.removedDuplicates += 1;
      }
    }
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

  commentForExistingAnnotation(annotation, newComment, previousImportedComment) {
    if (!this.hasKindleImportTag(annotation) || previousImportedComment === undefined) {
      return this.mergeComments(annotation.annotationComment, newComment);
    }
    const previousParts = new Set(
      String(previousImportedComment || "")
        .split(/\n\s*\n/)
        .map((part) => this.stripColourCode(part).toLowerCase())
        .filter(Boolean)
    );
    const manualParts = String(annotation.annotationComment || "")
      .split(/\n\s*\n/)
      .filter((part) => !previousParts.has(this.stripColourCode(part).toLowerCase()))
      .join("\n\n");
    return this.mergeComments(manualParts, newComment);
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
      "Kanzi: Recreate Annotation?",
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

  async saveRelatedItem(item) {
    const options = { skipDateModifiedUpdate: true };
    if (item.save) {
      await item.save(options);
      return;
    }
    if (item.saveTx) {
      await item.saveTx(options);
      return;
    }
    throw new Error("Related item cannot be saved by this Zotero build");
  },

  async addRelatedItemRelations(entries, dryRun, results, approvedOperationIDs = null) {
    const approved = approvedOperationIDs ? new Set(approvedOperationIDs) : null;
    const pairs = new Map();
    for (const entry of entries || []) {
      for (const target of entry.related_items || []) {
        const sourceID = Number(entry.parent_item_id);
        const targetID = Number(target.item_id);
        if (!sourceID || !targetID || sourceID === targetID) continue;
        const pairKey = [sourceID, targetID].sort((a, b) => a - b).join(":");
        if (!pairs.has(pairKey)) {
          pairs.set(pairKey, {
            sourceID,
            targetID,
            citationKey: target.citation_key || "",
            operationID: `relation:${pairKey}`,
          });
        }
      }
    }

    for (const pair of pairs.values()) {
      try {
        if (approved && !approved.has(pair.operationID)) continue;
        const source = Zotero.Items.get(pair.sourceID);
        const target = Zotero.Items.get(pair.targetID);
        if (!source || !target) {
          throw new Error(`Related item pair not found: ${pair.sourceID} -> ${pair.targetID}`);
        }
        if (source.libraryID !== target.libraryID) {
          results.relationsUnavailable += 1;
          continue;
        }
        if (dryRun) {
          results.relationsPlanned += 1;
          continue;
        }
        if (!source.addRelatedItem || !target.addRelatedItem) {
          throw new Error("This Zotero build does not support addRelatedItem()");
        }

        let changed = false;
        const addBothDirections = async () => {
          const sourceChanged = source.addRelatedItem(target);
          const targetChanged = target.addRelatedItem(source);
          if (sourceChanged) await this.saveRelatedItem(source);
          if (targetChanged) await this.saveRelatedItem(target);
          changed = sourceChanged || targetChanged;
        };
        if (Zotero.DB?.executeTransaction) {
          await Zotero.DB.executeTransaction(addBothDirections);
        } else {
          await addBothDirections();
        }
        if (changed) results.relationsAdded += 1;
        else results.relationsSkipped += 1;
      } catch (error) {
        Zotero.logError(error);
        results.relationFailures.push({
          parent_item_id: pair.sourceID,
          related_item_id: pair.targetID,
          citation_key: pair.citationKey,
          message: String(error),
        });
      }
    }
  },

  async backfillRelationLinks(entries, dryRun, results, approvedOperationIDs = null) {
    // Appends missing `Related: @key <link>` blocks to pre-existing
    // annotations. Cross-library targets can never become Related items,
    // so the comment link is the only visible connection for them.
    const approved = approvedOperationIDs ? new Set(approvedOperationIDs) : null;
    for (const entry of entries || []) {
      const targets = entry.related_items || [];
      if (!targets.length || !entry.clipping_id || !entry.attachment_item_id) continue;
      const operationID = `comment-link:${entry.clipping_id}`;
      if (approved && !approved.has(operationID)) continue;
      const block = this.relationCommentBlock(entry);
      try {
        const attachment = Zotero.Items.get(entry.attachment_item_id);
        if (!attachment) {
          throw new Error(`Attachment not found: ${entry.attachment_item_id}`);
        }
        const annotations = attachment.getAnnotations ? attachment.getAnnotations() : [];
        const tag = `kindle-id:${entry.clipping_id}`;
        const existing = (annotations || []).find((annotation) =>
          this.existingTags(annotation).includes(tag)
        );
        if (!existing) continue;
        const comment = String(existing.annotationComment || "");
        if (comment.includes(block)) continue;
        if (dryRun) {
          results.commentLinksPlanned += 1;
          continue;
        }
        existing.annotationComment = comment ? `${comment}\n\n${block}` : block;
        await this.saveExistingAnnotation(existing);
        results.commentLinksAdded += 1;
      } catch (error) {
        Zotero.logError(error);
        results.relationFailures.push({
          parent_item_id: entry.parent_item_id,
          related_item_id: (targets[0] || {}).item_id,
          citation_key: (targets[0] || {}).citation_key,
          message: `comment link: ${error}`,
        });
      }
    }
  },

  async reconcileWriterState(path, plan, results, previousPlan = null) {
    const plannedIds = new Set((plan.annotations || []).map((entry) => entry.clipping_id));
    const failedIds = new Set(
      (results.failed || [])
        .map((failure) => failure.clipping_id)
        .filter((clippingID) => plannedIds.has(clippingID))
    );
    plan.write_failed_ids = Array.from(failedIds).sort();
    plan.delete_failed_ids = Array.from(new Set(results.failedDeletionIds || [])).sort();
    const successfulIds = new Set(
      results.successfulClippingIds || Array.from(plannedIds).filter((id) => !failedIds.has(id))
    );
    const removedIds = new Set([
      ...(results.successfulDeletionIds || []),
      ...(results.maintenanceDeletedIds || []),
    ]);
    const currentByID = new Map(
      (plan.annotations || []).map((entry) => [entry.clipping_id, entry])
    );
    const generatedByID = new Map(
      (plan.all_annotations || []).map((entry) => [entry.clipping_id, entry])
    );
    const reconciliationExcluded = new Set(plan.reconciliation_excluded_ids || []);
    const previousHistory = previousPlan?.all_annotations || previousPlan?.annotations || [];
    const historyByID = new Map(previousHistory.map((entry) => [entry.clipping_id, entry]));
    for (const [clippingID, generated] of generatedByID) {
      if (
        !plannedIds.has(clippingID) &&
        !reconciliationExcluded.has(clippingID) &&
        historyByID.has(clippingID)
      ) {
        historyByID.set(clippingID, generated);
      }
    }
    for (const clippingID of successfulIds) {
      const entry = currentByID.get(clippingID);
      if (entry) historyByID.set(clippingID, entry);
    }
    for (const clippingID of removedIds) historyByID.delete(clippingID);
    plan.annotations = (plan.annotations || []).filter((entry) =>
      successfulIds.has(entry.clipping_id)
    );
    plan.all_annotations = Array.from(historyByID.values()).sort((left, right) =>
      (left.attachment_item_id || 0) - (right.attachment_item_id || 0) ||
      String(left.annotation?.sortIndex || "").localeCompare(String(right.annotation?.sortIndex || "")) ||
      String(left.clipping_id || "").localeCompare(String(right.clipping_id || ""))
    );
    const deferred = new Set(plan.deferred_clipping_ids || []);
    for (const clippingID of successfulIds) deferred.delete(clippingID);
    for (const clippingID of failedIds) deferred.add(clippingID);
    plan.deferred_clipping_ids = Array.from(deferred).sort();
    plan.discarded_clipping_ids = Array.from(new Set([
      ...(previousPlan?.discarded_clipping_ids || []),
      ...(plan.discarded_clipping_ids || []),
    ])).sort();
    const successfulDeletionIDs = new Set(results.successfulDeletionIds || []);
    plan.deletion_candidates = (plan.deletion_candidates || []).filter(
      (candidate) => !successfulDeletionIDs.has(candidate.clipping_id)
    );
    plan.pending_deletion_candidates = (plan.pending_deletion_candidates || []).filter(
      (candidate) => !successfulDeletionIDs.has(candidate.clipping_id)
    );
    delete plan.reconciliation_excluded_ids;
    plan.delta_annotation_count = (plan.annotations || []).length;
    plan.annotation_count = plan.all_annotations.length;
    await Zotero.File.putContentsAsync(path, JSON.stringify(plan, null, 2) + "\n");
  },

  emptyWriterResults(total = 0) {
    return {
      dryRun: false,
      total,
      created: 0,
      skippedExisting: 0,
      updatedComments: 0,
      updatedSortIndex: 0,
      recreatedForSortIndex: 0,
      blockedRecreateMissingTag: 0,
      recreateDeclined: 0,
      removedDuplicates: 0,
      updated: 0,
      updatedColours: 0,
      tagsAdded: 0,
      relationsAdded: 0,
      relationsSkipped: 0,
      relationsPlanned: 0,
      relationsUnavailable: 0,
      commentLinksAdded: 0,
      commentLinksPlanned: 0,
      relationFailures: [],
      deletedForIncremental: 0,
      failedDeletionIds: [],
      successfulDeletionIds: [],
      successfulClippingIds: [],
      maintenanceDeletedIds: [],
      failed: [],
    };
  },

  async writeAnnotations(plan, dryRun, onProgress, approvedOperationIDs = null) {
    if (plan.format !== "kindle-zotero-importer.zotero-writer-plan.v1") {
      throw new Error(`Unsupported plan format: ${plan.format}`);
    }

    const results = this.emptyWriterResults(plan.annotations.length);
    results.dryRun = dryRun;
    let importedAnnotations = [];
    let maintenanceReady = false;
    try {
      importedAnnotations = await this.collectImportedAnnotations();
      await this.maintainImportedAnnotations(
        importedAnnotations,
        dryRun,
        results,
        approvedOperationIDs
      );
      if (!dryRun && results.removedDuplicates) {
        importedAnnotations = await this.collectImportedAnnotations();
      }
      maintenanceReady = true;
    } catch (error) {
      Zotero.logError(error);
      results.failed.push({ clipping_id: "maintenance", message: String(error) });
    }
    const existingByAttachment = new Map();

    const getExistingAnnotations = async (attachment) => {
      if (!existingByAttachment.has(attachment.id)) {
        const annotations = attachment.getAnnotations ? attachment.getAnnotations() : [];
        const byFingerprint = new Map();

        for (const annotation of annotations) {
          if (!this.hasKindleImportTag(annotation)) continue;
          const fingerprint = this.existingAnnotationFingerprint(annotation);
          const kept = byFingerprint.get(fingerprint);
          if (!kept) {
            byFingerprint.set(fingerprint, annotation);
            continue;
          }
          if (!kept.annotationComment && annotation.annotationComment) {
            byFingerprint.set(fingerprint, annotation);
          }
        }

        existingByAttachment.set(attachment.id, byFingerprint);
      }
      return existingByAttachment.get(attachment.id);
    };

    let completed = 0;
    const successfulEntries = new Map();
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
        const existingAnnotation = existingAnnotations.get(fingerprint) ||
          Array.from(existingAnnotations.values()).find(
            (candidate) =>
              this.existingTags(candidate).includes(`kindle-id:${entry.clipping_id}`) &&
              this.areImportedDuplicates(candidate, annotation)
          );
        if (existingAnnotation) {
          const mergedComment = this.commentForExistingAnnotation(
            existingAnnotation,
            annotation.comment,
            entry.previous_imported_comment
          );
          let changed = false;
          if (existingAnnotation.annotationComment !== mergedComment) {
            existingAnnotation.annotationComment = mergedComment;
            changed = true;
            results.updatedComments += 1;
          }

          const existingTags = new Set(this.existingTags(existingAnnotation));
          for (const tag of annotation.tags || []) {
            const name = tag.name || tag.tag;
            if (!name || existingTags.has(name) || !existingAnnotation.addTag) continue;
            existingAnnotation.addTag(name);
            existingTags.add(name);
            changed = true;
            results.tagsAdded += 1;
          }

          // colour update (British spelling in code handles both)
          const existingColour = existingAnnotation.annotationColor || existingAnnotation.color || "";
          const newColour = annotation.color || "";
          const colourChanged = Boolean(newColour) && existingColour.toLowerCase() !== newColour.toLowerCase();
          if (colourChanged) {
            existingAnnotation.annotationColor = newColour;
            // some builds use .color
            try { existingAnnotation.color = newColour; } catch (_e) {}
            changed = true;
            results.updatedColours += 1;
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
                results.failed.push({
                  clipping_id: entry.clipping_id,
                  attachment_item_id: entry.attachment_item_id,
                  message: "Sort-order update was declined; the existing annotation was preserved",
                });
                continue;
              }
              await Zotero.Annotations.saveFromJSON(attachment, annotation);
              await existingAnnotation.eraseTx();
              existingAnnotations.set(fingerprint, {
                annotationComment: annotation.comment || "",
                annotationPosition: annotation.position,
                annotationSortIndex: annotation.sortIndex || "",
                annotationTags: annotation.tags || [],
                annotationText: annotation.text || "",
              });
              results.recreatedForSortIndex += 1;
              results.updated += 1;
              successfulEntries.set(entry.clipping_id, entry);
              continue;
            }
            results.updated += 1;
          } else if (sortIndexChanged && dryRun) {
            results.updatedSortIndex += 1;
          }
          if (!changed) results.skippedExisting += 1;
          successfulEntries.set(entry.clipping_id, entry);
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
        successfulEntries.set(entry.clipping_id, entry);
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

    const currentIDs = new Set((plan.annotations || []).map((entry) => entry.clipping_id));
    const relationEntries = (plan.all_annotations || []).filter(
      (entry) => !currentIDs.has(entry.clipping_id)
    );
    relationEntries.push(...successfulEntries.values());
    await this.addRelatedItemRelations(
      relationEntries,
      dryRun,
      results,
      approvedOperationIDs
    );
    await this.backfillRelationLinks(
      relationEntries,
      dryRun,
      results,
      approvedOperationIDs
    );

    if (!dryRun && plan.deletions && plan.deletions.length) {
      const deletionIds = new Set(plan.deletions);
      const deletionCandidates = new Map(
        (plan.deletion_candidates || []).map((candidate) => [candidate.clipping_id, candidate])
      );
      const alreadyDeletedIds = new Set(results.maintenanceDeletedIds);
      if (!maintenanceReady) {
        results.failedDeletionIds.push(...deletionIds);
      } else {
        const foundDeletionIds = new Set();
        for (const ann of importedAnnotations) {
          for (const tag of this.existingTags(ann)) {
            if (!tag.startsWith("kindle-id:")) continue;
            const id = tag.slice("kindle-id:".length);
            if (!deletionIds.has(id) || alreadyDeletedIds.has(id)) break;
            foundDeletionIds.add(id);
            const candidate = deletionCandidates.get(id);
            const replacementID = candidate?.replacement_clipping_id;
            if (replacementID && !successfulEntries.has(replacementID)) {
              const replacementEntry = (plan.all_annotations || []).find(
                (entry) => entry.clipping_id === replacementID
              );
              const replacementAttachment = replacementEntry
                ? Zotero.Items.get(replacementEntry.attachment_item_id)
                : null;
              const replacementExists = (replacementAttachment?.getAnnotations
                ? replacementAttachment.getAnnotations()
                : []
              ).some((annotation) =>
                this.existingTags(annotation).includes(`kindle-id:${replacementID}`)
              );
              if (!replacementExists) {
                results.failedDeletionIds.push(id);
                results.failed.push({
                  clipping_id: id,
                  message: `Deletion blocked because replacement ${replacementID} was not applied`,
                });
                break;
              }
            }
            const replacement = successfulEntries.get(replacementID || id);
            if (replacement) {
              const sameAttachment = (ann.parentItemID || ann.parentID) === replacement.attachment_item_id;
              const sameFingerprint = this.existingAnnotationFingerprint(ann) ===
                this.annotationFingerprint(replacement.annotation);
              if (sameAttachment && sameFingerprint) {
                if (replacementID && replacementID !== id) {
                  if (ann.removeTag) {
                    ann.removeTag(`kindle-id:${id}`);
                    await this.saveExistingAnnotation(ann);
                  }
                  results.successfulDeletionIds.push(id);
                }
                break;
              }
            } else if ((plan.annotations || []).some((entry) => entry.clipping_id === id)) {
              results.failedDeletionIds.push(id);
              break;
            }
            try {
              await ann.eraseTx();
              results.deletedForIncremental += 1;
              results.successfulDeletionIds.push(id);
            } catch (error) {
              results.failedDeletionIds.push(id);
              results.failed.push({ clipping_id: id, message: `Deletion failed: ${error}` });
            }
            break;
          }
        }
        for (const id of deletionIds) {
          if (!foundDeletionIds.has(id) && !results.failedDeletionIds.includes(id)) {
            results.successfulDeletionIds.push(id);
          }
        }
      }
    }

    results.successfulClippingIds = Array.from(successfulEntries.keys());

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
      this.alert("Kanzi", `Review file written to:\n${path}\n\n${error}`);
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
    await Kanzi.startup(data);
  } catch (error) {
    Zotero.logError(error);
  }
}

function shutdown(_data, _reason) {
  try {
    Kanzi.shutdown();
  } catch (error) {
    Zotero.logError(error);
  }
}

function onMainWindowLoad({ window }) {
  try {
    Kanzi.onMainWindowLoad(window);
  } catch (error) {
    Zotero.logError(error);
  }
}

function onMainWindowUnload({ window }) {
  try {
    Kanzi.onMainWindowUnload(window);
  } catch (error) {
    Zotero.logError(error);
  }
}
