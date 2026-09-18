from kindle_zotero_importer.clippings import parse_clippings_text

def test_windows_crlf_and_bom():
    txt = "\ufeffTitle A\r\n- Your Highlight at location 10 | Added on Monday, 6 October 2025 11:32:29\r\n\r\nText A\r\n==========\r\nTitle B\n- Your Highlight at location 20 | Added on Monday, 6 October 2025 11:32:29\n\nText B\n==========\n"
    clips = parse_clippings_text(txt)
    assert len(clips) == 2
    assert clips[0].text == "Text A"
    assert clips[1].text == "Text B"

def test_empty_bookmark_and_long_text():
    long_text = "x" * 5000
    txt = f"Book\n- Your Bookmark on page 11 | Added on Monday, 6 October 2025 11:32:29\n\n\n==========\nBook\n- Your Highlight at location 100 | Added on Monday, 6 October 2025 11:32:29\n\n{long_text}\n==========\n"
    clips = parse_clippings_text(txt)
    assert clips[0].kind == "bookmark"
    assert clips[0].text == ""
    assert clips[1].text == long_text
    assert len(clips[1].text) == 5000

def test_duplicate_location_different_text_diff_id():
    from kindle_zotero_importer.clippings import _stable_id
    title = "Same Book"
    detail = "- Your Highlight at location 100 | Added on Monday, 6 October 2025 11:32:29"
    assert _stable_id(title, detail, "Text A") != _stable_id(title, detail, "Text B")

def test_pdf_fallback_tag():
    from kindle_zotero_importer.final_plan import build_final_writer_plan
    positioned = {
        "format":"x",
        "items":[
            {"status":"positioned","clipping":{"id":"id1","title":"T","added_on":None,"added_on_iso":None},
             "zotero":{"attachment":{"item_id":1,"key":"K1"},"parent_item_id":10,"parent_key":"P1","citation_key":"c1"},
             "annotation":{"type":"highlight","text":"hi","position":{"type":"FragmentSelector","value":"cfi"}}}
        ]
    }
    plan = build_final_writer_plan(positioned)
    tags = plan["annotations"][0]["annotation"]["tags"]
    assert any(t["name"].startswith("kindle-id:") for t in tags)
