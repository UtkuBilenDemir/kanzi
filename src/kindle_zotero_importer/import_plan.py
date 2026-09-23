from __future__ import annotations

import re
from typing import Any


PLAN_FORMAT = "kindle-zotero-importer.import-plan.v1"

# Default bracket → colour map (British spelling in UI, Zotero field stays "color")
# grey is [r] per request — red is only [red] (full name) to avoid clash
DEFAULT_COLOUR_MAP: dict[str, str] = {
    "y": "#ffd400",
    "yellow": "#ffd400",
    "o": "#ff8c00",
    "orange": "#ff8c00",
    "r": "#ff6666",
    "red": "#ff6666",
    "e": "#8a8a8a",
    "grey": "#8a8a8a",
    "gray": "#8a8a8a",
    "g": "#5fb236",
    "green": "#5fb236",
    "b": "#2ea8e5",
    "blue": "#2ea8e5",
    "p": "#a28ae5",
    "purple": "#a28ae5",
    "m": "#e56eee",
    "magenta": "#e56eee",
    "pink": "#e56eee",
}


def _extract_colour(text: str, colour_map: dict[str, str] | None = None) -> tuple[str, str]:
    """If text starts with [code], return (colour_hex, stripped_text). Case-insensitive."""
    if not text:
        return "#ffd400", text
    cmap = {k.lower(): v for k, v in (colour_map or DEFAULT_COLOUR_MAP).items()}
    m = re.match(r"^\s*\[([^\]]+)\]\s*", text)
    if not m:
        return "#ffd400", text
    raw = m.group(1).strip().lower()
    # allow palette names and single letters
    hex_colour = cmap.get(raw)
    if not hex_colour:
        return "#ffd400", text
    return hex_colour, text[m.end():].lstrip()


def build_import_plan(
    clippings_payload: dict[str, Any],
    zotero_index: dict[str, Any],
    match_report: dict[str, Any],
    colour_map: dict[str, str] | None = None,
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
        _plan_clipping(clipping, matches_by_title, items_by_id, overrides_by_title, colour_map)
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
    colour_map: dict[str, str] | None = None,
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
        "annotation": _annotation_stub(clipping, colour_map) if attachment else None,
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


def _annotation_stub(clipping: dict[str, Any], colour_map: dict[str, str] | None = None) -> dict[str, Any]:
    annotation_type = "highlight" if clipping["kind"] == "highlight" else "note"
    raw_text = clipping["text"] if annotation_type == "highlight" else ""
    raw_comment = clipping.get("comment") or (clipping["text"] if annotation_type == "note" else None)
    # Colour from comment first (so [r] on a note colours the highlight), then from highlight text itself
    comment_colour, cleaned_comment = _extract_colour(raw_comment or "", colour_map) if raw_comment else ("#ffd400", raw_comment)
    text_colour, cleaned_text = _extract_colour(raw_text, colour_map)
    if raw_comment and comment_colour != "#ffd400":
        colour, comment = comment_colour, cleaned_comment
        text = cleaned_text if text_colour != "#ffd400" else raw_text
        # also strip bracket from highlight text if it had one
        if text_colour != "#ffd400":
            text = cleaned_text
    elif text_colour != "#ffd400":
        colour, text, comment = text_colour, cleaned_text, raw_comment
    else:
        colour, text, comment = "#ffd400", raw_text, raw_comment
    # also clean bracket from comment if it was the source
    if comment and comment != raw_comment:
        pass  # already stripped
    return {
        "type": annotation_type,
        "text": text,
        "comment": comment,
        "color": colour,
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
