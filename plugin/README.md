# Kanzi Zotero Plugin

This is a hybrid Zotero plugin wrapper around the current Python importer. Zotero owns the user interface and writes native annotations through Zotero APIs; the Python project still performs parsing, matching, planning, EPUB positioning, and PDF positioning.

## Use

1. Install `kanzi.xpi` in Zotero through `Tools > Plugins`.
2. Open `Tools > Kanzi...`.
3. Select the updated Kindle `My Clippings.txt` in the manager.
4. Follow the current stage, percentage, and elapsed time in the manager.
5. Review created, existing, updated, failed, and unresolved counts when it completes.

The XPI contains the importer Python source. On startup it extracts that source into the Zotero profile, where it keeps private mappings and generated audit artifacts. Python 3.11 or newer must be installed on the host; PDF positioning also requires Poppler (`pdftotext`, `pdftohtml`, and `pdfinfo`) and optionally uses `qpdf` for encrypted files. The plugin uses `match-overrides.json` there as the persistent source of title mappings and ignored titles.

## Build XPI

From the repository root:

```sh
python scripts/build_plugin.py
```

The output is `dist/kanzi.xpi`.

The plugin manifest targets Zotero `6.999` through `10.0.*`.
