import json, tempfile, pathlib
from pathlib import Path

def test_incremental_ids(tmp_path: Path):
    # simulate previous final with one integrated id
    prev_final = {"annotations":[{"clipping_id":"aaa"}]}
    (tmp_path/"import-plan.final.json").write_text(json.dumps(prev_final))
    prev_clipp = {"clippings":[{"id":"aaa","title":"T"},{"id":"bbb","title":"U"}]}
    (tmp_path/"clippings.json").write_text(json.dumps(prev_clipp))

    new_ids = {"aaa","bbb","ccc"}  # ccc is new
    prev_integrated = {"aaa"}
    to_process = new_ids - prev_integrated
    assert to_process == {"bbb","ccc"}
    deletions = prev_integrated - new_ids
    assert deletions == set()  # none removed
    # changed: aaa text changed -> new id ddd, old aaa no longer in new -> deletion
    new_ids2 = {"ddd","bbb","ccc"}
    assert (prev_integrated - new_ids2) == {"aaa"}
