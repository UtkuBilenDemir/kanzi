from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import re
from typing import Any


ENTRY_SEPARATOR = "=========="
DETAIL_RE = re.compile(
    r"^- Your (?P<kind>Highlight|Note|Bookmark)"
    r"(?: on page (?P<page>[^|]+?))?"
    r"(?: (?:\| location|at location) (?P<location>[^|]+?))?"
    r"(?: \| Added on (?P<date>.+))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Clipping:
    id: str
    title: str
    kind: str
    text: str
    raw_detail: str
    page: str | None = None
    location: str | None = None
    added_on: str | None = None
    added_on_iso: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_clippings_text(text: str) -> list[Clipping]:
    entries = [entry.strip() for entry in text.split(ENTRY_SEPARATOR) if entry.strip()]
    clippings: list[Clipping] = []

    for entry in entries:
        lines = entry.splitlines()
        if len(lines) < 2:
            continue

        title = lines[0].strip()
        raw_detail = lines[1].strip()
        body = "\n".join(line.rstrip() for line in lines[2:]).strip()
        match = DETAIL_RE.match(raw_detail)

        if match:
            kind = match.group("kind").lower()
            page = _clean(match.group("page"))
            location = _clean(match.group("location"))
            added_on = _clean(match.group("date"))
        else:
            kind = "unknown"
            page = None
            location = None
            added_on = None

        clippings.append(
            Clipping(
                id=_stable_id(title, raw_detail, body),
                title=title,
                kind=kind,
                text=body,
                raw_detail=raw_detail,
                page=page,
                location=location,
                added_on=added_on,
                added_on_iso=_parse_kindle_date(added_on),
            )
        )

    return clippings


def load_clippings(path: str) -> list[Clipping]:
    with open(path, "r", encoding="utf-8-sig") as file:
        return parse_clippings_text(file.read())


def clippings_to_jsonable(clippings: list[Clipping]) -> dict[str, Any]:
    return {
        "format": "kindle-zotero-importer.clippings.v1",
        "count": len(clippings),
        "clippings": [clipping.to_dict() for clipping in clippings],
    }


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _stable_id(title: str, raw_detail: str, text: str) -> str:
    digest = hashlib.sha256(
        f"{title}\n{raw_detail}\n{text}".encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _parse_kindle_date(value: str | None) -> str | None:
    if not value:
        return None

    for fmt in (
        "%A, %B %d, %Y %I:%M:%S %p",
        "%A, %d %B %Y %H:%M:%S",
        "%A, %B %d, %Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            pass
    return None
