import json
from pathlib import Path
import tempfile

from kindle_zotero_importer import cli
from kindle_zotero_importer.cli import (
    _add_previous_imported_comments,
    _changed_note_clipping_ids,
    _changed_override_titles,
    _build_deletion_candidates,
    _clipping_ids_for_titles,
    _deferred_clipping_ids,
    _deletion_ids,
    _discarded_clipping_ids,
    _merge_annotation_history,
    _merge_positioned_history,
    _replacement_clipping_ids,
    _unresolved_clipping_ids,
)
from kindle_zotero_importer.clippings import clippings_to_jsonable, load_clippings
from kindle_zotero_importer import pdf_position

def test_incremental_ids(tmp_path: Path):
    # simulate previous final with one integrated id
    prev_final = {"annotations":[{"clipping_id":"aaa"}]}
    (tmp_path/"import-plan.final.json").write_text(json.dumps(prev_final))
    prev_clipp = {"clippings":[{"id":"aaa","title":"T"},{"id":"bbb","title":"U"}]}
    (tmp_path/"clippings.json").write_text(json.dumps(prev_clipp))

    new_ids = {"aaa","bbb","ccc"}  # ccc is new
    prev_integrated = {"aaa"}
    to_process = new_ids - prev_integrated
    assert to_process == {"bbb","ccc"}
    deletions = prev_integrated - new_ids
    assert deletions == set()  # none removed
    # changed: aaa text changed -> new id ddd, old aaa no longer in new -> deletion
    new_ids2 = {"ddd","bbb","ccc"}
    assert (prev_integrated - new_ids2) == {"aaa"}


def test_merge_annotation_history_preserves_old_and_replaces_changed():
    old_a = {"clipping_id": "a", "attachment_item_id": 2, "annotation": {"sortIndex": "2"}}
    old_b = {"clipping_id": "b", "attachment_item_id": 1, "annotation": {"sortIndex": "1"}}
    new_a = {"clipping_id": "a", "attachment_item_id": 2, "annotation": {"sortIndex": "3"}}

    merged = _merge_annotation_history(
        {"all_annotations": [old_a, old_b]}, [new_a], []
    )

    assert merged == [old_b, new_a]


def test_merge_annotation_history_removes_deletions():
    previous = {
        "annotations": [
            {"clipping_id": "a", "attachment_item_id": 1, "annotation": {}},
            {"clipping_id": "b", "attachment_item_id": 1, "annotation": {}},
        ]
    }

    merged = _merge_annotation_history(previous, [], ["a"])

    assert [annotation["clipping_id"] for annotation in merged] == ["b"]


def test_full_history_retains_current_unresolved_annotation():
    previous = {
        "all_annotations": [
            {"clipping_id": "unresolved", "attachment_item_id": 1, "annotation": {}},
            {"clipping_id": "removed", "attachment_item_id": 1, "annotation": {}},
        ]
    }

    merged = _merge_annotation_history(previous, [], ["removed"])

    assert [annotation["clipping_id"] for annotation in merged] == ["unresolved"]


def test_deletions_include_removed_and_previous_failures():
    assert _deletion_ids(
        {"kept", "removed"},
        {"kept"},
        {"delete_failed_ids": ["retry"]},
    ) == {"removed", "retry"}


def test_deferred_clippings_are_reprocessed_while_they_remain_in_source():
    previous = {"deferred_clipping_ids": ["retry", "removed"]}

    assert _deferred_clipping_ids(previous, {"retry", "current"}) == {"retry"}


def test_discarded_clips_never_requeue_and_skips_are_not_unresolved():
    previous = {"discarded_clipping_ids": ["gone", "removed"]}
    assert _discarded_clipping_ids(previous) == {"gone", "removed"}

    plan = {
        "items": [
            {"clipping": {"id": "note"}, "status": "pdf-position-skipped-non-highlight"},
            {"clipping": {"id": "fail"}, "status": "pdf-text-not-found"},
            {"clipping": {"id": "done"}, "status": "positioned"},
        ]
    }
    assert _unresolved_clipping_ids(plan, {"note", "fail", "done"}) == {"fail"}


def test_source_revision_deletion_depends_on_replacement():
    previous_clippings = [
        {
            "id": "old",
            "title": "Book",
            "kind": "highlight",
            "raw_detail": "- Highlight on page 10 | Added today",
            "text": "short",
        }
    ]
    current_clippings = [
        {
            "id": "new",
            "title": "Book",
            "kind": "highlight",
            "raw_detail": "- Highlight on page 10 | Added today",
            "text": "short and extended",
        }
    ]
    assert _replacement_clipping_ids(previous_clippings, current_clippings) == {
        "old": "new"
    }
    previous_plan = {
        "all_annotations": [
            {
                "clipping_id": "old",
                "clipping_title": "Book",
                "attachment_item_id": 11,
                "annotation": {"text": "short"},
            }
        ]
    }
    candidates = _build_deletion_candidates(
        ["old"], previous_plan, previous_clippings, current_clippings, {"new"}
    )
    assert candidates[0]["replacement_clipping_id"] == "new"
    assert candidates[0]["reason"] == "source-revision"
    assert candidates[0]["blocked"] is False


def test_deletion_is_blocked_until_replacement_is_positioned():
    previous = {
        "all_annotations": [{"clipping_id": "old", "annotation": {"text": "old"}}]
    }
    old = [{"id": "old", "title": "Book", "kind": "highlight", "raw_detail": "same"}]
    new = [{"id": "new", "title": "Book", "kind": "highlight", "raw_detail": "same"}]
    candidate = _build_deletion_candidates(["old"], previous, old, new, set())[0]
    assert candidate["replacement_clipping_id"] == "new"
    assert candidate["blocked"] is True


def test_ambiguous_lineage_does_not_guess_replacement():
    old = [{"id": "old", "title": "Book", "kind": "highlight", "raw_detail": "same"}]
    current = [
        {"id": "new-1", "title": "Book", "kind": "highlight", "raw_detail": "same"},
        {"id": "new-2", "title": "Book", "kind": "highlight", "raw_detail": "same"},
    ]
    assert _replacement_clipping_ids(old, current) == {}
    previous = {"all_annotations": [{"clipping_id": "old", "annotation": {}}]}
    candidate = _build_deletion_candidates(
        ["old"], previous, old, current, set()
    )[0]
    assert candidate["reason"] == "ambiguous-source-revision"
    assert candidate["blocked"] is True


def test_pending_replacement_dependency_survives_advanced_clipping_snapshot():
    previous = {
        "all_annotations": [{"clipping_id": "old", "annotation": {}}],
        "pending_deletion_candidates": [{
            "clipping_id": "old",
            "replacement_clipping_id": "new",
            "reason": "source-revision",
        }],
    }
    current_snapshot = [
        {"id": "new", "title": "Book", "kind": "highlight", "raw_detail": "same"}
    ]
    candidate = _build_deletion_candidates(
        ["old"], previous, current_snapshot, current_snapshot, set()
    )[0]
    assert candidate["replacement_clipping_id"] == "new"
    assert candidate["blocked"] is True


def test_same_id_remap_is_blocked_when_current_positioning_fails():
    previous = {
        "all_annotations": [{"clipping_id": "same", "annotation": {}}]
    }
    clipping = [{"id": "same", "title": "Book", "kind": "highlight", "raw_detail": "same"}]
    candidate = _build_deletion_candidates(
        ["same"], previous, clipping, clipping, set()
    )[0]
    assert candidate["reason"] == "override-remap"
    assert candidate["blocked"] is True


def test_alternate_attachment_retry_prefers_pdf_when_epub_misses():
    from kindle_zotero_importer.cli import _reattempt_failed_with_alternate_attachments
    from kindle_zotero_importer.epub_position import add_epub_positions
    from kindle_zotero_importer.import_plan import build_import_plan
    from kindle_zotero_importer.pdf_position import add_pdf_positions

    fixtures = Path(__file__).parent / "fixtures" / "windows-smoke"
    epub_path = str(fixtures / "kanzi-dummy.epub")
    pdf_path = str(fixtures / "kanzi-dummy.pdf")
    quote = "This is a test highlight long enough to import for PDF."
    clippings_payload = {
        "format": "kindle-zotero-importer.clippings.v1",
        "clippings": [
            {
                "id": "q1",
                "title": "Dummy Book",
                "kind": "highlight",
                "text": quote,
                "page": None,
                "location": "100",
            }
        ],
    }
    zotero_index = {
        "format": "index",
        "items": [
            {
                "item_id": 1,
                "key": "ABC12345",
                "title": "Dummy Book",
                "fields": {},
                "attachments": [
                    {
                        "item_id": 11,
                        "key": "EPUBKEY1",
                        "title": "epub",
                        "content_type": "application/epub+zip",
                        "path": epub_path,
                        "resolved_path": epub_path,
                    },
                    {
                        "item_id": 12,
                        "key": "PDFKEY123",
                        "title": "pdf",
                        "content_type": "application/pdf",
                        "path": pdf_path,
                        "resolved_path": pdf_path,
                    },
                ],
            }
        ],
    }
    match_report = {
        "format": "matches",
        "matches": [
            {
                "clipping_title": "Dummy Book",
                "status": "matched",
                "candidates": [{"item_id": 1}],
            }
        ],
    }
    plan = build_import_plan(clippings_payload, zotero_index, match_report, None)
    assert plan["items"][0]["zotero"]["attachment"]["content_type"] == "application/epub+zip"
    positioned = add_pdf_positions(add_epub_positions(plan))
    assert positioned["items"][0]["status"] == "positioned"
    assert "partial-text-match" in positioned["items"][0]["problems"]
    rescued = _reattempt_failed_with_alternate_attachments(positioned)
    assert rescued["items"][0]["status"] == "positioned"
    assert "positioned-via-alternate-attachment" in rescued["items"][0]["problems"]
    assert "partial-text-match" not in rescued["items"][0]["problems"]


def test_changed_override_requeues_every_clipping_for_exact_title():
    previous = {"Shared title": {"citation_key": "old"}}
    current = {"Shared title": {"citation_key": "new"}}
    clippings = [
        {"id": "first", "title": "Shared title"},
        {"id": "second", "title": "Shared title"},
        {"id": "third", "title": "Different title"},
    ]

    changed_titles = _changed_override_titles(previous, current)

    assert changed_titles == {"Shared title"}
    assert _clipping_ids_for_titles(clippings, changed_titles) == {"first", "second"}


def test_previous_imported_comment_is_attached_to_reprocessed_entry():
    current = [{"clipping_id": "a", "annotation": {"comment": "new"}}]
    previous = {
        "all_annotations": [
            {"clipping_id": "a", "annotation": {"comment": "old"}}
        ]
    }

    _add_previous_imported_comments(current, previous)

    assert current[0]["previous_imported_comment"] == "old"


def test_retry_unresolved_excludes_positioned_ignored_and_removed_entries():
    previous = {
        "items": [
            {"clipping": {"id": "retry"}, "status": "pdf-text-not-found"},
            {"clipping": {"id": "done"}, "status": "positioned"},
            {"clipping": {"id": "ignored"}, "status": "ignored-title"},
            {"clipping": {"id": "removed"}, "status": "unmatched-title"},
        ]
    }

    assert _unresolved_clipping_ids(previous, {"retry", "done", "ignored"}) == {
        "retry"
    }


def test_changed_note_ids_detect_add_replace_and_remove():
    previous = [
        {"clipping_id": "added", "note_ids": []},
        {"clipping_id": "replaced", "note_ids": ["old"]},
        {"clipping_id": "removed", "note_ids": ["old"]},
        {"clipping_id": "same", "note_ids": ["same-note"]},
    ]
    current = [
        {"id": "added", "note_ids": ["new"]},
        {"id": "replaced", "note_ids": ["new"]},
        {"id": "removed"},
        {"id": "same", "note_ids": ["same-note"]},
    ]

    assert _changed_note_clipping_ids(current, previous) == {
        "added",
        "replaced",
        "removed",
    }


def test_positioned_history_preserves_unresolved_and_replaces_current():
    previous = {
        "items": [
            {"clipping": {"id": "keep"}, "status": "pdf-text-not-found"},
            {"clipping": {"id": "replace"}, "status": "epub-text-not-found"},
            {"clipping": {"id": "removed"}, "status": "unmatched-title"},
        ]
    }
    current = {
        "format": "plan",
        "items": [{"clipping": {"id": "replace"}, "status": "positioned"}],
    }

    merged = _merge_positioned_history(previous, current, {"keep", "replace"})

    assert {item["clipping"]["id"]: item["status"] for item in merged["items"]} == {
        "keep": "pdf-text-not-found",
        "replace": "positioned",
    }
    assert merged["status_counts"] == {"pdf-text-not-found": 1, "positioned": 1}


def test_pdf_position_reports_missing_tools():
    original = pdf_position._missing_required_tools
    pdf_position._missing_required_tools = lambda: ["pdftotext", "pdfinfo"]
    try:
        result = pdf_position.add_pdf_positions(
            {
                "items": [
                    {
                        "status": "ready-for-positioning",
                        "clipping": {"kind": "highlight", "text": "highlight"},
                        "zotero": {
                            "attachment": {"content_type": "application/pdf"}
                        },
                    }
                ]
            }
        )
    finally:
        pdf_position._missing_required_tools = original

    assert result["items"][0]["status"] == "pdf-tools-missing:pdftotext,pdfinfo"


def test_pdf_position_preserves_unresolved_item_without_zotero_match():
    item = {
        "status": "unmatched-title",
        "clipping": {"kind": "highlight", "text": "highlight"},
        "zotero": None,
    }

    result = pdf_position.add_pdf_positions({"items": [item]})

    assert result["items"] == [item]


def test_noop_incremental_writes_complete_artifacts():
    with tempfile.TemporaryDirectory() as temporary:
        workdir = Path(temporary)
        source = workdir / "My Clippings.txt"
        source.write_text(
            "Book\n- Your Highlight at location 10-11 | Added on Tuesday, 18 May 2021 14:18:13\n\n"
            "A highlight long enough to import\n==========\n",
            encoding="utf-8",
        )
        clippings = clippings_to_jsonable(load_clippings(str(source)))
        clipping_id = clippings["clippings"][0]["id"]
        (workdir / "clippings.json").write_text(json.dumps(clippings), encoding="utf-8")
        annotation = {
            "clipping_id": clipping_id,
            "attachment_item_id": 1,
            "annotation": {"sortIndex": "1"},
        }
        (workdir / "import-plan.final.json").write_text(
            json.dumps({"annotations": [annotation], "all_annotations": [annotation], "overrides_snapshot": {}}),
            encoding="utf-8",
        )

        originals = (
            cli.build_zotero_index,
            cli.build_match_report,
            cli.generate_override_skeleton,
            cli.build_mismatch_review,
        )
        cli.build_zotero_index = lambda *_args: {"format": "index", "items": []}
        cli.build_match_report = lambda *_args: {"format": "matches", "matches": []}
        cli.generate_override_skeleton = lambda *_args: {"format": "overrides", "overrides": []}
        cli.build_mismatch_review = lambda *_args: "review\n"
        try:
            result = cli.main(
                [
                    "run",
                    str(source),
                    "--workdir",
                    str(workdir),
                    "--db",
                    str(workdir / "zotero.sqlite"),
                    "--storage-root",
                    str(workdir / "storage"),
                ]
            )
        finally:
            (
                cli.build_zotero_index,
                cli.build_match_report,
                cli.generate_override_skeleton,
                cli.build_mismatch_review,
            ) = originals

        assert result == 0
        final_plan = json.loads((workdir / "import-plan.final.json").read_text())
        assert final_plan["annotations"] == []
        assert final_plan["all_annotations"] == [{
            **annotation,
            "related_items": [],
            "ambiguous_citekeys": [],
        }]
        assert final_plan["delta_annotation_count"] == 0
        assert (workdir / "import-plan.epub.json").exists()


def test_full_run_preserves_discard_tombstones():
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        source = workdir / "My Clippings.txt"
        source.write_text(
            "Book\n- Your Highlight on page 10 | Added on Monday, 6 October 2025 11:32:29\n\nDiscard me permanently\n==========\n",
            encoding="utf-8",
        )
        clipping_id = load_clippings(str(source))[0].id
        (workdir / "import-plan.final.json").write_text(
            json.dumps({"discarded_clipping_ids": [clipping_id], "all_annotations": []}),
            encoding="utf-8",
        )

        originals = (
            cli.build_zotero_index,
            cli.build_match_report,
            cli.generate_override_skeleton,
            cli.build_mismatch_review,
        )
        cli.build_zotero_index = lambda *_args: {"format": "index", "items": []}
        cli.build_match_report = lambda payload, *_args: {
            "format": "matches",
            "matches": [],
            "source_count": len(payload.get("clippings", [])),
        }
        cli.generate_override_skeleton = lambda *_args: {"format": "overrides", "overrides": []}
        cli.build_mismatch_review = lambda *_args: "review\n"
        try:
            result = cli.main([
                "run",
                str(source),
                "--workdir",
                str(workdir),
                "--db",
                str(workdir / "zotero.sqlite"),
                "--storage-root",
                str(workdir / "storage"),
                "--full",
            ])
        finally:
            (
                cli.build_zotero_index,
                cli.build_match_report,
                cli.generate_override_skeleton,
                cli.build_mismatch_review,
            ) = originals

        assert result == 0
        final_plan = json.loads((workdir / "import-plan.final.json").read_text())
        assert final_plan["discarded_clipping_ids"] == [clipping_id]
        assert final_plan["annotations"] == []
        assert json.loads((workdir / "matches.json").read_text())["source_count"] == 0


def test_corrupt_existing_state_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        source = workdir / "My Clippings.txt"
        source.write_text("", encoding="utf-8")
        (workdir / "import-plan.final.json").write_text("{not json", encoding="utf-8")
        try:
            cli.main([
                "run",
                str(source),
                "--workdir",
                str(workdir),
                "--db",
                str(workdir / "zotero.sqlite"),
                "--storage-root",
                str(workdir / "storage"),
            ])
        except ValueError as error:
            assert "Existing import state is unreadable" in str(error)
        else:
            raise AssertionError("corrupt state must stop the import")


def test_structurally_invalid_existing_state_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        source = workdir / "My Clippings.txt"
        source.write_text("", encoding="utf-8")
        (workdir / "import-plan.final.json").write_text("{}", encoding="utf-8")
        try:
            cli.main([
                "run",
                str(source),
                "--workdir",
                str(workdir),
                "--db",
                str(workdir / "zotero.sqlite"),
                "--storage-root",
                str(workdir / "storage"),
            ])
        except ValueError as error:
            assert "Existing import state is unreadable" in str(error)
        else:
            raise AssertionError("structurally invalid state must stop the import")
