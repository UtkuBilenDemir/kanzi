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


def _fuzzy_hash(text: str) -> str:
    # Trigram Jaccard-ish: sort unique trigrams of normalised text, hash them.
    # More tolerant to OCR swaps (rn/m, 1/l, 0/O) than strict SHA.
    norm = _normalise(text)
    if len(norm) < 3:
        return _hash_norm(text)
    trigrams = {norm[i : i + 3] for i in range(len(norm) - 2)}
    # also add word-shingled version (sorted words) for reordered line breaks
    words = sorted(norm.split())
    tri_words = {" ".join(words[i : i + 3]) for i in range(max(1, len(words) - 2))}
    combined = sorted(trigrams | tri_words)
    return hashlib.sha256(" ".join(combined).encode("utf-8")).hexdigest()[:16]


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
        raw = annotation.get("text") or clipping.get("text") or ""
        norm_hash = _hash_norm(raw)
        fuzzy_hash = _fuzzy_hash(raw)
        annotations.append(
            {
                "clipping_id": clipping["id"],
                "clipping_title": clipping["title"],
                "clipping_added_on": clipping.get("added_on"),
                "clipping_added_on_iso": clipping.get("added_on_iso"),
                "note_ids": clipping.get("note_ids", []),
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
                "fuzzy_hash": fuzzy_hash,
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
