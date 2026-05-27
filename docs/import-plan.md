# Import Plan Contract

The long-term plugin boundary is a JSON contract. Python can generate this contract during prototyping; a future Zotero plugin can either consume it or reimplement the same planning logic in TypeScript.

## Current Parser Output

```json
{
  "format": "kindle-zotero-importer.clippings.v1",
  "count": 1,
  "clippings": [
    {
      "id": "stable-hash-prefix",
      "title": "Book Title (Author)",
      "kind": "highlight",
      "text": "Highlighted text",
      "raw_detail": "- Your Highlight on page 10 | Location 100-101 | Added on ...",
      "page": "10",
      "location": "100-101",
      "added_on": "Kindle date string",
      "added_on_iso": "Parsed ISO datetime when recognized"
    }
  ]
}
```

## Future Import Plan

The final writer-facing plan should add matched Zotero targets and annotation positions:

```json
{
  "format": "kindle-zotero-importer.import-plan.v1",
  "items": [
    {
      "clipping_id": "stable-hash-prefix",
      "status": "matched",
      "confidence": "exact-text-match",
      "zotero": {
        "parent_item_id": 51395,
        "attachment_item_id": 51402,
        "attachment_type": "application/epub+zip"
      },
      "annotation": {
        "type": "highlight",
        "text": "Highlighted text",
        "comment": null,
        "color": "#ffd400",
        "pageLabel": "",
        "sortIndex": "00014|00047607",
        "position": {}
      }
    }
  ]
}
```
