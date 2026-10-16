> [!CAUTION]
> **This project has been heavily vibecoded.**

# Kanzi - `K`indle `an`notations to `Z`otero `I`mporter

<p align="center">

<a href="https://github.com/sponsors/UtkuBilenDemir"><img src="https://img.shields.io/badge/please%20give%20me%20money+-111111?style=flat-square" alt="please give me money+"></a>

</p>

Kanzi imports highlights and notes from Kindle's cumulative `My Clippings.txt` file as native annotations on PDF and EPUB attachments in Zotero.

It works with books and documents copied to a Kindle manually, not only purchases associated with an Amazon account. Imports run from Zotero after the required host tools are installed.

> [!IMPORTANT]
> Kanzi shows a complete review before changing Zotero. Preparing a review is read-only. You choose which annotation additions, updates, removals, maintenance actions, item relations, and comment links to apply.

## What Kanzi does

- Matches Kindle document titles to Zotero items.
- Finds the highlighted text in attached PDFs and EPUBs.
- Creates native Zotero annotations at the matched position.
- Imports Kindle notes and optional colour codes.
- Remembers completed work so normal imports process only changes.
- Lets you resolve uncertain title or attachment matches without a terminal.
- Turns `@citekey` references into Zotero links and same-library Related items.
- Preserves manual Zotero annotations and manual additions to imported comments.

Kanzi never writes directly to `zotero.sqlite`. All Zotero changes use Zotero's own annotation and item APIs.

## Requirements

- Zotero 7 through 10.
- Python 3.11 or newer.
- EPUB imports: no additional positioning tools.
- PDF imports: Poppler tools `pdftotext`, `pdftohtml`, and `pdfinfo`.
- Encrypted PDFs: `qpdf` is recommended as a fallback.

Kanzi detects standard Python installations on macOS, Linux, and Windows. Paths can also be set under `Kanzi -> Settings`.

## Install

1. Download `kanzi.xpi` from the [latest release](https://github.com/UtkuBilenDemir/kanzi/releases/latest) (`0.7.2`).
2. Open Zotero and select `Tools -> Plugins`.
3. Open the gear menu and choose `Install Plugin From File...`.
4. Select `kanzi.xpi`, then restart Zotero.
5. Open `Tools -> Kanzi...`.

### macOS

With Homebrew:

```sh
brew install python poppler qpdf
```

### Windows

Open PowerShell:

```powershell
winget install --id Python.Python.3.13 --exact
winget install --id oschwartz10612.Poppler --exact
winget install --id QPDF.QPDF --exact
```

Fully quit and reopen Zotero after installation so it receives the updated `PATH`. To verify the tools in a new PowerShell window:

```powershell
python --version
pdftotext -v
pdftohtml -v
pdfinfo -v
qpdf --version
```

### Debian and Ubuntu

```sh
sudo apt install python3 poppler-utils qpdf
```

## First import

Keep `My Clippings.txt` cumulative. On a connected Kindle it is normally at `Documents/My Clippings.txt`.

### 1. Prepare

Open `Tools -> Kanzi...`, choose one run mode, then select `My Clippings.txt`:

- **Update changes (recommended):** process new, changed, removed, deferred, or previously failed clippings.
- **Update changes and try unresolved again:** also retry titles, attachments, and positions that previously failed.
- **Recheck all clippings:** rebuild every plan entry while reusing existing Zotero annotations instead of duplicating them.

Kanzi reads the files and builds a preview. Zotero is not changed during this stage.

### 2. Review

The review lists every proposed mutation by category:

- Annotation additions and updates, grouped by Kindle title.
- Kanzi annotation maintenance, such as merging tagged duplicates.
- Annotation removals, including why each removal is proposed.
- Bidirectional Zotero item relations.
- Clickable citekey links for existing annotations.

Each row shows the destination Zotero item and library where available. Untick any operation you want to leave for later. A removal that depends on a replacement remains blocked until the replacement is successfully positioned and selected.

Warnings do not make changes. For example, if a citation key identifies multiple items in the same library, Kanzi reports the ambiguity instead of choosing one.

### 3. Apply

Select `Apply selected changes`. Only checked operations are written. Closing the manager or choosing `Cancel - no Zotero changes` leaves Zotero unchanged and keeps pending annotations available for a later run.

Kanzi only performs automatic maintenance on annotations tagged `kindle-import`. It does not delete or rewrite ordinary annotations created manually in Zotero.

### 4. Results

The final result is one of:

- **Completed:** all selected operations succeeded.
- **Completed with issues:** safe operations completed, but specific items need attention.
- **Failed:** the run could not be applied.

Expand `Technical details` for exact counters and failure messages. Retrying is safe.

## Resolve problems

Open `Conflicts` when a title, attachment, or text position could not be resolved.

- Expand a title to inspect its highlights and the original technical status.
- Select a suggested Zotero item with `Use`.
- Enter a citation key, Zotero key, or item ID with `Use Custom`.
- Select `Ignore Title` if the document should never be imported.
- Use `Copy` to copy unresolved highlight text for manual placement.
- Use `Discard` to suppress a clipping permanently. Discards remain suppressed in every run mode, including `Recheck all clippings`.

Saved choices live in `match-overrides.json` in Kanzi's runtime folder. The `Mappings` tab lists them and lets you delete a mapping so the title can be matched again.

## Coloured highlights

Place a colour code at the beginning of a Kindle highlight or its attached note. Kanzi strips the code before import.

`[o] This is orange` becomes an orange highlight containing `This is orange`.

| Code | Full name | Hex |
|---|---|---|
| `y` | `yellow` | `#ffd400` |
| `o` | `orange` | `#ff8c00` |
| `r` | `red` | `#ff6666` |
| `e` | `grey` or `gray` | `#8a8a8a` |
| `g` | `green` | `#5fb236` |
| `b` | `blue` | `#2ea8e5` |
| `p` | `purple` | `#a28ae5` |
| `m` | `magenta` or `pink` | `#e56eee` |

Short and full names are case-insensitive. Edit the mapping under `Settings -> Highlight colours`.

## Citekey references

A Kindle highlight or note can refer to another Zotero item with `@citekey`.

- Kanzi appends a clickable `zotero://select/...` link to the annotation comment.
- If both parent items are in the same Zotero library, Kanzi can add a bidirectional native Related relation after review.
- Zotero cannot create native relations across libraries. In that case the clickable comment link is used instead.
- If duplicate citation keys remain ambiguous after preferring the source library, Kanzi warns and creates no guessed relation.

## Important limitations

- Kindle provides clipping text, not a stable PDF or EPUB coordinate. Kanzi must find the text again in the attachment.
- Scanned and OCR-derived PDFs can be slow or fail because their extracted text differs from the Kindle text.
- PDF page labels can differ from physical PDF page indexes.
- A linked web attachment is not a local PDF or EPUB. Attach the actual file to the Zotero item.
- Cross-library native Zotero relations are not supported by Zotero.

Unresolved entries remain visible and retryable rather than being silently marked as complete.

## Data and privacy

Annotation sharing is off by default. No AI service is involved in an import.

If sharing is enabled under `Settings`, Kanzi sends a random pseudonymous installation ID, citation key and publication metadata, raw highlight text and comments, normalised and fuzzy hashes, colour, and dates to `annotation.utkubilen.de`. The collector does not receive your Zotero account identity, but free text can contain identifying information and is therefore not anonymous.

## Technical behavior

### Pipeline

1. Parse and deduplicate `My Clippings.txt`.
2. read Zotero items and attachments from a read-only SQLite connection.
3. Match Kindle titles to Zotero items, applying saved overrides.
4. Position EPUB highlights with CFI selectors.
5. Position PDF highlights with Poppler page text and rectangles, including tolerant OCR matching.
6. Build a writer plan and compare it with live Zotero state.
7. Apply only explicitly approved operations through Zotero APIs.
8. Reconcile the persistent ledger with successful writes and retryable failures.

### Safety invariants

- Preparing and reviewing are read-only with respect to Zotero.
- A no-change plan performs no Zotero save.
- A prior annotation is not removed unless its selected replacement exists or was successfully written.
- Failed writes and deletions stay retryable.
- Discard tombstones survive source disappearance and Full/Recheck runs.
- Corrupt persistent state stops the import instead of being treated as empty.
- Automatic maintenance is limited to `kindle-import` annotations.

### Runtime files

The manager's `Artifacts` tab opens or reveals generated plans. Important files include:

- `import-plan.final.json`: cumulative annotation ledger and pending writer plan.
- `import-plan.positioned.json`: positioning outcomes and technical statuses.
- `match-overrides.json`: persistent title mappings and ignored titles.
- `mismatch-review.md`: text report for unresolved entries.
- `plugin-summary.json`: latest pipeline summary.

These files are stored in Kanzi's private runtime folder inside the Zotero profile.

## Development

```sh
python scripts/build_plugin.py
python tests/run_tests.py
node tests/test_manager_logic.js
node --check plugin/bootstrap.js
```

The build produces `dist/kanzi.xpi` with the Python runtime included. The Python package requires 3.11 or newer and has no mandatory third-party Python dependencies.

For the complete release verification matrix, see [`docs/testing-0.7.2.md`](docs/testing-0.7.2.md). Release notes are in [`docs/release-0.7.2.md`](docs/release-0.7.2.md).

## Releases and support

Stable releases attach `kanzi.xpi` and `updates.json` on [GitHub Releases](https://github.com/UtkuBilenDemir/kanzi/releases). Zotero checks `releases/latest/download/updates.json` for updates.

Report problems or request features through [GitHub Issues](https://github.com/UtkuBilenDemir/kanzi/issues). Include the human-readable message, the original technical status, your operating system, Zotero version, and whether the attachment is PDF or EPUB.

Kanzi is MIT-licensed.
