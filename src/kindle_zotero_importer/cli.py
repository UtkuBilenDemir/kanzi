from __future__ import annotations

import argparse
import json
import sys

from .clippings import clippings_to_jsonable, load_clippings
from .epub_position import add_epub_positions
from .final_plan import build_final_writer_plan
from .import_plan import build_import_plan
from .matcher import build_match_report, load_json
from .mismatch_review import build_mismatch_review
from .overrides import generate_override_skeleton, load_overrides
from .pdf_position import add_pdf_positions
from .zotero_index import build_zotero_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kindle-zotero-importer",
        description="Generate Zotero import-plan data from Kindle clippings.",
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

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
