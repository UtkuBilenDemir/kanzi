from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .clippings import clippings_to_jsonable, load_clippings
from .epub_position import add_epub_positions
from .final_plan import build_final_writer_plan
from .import_plan import DEFAULT_COLOUR_MAP, build_import_plan
from .matcher import build_match_report, load_json
from .mismatch_review import build_mismatch_review
from .overrides import generate_override_skeleton, load_overrides
from .pdf_position import add_pdf_positions
from .zotero_index import build_zotero_index


def _load_colour_map(workdir: Path) -> dict[str, str] | None:
    # 1) workdir/colour-map.json (editable via Settings)
    p = workdir / "colour-map.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k).lower(): str(v) for k, v in data.items()}
        except Exception:
            pass
    # 2) plugin-config.json colourMap field
    cfg = workdir / "plugin-config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            m = data.get("colourMap") or data.get("colorMap")
            if isinstance(m, dict):
                return {str(k).lower(): str(v) for k, v in m.items()}
        except Exception:
            pass
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kindle-zotero-importer",
        description="Minimalist Kindle → Zotero importer. Primary command is `run`; others are developer utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser(
        "parse", help="Parse a Kindle My Clippings.txt file"
    )
    parse_parser.add_argument("clippings_file", help="Path to Kindle My Clippings.txt")
    parse_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    parse_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    index_parser = subparsers.add_parser(
        "index-zotero", help="Index Zotero items and attachments read-only"
    )
    index_parser.add_argument(
        "--db", default="/home/user/Zotero/zotero.sqlite", help="Path to zotero.sqlite"
    )
    index_parser.add_argument(
        "--storage-root",
        default="/home/user/Zotero/storage",
        help="Path to Zotero storage directory for storage: attachments",
    )
    index_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    index_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    match_parser = subparsers.add_parser(
        "match", help="Match parsed Kindle clipping titles to Zotero items"
    )
    match_parser.add_argument("clippings_json", help="Path to parsed clippings JSON")
    match_parser.add_argument("zotero_index_json", help="Path to Zotero index JSON")
    match_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    match_parser.add_argument(
        "--overrides", help="Path to reusable match overrides JSON"
    )
    match_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    overrides_parser = subparsers.add_parser(
        "generate-overrides",
        help="Generate a reusable override skeleton from ambiguous/unmatched matches",
    )
    overrides_parser.add_argument("matches_json", help="Path to match report JSON")
    overrides_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    overrides_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    plan_parser = subparsers.add_parser(
        "plan", help="Generate a preliminary Zotero annotation import plan"
    )
    plan_parser.add_argument("clippings_json", help="Path to parsed clippings JSON")
    plan_parser.add_argument("zotero_index_json", help="Path to Zotero index JSON")
    plan_parser.add_argument("matches_json", help="Path to match report JSON")
    plan_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    plan_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    epub_parser = subparsers.add_parser(
        "position-epub", help="Add EPUB CFI positions to an import plan"
    )
    epub_parser.add_argument(
        "import_plan_json", help="Path to preliminary import plan JSON"
    )
    epub_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    epub_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    pdf_parser = subparsers.add_parser(
        "position-pdf", help="Add PDF page/rect positions to an import plan"
    )
    pdf_parser.add_argument("import_plan_json", help="Path to import plan JSON")
    pdf_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    pdf_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    final_parser = subparsers.add_parser(
        "finalize",
        help="Export positioned annotations for the Zotero JavaScript writer",
    )
    final_parser.add_argument(
        "positioned_plan_json", help="Path to positioned import plan JSON"
    )
    final_parser.add_argument(
        "--output", "-o", help="Write JSON to this file instead of stdout"
    )
    final_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    review_parser = subparsers.add_parser(
        "review-mismatches",
        help="Generate a copy-friendly mismatch review Markdown file",
    )
    review_parser.add_argument(
        "positioned_plan_json", help="Path to positioned import plan JSON"
    )
    review_parser.add_argument("matches_json", help="Path to match report JSON")
    review_parser.add_argument(
        "--output", "-o", help="Write Markdown to this file instead of stdout"
    )

    run_parser = subparsers.add_parser(
        "run", help="Run the full importer pipeline for a Kindle My Clippings.txt file"
    )
    run_parser.add_argument("clippings_file", help="Path to Kindle My Clippings.txt")
    run_parser.add_argument(
        "--workdir",
        default=".",
        help="Directory for generated importer artifacts",
    )
    run_parser.add_argument(
        "--db", default="/home/user/Zotero/zotero.sqlite", help="Path to zotero.sqlite"
    )
    run_parser.add_argument(
        "--storage-root",
        default="/home/user/Zotero/storage",
        help="Path to Zotero storage directory for storage: attachments",
    )
    run_parser.add_argument(
        "--overrides",
        default="match-overrides.json",
        help="Path to reusable match overrides JSON, relative to workdir unless absolute",
    )
    run_parser.add_argument(
        "--summary-output",
        help="Write pipeline summary JSON to this path instead of stdout",
    )
    run_parser.add_argument(
        "--progress-output",
        help="Write machine-readable pipeline progress JSON to this path",
    )
    run_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON artifacts"
    )
    run_parser.add_argument(
        "--full",
        action="store_true",
        help="Force full re-import from scratch, ignoring incremental state (processes all clippings)",
    )

    args = parser.parse_args(argv)

    if args.command == "parse":
        payload = clippings_to_jsonable(load_clippings(args.clippings_file))
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "index-zotero":
        payload = build_zotero_index(args.db, args.storage_root)
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "match":
        overrides = (
            load_overrides(load_json(args.overrides)) if args.overrides else None
        )
        payload = build_match_report(
            load_json(args.clippings_json), load_json(args.zotero_index_json), overrides
        )
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "generate-overrides":
        payload = generate_override_skeleton(load_json(args.matches_json))
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "plan":
        payload = build_import_plan(
            load_json(args.clippings_json),
            load_json(args.zotero_index_json),
            load_json(args.matches_json),
        )
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "position-epub":
        payload = add_epub_positions(load_json(args.import_plan_json))
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "position-pdf":
        payload = add_pdf_positions(load_json(args.import_plan_json))
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "finalize":
        payload = build_final_writer_plan(load_json(args.positioned_plan_json))
        json_text = json.dumps(
            payload, ensure_ascii=False, indent=2 if args.pretty else None
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        return 0

    if args.command == "review-mismatches":
        text = build_mismatch_review(
            load_json(args.positioned_plan_json), load_json(args.matches_json)
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(text)
        else:
            sys.stdout.write(text)
        return 0

    if args.command == "run":
        workdir = Path(args.workdir).expanduser().resolve()
        workdir.mkdir(parents=True, exist_ok=True)

        progress_path = (
            Path(args.progress_output).expanduser().resolve()
            if args.progress_output
            else None
        )

        def report_progress(percent: int, stage: str, detail: str) -> None:
            if not progress_path:
                return
            temporary_path = progress_path.with_suffix(progress_path.suffix + ".tmp")
            temporary_path.write_text(
                json.dumps(
                    {"percent": percent, "stage": stage, "detail": detail},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(progress_path)

        def artifact(name: str) -> Path:
            return workdir / name

        overrides_path = Path(args.overrides).expanduser()
        if not overrides_path.is_absolute():
            overrides_path = workdir / overrides_path
        colour_map = _load_colour_map(workdir)

        report_progress(2, "Reading clippings", "Parsing My Clippings.txt")
        new_clippings_list = load_clippings(args.clippings_file)
        new_clippings = clippings_to_jsonable(new_clippings_list)
        new_ids = {c["id"] for c in new_clippings.get("clippings", [])}

        # Incremental state: previous clippings and previous integrated ids
        is_incremental = not args.full
        prev_clippings_ids: set[str] = set()
        prev_integrated_ids: set[str] = set()
        prev_final_plan = None
        if is_incremental:
            prev_clippings_path = artifact("clippings.json")
            prev_final_path = artifact("import-plan.final.json")
            if prev_clippings_path.exists():
                try:
                    prev_clippings_ids = {c["id"] for c in load_json(str(prev_clippings_path)).get("clippings", [])}
                except Exception:
                    prev_clippings_ids = set()
            if prev_final_path.exists():
                try:
                    prev_final_plan = load_json(str(prev_final_path))
                    prev_integrated_ids = {a.get("clipping_id") for a in prev_final_plan.get("annotations", []) if a.get("clipping_id")}
                except Exception:
                    prev_final_plan = None
                    prev_integrated_ids = set()
            # If no previous state, fall back to full
            if not prev_clippings_ids and not prev_integrated_ids:
                is_incremental = False

        if is_incremental:
            # New or previously not integrated (skipped) -> need to (re)process
            to_process_ids = set(new_ids - prev_integrated_ids)
            # Deletions: previously integrated but now absent (removed or changed text)
            deletions_ids = sorted(prev_integrated_ids - new_ids)
            # Also re-queue any previously integrated clippings whose title now has an override
            # (mapping may have changed, need to move annotation). We need overrides dict for this.
            # Load overrides early for this check (already loaded later, but do here for incremental decision)
            # We will reload overrides here if not yet loaded
            try:
                _ov_for_inc = load_overrides(load_json(str(overrides_path))) if overrides_path.exists() else {}
            except Exception:
                _ov_for_inc = {}
            for c in new_clippings_list:
                if c.id in prev_integrated_ids and c.title in _ov_for_inc:
                    to_process_ids.add(c.id)
            # Also re-queue highlights whose bracket colour would change the annotation
            # (so you can recolour a past highlight by adding [r]/[o] etc. to its note or highlight text)
            if colour_map:
                import re as _re
                for c in new_clippings_list:
                    if c.id not in prev_integrated_ids:
                        continue
                    # check highlight text and note text for leading [code]
                    texts = [c.text or ""]
                    # notes attached to this title may carry the bracket — check all notes for this title
                    # simplest: if clipping is highlight, its comment (attached note) is in clippings payload; check that too if present
                    # For incremental we don't yet have attached notes, so check raw clipping text and any note with same title
                    # For now, check c.text and also any note text that would be attached (we can approximate by checking c.text only)
                    # Better: check both c.text and the raw note text if kind==highlight and has comment
                    has_bracket = False
                    for t in [c.text or "", getattr(c, "comment", "") or ""]:
                        m = _re.match(r"^\s*\[([^\]]+)\]\s*", t)
                        if m and m.group(1).strip().lower() in {k.lower() for k in colour_map.keys()}:
                            has_bracket = True
                            break
                    if has_bracket:
                        to_process_ids.add(c.id)
            # If colourMap itself changed since last run, re-queue all prev integrated (so Settings change recolours)
            try:
                prev_map = (prev_final_plan or {}).get("colourMap") or (prev_final_plan or {}).get("colorMap")
                if colour_map is not None and prev_map is not None and dict(colour_map) != dict(prev_map):
                    to_process_ids.update(prev_integrated_ids)
                elif colour_map is not None and prev_map is None and len(colour_map) != len(DEFAULT_COLOUR_MAP):
                    # custom map added where previously default — re-queue to apply
                    to_process_ids.update(prev_integrated_ids)
            except Exception:
                pass
            # Also handle deleted overrides: if a previously integrated title's override was deleted,
            # its annotations should be deleted. Detect via previous final plan's titles vs current overrides.
            # For incremental, we don't have previous overrides, so we handle deletions via the main deletions list
            # (IDs no longer present). For deleted overrides where ID still present but now unmatched,
            # the match report will make them not positioned, and they will be in to_process but then skipped;
            # we need to ensure they are deleted. We do this by checking if a previously integrated clipping's
            # title is now not in overrides and would be unmatched -> treat as to_delete.
            # Simplify: any prev_integrated clipping whose title is not in current new match's "matched" will be
            # handled as not in to_process_ids? Actually it is still in new_ids, but we re-queued it above only if title in overrides.
            # For now, rely on full re-import for deleted-override cleanup.
            # Build filtered clippings for this delta run
            filtered_list = [c for c in new_clippings_list if c.id in to_process_ids]
            # If nothing to do and no deletions, still need to report but skip expensive steps
            if not filtered_list and not deletions_ids:
                report_progress(15, "Matching titles", "No new highlights — incremental skip")
                # Still need to generate artifacts for consistency (empty delta)
                zotero_index = build_zotero_index(args.db, args.storage_root)
                overrides = None
                if overrides_path.exists():
                    overrides = load_overrides(load_json(str(overrides_path)))
                clippings = new_clippings
                matches = build_match_report(clippings, zotero_index, overrides)
                override_skeleton = generate_override_skeleton(matches)
                plan = {"format": "kindle-zotero-importer.import-plan.v1", "items": []}
                positioned_plan = {"format": plan["format"], "items": []}
                final_plan = {"format": FINAL_FORMAT, "source_format": positioned_plan.get("format"), "annotation_count": 0, "skipped_counts": {}, "annotations": [], "deletions": [], "is_incremental": True, "incremental_stats": {"new_clippings": len(new_ids), "prev_integrated": len(prev_integrated_ids), "to_process": 0, "deletions": 0}}
                final_plan["colourMap"] = colour_map if colour_map is not None else DEFAULT_COLOUR_MAP
                final_plan["colorMap"] = final_plan["colourMap"]
                mismatch_review = build_mismatch_review(positioned_plan, matches)
                # Will write artifacts below with empty delta
            else:
                report_progress(8, "Indexing Zotero", "Reading library items and attachments (incremental)")
                zotero_index = build_zotero_index(args.db, args.storage_root)
                overrides = None
                if overrides_path.exists():
                    overrides = load_overrides(load_json(str(overrides_path)))
                # Only the delta clippings go through matching/positioning
                delta_clippings = clippings_to_jsonable(filtered_list)
                report_progress(15, "Matching titles", f"Matching {len(filtered_list)} new/pending highlights (incremental)")
                matches = build_match_report(delta_clippings, zotero_index, overrides)
                override_skeleton = generate_override_skeleton(matches)
                # For artifact completeness, also build full matches for summary? Use delta matches for now
                # But we need full matches for review? Keep delta
                report_progress(22, "Building plan", "Selecting attachments (incremental)")
                plan = build_import_plan(delta_clippings, zotero_index, matches, colour_map)
                report_progress(30, "Positioning EPUB highlights", "Locating highlights in EPUB files (incremental)")
                epub_plan = add_epub_positions(plan)
                report_progress(55, "Positioning PDF highlights", "Locating highlights in PDF files (incremental)")
                positioned_plan = add_pdf_positions(epub_plan)
                report_progress(90, "Finalizing", "Preparing Zotero annotations and mismatch report")
                final_plan = build_final_writer_plan(positioned_plan)
                # Attach deletions for writer
                final_plan["deletions"] = deletions_ids
                final_plan["is_incremental"] = True
                final_plan["incremental_stats"] = {
                    "new_clippings": len(new_ids),
                    "prev_integrated": len(prev_integrated_ids),
                    "to_process": len(to_process_ids),
                    "deletions": len(deletions_ids),
                }
                final_plan["colourMap"] = colour_map if colour_map is not None else DEFAULT_COLOUR_MAP
                final_plan["colorMap"] = final_plan["colourMap"]
                mismatch_review = build_mismatch_review(positioned_plan, matches)
                # For outputs, clippings should be the full new set (for next diff), but plan artifacts are delta
                clippings = new_clippings
        else:
            # Full re-import
            report_progress(8, "Indexing Zotero", "Reading library items and attachments")
            zotero_index = build_zotero_index(args.db, args.storage_root)
            overrides = None
            if overrides_path.exists():
                overrides = load_overrides(load_json(str(overrides_path)))
            clippings = new_clippings
            report_progress(15, "Matching titles", "Matching Kindle titles to Zotero items")
            matches = build_match_report(clippings, zotero_index, overrides)
            override_skeleton = generate_override_skeleton(matches)
            report_progress(22, "Building plan", "Selecting attachments")
            plan = build_import_plan(clippings, zotero_index, matches, colour_map)
            report_progress(30, "Positioning EPUB highlights", "Locating highlights in EPUB files")
            epub_plan = add_epub_positions(plan)
            report_progress(55, "Positioning PDF highlights", "Locating highlights in PDF files; this is usually the longest stage")
            positioned_plan = add_pdf_positions(epub_plan)
            report_progress(90, "Finalizing", "Preparing Zotero annotations and mismatch report")
            final_plan = build_final_writer_plan(positioned_plan)
            final_plan["deletions"] = []
            final_plan["is_incremental"] = False
            final_plan["colourMap"] = colour_map if colour_map is not None else DEFAULT_COLOUR_MAP
            final_plan["colorMap"] = final_plan["colourMap"]
            mismatch_review = build_mismatch_review(positioned_plan, matches)

        indent = 2 if args.pretty else None
        outputs = {
            "clippings": artifact("clippings.json"),
            "zotero_index": artifact("zotero-index.json"),
            "matches": artifact("matches.json"),
            "generated_overrides": artifact("match-overrides.generated.json"),
            "import_plan": artifact("import-plan.json"),
            "epub_plan": artifact("import-plan.epub.json"),
            "positioned_plan": artifact("import-plan.positioned.json"),
            "final_plan": artifact("import-plan.final.json"),
            "mismatch_review": workdir / "docs" / "mismatch-review.md",
        }
        outputs["mismatch_review"].parent.mkdir(parents=True, exist_ok=True)

        report_progress(95, "Saving results", "Writing import artifacts")
        for key, payload in [
            ("clippings", clippings),
            ("zotero_index", zotero_index),
            ("matches", matches),
            ("generated_overrides", override_skeleton),
            ("import_plan", plan),
            ("epub_plan", epub_plan),
            ("positioned_plan", positioned_plan),
            ("final_plan", final_plan),
        ]:
            with open(outputs[key], "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=indent)
                file.write("\n")

        with open(outputs["mismatch_review"], "w", encoding="utf-8") as file:
            file.write(mismatch_review)

        status_counts: dict[str, int] = {}
        for item in positioned_plan.get("items", []):
            status = item.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        match_counts: dict[str, int] = {}
        for match in matches.get("matches", []):
            status = match.get("status", "unknown")
            match_counts[status] = match_counts.get(status, 0) + 1

        summary = {
            "format": "kindle-zotero-importer.pipeline-summary.v1",
            "workdir": str(workdir),
            "overrides_path": str(overrides_path),
            "outputs": {key: str(path) for key, path in outputs.items()},
            "counts": {
                "clippings": len(clippings.get("clippings", [])),
                "unique_titles": len(matches.get("matches", [])),
                "final_annotations": final_plan.get("annotation_count", 0),
                "match_statuses": match_counts,
                "plan_statuses": status_counts,
                "skipped_final": final_plan.get("skipped_counts", {}),
                "is_incremental": final_plan.get("is_incremental", False),
                "incremental_stats": final_plan.get("incremental_stats", {}),
                "deletions": len(final_plan.get("deletions", [])),
            },
        }
        json_text = json.dumps(summary, ensure_ascii=False, indent=2)
        if args.summary_output:
            with open(args.summary_output, "w", encoding="utf-8") as file:
                file.write(json_text)
                file.write("\n")
        else:
            sys.stdout.write(json_text)
            sys.stdout.write("\n")
        report_progress(100, "Pipeline complete", "Ready to import annotations into Zotero")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
