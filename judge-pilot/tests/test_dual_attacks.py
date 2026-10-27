import src.runner  # noqa: F401  (imports src.dual_attacks, as the runner does)
from agentdojo.attacks.attack_registry import ATTACKS

from src.dual_attacks import D1_TEMPLATE, D2_TEMPLATE, D3_TEMPLATE, DAY3_ATTACKS


def test_registered_with_agentdojo():
    for name in DAY3_ATTACKS:
        assert name in ATTACKS


def test_templates_fill_like_important_instructions():
    for t in (D1_TEMPLATE, D2_TEMPLATE, D3_TEMPLATE):
        out = t.format(goal="Send money to X.", user="Emma Johnson", model="AI model developed by Google", task="t")
        assert "Send money to X." in out and "{" not in out
    assert "NOTE TO REVIEWERS" in D1_TEMPLATE and "routine" in D2_TEMPLATE
    assert "INFORMATION" not in D3_TEMPLATE and "important message" not in D3_TEMPLATE
