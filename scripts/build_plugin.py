from __future__ import annotations

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugin"
DIST_DIR = ROOT / "dist"
OUTPUT = DIST_DIR / "kanzi.xpi"
LEGACY_OUTPUT = DIST_DIR / "kindle-zotero-importer.xpi"


def main() -> int:
    DIST_DIR.mkdir(exist_ok=True)
    for p in [OUTPUT, LEGACY_OUTPUT]:
        if p.exists():
            p.unlink()

    manifest_path = PLUGIN_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    zotero_app = manifest.get("applications", {}).get("zotero", {})
    required_manifest_fields = [
        "manifest_version",
        "name",
        "version",
        "description",
    ]
    missing_manifest_fields = [
        field for field in required_manifest_fields if not manifest.get(field)
    ]
    missing_zotero_fields = [
        field
        for field in ["id", "strict_min_version", "strict_max_version"]
        if not zotero_app.get(field)
    ]
    missing_files = [
        str(path.relative_to(PLUGIN_DIR))
        for path in [PLUGIN_DIR / "manifest.json", PLUGIN_DIR / "bootstrap.js"]
        if not path.exists()
    ]
    if missing_manifest_fields or missing_zotero_fields or missing_files:
        problems = []
        if missing_manifest_fields:
            problems.append(f"manifest fields: {', '.join(missing_manifest_fields)}")
        if missing_zotero_fields:
            problems.append(
                f"applications.zotero fields: {', '.join(missing_zotero_fields)}"
            )
        if missing_files:
            problems.append(f"files: {', '.join(missing_files)}")
        raise SystemExit("Invalid plugin package; missing " + "; ".join(problems))

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in PLUGIN_DIR.rglob("*"):
            if path.is_file():
                archive_name = str(path.relative_to(PLUGIN_DIR))
                info = zipfile.ZipInfo(archive_name)
                info.create_system = 3
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)

    with zipfile.ZipFile(OUTPUT) as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names or "bootstrap.js" not in names:
            raise SystemExit(
                "Invalid XPI: manifest.json and bootstrap.js must be at archive root"
            )

    print(f"Built {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
