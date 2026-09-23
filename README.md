
> [!CAUTION]
> **This project has been heavily vibecoded.**

# Kanzi — Kindle annotations to Zotero

Import Kindle `My Clippings.txt` highlights into Zotero as native annotations; directly inside Zotero, no terminal needed. Formerly *Kindle Zotero Importer*.

[<img src="https://img.shields.io/badge/please%20give%20me%20money+-red?style=for-the-badge" alt="please give me money+">](https://github.com/sponsors/UtkuBilenDemir)

## Install (30 seconds)

1. Download `kindle-zotero-importer.xpi` from [Releases](../../releases) (latest `0.6.11`, or `0.6.10-beta` for preview).
2. In Zotero: `Tools → Plugins → gear → Install Plugin From File…` → pick the `.xpi` → restart Zotero.
3. `Tools → Kanzi…` (or `Kindle Zotero Importer…`) to open the manager.

Works with Zotero 7–10; macOS/Windows/Linux; PDF and EPUB. Colours via bracket: `[o] orange`, `[r] red`, `[e] grey`, `[y]` yellow, etc. — all single letters unique, editable in `Settings → Highlight colours`.

## Use

1. **Choose your file**; click `Choose My Clippings.txt` and pick your *cumulative* `My Clippings.txt` from Kindle (`/Documents/My Clippings.txt`); keep the window open; you will see live progress.
2. **Check Integrated**; after the run, `Integrated` shows what was imported (`Highlight Text`; `Citekey`; `Added On`; `Integrated`; `Page`); filter to find anything.
3. **Fix Conflicts**; if a Kindle title did not match a Zotero item, `Conflicts` shows it with up to 3 suggestions `citekey · title (score%)`; click `Use` on the right one; or type any `citation key` / `Zotero key` / `Item ID` under `Use Custom`; or `Ignore Title` to skip it forever; if you map `chabot2013` for one `Simondon` variant, it will offer to apply the same mapping to the other variants with that candidate.
4. **Re-import**; after you have fixed one or more titles, click `↻ Re-import with saved overrides` (re-uses the last file; or asks for it); only new/changed highlights are re-positioned; already integrated ones are skipped, so the second run is fast; check `Full re-import from scratch` only if you want to rebuild everything.
5. **Mappings**; see all titles you have approved or ignored, newest first, with date; `Delete` any entry to send it back to `Conflicts` for re-matching.
6. **Settings / Artifacts**; change `Python`/`Zotero DB` paths and `Save Settings`; or `Open`/`Reveal` any generated file (`mismatch-review.md`; `match-overrides.json`; …).

Your choices are saved in `match-overrides.json` in the project folder; back it up, share it, or delete an entry to undo a mapping.

## Highlight colours

Start a highlight **or** its Kindle note with `[code]` to set colour — the bracket is stripped, so Zotero shows only the text.

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

All single letters are unique (`e` is grey to keep `g` for green). Both `[o]` and `[orange]` work, case-insensitive, whitespace trimmed. Example: Kindle highlight ` [o] This is orange` → orange highlight with text `This is orange`; Kindle note `[r] important` attached to a highlight → that highlight turns red, note becomes `important`. Change any mapping in `Settings → Highlight colours` (hex picker + preview, `+ Add mapping`, `Reset to defaults`) — British spelling throughout.

## Manager — User guide

`Tools → Kanzi…` opens the manager (`chrome://kanzi/content/manager.html`, Zotero 7–10).

*   **Summary** — `clippings` / `unique titles` / `final annotations` / `conflicts`; `Match Statuses` (`matched`/`ignored`/`unmatched`/`ambiguous`) and `Plan Statuses` (`positioned`/`epub-text-not-found` etc.). Run panel shows `Choose My Clippings.txt`, `progress` + `stage`/`detail`, `Full re-import` checkbox.
*   **Integrated** — last `import-plan.final.json` annotations (`Kindle Title` | `Citekey` | `Highlight Text` | `Added On` | `Integrated` | `Page` with colour swatch). Filter top-right, `400` shown, sortable/resizable.
*   **Conflicts** — unresolved titles (`Title match` / `Override suggestion` / `Attachment/position`). `Candidates / Detail` shows `N suggestion(s) — top: citekey (score%)`, each candidate has `Use` button, plus `Use Custom` (`citekey` / `Zotero key` / `ID`) and `Ignore Title`. Saving shows `Re-import` bar (`↻ Re-import with saved overrides` re-uses last file). Title-variant grouping: if you `Use` `chabot2013` for one `Simondon` variant, it offers to apply to other variants with same candidate.
*   **Mappings** — persistent `match-overrides.json` (`Kindle Title` | `Resolution` | `Status` | `Count` | `Updated` | `Delete`). `Delete` sends it back to `Conflicts`. Filterable.
*   **Settings** — `Project directory`, `Python`, `Zotero DB`, `Zotero storage`, `Share anonymized annotations` (on by default, `annotation.utkubilen.de`, private, hashed only), **Highlight colours** table as above. `Save Settings` writes `plugin-config.json` + `colour-map.json` for the pipeline (`src/kindle_zotero_importer/cli.py:12` `_load_colour_map()`), no restart. Also `Artifacts` helpers.
*   **Artifacts** — `Mismatch review` (`docs/mismatch-review.md`), `Persistent overrides`, `Generated suggestions`, `Positioned plan`, `Final writer plan`, `Plugin summary` — each `Open`/`Reveal`.

Incremental is default: only new/changed highlights + colour-changed past highlights are re-positioned; use `Full re-import` to rebuild all (e.g. after changing many mappings).

## Tips

- Keep `My Clippings.txt` cumulative (do not clear it on the Kindle); the importer remembers what is already integrated via `kindle-id:<hash>` tags, so re-imports are incremental.
- If a highlight is positioned in the wrong place, check that the Zotero item has the correct PDF/EPUB attached (not a link); `Matched-title-no-attachment` in `Conflicts` means that.
- `Full re-import` is only needed if you changed many mappings at once or want to rebuild from scratch.
- Colours: start a highlight or note with `[o]`, `[r]` red, `[e]` grey, `[y]` yellow, `[g]` green, `[b]` blue, `[p]` purple, `[m]` magenta — e.g. `[o] This is orange` → orange, bracket stripped. Full names (`[orange]`, `[red]`, `[grey]` etc.) also work. Change mappings in `Settings → Highlight colours` (British spelling).

## For developers / CLI

```sh
python scripts/build_plugin.py  # → dist/kindle-zotero-importer.xpi
python -m kindle_zotero_importer run "/path/to/My Clippings.txt" --workdir . --pretty
python -m kindle_zotero_importer run ... --full  # ignore incremental; re-process all
```

PDF positioning uses Poppler (`pdftotext`; `pdftohtml`; `pdfinfo`) + `qpdf` fallback; EPUB uses CFI. Zotero writes are only via `Zotero.Annotations`; never direct `zotero.sqlite` writes.

Anonymized sharing is **on by default** to help future development (only `citation key`; hashed highlight; `color`; `has comment` + note; `added_on`; `integrated_at`; never raw highlight text); opt out anytime in `Manager → Settings` → uncheck `Share anonymized annotations` (also `annotation.utkubilen.de`, private, no AI).

## Releases

Stable releases are on `Releases` with `kindle-zotero-importer.xpi` + `updates.json` attached. Pre-releases (`beta`) are marked `Pre-release` on GitHub. Zotero auto-updates from `releases/latest/download/updates.json`.

## Support

Issues and pull requests welcome at [Issues](../../issues).
