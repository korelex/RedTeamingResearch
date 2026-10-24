from src.analyze_day2 import binom_upper, fisher_greater, holm, kappa, mcnemar_one_sided


def test_exact_tests():
    assert binom_upper(0, 5) == 1.0 and abs(binom_upper(5, 5) - 1 / 32) < 1e-12
    assert mcnemar_one_sided(0, 0) == 1.0
    assert abs(mcnemar_one_sided(8, 1) - 10 / 512) < 1e-12
    # 3/3 vs 0/3: P = 1 / C(6,3)
    assert abs(fisher_greater(3, 3, 0, 3) - 1 / 20) < 1e-12
    assert fisher_greater(0, 3, 3, 3) == 1.0


def test_holm_and_kappa():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == {"a": 0.03, "c": 0.06, "b": 0.06}
    assert kappa([("A", "A"), ("B", "B")]) == 1.0
    assert kappa([("A", "B"), ("B", "A")]) == -1.0
