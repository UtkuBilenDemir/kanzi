# Kindle Zotero Importer

Prototype importer for turning Kindle `My Clippings.txt` entries into a JSON import plan that Zotero can later write as native annotations.

The project intentionally keeps Zotero writes out of Python. Python parses, matches, and plans. Zotero JavaScript, and eventually a Zotero plugin, will perform annotation creation through Zotero's own APIs.

## Current Milestone

Parse Kindle clippings and emit a stable JSON preview:

```sh
python -m kindle_zotero_importer parse "/path/to/My Clippings.txt" --output clippings.json
```

Index Zotero items and PDF/EPUB attachments read-only:

```sh
python -m kindle_zotero_importer index-zotero --output zotero-index.json
```

Match parsed Kindle titles to Zotero items:

```sh
python -m kindle_zotero_importer match clippings.json zotero-index.json --overrides match-overrides.json --output matches.json
```

Generate reusable manual overrides for ambiguous/unmatched titles:

```sh
python -m kindle_zotero_importer generate-overrides matches.json --output match-overrides.generated.json --pretty
```

Apply reviewed overrides:

```sh
python -m kindle_zotero_importer match clippings.json zotero-index.json --overrides match-overrides.json --output matches.json
```

Keep confirmed mappings in `match-overrides.json`. The `match-overrides.generated.json` file is only a disposable review skeleton and can be regenerated from the current `matches.json` at any time.

If a matched Zotero item has multiple usable PDF/EPUB attachments, add the selected attachment to the same override entry:

```json
{
  "clipping_title": "Example Kindle Title",
  "resolution": {
    "citation_key": "example2024",
    "attachment_key": "ABC12345"
  }
}
```

Use either `attachment_key` or `attachment_item_id`. Attachment choices are listed in `docs/mismatch-review.md` when an item is ambiguous.

For cumulative Kindle exports, rerun the whole pipeline against the latest `My Clippings.txt`. Previously confirmed overrides in `match-overrides.json` will be applied automatically to old and new clippings.

Review unresolved cases in `docs/mismatch-review.md` after each run. Prioritize:

1. `matched-title-no-attachment`: add/link the missing PDF or EPUB in Zotero.
2. `unmatched-title`: add a confirmed title mapping to `match-overrides.json`.
3. position failures: improve text/position matching or handle manually.

Regenerate the copy-friendly review report:

```sh
python -m kindle_zotero_importer review-mismatches import-plan.positioned.json matches.json --output docs/mismatch-review.md
```

Each reviewed title includes a YAML-style block with standalone keys such as `clipping_title`, `citation_key`, `zotero_item_id`, `zotero_key`, and `override_entry` for easy copying.

Generate a preliminary import plan for matched titles:

```sh
python -m kindle_zotero_importer plan clippings.json zotero-index.json matches.json --output import-plan.json --pretty
```

Position annotations and export the Zotero writer plan:

```sh
python -m kindle_zotero_importer position-epub import-plan.json --output import-plan.epub.json --pretty
python -m kindle_zotero_importer position-pdf import-plan.epub.json --output import-plan.positioned.json --pretty
python -m kindle_zotero_importer finalize import-plan.positioned.json --output import-plan.final.json --pretty
```

## Safety Rule

Do not write directly to `zotero.sqlite`. Use read-only SQLite access for indexing and Zotero's JavaScript API for writes.
