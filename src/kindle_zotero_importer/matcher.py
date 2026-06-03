from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
import re
import unicodedata
from typing import Any

from .overrides import resolve_override


@dataclass(frozen=True)
class MatchCandidate:
    item_id: int
    key: str
    title: str | None
    citation_key: str | None
    creators: list[str]
    attachment_count: int
    score: float
    reason: str


@dataclass(frozen=True)
class TitleMatch:
    clipping_title: str
    clipping_count: int
    candidates: list[MatchCandidate]
    status_override: str | None = None


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def build_match_report(
    clippings_payload: dict[str, Any],
    zotero_index: dict[str, Any],
    overrides: dict[str, dict[str, Any]] | None = None,
    max_candidates: int = 5,
) -> dict[str, Any]:
    title_counts = _clipping_title_counts(clippings_payload)
    matches = [
        _match_title(
            title,
            count,
            zotero_index["items"],
            max_candidates,
            overrides.get(title) if overrides else None,
        )
        for title, count in sorted(
            title_counts.items(), key=lambda item: item[0].lower()
        )
    ]
    status_counts = _status_counts(matches)
    return {
        "format": "kindle-zotero-importer.match-report.v1",
        "clipping_title_count": len(matches),
        "matched_title_count": status_counts["matched"],
        "ambiguous_title_count": status_counts["ambiguous"],
        "unmatched_title_count": status_counts["unmatched"],
        "ignored_title_count": status_counts["ignored"],
        "matches": [
            {
                "clipping_title": match.clipping_title,
                "clipping_count": match.clipping_count,
                "status": _match_status(match),
                "override": overrides.get(match.clipping_title) if overrides else None,
                "candidates": [asdict(candidate) for candidate in match.candidates],
            }
            for match in matches
        ],
    }


def _clipping_title_counts(clippings_payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for clipping in clippings_payload["clippings"]:
        title = clipping["title"]
        counts[title] = counts.get(title, 0) + 1
    return counts


def _match_title(
    clipping_title: str,
    count: int,
    items: list[dict[str, Any]],
    max_candidates: int,
    override: dict[str, Any] | None = None,
) -> TitleMatch:
    if override:
        if override.get("ignore") is True:
            return TitleMatch(clipping_title, count, [], "ignored")
        item, reason = resolve_override(clipping_title, override, items)
        if item:
            return TitleMatch(clipping_title, count, [_candidate(item, 1.0, reason)])
        return TitleMatch(
            clipping_title,
            count,
            [
                MatchCandidate(
                    item_id=0,
                    key="",
                    title=None,
                    citation_key=None,
                    creators=[],
                    attachment_count=0,
                    score=0.0,
                    reason=reason,
                )
            ],
        )

    citekey = _extract_citekey(clipping_title)
    normalized_clipping_title = _normalize_title(clipping_title)
    candidates: list[MatchCandidate] = []

    for item in items:
        item_citekey = item["fields"].get("citationKey")
        if citekey and item_citekey and citekey.casefold() == item_citekey.casefold():
            candidates.append(_candidate(item, 1.0, "citationKey"))
            continue

        item_title = item.get("title")
        if not item_title:
            continue

        normalized_item_title = _normalize_title(item_title)
        if not normalized_item_title:
            continue

        if normalized_item_title == normalized_clipping_title:
            candidates.append(_candidate(item, 0.98, "title-exact"))
        elif normalized_item_title in normalized_clipping_title:
            candidates.append(
                _candidate(item, 0.92, "title-contained-in-clipping-title")
            )
        elif normalized_clipping_title in normalized_item_title:
            candidates.append(
                _candidate(item, 0.88, "clipping-title-contained-in-title")
            )
        else:
            score = SequenceMatcher(
                None, normalized_clipping_title, normalized_item_title
            ).ratio()
            if score >= 0.82:
                candidates.append(_candidate(item, round(score, 4), "title-fuzzy"))

    candidates.sort(
        key=lambda candidate: (candidate.score, candidate.attachment_count),
        reverse=True,
    )
    return TitleMatch(clipping_title, count, candidates[:max_candidates])


def _candidate(item: dict[str, Any], score: float, reason: str) -> MatchCandidate:
    return MatchCandidate(
        item_id=item["item_id"],
        key=item["key"],
        title=item.get("title"),
        citation_key=item["fields"].get("citationKey"),
        creators=item.get("creators", []),
        attachment_count=len(item.get("attachments", [])),
        score=score,
        reason=reason,
    )


def _extract_citekey(title: str) -> str | None:
    stripped = title.strip()
    if re.fullmatch(r"@?[A-Za-z][A-Za-z0-9_:\-.]+", stripped):
        return stripped.removeprefix("@")

    match = re.search(r"(?:^|[\s\[(])@([A-Za-z][A-Za-z0-9_:\-.]+)(?:$|[\s\])])", title)
    if match:
        return match.group(1)

    match = re.match(r"^([A-Za-z][A-Za-z'\-]+)_([0-9]{4})(?:_|\b)", stripped)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None


def _normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    )
    value = value.casefold()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\bby\b.*$", " ", value)
    value = re.sub(r"\bz-lib\.org\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _status_counts(matches: list[TitleMatch]) -> dict[str, int]:
    counts = {"matched": 0, "ambiguous": 0, "unmatched": 0, "ignored": 0}
    for match in matches:
        counts[_match_status(match)] += 1
    return counts


def _match_status(match: TitleMatch) -> str:
    if match.status_override:
        return match.status_override
    if not match.candidates:
        return "unmatched"
    if len(match.candidates) == 1:
        return "matched"
    if match.candidates[0].score > match.candidates[1].score:
        return "matched"
    return "ambiguous"
