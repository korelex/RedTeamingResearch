"""Offline tests: no model calls, no credentials needed."""

import json
import threading

from src.logger import RUN_FIELDS, RunLogger, extract_tool_calls, make_run_id, state_diff
from src.runner import RunSpec, pending_specs

MODEL = "gemini-test"


def _record(run_id, error=None, **kw):
    rec = {f: None for f in RUN_FIELDS}
    rec.update(run_id=run_id, error=error, transcript=[], tool_calls=[], state_available=False,
               state_snapshot_omitted=False, tokens_in=0, tokens_out=0, est_cost_usd=0.0)
    rec.update(kw)
    return rec


def test_run_id_stable_and_differs_across_repeats():
    a = make_run_id("banking", "user_task_0", "injection_task_0", "important_instructions", 0, MODEL)
    b = make_run_id("banking", "user_task_0", "injection_task_0", "important_instructions", 0, MODEL)
    c = make_run_id("banking", "user_task_0", "injection_task_0", "important_instructions", 1, MODEL)
    assert a == b
    assert a != c
    assert len(a) == 16 and all(ch in "0123456789abcdef" for ch in a)
    # null parts are encoded as "none"
    assert make_run_id("banking", "user_task_0", None, None, 0, MODEL) == make_run_id(
        "banking", "user_task_0", "none", "none", 0, MODEL
    )
    spec = RunSpec("banking", "user_task_0", None, None, 0)
    assert spec.run_id(MODEL) == make_run_id("banking", "user_task_0", None, None, 0, MODEL)


def test_resume_skips_completed_and_retries_errored(tmp_path):
    ok = RunSpec("banking", "user_task_0", "injection_task_0", "important_instructions", 0)
    failed = RunSpec("banking", "user_task_1", "injection_task_0", "important_instructions", 0)
    failed_then_ok = RunSpec("slack", "user_task_1", "injection_task_1", "important_instructions", 0)
    new = RunSpec("slack", "user_task_2", "injection_task_1", "important_instructions", 0)
    err = {"type": "ServerError", "message": "503", "traceback": ""}
    lines = [
        _record(ok.run_id(MODEL)),
        _record(failed.run_id(MODEL), error=err),
        _record(failed_then_ok.run_id(MODEL), error=err),
        _record(failed_then_ok.run_id(MODEL)),
    ]
    (tmp_path / "2026-01-01.jsonl").write_text("\n".join(json.dumps(r) for r in lines) + "\n{not json\n")
    todo = pending_specs([ok, failed, failed_then_ok, new], MODEL, tmp_path)
    assert todo == [failed, new]


def test_logger_lines_parse_as_json(tmp_path):
    logger = RunLogger(tmp_path, "2026-01-01")
    weird = {"text": 'quotes " and \n newlines and unicode é ☃', "nested": [{"a": 1}]}

    def worker(i):
        logger.write(_record(f"{i:016x}", transcript=[weird], injection_text={"v": "x\ny"}))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = logger.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    for line in lines:
        obj = json.loads(line)
        assert list(obj.keys()) == RUN_FIELDS
        assert obj["transcript"][0] == weird


def test_state_diff_small_dicts():
    before = {"balance": 100, "tx": [{"id": 1, "amt": 5}], "name": "a", "gone": True}
    after = {"balance": 90, "tx": [{"id": 1, "amt": 5}, {"id": 2, "amt": 10}], "name": "a", "new": 1}
    diff = state_diff(before, after)
    assert {"path": "/balance", "before": 100, "after": 90} in diff
    assert {"path": "/tx/1", "before": None, "after": {"id": 2, "amt": 10}} in diff
    assert {"path": "/gone", "before": True, "after": None} in diff
    assert {"path": "/new", "before": None, "after": 1} in diff
    assert len(diff) == 4
    assert state_diff(before, before) == []


def test_extract_tool_calls_pairs_results():
    transcript = [
        {"role": "user", "content": [{"type": "text", "content": "hi"}]},
        {"role": "assistant", "content": [], "tool_calls": [
            {"function": "f", "args": {"x": 1}, "id": None},
            {"function": "g", "args": {}, "id": None},
        ]},
        {"role": "tool", "tool_call": {"function": "f", "args": {"x": 1}}, "tool_call_id": None,
         "content": [{"type": "text", "content": "r1"}], "error": None},
        {"role": "tool", "tool_call": {"function": "g", "args": {}}, "tool_call_id": None,
         "content": [{"type": "text", "content": ""}], "error": "boom"},
    ]
    assert extract_tool_calls(transcript) == [
        {"order": 0, "name": "f", "args": {"x": 1}, "result": "r1"},
        {"order": 1, "name": "g", "args": {}, "result": "boom"},
    ]


def _fake_response(finish_reason, text=None, prompt=10, out=2):
    from types import SimpleNamespace as NS

    parts = [NS(text=text, function_call=None)] if text else None
    content = NS(parts=parts) if parts else None
    return NS(
        candidates=[NS(finish_reason=finish_reason, content=content)],
        usage_metadata=NS(prompt_token_count=prompt, candidates_token_count=out, thoughts_token_count=1),
    )


class _FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_content(self, *, model, contents, config):
        self.calls += 1
        return self.responses.pop(0)


def _wrapper(responses):
    from src.runner import UsageAccumulator, _InstrumentedModels

    acc = UsageAccumulator()
    fake = _FakeModels(responses)
    models = _InstrumentedModels(fake, acc, seed=7, timeout_ms=None, retry={})
    models.malformed_sleep_s = 0.0
    return models, fake, acc


def test_malformed_response_becomes_error_after_two_retries():
    from src.runner import malformed_error

    models, fake, acc = _wrapper([_fake_response("MALFORMED_RESPONSE")] * 3)
    resp = models.generate_content(model="m", contents=[], config=None)
    assert fake.calls == 3  # 1 call + 2 in-wrapper retries
    assert response_is(resp, "MALFORMED_RESPONSE")
    assert acc.finish_reasons == ["MALFORMED_RESPONSE"] * 3
    assert acc.malformed is True
    assert acc.tokens_in == 30 and acc.tokens_out == 9  # every billed attempt is counted
    assert acc.seeds == [7]
    err = malformed_error(acc)
    assert err["type"] == "MalformedResponse" and "MALFORMED_RESPONSE" in err["message"]


def test_malformed_then_ok_is_not_error():
    from src.runner import malformed_error

    models, fake, acc = _wrapper([_fake_response("SAFETY"), _fake_response("STOP", text="hi")])
    models.generate_content(model="m", contents=[], config=None)
    assert fake.calls == 2
    assert acc.finish_reasons == ["SAFETY", "STOP"]
    assert acc.malformed is False and malformed_error(acc) is None


def response_is(resp, reason):
    return resp.candidates[0].finish_reason == reason


def test_rerun_ids_override_completed(tmp_path):
    ok = RunSpec("banking", "user_task_0", "injection_task_0", "important_instructions", 0)
    (tmp_path / "x.jsonl").write_text(json.dumps(_record(ok.run_id(MODEL))) + "\n")
    assert pending_specs([ok], MODEL, tmp_path) == []
    assert pending_specs([ok], MODEL, tmp_path, rerun_ids={ok.run_id(MODEL)}) == [ok]


def test_stratified_per_injection_sampling():
    from collections import Counter

    from src.runner import stratified_per_injection_pairs

    uts = [f"user_task_{i}" for i in range(16)]
    its = [f"injection_task_{i}" for i in range(9)]
    pairs = stratified_per_injection_pairs("banking", uts, its, 4, 0)
    assert len(pairs) == 4 * len(its)
    assert {it for _, _, it in pairs} == set(its)
    for it in its:
        per_it = [ut for _, ut, i in pairs if i == it]
        assert len(per_it) == 4 and len(set(per_it)) == 4  # no replacement within an injection task
    counts = Counter(ut for _, ut, _ in pairs)
    full = [counts.get(ut, 0) for ut in uts]
    assert max(full) - min(full) <= 1
    assert pairs == stratified_per_injection_pairs("banking", uts, its, 4, 0)  # deterministic
    assert pairs != stratified_per_injection_pairs("banking", uts, its, 4, 1)
    import pytest

    with pytest.raises(SystemExit):
        stratified_per_injection_pairs("banking", uts, its, 17, 0)
