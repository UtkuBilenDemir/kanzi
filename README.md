# Kindle Zotero Importer

Import Kindle `My Clippings.txt` highlights into Zotero as native annotations — directly inside Zotero, no terminal needed.

The hybrid Zotero plugin (`plugin/`) owns the UI and writes annotations through Zotero's native APIs. The Python pipeline (`src/kindle_zotero_importer/`) does parsing, matching, and EPUB/PDF positioning.

## What it does now (0.6.4)

- **One Tools entry**: `Tools → Kindle Zotero Importer…` opens a manager window (`chrome://kindle-zotero-importer/content/manager.html`).
- **File picker + staged progress**: choose your cumulative `My Clippings.txt` → live stage, percent, elapsed, `plugin-progress.json` (`Reading clippings → Indexing Zotero → Matching → Building plan → Positioning EPUB → Positioning PDF → Finalizing → Saving`).
- **Incremental by default**: hashes each clipping `sha256(title|raw_detail|text)[:16]` (`src/kindle_zotero_importer/clippings.py:98`). Only new/changed `id`s (`new_ids - prev_integrated_ids`) go through expensive `pdftohtml`/`pdftotext` (`src/kindle_zotero_importer/pdf_position.py:120,197`). Already integrated `kindle-id:<id>` tags (`src/kindle_zotero_importer/final_plan.py:44`) are skipped. Check `Full re-import from scratch` to ignore incremental and re-process all 2379.
- **Integrated tab**: last `import-plan.final.json` annotations (`975` in current artifacts) with `Kindle Title | Citekey | Highlight Text | Added On | Integrated | Page`, filterable, newest `Integrated` first.
- **Conflicts tab**: unresolved title matches (`matched`/`ignored` filtered out). Each row shows `Source | Status | Count | Kindle Title | Candidates / Detail` (`N suggestion(s) — top: citekey (%)`) and an explicit `candidate-list` — each candidate `citekey · title (score%)` with its own `Use` button (`saveCandidateAt`). Free-form `or enter any citekey / Zotero key / ID` + `Use Custom` + `Ignore Title`. If you map `chabot2013` for one `simondon` variant, it offers to apply the same mapping to other variants sharing that candidate and hides them immediately.
- **Mappings tab**: persistent `match-overrides.json` (`38` entries) with `Kindle Title | Resolution | Status | Count | Date | Action`, sorted by `updated_at` newest first (`plugin/bootstrap.js:288` `created_at`/`updated_at` ISO), filterable, `Delete` per row returns title to `Conflicts` after next `Re-import`.
- **Re-import bar**: after any `Use`/`Use Custom`/`Ignore` or `Delete`, a `Re-import with saved overrides` bar appears reusing `lastClippingsPath` (`plugin/bootstrap.js:734` `runManagedImportWithPath`) or prompting for file. Explains why re-import is needed (new `citation_key` → new attachment → new `epubcfi`/`pdf rect`/`sortIndex`).
- **Settings tab**: editable `Project directory`, `Python`, `Zotero DB`, `Zotero storage` (`setting-*` ids) + `Save Settings` → `plugin/bootstrap.js:315` `saveSettingsFromManager` writes prefs + `plugin-config.json`.
- **Artifacts tab**: per-row `Open`/`Reveal` for `docs/mismatch-review.md`, `match-overrides.json`, `import-plan.*.json`, `plugin-summary.json`.
- **Theme**: black `#0a0a0a` over white `#ffffff` `iA Writer Duo` monospace, `table-layout:fixed` with draggable `div.resizer` (`plugin/manager.html:270`) and sortable `th` (`▲/▼`) for all tables, selectable text.

## Install

```sh
python scripts/build_plugin.py
# → dist/kindle-zotero-importer.xpi  (manifest 0.6.4, Zotero 6.999–10.0.*)
```

In Zotero 10: `Tools → Plugins → gear → Install Plugin From File…` → `dist/kindle-zotero-importer.xpi` → restart → `Tools → Kindle Zotero Importer…`.

`plugin/manifest.json:11` `update_url` `https://github.com/UtkuBilenDemir/kindle-zotero_importer/releases/latest/download/updates.json` enables auto-update.

## Use

1. `Tools → Kindle Zotero Importer…` → `Choose My Clippings.txt` (cumulative file).
2. Keep manager open for `Positioning … (incremental)` progress and `Result` (`created`/`already present`/`updated`/`failed`/`deletedForIncremental`).
3. `Conflicts` → pick `Use` per candidate or `Use Custom` with any `citation_key` (`deleuze1987`), 8-char `Zotero key` (`JTDWDKRH`), or numeric `item_id`; use `Ignore Title` for titles to skip.
4. `Re-import with saved overrides` (uses last file, or prompts) → re-matches/positions only the delta and writes `kindle-import` + `kindle-id:<hash>` tagged annotations.
5. `Integrated` to verify highlights (`Added On` Kindle date, `Integrated` UTC now, `Citekey` always visible), `Mappings` to review/delete established overrides.

For title variants (`gilbert-simondon…` vs `On the Mode… (Univocal)` both candidate `simondon2017a`/`chabot2013`), mapping one offers to apply to the others sharing that candidate — or map them individually; they clear from `Conflicts` immediately and after `Re-import` are `matched` in `matches.json` and absent from `match-overrides.generated.json`.

For full rebuild, check `Full re-import from scratch` in the run-panel.

## CLI (for debugging)

```sh
python -m kindle_zotero_importer run "/path/to/My Clippings.txt" --workdir . --db ~/Zotero/zotero.sqlite --storage-root ~/Zotero/storage --overrides match-overrides.json --summary-output plugin-summary.json --pretty
python -m kindle_zotero_importer run ... --full   # ignore incremental
PYTHONPATH=src python -m kindle_zotero_importer parse "/path/to/My Clippings.txt" --pretty | head
```

`--progress-output plugin-progress.json` drives the manager progress bar.

PDF positioning uses Poppler (`pdftotext`, `pdftohtml`, `pdfinfo`) plus `qpdf --decrypt` fallback; EPUB uses `epubcfi`.

## Safety Rule

Never write directly to `zotero.sqlite`. Python is read-only for indexing; writes are only via `Zotero.Annotations.saveFromJSON` / `eraseTx` in `plugin/bootstrap.js:975` `writeAnnotations`.

## Releases — including beta

GitHub Releases are built from `dist/kindle-zotero-importer.xpi`:

```sh
python scripts/build_plugin.py
# tag and push
git tag v0.6.4 && git push origin v0.6.4
# GitHub → Releases → Draft a new release → Tag v0.6.4 → Title 0.6.4 → Attach dist/kindle-zotero-importer.xpi
# Generate updates.json:
# {
#   "addons": {
#     "kindlezoteroimporter@utkubilen.de": {
#       "updates": [{
#         "version": "0.6.4",
#         "update_link": "https://github.com/UtkuBilenDemir/kindle-zotero_importer/releases/download/v0.6.4/kindle-zotero-importer.xpi",
#         "applications": {"zotero": {"strict_min_version": "6.999"}}
#       }]
#     }
#   }
# }
# upload updates.json to the same release (update_url points to /releases/latest/download/updates.json)
```

For a **beta/pre-release**: on the GitHub Release form check `Set as a pre-release` and use a tag like `v0.6.4-beta.1` with `version` `0.6.4-beta.1` in `plugin/manifest.json:4` and `updates.json`. Zotero will offer it as an update only to users on that channel; stable `v0.6.4` stays `latest`. You can also mark `This is a pre-release` without changing `update_url` — `strict_max_version` `10.0.*` already allows beta testing in Zotero 10.

## Donations

Zotero has no built-in plugin donation. Add your sponsor link to `README.md` and `plugin/manifest.json:6` `homepage_url`, and to the manager `infobox` (`plugin/manager.html:485`). Recommended: GitHub Sponsors (`https://github.com/sponsors/UtkuBilenDemir`) or Ko-fi/PayPal/OpenCollective. The `Donate` button in `Plugins` manager comes from `aboutURL` if you add `"aboutURL": "https://github.com/sponsors/…"` to `manifest.json`.

## Project layout

- `plugin/` — hybrid bootstrap plugin (`bootstrap.js`, `manager.html`, `manifest.json`, `prefs.js`)
- `src/kindle_zotero_importer/` — `clippings.py`, `zotero_index.py`, `matcher.py`, `import_plan.py`, `epub_position.py`, `pdf_position.py`, `final_plan.py`, `cli.py`
- `scripts/build_plugin.py` — reproducible XPI builder
- `match-overrides.json` — persistent title → `citation_key`/`zotero_key`/`ignore` mappings (now with `created_at`/`updated_at`, sorted newest first)
