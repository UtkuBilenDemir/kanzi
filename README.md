> [!CAUTION]
> **This project has been heavily vibecoded.**

# Kanzi — `K`indle `an`notations to `Z`otero `I`mporter

Import Kindle `My Clippings.txt` highlights into Zotero as native annotations, directly inside Zotero. Once the required host tools are installed, imports run from the manager without CLI commands. Formerly *Kindle Zotero Importer*.

<p align="center">

<a href="https://github.com/sponsors/UtkuBilenDemir"><img src="https://img.shields.io/badge/please%20give%20me%20money+-111111?style=flat-square" alt="please give me money+"></a>

</p>

# Install

1. Download `kanzi.xpi` from [Releases](https://github.com/UtkuBilenDemir/kanzi/releases) (latest `0.7.0`).
2. In Zotero: `Tools` → `Plugins` → `gear` → `Install Plugin From File…` → pick the `.xpi` → restart Zotero.
3. `Tools` → `Kanzi…` to open the manager.

Works with Zotero 7 to 10. Kanzi packages its importer source, but requires Python 3.11 or newer on the host. EPUB imports need no external positioning tools. PDF imports additionally require Poppler (`pdftotext`, `pdftohtml`, `pdfinfo`); `qpdf` is recommended for encrypted PDFs. Kanzi detects standard Python installations automatically on macOS, Linux and Windows.

## Windows

Open PowerShell and install the host tools:

```powershell
winget install --id Python.Python.3.13 --exact
winget install --id oschwartz10612.Poppler --exact
winget install --id QPDF.QPDF --exact  # Optional: handles copy-protected PDFs
```

Fully quit and reopen Zotero after installation so it receives the updated `PATH`, then install `kanzi.xpi` and open `Tools` → `Kanzi…`. Kanzi checks standard per-user and system Python locations as well as `PATH`; you should not need to enter an executable path manually. EPUB-only imports require Python but not Poppler.

To verify the installation in a new PowerShell window:

```powershell
python --version
pdftotext -v
pdftohtml -v
pdfinfo -v
qpdf --version  # Optional
```

# Use

1. **Choose your file.** Click `Choose My Clippings.txt` and pick your *cumulative* `My Clippings.txt` from Kindle (`Documents/My Clippings.txt`). Keep the window open. You will see live progress.
2. **Review before writing.** New highlights are grouped by title and selected by default. Untick individual highlights or whole titles, then press `Integrate selected`. Skipped highlights return on the next run. `Cancel` and closing the manager write nothing to Zotero and do not mark pending highlights as integrated.
3. **Check Integrated.** After integration, `Integrated` shows what was imported. Columns are `Highlight Text`, `Citekey`, `Added On`, `Integrated` and `Page`. Use the filter to find anything.
4. **Fix Conflicts.** If a Kindle title did not match a Zotero item, `Conflicts` shows one expandable row for that title with up to three suggestions `citekey · title (score%)`. Expand it to inspect individual highlights and positioning problems. Click `Use` on the right candidate, enter a citation key, Zotero key or item ID under `Use Custom`, or choose `Ignore Title`. Tables can be sorted and resized.
5. **Re-import.** After you have fixed one or more titles, click `Re-import with saved overrides`. It reuses the last file, or asks for it. Only new, changed, deferred or removed highlights are processed. Already integrated ones are skipped, so the second run is fast. Use `Retry unresolved attachments and positions` for prior failures without rebuilding successful annotations. Tick `Full re-import from scratch` only if you want to rebuild everything.
6. **Mappings.** See all titles you have approved or ignored, newest first, with date. Use `Delete` to send any entry back to `Conflicts` for rematching.
7. **Settings and Artifacts.** Change `Python` or `Zotero DB` paths and `Save Settings`. Or use `Open` or `Reveal` for any generated file, such as `mismatch-review.md` or `match-overrides.json`.

Your choices are saved in `match-overrides.json` in Kanzi's private runtime folder inside your Zotero profile. Back it up or delete an entry to undo a mapping; it is excluded from Git because it contains your document titles.

# Coloured highlights

You can specify the colour of your highlights while writing the note by adding a bracket at the start.

Write `[o] This is orange` on Kindle, either as the highlight itself or as the note attached to it. Kanzi strips the bracket and imports the highlight in that colour. For example, `[o] This is orange` becomes orange highlight with text `This is orange`. If the note is `[r] important`, the highlight turns red and the note becomes `important`.

All codes are single letters and unique:

| Code | Full name | Hex | Colour |
|------|-----------|-----|--------|
| `y` | `yellow` | `#ffd400` | yellow |
| `o` | `orange` | `#ff8c00` | orange |
| `r` | `red` | `#ff6666` | red |
| `e` | `grey` / `gray` | `#8a8a8a` | grey |
| `g` | `green` | `#5fb236` | green |
| `b` | `blue` | `#2ea8e5` | blue |
| `p` | `purple` | `#a28ae5` | purple |
| `m` | `magenta` / `pink` | `#e56eee` | magenta |

Both `[o]` and `[orange]` work, case is not sensitive, and space after the bracket is ignored. Change any mapping in `Settings` → `Highlight colours` using the hex picker and preview. Use `+ Add mapping` or `Reset to defaults`. British spelling is used throughout.

# Tips

* Keep `My Clippings.txt` cumulative. Do not clear it on the Kindle. The importer remembers what is already integrated via `kindle-id:<hash>` tags, so re-imports are incremental.
* If a highlight is in the wrong place, check that the Zotero item has the correct PDF or EPUB attached, not a link. `Matched-title-no-attachment` in `Conflicts` means that.
* `Full re-import` is only needed if you changed many mappings at once or want to rebuild from scratch.
* Past highlights will recolour incrementally when you add a bracket code to them, or when you change the colour map in Settings. Otherwise use `Full re-import` to recolour everything.

# Detailed Guide

`Tools` → `Kanzi…` opens the manager.

**Summary.** Shows `clippings`, `unique titles`, `final annotations` and `conflicts`. Also `Match Statuses` and `Plan Statuses`. The run panel shows `Choose My Clippings.txt`, progress, stage and detail, and the `Full re-import` checkbox. After positioning, the pending review lets you select exactly what is written to Zotero.

**Integrated.** All annotations remembered in `import-plan.final.json`. Columns are `Kindle Title`, `Citekey`, `Highlight Text`, `Added On`, `Integrated` and `Page` with colour swatch. Filter at the top right; results are resizable and paginated.

**Conflicts.** One row per unresolved Kindle title, combining title-match and attachment/position statuses. Expand a row to inspect its highlights and positioning problems. `Candidates` shows `N suggestion(s) — top: citekey (score%)`. Each candidate has a `Use` button. Below that is `Use Custom` and `Ignore Title`. Saving shows the `Re-import` bar. Columns are sortable and resizable.

**Mappings.** Persistent `match-overrides.json`. Columns are `Kindle Title`, `Resolution`, `Status`, `Count` and `Updated`. Use `Delete` to send it back to `Conflicts`. Filterable.

**Settings.** `Project directory`, `Python`, `Zotero DB`, `Zotero storage`, annotation sharing, and `Highlight colours` as above. Sharing is off until you explicitly opt in and can be disabled here at any time. `Save Settings` writes `plugin-config.json` and `colour-map.json` for the pipeline. No restart is needed.

**Artifacts.** `Mismatch review`, `Persistent overrides`, `Generated suggestions`, `Positioned plan`, `Final writer plan` and `Plugin summary`. Each has `Open` and `Reveal`.

Incremental is default. Only new, changed or colour-changed highlights are repositioned.

# For developers / CLI

```sh
python scripts/build_plugin.py  # → dist/kanzi.xpi, including the Python runtime
python -m kindle_zotero_importer run "/path/to/My Clippings.txt" --workdir . --pretty
python -m kindle_zotero_importer run ... --full  # ignore incremental and reprocess all
```

PDF positioning uses host-installed Poppler (`pdftotext`, `pdftohtml`, `pdfinfo`) plus `qpdf` fallback. EPUB uses CFI. Zotero writes are only via `Zotero.Annotations`. It never writes `zotero.sqlite` directly.

# Releases

Stable releases are on `Releases` with `kanzi.xpi` and `updates.json` attached. Pre-releases (`beta`) are marked `Pre-release` on GitHub. Zotero auto-updates from `releases/latest/download/updates.json`.

# Support

Issues and pull requests welcome at [Issues](../../issues).

Annotation sharing is off until you explicitly opt in. If enabled, it sends a random pseudonymous installation ID, citation key and publication metadata (including DOI/ISBN when available), raw highlight text and comments, normalised/fuzzy hashes, colour, and dates to `annotation.utkubilen.de`. The collector does not receive your Zotero account identity, but free text can contain identifying information and therefore is not anonymous. Change this any time in `Manager` → `Settings`.
