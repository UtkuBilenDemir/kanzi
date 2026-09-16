from __future__ import annotations

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
OUTPUT = DIST_DIR / "kindle-zotero-importer-canary.xpi"


def main() -> int:
    DIST_DIR.mkdir(exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    manifest = {
        "manifest_version": 2,
        "name": "Kindle Zotero Importer Canary",
        "version": "0.1.0",
        "description": "Minimal install test for Kindle Zotero Importer.",
        "homepage_url": "https://github.com/UtkuBilenDemir/kindle-zotero_importer",
        "author": "Utku Bilen Demir",
        "applications": {
            "zotero": {
                "id": "kindlezoteroimportercanary@utkubilen.de",
                "update_url": "https://github.com/UtkuBilenDemir/kindle-zotero_importer/releases/latest/download/updates-canary.json",
                "strict_min_version": "6.999",
                "strict_max_version": "9.*",
            }
        },
    }
    bootstrap = """
function install(data, reason) {}
function uninstall(data, reason) {}
async function startup(data, reason) {
  await Zotero.initializationPromise;
  Zotero.debug('Kindle Zotero Importer Canary started');
}
function shutdown(data, reason) {}
""".lstrip()

    prefs = 'pref("extensions.kindleZoteroImporterCanary.enabled", true);\n'

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in [
            ("bootstrap.js", bootstrap),
            ("manifest.json", json.dumps(manifest, indent=2) + "\n"),
            ("prefs.js", prefs),
        ]:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, content, zipfile.ZIP_DEFLATED)

    print(f"Built {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
