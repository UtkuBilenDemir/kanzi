from kindle_zotero_importer.clippings import (
    Clipping,
    _stable_id,
    dedup_clippings,
    parse_clippings_text,
)

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


def _clipping(identifier, kind, text, location):
    return Clipping(
        id=identifier,
        title="Book",
        kind=kind,
        text=text,
        raw_detail="detail",
        location=location,
    )


def test_dedup_keeps_longest_progressive_highlight_revision():
    short = _clipping("short", "highlight", "A selection long enough to compare", "53-54")
    long = _clipping(
        "long",
        "highlight",
        "A selection long enough to compare and its extended ending",
        "53-55",
    )

    assert dedup_clippings([short, long]) == [long]


def test_dedup_preserves_unrelated_text_with_same_location_start():
    short = _clipping(
        "short",
        "highlight",
        "J. he is actually of obscure extraction and this is long enough",
        "53-54",
    )
    corrected = _clipping(
        "corrected",
        "highlight",
        "A. J. he is actually of obscure extraction and this is long enough",
        "53-55",
    )

    assert dedup_clippings([short, corrected]) == [short, corrected]


def test_dedup_preserves_same_text_at_different_locations():
    first = _clipping("first", "highlight", "A repeated sentence in a book", "10-11")
    second = _clipping("second", "highlight", "A repeated sentence in a book", "80-81")

    assert dedup_clippings([first, second]) == [first, second]


def test_dedup_never_collides_notes_with_highlights():
    highlight = _clipping("highlight", "highlight", "Same meaningful text", "10-11")
    note = _clipping("note", "note", "Same meaningful text", "11")

    assert dedup_clippings([highlight, note]) == [highlight, note]
