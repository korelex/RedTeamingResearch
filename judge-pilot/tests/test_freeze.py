import json

import pytest

from src import freeze


def test_load_frozen_detects_tampering(tmp_path):
    dest = tmp_path / "ds"
    dest.mkdir()
    (dest / "runs.jsonl").write_text(json.dumps({"run_id": "a"}) + "\n")
    (dest / "SHA256SUMS").write_text(f"{freeze.sha256(dest / 'runs.jsonl')}  runs.jsonl\n")
    assert freeze.load_frozen("ds", root=tmp_path) == [{"run_id": "a"}]

    (dest / "runs.jsonl").write_text(json.dumps({"run_id": "b"}) + "\n")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        freeze.load_frozen("ds", root=tmp_path)
