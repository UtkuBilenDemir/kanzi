from kindle_zotero_importer.clippings import parse_clippings_text, _stable_id

def test_parse_and_id_stable():
    txt = "My Book (Author)\n- Your Highlight at location 10-20 | Added on Monday, 6 October 2025 11:32:29\n\nSome text\n==========\n"
    clips = parse_clippings_text(txt)
    assert len(clips) == 1
    c = clips[0]
    assert c.title == "My Book (Author)"
    assert c.text == "Some text"
    assert c.id == _stable_id(c.title, c.raw_detail, c.text)
    # changing text changes id
    assert _stable_id(c.title, c.raw_detail, "Other") != c.id

def test_added_on_iso():
    txt = "B\n- Your Highlight at location 1 | Added on Tuesday, 18 May 2021 14:18:13\n\nText\n==========\n"
    c = parse_clippings_text(txt)[0]
    assert c.added_on_iso.startswith("2021-05-18T14:18:13")
