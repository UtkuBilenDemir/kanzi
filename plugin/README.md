# Kindle Zotero Importer Zotero Plugin

This is a hybrid Zotero plugin wrapper around the current Python importer. Zotero owns the user interface and writes native annotations through Zotero APIs; the Python project still performs parsing, matching, planning, EPUB positioning, and PDF positioning.

## Use

1. Install `kindle-zotero-importer.xpi` in Zotero through `Tools > Plugins`.
2. Open `Tools > Kindle Zotero Importer...`.
3. Select the updated Kindle `My Clippings.txt` in the manager.
4. Follow the current stage, percentage, and elapsed time in the manager.
5. Review created, existing, updated, failed, and unresolved counts when it completes.

The plugin uses `match-overrides.json` from the project directory as the persistent source of title mappings and ignored titles. Generated JSON artifacts are still written to the project directory for audit and debugging.

## Build XPI

From the repository root:

```sh
python scripts/build_plugin.py
```

The output is `dist/kindle-zotero-importer.xpi`.

The plugin manifest targets Zotero `6.999` through `10.0.*`.
