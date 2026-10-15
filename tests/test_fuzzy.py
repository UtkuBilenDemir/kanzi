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
             "zotero":{"attachment":{"item_id":1,"key":"K1"},"parent_item_id":10,"parent_key":"P1","citation_key":"c1","related_items":[{"item_id":20,"key":"P2","citation_key":"c2"}]},
             "annotation":{"type":"highlight","text":"hi","position":{"type":"FragmentSelector","value":"cfi"}}}
        ]
    }
    plan = build_final_writer_plan(positioned)
    tags = plan["annotations"][0]["annotation"]["tags"]
    assert any(t["name"].startswith("kindle-id:") for t in tags)
    assert plan["annotations"][0]["related_items"][0]["item_id"] == 20


def test_pdf_tolerates_of_split_artifact():
    from kindle_zotero_importer.pdf_position import find_pdf_text_page, find_pdf_rects, PDFPageXML, PDFWord
    quote = "nothing other than idolatry of the machine and which"
    page_text = "nothing other than idolatry o f the machine and which"
    assert find_pdf_text_page([page_text], quote) == 0
    words = []
    cursor = 0
    for w in page_text.split():
        words.append(PDFWord(text=w, left=0.0, top=0.0, width=10.0, height=10.0, start=cursor, end=cursor + len(w)))
        cursor += len(w) + 1
    page = PDFPageXML(index=0, width=100.0, height=100.0, words=words)
    rects = find_pdf_rects("dummy.pdf", page, quote, {("dummy.pdf", 0): (100.0, 100.0)})
    assert rects is not None
    assert rects["pageIndex"] == 0
    assert rects["rects"]


def test_pdf_tolerates_punctuation_and_quotes():
    from kindle_zotero_importer.pdf_position import find_pdf_text_page
    quote = "This, then, gives rise to “intemperate technicism”."
    page = "this then gives rise to intemperate technicism"
    assert find_pdf_text_page([page], quote) == 0


def test_pdf_partial_half_anchors_spanning_text():
    from kindle_zotero_importer.pdf_position import find_pdf_text_page
    first = "A" * 70
    second = "Z" * 70
    quote = first + second
    page = "xx " + first.lower() + " yy"
    assert find_pdf_text_page([page], quote) == 0


def test_pdf_shingle_fallback_scattered_ocr_errors():
    from kindle_zotero_importer.pdf_position import find_pdf_text_page
    quote = (
        "Gerçekçi zındıklık yolunu tutuşsa bir mucize görse bile kendinde "
        "buna inanmamasım sağlayacak güç ve yeteneği bulur mucize yadsınaraz "
        "dururda bile olsa boyun eğmez"
    )
    page = (
        "gerçekçi zındıklık yolunu tutuşsa bir mucize görse bile kendinde "
        "buna inanmaması sağlayacak güç ve yeteneği bulur mucize yadsınamaz "
        "dururda bile olsa boyun eğmez"
    )
    assert find_pdf_text_page([page], quote) == 0


def test_page_hint_snippet_around_kindle_page():
    from kindle_zotero_importer.pdf_position import _page_hint_text
    pages = ["", "intro words here", "target page words here", "trailing words"]
    hint = _page_hint_text(pages, "3")
    assert hint is not None
    assert hint["kindle_page"] == "3"
    assert "target page words" in hint["text"]
    assert _page_hint_text(pages, None) is None
    assert _page_hint_text(pages, "99") is None


def test_citekey_mentions_become_zotero_links():
    from kindle_zotero_importer.import_plan import build_import_plan
    clippings_payload = {
        "format": "x",
        "clippings": [
            {
                "id": "c1",
                "title": "Book A",
                "kind": "highlight",
                "text": "As argued by @bookb2020, this follows.",
                "page": None,
                "location": "10",
            }
        ],
    }
    zotero_index = {
        "format": "x",
        "items": [
            {
                "item_id": 1,
                "key": "PARENT01",
                "title": "Book A",
                "fields": {"citationKey": "booka2020"},
                "attachments": [
                    {
                        "item_id": 11,
                        "key": "ATTACH01",
                        "title": "pdf",
                        "content_type": "application/pdf",
                        "path": "x.pdf",
                        "resolved_path": "x.pdf",
                    }
                ],
            },
            {
                "item_id": 2,
                "key": "TARGET02",
                "title": "Book B",
                "fields": {"citationKey": "bookb2020"},
                "attachments": [],
            },
        ],
    }
    match_report = {
        "format": "x",
        "matches": [
            {
                "clipping_title": "Book A",
                "status": "matched",
                "candidates": [{"item_id": 1}],
            }
        ],
    }
    plan = build_import_plan(clippings_payload, zotero_index, match_report, None)
    comment = plan["items"][0]["annotation"]["comment"] or ""
    assert "@bookb2020" in comment
    assert "zotero://select/library/items/TARGET02" in comment
    assert plan["items"][0]["zotero"]["related_items"] == [
        {
            "item_id": 2,
            "key": "TARGET02",
            "citation_key": "bookb2020",
            "link": "zotero://select/library/items/TARGET02",
        }
    ]
    # self-links are skipped
    clippings_payload["clippings"][0]["text"] = "See @booka2020 here."
    plan = build_import_plan(clippings_payload, zotero_index, match_report, None)
    assert "zotero://select" not in (plan["items"][0]["annotation"]["comment"] or "")
    assert plan["items"][0]["zotero"]["related_items"] == []


def test_historical_annotations_gain_citekey_relations():
    from kindle_zotero_importer.cli import _refresh_history_relations
    history = [
        {
            "clipping_id": "old",
            "parent_item_id": 1,
            "annotation": {
                "text": "An old highlight",
                "comment": "body without organs @deleuze1983",
            },
        }
    ]
    zotero_index = {
        "items": [
            {
                "item_id": 1,
                "key": "SOURCE01",
                "fields": {"citationKey": "simondon2017a"},
            },
            {
                "item_id": 2,
                "key": "TARGET02",
                "fields": {"citationKey": "deleuze1983"},
            },
        ]
    }
    _refresh_history_relations(history, zotero_index)
    assert history[0]["related_items"] == [
        {
            "item_id": 2,
            "key": "TARGET02",
            "citation_key": "deleuze1983",
            "link": "zotero://select/library/items/TARGET02",
        }
    ]


def test_group_library_targets_use_group_select_links():
    from kindle_zotero_importer.import_plan import _select_link
    assert (
        _select_link({"key": "ABC123", "group_id": 6644344})
        == "zotero://select/groups/6644344/items/ABC123"
    )
    assert (
        _select_link({"key": "ABC123", "group_id": None})
        == "zotero://select/library/items/ABC123"
    )
    assert (
        _select_link({"key": "ABC123"})
        == "zotero://select/library/items/ABC123"
    )


def test_epub_tolerates_extraction_artifacts():
    from kindle_zotero_importer.epub_position import find_epub_cfi, TextNode
    nodes = [TextNode(spine_index=0, cfi_parent_path="/4/2", text_step="1", text="idolatry o f the machine", start=0, end=24)]
    quote = "idolatry of the machine and which"
    # quote is longer than node, so exact fails; use full haystack variant
    nodes = [TextNode(spine_index=0, cfi_parent_path="/4/2", text_step="1", text="nothing other than idolatry o f the machine and which", start=0, end=53)]
    result = find_epub_cfi(nodes, quote)
    assert result is not None
    assert result["selector"]["value"].startswith("epubcfi(")
