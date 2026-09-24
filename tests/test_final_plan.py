from kindle_zotero_importer.final_plan import build_final_writer_plan

def test_final_includes_kindle_id_tag():
    positioned = {
        "format":"x",
        "items":[
            {"status":"positioned","clipping":{"id":"abc123","title":"T","added_on":None,"added_on_iso":None,"note_ids":["note1"]},
             "zotero":{"attachment":{"item_id":1,"key":"K1"},"parent_item_id":10,"parent_key":"P1","citation_key":"c1"},
             "annotation":{"type":"highlight","text":"hi","position":{"type":"FragmentSelector","value":"cfi"}}}
        ]
    }
    plan = build_final_writer_plan(positioned)
    assert plan["annotation_count"]==1
    tags = plan["annotations"][0]["annotation"]["tags"]
    assert {"name":"kindle-import"} in tags
    assert {"name":"kindle-id:abc123"} in tags
    assert plan["annotations"][0]["clipping_id"]=="abc123"
    assert plan["annotations"][0]["note_ids"] == ["note1"]

def test_final_skips_non_positioned():
    positioned = {"format":"x","items":[{"status":"epub-text-not-found","clipping":{"id":"a"},"zotero":{},"annotation":{}}]}
    plan = build_final_writer_plan(positioned)
    assert plan["annotation_count"]==0
    assert plan["skipped_counts"]["epub-text-not-found"]==1
