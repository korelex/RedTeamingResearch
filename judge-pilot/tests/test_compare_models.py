import json

import pytest

from src import compare_models as cm
from src.inspect_run import dedupe_runs, load_records


def rec(run_id, model, ut="u1", inj="i1", repeat=0, strict=False, seen=True, cost=0.01,
        error=None, last="Done.", baseline=False, **extra):
    r = {
        "run_id": run_id, "model_id": model, "suite": "banking", "user_task_id": ut,
        "injection_task_id": None if baseline else inj, "attack": None if baseline else "ii",
        "repeat": repeat, "is_baseline": baseline,
        "compromised": None if baseline else strict, "compromised_strict": None if baseline else strict,
        "injection_seen": None if baseline else seen, "utility": True,
        "transcript": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": last}],
        "tokens_in": 100, "tokens_out": 10, "est_cost_usd": cost, "duration_s": 2.0,
        "error": error, "malformed": False,
    }
    r.update(extra)
    return r


def write(tmp_path, records):
    d = tmp_path / "runs"
    d.mkdir()
    (d / "a.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return d


def stats(d, model):
    lines = load_records(d)
    return cm.model_stats(model, lines, dedupe_runs(lines))


def test_per_model_aggregation(tmp_path):
    recs = [
        rec("a1", "A", strict=True, cost=0.10),
        rec("a2", "A", ut="u2", strict=False, cost=0.10),
        rec("a3", "A", ut="u3", baseline=True, cost=0.10),
        rec("a4", "A", ut="u4", error={"type": "X", "message": "m"}, cost=0.05),  # errored, still billed
        rec("b1", "B", strict=True, cost=1.0),
    ]
    d = write(tmp_path, recs)
    s = stats(d, "A")
    assert (s["runs"], s["completed"], s["errored"]) == (4, 3, 1)
    assert s["total_cost"] == pytest.approx(0.35)
    assert s["cost_per_completed"] == pytest.approx(0.35 / 3)
    assert s["strict"] == (1, 2)
    assert s["baseline_utility"] == (1, 1)
    assert s["judge_ready"] == 2
    assert s["cost_per_strict"] == pytest.approx(0.35)
    assert s["strict_given_seen"] == (1, 2)
    assert stats(d, "B")["total_cost"] == pytest.approx(1.0)


def test_repeat_agreement_and_malformed(tmp_path):
    recs = [
        rec("a1", "A", repeat=0, strict=True),
        rec("a2", "A", repeat=1, strict=False),
        rec("a3", "A", ut="u2", repeat=0, strict=True),
        rec("a4", "A", ut="u2", repeat=1, strict=True, malformed=True),
    ]
    s = stats(write(tmp_path, recs), "A")
    assert s["agreement"] == (1, 2)
    assert s["malformed"] == (1, 4)


def test_paired_mcnemar_zero_vs_six(tmp_path):
    recs = []
    for i in range(6):
        recs.append(rec(f"a{i}", "A", ut=f"u{i}", strict=False))
        recs.append(rec(f"b{i}", "B", ut=f"u{i}", strict=True))
    recs.append(rec("a9", "A", ut="u9", strict=True))
    recs.append(rec("b9", "B", ut="u9", strict=True))
    recs.append(rec("a10", "A", ut="u10", strict=False))
    recs.append(rec("b10", "B", ut="u10", strict=False))
    recs.append(rec("a11", "A", ut="u11", strict=True))  # B missing -> not a pair
    d = write(tmp_path, recs)
    p = cm.paired_counts(dedupe_runs(load_records(d)), "A", "B")
    assert (p["n"], p["both"], p["only_a"], p["only_b"], p["neither"]) == (8, 1, 0, 6, 1)
    assert p["p"] == pytest.approx(0.03125)
    assert cm.mcnemar_exact(0, 0) == 1.0
    assert cm.mcnemar_exact(3, 3) == 1.0


def test_clarifying_detection(tmp_path):
    assert cm.is_clarifying(rec("x", "A", last="Which account?"))
    assert cm.is_clarifying(rec("x", "A", last=[{"type": "text", "content": "Sure, which one? "}]))
    assert not cm.is_clarifying(rec("x", "A", last="All done."))
    assert not cm.is_clarifying({"transcript": []})
    d = write(tmp_path, [rec("a1", "A", last="Which?"), rec("a2", "A", ut="u2")])
    assert stats(d, "A")["clarifying"] == (1, 2)


def test_single_model_and_missing_model(tmp_path, capsys):
    d = write(tmp_path, [rec("a1", "A", strict=True)])
    cfg = tmp_path / "config.yaml"
    cfg.write_text("spend_cap_usd: 5\n")
    assert cm.main(["--config", str(cfg), "--data-dir", str(d)]) == 0
    out = capsys.readouterr().out
    assert "skipped: needs exactly 2 models" in out
    assert cm.main(["--config", str(cfg), "--data-dir", str(d), "--models", "A", "Z"]) == 0
    out = capsys.readouterr().out
    assert "n/a" in out  # zero-run model renders without crashing


def test_two_model_verdict(tmp_path, capsys):
    recs = [rec("a1", "A", strict=False, cost=0.1), rec("b1", "B", strict=True, cost=0.5)]
    d = write(tmp_path, recs)
    cfg = tmp_path / "config.yaml"
    cfg.write_text("x: 1\n")
    assert cm.main(["--config", str(cfg), "--data-dir", str(d)]) == 0
    out = capsys.readouterr().out
    assert "B costs 5.0x A per run" in out
    assert "McNemar p=1" in out
