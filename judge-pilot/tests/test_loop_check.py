from src.loop_check import signals


def test_loop_signals():
    call = {"name": "read_file", "args": {"file_path": "a.txt"}}
    looping = {"tool_calls": [call, call, call, {"name": "x", "args": {}}], "finish_reasons": ["STOP"] * 16, "tokens_out": 1600}
    s = signals(looping)
    assert s["dup_calls"] == 2 and s["max_streak"] == 3 and s["model_calls"] == 16
    assert set(s["flags"]) == {"dup_calls", "max_streak", "model_calls"}
    clean = {"tool_calls": [call], "finish_reasons": ["STOP", "STOP"], "tokens_out": 500}
    assert signals(clean)["flags"] == []
    thinking = {"tool_calls": [], "finish_reasons": ["MAX_TOKENS"], "tokens_out": 65000}
    assert set(signals(thinking)["flags"]) == {"out_per_call", "max_tokens"}
