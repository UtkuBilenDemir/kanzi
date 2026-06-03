from __future__ import annotations

from collections import defaultdict
import json
from typing import Any


SECTIONS = [
    (
        "Matched Zotero Item But No Attachment",
        "matched-title-no-attachment",
        "Attach/link a PDF or EPUB to the listed Zotero item, then re-index Zotero.",
    ),
    (
        "Unmatched Kindle Titles",
        "unmatched-title",
        "Add one confirmed mapping to match-overrides.json using citation_key, zotero_key, or zotero_item_id.",
    ),
    (
        "Matched Attachment But Missing File Path",
        "pdf-position-missing-path",
        "Fix Zotero linked-file/storage path, then re-index Zotero.",
    ),
    (
        "Attachment Found But Text Position Failed",
        "epub-text-not-found",
        "Needs looser EPUB text matching or manual review.",
    ),
    (
        "PDF Text Not Found",
        "pdf-text-not-found",
        "Needs looser PDF text matching/OCR/page-offset handling.",
    ),
    (
        "PDF Rectangles Not Found",
        "pdf-rects-not-found",
        "Needs improved PDF rectangle recovery after text/page match.",
    ),
    (
        "PDF Position Errors",
        "pdf-position-error:",
        "Inspect the PDF extraction command error, file validity, encryption, or permissions.",
    ),
]


def build_mismatch_review(
    positioned_plan: dict[str, Any], match_report: dict[str, Any]
) -> str:
    match_by_title = {
        match["clipping_title"]: match for match in match_report["matches"]
    }
    by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in positioned_plan["items"]:
        if item.get("status") != "positioned":
            by_status[item.get("status", "unknown")].append(item)

    lines = [
        "# Mismatch Review",
        "",
        "Persistent rule: confirmed title matches go in `match-overrides.json`, not `match-overrides.generated.json`. The generated file can be replaced at any time.",
        "",
    ]
    for heading, status, instruction in SECTIONS:
        section_items = _items_for_status(by_status, status)
        summaries = _title_summaries(section_items, match_by_title)
        lines += [
            f"## {heading}",
            "",
            f"Status: `{status}`",
            f"Clippings: {len(section_items)}",
            f"Unique titles: {len(summaries)}",
            f"Action: {instruction}",
            "",
        ]
        for summary in summaries[:30]:
            lines += _summary_lines(status, summary)
        if len(summaries) > 30:
            lines += [f"_Showing first 30 of {len(summaries)} unique titles._", ""]

    return "\n".join(lines).rstrip() + "\n"


def _items_for_status(
    by_status: dict[str, list[dict[str, Any]]], status: str
) -> list[dict[str, Any]]:
    if status.endswith(":"):
        items: list[dict[str, Any]] = []
        for item_status, status_items in by_status.items():
            if item_status.startswith(status):
                items.extend(status_items)
        return items
    return by_status.get(status, [])


def _title_summaries(
    items: list[dict[str, Any]], match_by_title: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for item in items:
        clipping = item["clipping"]
        title = clipping["title"]
        summary = summaries.setdefault(
            title,
            {
                "title": title,
                "count": 0,
                "kinds": defaultdict(int),
                "examples": [],
                "zotero": item.get("zotero"),
                "match": match_by_title.get(title),
            },
        )
        summary["count"] += 1
        summary["kinds"][clipping.get("kind")] += 1
        if len(summary["examples"]) < 3:
            summary["examples"].append(
                {
                    "kind": clipping.get("kind"),
                    "page": clipping.get("page"),
                    "location": clipping.get("location"),
                    "text": (clipping.get("text") or "")[:180],
                }
            )
    return sorted(
        summaries.values(),
        key=lambda summary: (-summary["count"], summary["title"].casefold()),
    )


def _summary_lines(status: str, summary: dict[str, Any]) -> list[str]:
    match = summary.get("match") or {}
    candidates = match.get("candidates") or []
    best = candidates[0] if candidates else {}
    zotero = summary.get("zotero") or {}
    citation_key = zotero.get("citation_key") or best.get("citation_key") or ""
    zotero_item_id = zotero.get("parent_item_id") or best.get("item_id") or ""
    zotero_key = best.get("key") or ""
    attachment_count = best.get("attachment_count")
    expected_attachment_type = zotero.get(
        "expected_attachment_type"
    ) or _expected_attachment_type(status, summary)
    override_resolution = _override_resolution(citation_key, zotero_key, zotero_item_id)

    lines = [f"### {summary['title']}", "", "```yaml"]
    lines += [
        f"clipping_title: {_yaml_string(summary['title'])}",
        f"status: {status}",
        f"clipping_count: {summary['count']}",
        "kinds: " + _yaml_inline_map(summary["kinds"]),
        f"citation_key: {_yaml_string(citation_key)}",
        f"zotero_item_id: {_yaml_value(zotero_item_id)}",
        f"zotero_key: {_yaml_string(zotero_key)}",
        f"zotero_title: {_yaml_string(zotero.get('parent_title') or best.get('title') or '')}",
        f"attachment_count: {_yaml_value(attachment_count)}",
        f"expected_attachment_type: {_yaml_string(expected_attachment_type)}",
        f"match_score: {_yaml_value(best.get('score'))}",
        f"match_reason: {_yaml_string(best.get('reason') or '')}",
    ]
    attachments = zotero.get("attachment_choices") or []
    if attachments:
        lines.append("attachment_choices:")
        for attachment in attachments:
            lines += [
                f"  - attachment_item_id: {attachment.get('item_id')}",
                f"    attachment_key: {_yaml_string(attachment.get('key') or '')}",
                f"    attachment_title: {_yaml_string(attachment.get('title') or '')}",
                f"    content_type: {_yaml_string(attachment.get('content_type') or '')}",
                f"    path: {_yaml_string(attachment.get('resolved_path') or attachment.get('path') or '')}",
            ]
    if override_resolution:
        lines += [
            "override_entry:",
            f"  clipping_title: {_yaml_string(summary['title'])}",
            "  resolution:",
            f"    {override_resolution[0]}: {_yaml_value(override_resolution[1])}",
        ]
        if attachments:
            lines += [
                '    attachment_key: "PASTE_SELECTED_ATTACHMENT_KEY"',
                "    attachment_item_id: null",
            ]
    lines += ["```", ""]

    if candidates:
        lines += ["Candidates:"]
        for candidate in candidates[:5]:
            lines.append(
                "- "
                f"citation_key: `{candidate.get('citation_key')}`, "
                f"zotero_item_id: `{candidate.get('item_id')}`, "
                f"zotero_key: `{candidate.get('key')}`, "
                f"attachments: `{candidate.get('attachment_count')}`, "
                f"score: `{candidate.get('score')}`, "
                f"title: {candidate.get('title')}"
            )
        lines.append("")

    for example in summary["examples"]:
        text = example["text"].replace("\n", " ")
        lines.append(
            f"- Example: {example['kind']} page `{example['page']}` loc `{example['location']}`: {text}"
        )
    lines.append("")
    return lines


def _override_resolution(
    citation_key: str, zotero_key: str, zotero_item_id: str | int
) -> tuple[str, str | int] | None:
    if citation_key:
        return "citation_key", citation_key
    if zotero_key:
        return "zotero_key", zotero_key
    if zotero_item_id:
        return "zotero_item_id", zotero_item_id
    return None


def _expected_attachment_type(status: str, summary: dict[str, Any]) -> str:
    if status.startswith("epub-"):
        return "epub"
    if status.startswith("pdf-"):
        return "pdf"
    pages = 0
    locations = 0
    for example in summary["examples"]:
        if example.get("page"):
            pages += 1
        if example.get("location"):
            locations += 1
    if pages and not locations:
        return "pdf-preferred"
    if locations and not pages:
        return "epub-preferred"
    return "pdf-or-epub"


def _yaml_inline_map(values: dict[str, int]) -> str:
    return (
        "{"
        + ", ".join(f"{key}: {value}" for key, value in sorted(values.items()))
        + "}"
    )


def _yaml_value(value: Any) -> str:
    if value is None or value == "":
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return _yaml_string(str(value))


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
