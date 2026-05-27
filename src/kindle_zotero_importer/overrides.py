from __future__ import annotations

from collections.abc import Callable
from typing import Any


OVERRIDES_FORMAT = "kindle-zotero-importer.match-overrides.v1"


class OverrideError(ValueError):
    pass


def load_overrides(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if payload.get("format") != OVERRIDES_FORMAT:
        raise OverrideError(f"unsupported overrides format: {payload.get('format')}")

    overrides: dict[str, dict[str, Any]] = {}
    for entry in payload.get("overrides", []):
        clipping_title = entry.get("clipping_title")
        if not clipping_title:
            raise OverrideError("override missing clipping_title")

        resolution = _clean_resolution(entry.get("resolution") or {})
        if not resolution:
            continue
        item_fields = [
            key
            for key in ("citation_key", "zotero_key", "zotero_item_id")
            if key in resolution
        ]
        if len(item_fields) != 1:
            raise OverrideError(
                f"override for {clipping_title!r} must contain exactly one item resolution field"
            )
        overrides[clipping_title] = resolution

    return overrides


def resolve_override(
    clipping_title: str, resolution: dict[str, Any], items: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, str]:
    if "citation_key" in resolution:
        value = str(resolution["citation_key"]).casefold()
        return _find_item(
            items,
            lambda item: (item["fields"].get("citationKey") or "").casefold() == value,
            f"override-citation-key:{resolution['citation_key']}",
            clipping_title,
        )
    if "zotero_key" in resolution:
        value = str(resolution["zotero_key"]).casefold()
        return _find_item(
            items,
            lambda item: item["key"].casefold() == value,
            f"override-zotero-key:{resolution['zotero_key']}",
            clipping_title,
        )
    if "zotero_item_id" in resolution:
        value = int(resolution["zotero_item_id"])
        return _find_item(
            items,
            lambda item: item["item_id"] == value,
            f"override-zotero-item-id:{value}",
            clipping_title,
        )
    raise OverrideError(f"unsupported override resolution for {clipping_title!r}")


def generate_override_skeleton(match_report: dict[str, Any]) -> dict[str, Any]:
    overrides = []
    for match in match_report.get("matches", []):
        if match.get("status") == "matched":
            continue
        overrides.append(
            {
                "clipping_title": match["clipping_title"],
                "resolution": {
                    "citation_key": "",
                    "zotero_key": "",
                    "zotero_item_id": None,
                    "attachment_key": "",
                    "attachment_item_id": None,
                },
                "notes": "Fill exactly one item resolution field. Prefer citation_key when available. Optionally add attachment_key or attachment_item_id for ambiguous attachments.",
                "candidates": match.get("candidates", []),
            }
        )

    return {"format": OVERRIDES_FORMAT, "overrides": overrides}


def _clean_resolution(resolution: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key in (
        "citation_key",
        "zotero_key",
        "zotero_item_id",
        "attachment_key",
        "attachment_item_id",
    ):
        value = resolution.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        cleaned[key] = value.strip() if isinstance(value, str) else value
    return cleaned


def _find_item(
    items: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    reason: str,
    clipping_title: str,
) -> tuple[dict[str, Any] | None, str]:
    matches = [item for item in items if predicate(item)]
    if len(matches) == 1:
        return matches[0], reason
    if not matches:
        return None, f"override-unresolved:{clipping_title}"
    return None, f"override-ambiguous:{clipping_title}"
