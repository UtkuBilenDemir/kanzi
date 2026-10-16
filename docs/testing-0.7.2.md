# Kanzi 0.7.2 Test Strategy

This checklist verifies the new review workflow and the existing import behavior it must preserve.

## Test safely

Use a separate Zotero profile or a small test library. Back up the Zotero data directory and Kanzi runtime directory before destructive scenarios. Keep copies of each `My Clippings.txt` variant used in the test.

Record for every scenario:

- Operating system and Zotero version.
- Kanzi version shown under `Tools -> Plugins`.
- Run mode and selected review operations.
- Result heading and issue count.
- Whether Zotero item modification dates changed unexpectedly.
- Relevant original technical statuses from `Technical details`.

## Automated checks

Run from the repository root:

```sh
python tests/run_tests.py
node tests/test_manager_logic.js
node --check plugin/bootstrap.js
git diff --check
python scripts/build_plugin.py
```

Inspect the package:

```sh
unzip -t dist/kanzi.xpi
unzip -p dist/kanzi.xpi manifest.json
```

Expected: all tests pass, the archive is valid, and the packaged manifest reports `0.7.2`.

## Installation smoke test

1. Install the built XPI in a clean Zotero profile.
2. Restart Zotero and open `Tools -> Kanzi...`.
3. Confirm the manager loads without an error.
4. Confirm `Tools -> Plugins` reports version `0.7.2`.
5. Open Settings and verify the detected Python, Zotero database, and storage paths.

Expected: the plugin starts on Zotero 7, 8, 9, or 10 without changing library data.

## Four-stage workflow

### Prepare

1. Select each run mode in turn.
2. Confirm only one mode can be active.
3. Start a run and watch the stage indicator and progress.

Expected: the indicator advances through Prepare and Review without moving backwards. The explanatory text matches the selected mode.

### Review

Prepare a fixture containing at least two titles and several highlights.

1. Confirm additions and updates are grouped by Kindle title.
2. Confirm each group shows the destination Zotero item and library.
3. Untick one highlight, one whole title, and one non-annotation operation.
4. Use Select none, then Select all.
5. Cancel the review and inspect Zotero.
6. Prepare again, close the manager window, reopen it, and run again.

Expected: cancelled, closed, and unticked operations make no Zotero changes. Deferred highlights return on a later review.

### Apply

1. Apply a mixed selection of additions and updates.
2. Confirm only checked operations occur.
3. Run the same file again in Update changes mode.

Expected: the second run proposes no annotation write for already-current annotations and does not update their Zotero modification dates.

### Results

1. Complete a successful run.
2. Cause one safe failure, such as temporarily removing an expected attachment after review.
3. Cause a preparation failure, such as selecting an unreadable file.

Expected: the headings are Completed, Completed with issues, and Failed respectively. Technical details contain exact counters and failure messages. Retrying does not duplicate successful annotations.

## Run modes

### Update changes

1. Import a baseline clipping file.
2. Add one clipping, extend one existing clipping, and remove one clipping from a copy.
3. Run Update changes.

Expected: only the additions, replacement update, and safe removal appear in review.

### Update and retry unresolved

1. Produce an unresolved title or missing attachment.
2. Fix the Zotero item or attachment.
3. Run Update changes without retry, then run Update changes and try unresolved again.

Expected: normal Update does not rebuild unrelated work. Retry proposes the repaired unresolved clipping.

### Recheck all clippings

1. Run a previously imported cumulative file with Recheck all clippings.
2. Review the operations and apply them.

Expected: Kanzi rechecks every plan entry but reuses equivalent Zotero annotations rather than duplicating them.

## Deletion safety

### Removed source clipping

1. Import a clipping.
2. Remove it from a test copy of `My Clippings.txt`.
3. Prepare Update changes.
4. Untick the removal, apply, and verify the annotation remains.
5. Prepare again, approve the removal, and apply.

Expected: the annotation is removed only in step 5.

### Replacement dependency

1. Import a short progressive highlight.
2. Replace it with a longer revision at the same Kindle location.
3. Prepare the review.
4. Deselect the replacement.
5. Repeat with a replacement that cannot be positioned.
6. Finally fix and select the replacement.

Expected: the old annotation survives steps 4 and 5. It is removed only after the replacement succeeds. If both resolve to the same annotation fingerprint, Kanzi keeps the surviving annotation.

## Discard durability

1. Discard an unresolved clipping from Conflicts.
2. Run Update changes.
3. Run Update changes and try unresolved again.
4. Run Recheck all clippings.
5. Remove the clipping temporarily from the source, run once, restore it, and run again.

Expected: the discarded clipping never returns in any review. Other clippings continue normally.

## Maintenance boundaries

1. Create two duplicate annotations carrying the `kindle-import` tag.
2. Create a similar annotation manually without the tag.
3. Prepare a review.
4. Untick duplicate maintenance and apply other operations.
5. Prepare again and approve maintenance.

Expected: the untagged manual annotation is never changed. Tagged duplicates merge only after approval. Manual additions in imported annotation comments survive comment updates.

## Citekeys and relations

### Same library

1. Add `@targetcitekey` to a clipping or attached Kindle note.
2. Keep source and target Zotero items in the same library.
3. Review and apply both the annotation and relation operations.

Expected: the annotation contains a clickable link and both Zotero items show the native Related relation.

### Different libraries

1. Put the source in My Library and the target in a group library, or use two different group libraries.
2. Import a clipping containing the target citekey.

Expected: the review explains that a native relation is unavailable. The annotation receives a clickable group-aware link, and no relation failure is reported.

### Duplicate citation key

1. Give two target items the same citation key in different libraries.
2. Verify the item in the source library is chosen.
3. Add a second duplicate to the source library and prepare again.

Expected: step 2 resolves to the same-library item. Step 3 shows an ambiguity warning and creates neither a guessed link nor a relation.

### Historical backfill

1. Import a highlight before adding its `@citekey` note or before the target exists.
2. Add/fix the reference and prepare again.
3. Select only the relation or comment-link operation while leaving unrelated annotation operations unticked.

Expected: the selected relationship operation works independently and no unrelated annotation changes occur.

## Positioning regression

Test at least one EPUB and these PDF types:

- Normal searchable PDF.
- PDF with punctuation or quote differences.
- Hyphenated or line-broken text.
- OCR text containing several scattered character errors.
- Encrypted PDF with `qpdf` installed.
- Scanned PDF with no usable text layer.

Expected: searchable and tolerant-match fixtures position correctly. Unpositionable scans remain unresolved with a human-readable remedy and original technical status.

## Groups and destinations

1. Import into My Library.
2. Import into a Zotero group library.
3. Review additions, deletions, relations, and links.

Expected: review rows identify the correct item and library. Group links use `zotero://select/groups/<group-id>/items/<key>`.

## Corrupt-state recovery

This is an advanced destructive test. Work only on a copied runtime directory.

1. Replace `import-plan.final.json` with invalid JSON.
2. Prepare an import.

Expected: Kanzi stops with an unreadable-state message and performs no Zotero write. Restore the file from backup or move it aside only when intentionally starting a new history.

## Privacy regression

1. Leave annotation sharing disabled and run an import while monitoring network requests.
2. Enable sharing, run a small import, then disable it again.

Expected: no annotation payload is sent while disabled. The setting remains explicit and reversible.

## Release acceptance

A release candidate is acceptable when:

- Every automated check passes.
- The XPI installs and starts in a clean profile.
- Cancel, close, no-op, and deselection paths perform no Zotero write.
- Replacement-bound removals cannot cause annotation loss.
- Manual annotations remain untouched.
- All three run modes and all six review categories behave as documented.
- Results identify partial failures without duplicating successful work.
- README installation and recovery instructions match the built plugin.
