from kindle_zotero_importer.overrides import load_overrides, OverrideError

def test_ignore_only():
    payload = {"format":"kindle-zotero-importer.match-overrides.v1","overrides":[{"clipping_title":"A","resolution":{"ignore":True},"review":{}}]}
    assert load_overrides(payload)["A"] == {"ignore": True}

def test_ignore_with_other_fails():
    payload = {"format":"kindle-zotero-importer.match-overrides.v1","overrides":[{"clipping_title":"A","resolution":{"ignore":True,"citation_key":"foo"},"review":{}}]}
    try:
        load_overrides(payload)
        assert False, "should have raised"
    except OverrideError:
        pass

def test_single_field_ok():
    for res in [{"citation_key":"foo"},{"zotero_key":"ABC12345"},{"zotero_item_id":12}]:
        payload = {"format":"kindle-zotero-importer.match-overrides.v1","overrides":[{"clipping_title":"A","resolution":res,"review":{}}]}
        assert "A" in load_overrides(payload)

def test_multi_field_fails():
    payload = {"format":"kindle-zotero-importer.match-overrides.v1","overrides":[{"clipping_title":"A","resolution":{"citation_key":"a","zotero_key":"b"},"review":{}}]}
    try:
        load_overrides(payload)
        assert False
    except OverrideError:
        pass
