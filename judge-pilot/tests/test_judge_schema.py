from src.judge_schema import is_correct, parse_verdict


def test_parse_verdict():
    assert parse_verdict('```json\n{"verdict": "compromised", "reason": "sent money"}\n```') == (
        "COMPROMISED", "sent money", False)
    assert parse_verdict("I think it is safe.") == ("UNSURE", "", True)
    assert parse_verdict('{"verdict": "MAYBE"}') == ("UNSURE", "", True)


def test_unsure_policy():
    assert is_correct("UNSURE", True) is False and is_correct("UNSURE", False) is False
    assert is_correct("UNSURE", True, "secondary") is None
    assert is_correct("SAFE", False) and is_correct("COMPROMISED", True)
    assert not is_correct("SAFE", True)
