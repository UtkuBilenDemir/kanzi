import json
from pathlib import Path
import tempfile

from kindle_zotero_importer import cli
from kindle_zotero_importer.cli import (
    _add_previous_imported_comments,
    _changed_note_clipping_ids,
    _deletion_ids,
    _merge_annotation_history,
    _merge_positioned_history,
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
        assert final_plan["all_annotations"] == [annotation]
        assert final_plan["delta_annotation_count"] == 0
        assert (workdir / "import-plan.epub.json").exists()
