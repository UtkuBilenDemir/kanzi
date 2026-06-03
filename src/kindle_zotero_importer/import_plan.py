from __future__ import annotations

import re
from typing import Any


PLAN_FORMAT = "kindle-zotero-importer.import-plan.v1"


def build_import_plan(
    clippings_payload: dict[str, Any],
    zotero_index: dict[str, Any],
    match_report: dict[str, Any],
) -> dict[str, Any]:
    items_by_id = {item["item_id"]: item for item in zotero_index["items"]}
    matches_by_title = {
        match["clipping_title"]: match for match in match_report["matches"]
    }
    overrides_by_title = {
        match["clipping_title"]: (match.get("override") or {})
        for match in match_report["matches"]
    }
    clippings = _attach_notes_to_highlights(clippings_payload["clippings"])
    plan_items = [
        _plan_clipping(clipping, matches_by_title, items_by_id, overrides_by_title)
        for clipping in clippings
        if clipping["kind"] in {"highlight", "note"}
    ]
    status_counts: dict[str, int] = {}
    for item in plan_items:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1

    return {
        "format": PLAN_FORMAT,
        "source": {
            "clippings_format": clippings_payload.get("format"),
            "zotero_index_format": zotero_index.get("format"),
            "match_report_format": match_report.get("format"),
        },
        "count": len(plan_items),
        "status_counts": status_counts,
        "items": plan_items,
    }


def _plan_clipping(
    clipping: dict[str, Any],
    matches_by_title: dict[str, dict[str, Any]],
    items_by_id: dict[int, dict[str, Any]],
    overrides_by_title: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    base = {
        "clipping": clipping,
        "status": "unmatched-title",
        "match": None,
        "zotero": None,
        "annotation": None,
        "problems": [],
    }
    match = matches_by_title.get(clipping["title"])
    if match and match.get("status") == "ignored":
        base["status"] = "ignored-title"
        base["match"] = None
        base["problems"] = ["ignored by match override"]
        return base
    if not match or match.get("status") != "matched" or not match.get("candidates"):
        return base

    candidate = match["candidates"][0]
    if not candidate.get("item_id"):
        base["match"] = candidate
        base["problems"] = [candidate.get("reason", "unresolved-match")]
        return base

    zotero_item = items_by_id.get(candidate["item_id"])
    if not zotero_item:
        base["status"] = "missing-zotero-item"
        base["match"] = candidate
        base["problems"] = ["matched item is absent from Zotero index"]
        return base

    attachment, attachment_status, problems = _choose_attachment(
        zotero_item, overrides_by_title.get(clipping["title"]) or {}
    )
    status = "ready-for-positioning" if attachment else attachment_status
    return {
        "clipping": clipping,
        "status": status,
        "match": candidate,
        "zotero": {
            "parent_item_id": zotero_item["item_id"],
            "parent_key": zotero_item["key"],
            "parent_title": zotero_item.get("title"),
            "citation_key": zotero_item["fields"].get("citationKey"),
            "attachment": attachment,
            "attachment_choices": zotero_item.get("attachments", []),
            "expected_attachment_type": _expected_attachment_type(
                clipping, zotero_item.get("attachments", [])
            ),
        },
        "annotation": _annotation_stub(clipping) if attachment else None,
        "problems": problems,
    }


def _choose_attachment(
    zotero_item: dict[str, Any],
    override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str, list[str]]:
    attachments = zotero_item.get("attachments", [])
    if not attachments:
        return (
            None,
            "matched-title-no-attachment",
            ["matched Zotero item has no PDF/EPUB attachment"],
        )
    if override:
        attachment, problem = _attachment_from_override(attachments, override)
        if attachment:
            return (
                attachment,
                "ready-for-positioning",
                ["selected attachment by override"],
            )
        if problem:
            return None, "matched-title-attachment-override-unresolved", [problem]
    if len(attachments) == 1:
        return attachments[0], "ready-for-positioning", []

    epubs = [
        attachment
        for attachment in attachments
        if attachment.get("content_type") == "application/epub+zip"
    ]
    if len(epubs) == 1:
        return (
            epubs[0],
            "ready-for-positioning",
            ["multiple attachments; selected sole EPUB"],
        )

    return (
        None,
        "matched-title-ambiguous-attachment",
        [f"matched Zotero item has {len(attachments)} PDF/EPUB attachments"],
    )


def _expected_attachment_type(
    clipping: dict[str, Any], attachments: list[dict[str, Any]]
) -> str:
    content_types = {attachment.get("content_type") for attachment in attachments}
    if len(content_types) == 1:
        content_type = next(iter(content_types))
        if content_type == "application/epub+zip":
            return "epub"
        if content_type == "application/pdf":
            return "pdf"
    if clipping.get("page") and not clipping.get("location"):
        return "pdf-preferred"
    if clipping.get("location") and not clipping.get("page"):
        return "epub-preferred"
    return "pdf-or-epub"


def _attachment_from_override(
    attachments: list[dict[str, Any]], override: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    if "attachment_item_id" in override:
        value = int(override["attachment_item_id"])
        matches = [
            attachment for attachment in attachments if attachment["item_id"] == value
        ]
        if len(matches) == 1:
            return matches[0], None
        return (
            None,
            f"attachment_item_id override did not match one attachment: {value}",
        )
    if "attachment_key" in override:
        value = str(override["attachment_key"]).casefold()
        matches = [
            attachment
            for attachment in attachments
            if attachment["key"].casefold() == value
        ]
        if len(matches) == 1:
            return matches[0], None
        return (
            None,
            f"attachment_key override did not match one attachment: {override['attachment_key']}",
        )
    return None, None


def _annotation_stub(clipping: dict[str, Any]) -> dict[str, Any]:
    annotation_type = "highlight" if clipping["kind"] == "highlight" else "note"
    return {
        "type": annotation_type,
        "text": clipping["text"] if annotation_type == "highlight" else "",
        "comment": clipping.get("comment")
        or (clipping["text"] if annotation_type == "note" else None),
        "color": "#ffd400",
        "pageLabel": clipping.get("page") or "",
        "sortIndex": None,
        "position": None,
        "tags": [{"name": "kindle-import"}],
    }


def _attach_notes_to_highlights(
    clippings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    updated = [dict(clipping) for clipping in clippings]
    attached_note_ids = set()
    for note_index, note in enumerate(updated):
        if note["kind"] != "note" or not note.get("text"):
            continue
        highlight_index = _matching_highlight_index(updated, note_index, note)
        if highlight_index is None:
            continue
        highlight = dict(updated[highlight_index])
        comments = [
            comment for comment in (highlight.get("comment"), note["text"]) if comment
        ]
        highlight["comment"] = "\n\n".join(comments)
        highlight["note_ids"] = [*highlight.get("note_ids", []), note["id"]]
        updated[highlight_index] = highlight
        attached_note_ids.add(note["id"])
    return [
        clipping
        for clipping in updated
        if clipping["kind"] != "note" or clipping["id"] not in attached_note_ids
    ]


def _matching_highlight_index(
    clippings: list[dict[str, Any]], note_index: int, note: dict[str, Any]
) -> int | None:
    note_location = _range_start(note.get("location"))
    if note_location is not None:
        for index, clipping in enumerate(clippings):
            if clipping["kind"] != "highlight" or clipping["title"] != note["title"]:
                continue
            highlight_range = _number_range(clipping.get("location"))
            if (
                highlight_range
                and highlight_range[0] <= note_location <= highlight_range[1]
            ):
                return index

    note_page = _range_start(note.get("page"))
    if note_page is None:
        return None
    for index in range(note_index - 1, -1, -1):
        clipping = clippings[index]
        if clipping["kind"] != "highlight" or clipping["title"] != note["title"]:
            continue
        highlight_page = _number_range(clipping.get("page"))
        if highlight_page and highlight_page[0] <= note_page <= highlight_page[1]:
            return index
    return None


def _range_start(value: str | None) -> int | None:
    number_range = _number_range(value)
    return number_range[0] if number_range else None


def _number_range(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    numbers = [int(number) for number in re.findall(r"\d+", value)]
    if not numbers:
        return None
    return numbers[0], numbers[-1]
