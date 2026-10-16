# Kanzi 0.7.2

Kanzi 0.7.2 makes Zotero changes explicit and reviewable. The manager now follows a four-stage Prepare, Review, Apply, and Results workflow.

## Highlights

- Review annotation additions, updates, removals, maintenance, item relations, and comment links before applying them.
- See destination Zotero items and libraries in the review.
- Choose one clear run mode: Update changes, retry unresolved work, or recheck all clippings.
- Receive Completed, Completed with issues, or Failed results with expandable technical details.
- Read human-friendly status labels and suggested remedies while retaining the original technical status.
- Use clickable `@citekey` links and bidirectional same-library Zotero relations.
- Receive a warning instead of an arbitrary match when duplicate citation keys remain ambiguous.

## Safety changes

- Preparing a review does not mutate Zotero.
- No-change plans do not perform Zotero saves.
- Old annotations are removed only after their selected replacements exist or are successfully written.
- Deselecting or failing a replacement suppresses its dependent removal.
- Discarded clippings stay discarded during normal, retry, and recheck runs, even after temporary source disappearance.
- Corrupt persistent state stops the import instead of being interpreted as an empty history.
- Automatic duplicate/comment maintenance only touches annotations tagged `kindle-import`.
- Failed writes and deletions remain in the retry ledger.

## Matching and positioning

- Duplicate citation keys prefer the source item's Zotero library and remain unresolved if still ambiguous.
- PDF and EPUB attachment fallback is retained.
- Tolerant PDF matching includes six-word shingle recovery for scattered OCR differences.
- Cross-library references use clickable comment links because Zotero does not permit native Related relations across libraries.

## Upgrade

Install `kanzi.xpi` from the release in Zotero through `Tools -> Plugins -> gear -> Install Plugin From File...`, then restart Zotero.

Existing mappings, successful annotation history, pending retries, and discard tombstones are retained. The normal Update changes mode is recommended for the first run after upgrading.

## Requirements

- Zotero 7 through 10.
- Python 3.11 or newer.
- Poppler for PDF positioning.
- Optional `qpdf` for encrypted PDFs.

See [`testing-0.7.2.md`](testing-0.7.2.md) for automated and manual verification steps.
