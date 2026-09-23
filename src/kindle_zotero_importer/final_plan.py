from __future__ import annotations

import datetime
import hashlib
import re
import unicodedata
from typing import Any


def _normalise(text: str) -> str:
    if not text:
        return ""
    # NFKC, lower, strip, de-hyphenate, collapse whitespace/punct
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"-\s*\n\s*", "", t)  # de-hyphenate line breaks
    t = re.sub(r"[\u2010-\u2015\u2018\u2019\u201c\u201d]", "'", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _hash_norm(text: str) -> str:
    return hashlib.sha256(_normalise(text).encode("utf-8")).hexdigest()[:16]


FINAL_FORMAT = "kindle-zotero-importer.zotero-writer-plan.v1"


def build_final_writer_plan(positioned_plan: dict[str, Any]) -> dict[str, Any]:
    annotations = []
    skipped: dict[str, int] = {}
    for item in positioned_plan["items"]:
        if item.get("status") != "positioned":
            skipped[item["status"]] = skipped.get(item["status"], 0) + 1
            continue
        attachment = item["zotero"]["attachment"]
        annotation = item["annotation"]
        if not annotation.get("position"):
            skipped["positioned-missing-writer-fields"] = (
                skipped.get("positioned-missing-writer-fields", 0) + 1
            )
            continue
        clipping = item["clipping"]
        # robust identifiers for cross-library unification
        norm_hash = _hash_norm(annotation.get("text") or clipping.get("text") or "")
        annotations.append(
            {
                "clipping_id": clipping["id"],
                "clipping_title": clipping["title"],
                "clipping_added_on": clipping.get("added_on"),
                "clipping_added_on_iso": clipping.get("added_on_iso"),
                "integrated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "attachment_item_id": attachment["item_id"],
                "attachment_key": attachment["key"],
                "parent_item_id": item["zotero"]["parent_item_id"],
                "parent_key": item["zotero"]["parent_key"],
                "citation_key": item["zotero"].get("citation_key"),
                "doi": item["zotero"].get("doi"),
                "isbn": item["zotero"].get("isbn"),
                "issn": item["zotero"].get("issn"),
                "publication_title": item["zotero"].get("publication_title"),
                "norm_hash": norm_hash,
                "annotation": {
                    "type": annotation["type"],
                    "text": annotation.get("text") or "",
                    "comment": annotation.get("comment") or "",
                    "color": annotation.get("color") or "#ffd400",
                    "pageLabel": annotation.get("pageLabel") or "",
                    "sortIndex": annotation.get("sortIndex"),
                    "position": annotation["position"],
                    "tags": [
                        {"name": "kindle-import"},
                        {"name": f"kindle-id:{clipping['id']}"},
                    ],
                },
            }
        )

    annotations.sort(
        key=lambda entry: (
            entry.get("attachment_item_id") or 0,
            entry["annotation"].get("sortIndex") or "",
            entry.get("clipping_id") or "",
        )
    )

    return {
        "format": FINAL_FORMAT,
        "source_format": positioned_plan.get("format"),
        "annotation_count": len(annotations),
        "skipped_counts": skipped,
        "annotations": annotations,
    }
