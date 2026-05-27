from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import sqlite3
from typing import Any


METADATA_FIELDS = (
    "title",
    "publicationTitle",
    "shortTitle",
    "DOI",
    "ISBN",
    "date",
    "url",
    "citationKey",
)


@dataclass(frozen=True)
class ZoteroAttachment:
    item_id: int
    key: str
    title: str | None
    content_type: str | None
    path: str | None
    resolved_path: str | None


@dataclass(frozen=True)
class ZoteroItem:
    item_id: int
    key: str
    item_type: str
    title: str | None
    creators: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    attachments: list[ZoteroAttachment] = field(default_factory=list)


def build_zotero_index(db_path: str, storage_root: str | None = None) -> dict[str, Any]:
    db_uri = f"file:{Path(db_path)}?mode=ro&immutable=1"
    with sqlite3.connect(db_uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        items = _load_parent_items(connection)
        creators = _load_creators(connection)
        attachments = _load_attachments(connection, storage_root)

    indexed_items: list[ZoteroItem] = []
    for row in items:
        fields = _metadata_for_item(row)
        indexed_items.append(
            ZoteroItem(
                item_id=row["itemID"],
                key=row["key"],
                item_type=row["typeName"],
                title=fields.get("title"),
                creators=creators.get(row["itemID"], []),
                fields=fields,
                attachments=attachments.get(row["itemID"], []),
            )
        )

    return {
        "format": "kindle-zotero-importer.zotero-index.v1",
        "database": str(db_path),
        "count": len(indexed_items),
        "attachment_count": sum(len(item.attachments) for item in indexed_items),
        "items": [_item_to_dict(item) for item in indexed_items],
    }


def _load_parent_items(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    field_columns = ",\n".join(
        f"MAX(CASE WHEN fc.fieldName = '{field_name}' THEN idv.value END) AS {field_name}"
        for field_name in METADATA_FIELDS
    )
    query = f"""
        SELECT
            i.itemID,
            i.key,
            it.typeName,
            {field_columns}
        FROM items i
        JOIN itemTypesCombined it ON it.itemTypeID = i.itemTypeID
        LEFT JOIN itemData id ON id.itemID = i.itemID
        LEFT JOIN fieldsCombined fc ON fc.fieldID = id.fieldID
        LEFT JOIN itemDataValues idv ON idv.valueID = id.valueID
        WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
          AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
        GROUP BY i.itemID
        ORDER BY title COLLATE NOCASE
    """
    return list(connection.execute(query))


def _load_creators(connection: sqlite3.Connection) -> dict[int, list[str]]:
    rows = connection.execute(
        """
        SELECT ic.itemID, c.firstName, c.lastName, c.fieldMode
        FROM itemCreators ic
        JOIN creators c ON c.creatorID = ic.creatorID
        ORDER BY ic.itemID, ic.orderIndex
        """
    )
    creators: dict[int, list[str]] = {}
    for row in rows:
        creators.setdefault(row["itemID"], []).append(_format_creator(row))
    return creators


def _load_attachments(
    connection: sqlite3.Connection, storage_root: str | None
) -> dict[int, list[ZoteroAttachment]]:
    rows = connection.execute(
        """
        SELECT
            a.parentItemID,
            a.itemID,
            i.key,
            a.contentType,
            a.path,
            idv.value AS title
        FROM itemAttachments a
        JOIN items i ON i.itemID = a.itemID
        LEFT JOIN itemData id ON id.itemID = a.itemID
        LEFT JOIN fieldsCombined fc ON fc.fieldID = id.fieldID AND fc.fieldName = 'title'
        LEFT JOIN itemDataValues idv ON idv.valueID = id.valueID
        WHERE a.parentItemID IS NOT NULL
          AND a.contentType IN ('application/pdf', 'application/epub+zip')
          AND a.itemID NOT IN (SELECT itemID FROM deletedItems)
        ORDER BY a.parentItemID, title COLLATE NOCASE
        """
    )
    attachments: dict[int, list[ZoteroAttachment]] = {}
    for row in rows:
        attachment = ZoteroAttachment(
            item_id=row["itemID"],
            key=row["key"],
            title=row["title"],
            content_type=row["contentType"],
            path=row["path"],
            resolved_path=_resolve_attachment_path(
                row["path"], row["key"], storage_root
            ),
        )
        attachments.setdefault(row["parentItemID"], []).append(attachment)
    return attachments


def _metadata_for_item(row: sqlite3.Row) -> dict[str, str]:
    return {
        field_name: row[field_name] for field_name in METADATA_FIELDS if row[field_name]
    }


def _format_creator(row: sqlite3.Row) -> str:
    first_name = (row["firstName"] or "").strip()
    last_name = (row["lastName"] or "").strip()
    if row["fieldMode"] == 1:
        return last_name or first_name
    return " ".join(part for part in (first_name, last_name) if part)


def _resolve_attachment_path(
    path: str | None, key: str, storage_root: str | None
) -> str | None:
    if not path:
        return None
    if path.startswith("storage:"):
        if not storage_root:
            return path
        return str(Path(storage_root) / key / path.removeprefix("storage:"))
    if path.startswith("attachments:"):
        return path
    return path


def _item_to_dict(item: ZoteroItem) -> dict[str, Any]:
    data = asdict(item)
    data["attachments"] = [asdict(attachment) for attachment in item.attachments]
    return data
