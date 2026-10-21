"""Read-only comparison of agent models (quality vs cost) over recorded runs.

Usage (from the project root):
    python -m src.compare_models --config config.yaml [--data-dir data/runs] [--models A B]
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.inspect_run import dedupe_runs, is_baseline, load_records, text_of_content, run_label
from src.morning_check import _load_config, wilson_interval

DEFAULT_DATA_DIR = "data/runs"


def _num(v: Any) -> float | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _div(a: float, b: float) -> float | None:
    return a / b if b else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _fmt_rate(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.1f}%)" if n else f"{k}/{n} (n/a)"


def _fmt_rate_ci(k: int, n: int) -> str:
    ci = wilson_interval(k, n)
    if ci is None:
        return f"{k}/{n} (n/a)"
    return f"{k}/{n} {100 * k / n:.1f}% [{ci[0]:.2f},{ci[1]:.2f}]"


def _fmt_usd(v: float | None, digits: int = 4) -> str:
    return "n/a" if v is None else f"${v:.{digits}f}"


def _fmt_f(v: float | None, digits: int = 1) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}"


def final_assistant_text(rec: dict[str, Any]) -> str:
    """Text of the last transcript message with role 'assistant' ('' if none)."""
    transcript = rec.get("transcript")
    if not isinstance(transcript, list):
        return ""
    for msg in reversed(transcript):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            return text_of_content(msg.get("content"))
    return ""


def is_clarifying(rec: dict[str, Any]) -> bool:
    return final_assistant_text(rec).strip().endswith("?")


def run_key(rec: dict[str, Any]) -> tuple:
    return (
        rec.get("suite"),
        rec.get("user_task_id"),
        rec.get("injection_task_id"),
        rec.get("attack"),
        rec.get("repeat"),
    )


def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value from discordant counts (binomial, p=0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def model_stats(model: str, all_lines: list[dict], runs: list[dict]) -> dict[str, Any]:
    lines = [r for r in all_lines if run_label(r) == model]
    mruns = [r for r in runs if run_label(r) == model]
    completed = [r for r in mruns if r.get("error") is None]
    errored = [r for r in mruns if r.get("error") is not None]
    attacked = [r for r in completed if not is_baseline(r)]
    baseline = [r for r in completed if is_baseline(r)]

    total_cost = sum(c for c in (_num(r.get("est_cost_usd")) for r in lines) if c is not None)

    def avg(field: str) -> float | None:
        return _mean([v for v in (_num(r.get(field)) for r in completed) if v is not None])

    def util(rs: list[dict]) -> tuple[int, int]:
        scored = [r for r in rs if isinstance(r.get("utility"), bool)]
        return sum(r["utility"] for r in scored), len(scored)

    def flag(rs: list[dict], field: str) -> tuple[int, int]:
        scored = [r for r in rs if isinstance(r.get(field), bool)]
        return sum(r[field] for r in scored), len(scored)

    seen = [r for r in attacked if r.get("injection_seen") is True]
    seen_scored = [r for r in attacked if isinstance(r.get("injection_seen"), bool)]
    strict_scored = [r for r in attacked if isinstance(r.get("compromised_strict"), bool)]
    strict_total = sum(r["compromised_strict"] for r in strict_scored)
    seen_strict = [r for r in seen if isinstance(r.get("compromised_strict"), bool)]

    groups: dict[tuple, list[bool]] = defaultdict(list)
    for r in strict_scored:
        groups[run_key(r)[:4]].append(r["compromised_strict"])
    multi = [v for v in groups.values() if len(v) >= 2]

    malformed_ids = {str(r.get("run_id")) for r in lines if r.get("malformed") is True}
    run_ids = {str(r.get("run_id")) for r in mruns}

    return {
        "model": model,
        "runs": len(mruns),
        "completed": len(completed),
        "errored": len(errored),
        "total_cost": total_cost,
        "cost_per_completed": _div(total_cost, len(completed)),
        "avg_tokens_in": avg("tokens_in"),
        "avg_tokens_out": avg("tokens_out"),
        "avg_duration": avg("duration_s"),
        "baseline_utility": util(baseline),
        "attacked_utility": util(attacked),
        "loose": flag(attacked, "compromised"),
        "strict": flag(attacked, "compromised_strict"),
        "seen": (len(seen), len(seen_scored)),
        "strict_given_seen": (sum(r["compromised_strict"] for r in seen_strict), len(seen_strict)),
        "clarifying": (sum(1 for r in completed if is_clarifying(r)), len(completed)),
        "malformed": (len(malformed_ids & run_ids), len(mruns)),
        "agreement": (sum(1 for v in multi if len(set(v)) == 1), len(multi)),
        "judge_ready": len(seen),
        "cost_per_judge_ready": _div(total_cost, len(seen)),
        "cost_per_strict": _div(total_cost, strict_total),
        "strict_total": strict_total,
    }


def paired_counts(runs: list[dict], a: str, b: str) -> dict[str, Any]:
    """Pairs completed for both models with a boolean compromised_strict on both sides."""

    def index(model: str) -> dict[tuple, dict]:
        return {
            run_key(r): r
            for r in runs
            if run_label(r) == model and r.get("error") is None and not is_baseline(r)
        }

    ia, ib = index(a), index(b)
    both = only_a = only_b = neither = 0
    for key in ia.keys() & ib.keys():
        va, vb = ia[key].get("compromised_strict"), ib[key].get("compromised_strict")
        if not (isinstance(va, bool) and isinstance(vb, bool)):
            continue
        if va and vb:
            both += 1
        elif va:
            only_a += 1
        elif vb:
            only_b += 1
        else:
            neither += 1
    return {
        "n": both + only_a + only_b + neither,
        "both": both,
        "only_a": only_a,
        "only_b": only_b,
        "neither": neither,
        "p": mcnemar_exact(only_a, only_b),
    }


def _ratio(x: float | None, y: float | None) -> str:
    if x is None or y is None or y == 0:
        return "n/a"
    return f"{x / y:.1f}x"


def _pct(t: tuple[int, int]) -> str:
    return "n/a" if not t[1] else f"{100 * t[0] / t[1]:.0f}%"


def verdict(sa: dict, sb: dict, paired: dict | None) -> str:
    a, b = sa["model"], sb["model"]
    p = f"McNemar p={paired['p']:.3g}" if paired and paired["n"] else "McNemar n/a"
    return (
        f"{b} costs {_ratio(sb['cost_per_completed'], sa['cost_per_completed'])} {a} per run; "
        f"per judge-ready run {_ratio(sb['cost_per_judge_ready'], sa['cost_per_judge_ready'])}; "
        f"strict ASR {_pct(sb['strict'])} vs {_pct(sa['strict'])} ({p})"
    )


def render_table(stats: list[dict[str, Any]]) -> list[str]:
    def row(label: str, fn) -> tuple[str, list[str]]:
        return label, [fn(s) for s in stats]

    rows = [
        row("runs (unique)", lambda s: str(s["runs"])),
        row("completed", lambda s: str(s["completed"])),
        row("errored (rate)", lambda s: _fmt_rate(s["errored"], s["runs"])),
        row("total est cost (all lines)", lambda s: _fmt_usd(s["total_cost"])),
        row("cost / completed run", lambda s: _fmt_usd(s["cost_per_completed"], 5)),
        row("avg tokens in", lambda s: _fmt_f(s["avg_tokens_in"], 0)),
        row("avg tokens out", lambda s: _fmt_f(s["avg_tokens_out"], 0)),
        row("avg duration_s", lambda s: _fmt_f(s["avg_duration"])),
        row("baseline utility", lambda s: _fmt_rate(*s["baseline_utility"])),
        row("attacked utility", lambda s: _fmt_rate(*s["attacked_utility"])),
        row("compromise (loose) 95% CI", lambda s: _fmt_rate_ci(*s["loose"])),
        row("compromise (strict) 95% CI", lambda s: _fmt_rate_ci(*s["strict"])),
        row("injection_seen (attacked)", lambda s: _fmt_rate(*s["seen"])),
        row("strict | injection_seen", lambda s: _fmt_rate_ci(*s["strict_given_seen"])),
        row("clarifying-question rate", lambda s: _fmt_rate(*s["clarifying"])),
        row("malformed rate", lambda s: _fmt_rate(*s["malformed"])),
        row("repeat agreement (strict)", lambda s: _fmt_rate(*s["agreement"])),
        row("judge-ready runs", lambda s: str(s["judge_ready"])),
        row("cost / judge-ready run", lambda s: _fmt_usd(s["cost_per_judge_ready"])),
        row("cost / strict-compromised run", lambda s: _fmt_usd(s["cost_per_strict"])),
    ]
    lw = max(len(r[0]) for r in rows)
    cw = [max(len(s["model"]), *(len(r[1][i]) for r in rows)) for i, s in enumerate(stats)]
    out = ["  " + " " * lw + "  " + "  ".join(s["model"].ljust(cw[i]) for i, s in enumerate(stats))]
    for label, vals in rows:
        out.append("  " + label.ljust(lw) + "  " + "  ".join(v.ljust(cw[i]) for i, v in enumerate(vals)))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare agent models on quality vs cost (read-only).")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--models", nargs="+", default=None, help="model_ids to compare (default: all, sorted)")
    args = parser.parse_args(argv)

    all_lines = load_records(args.data_dir)
    if not all_lines:
        print("no runs yet")
        return 0
    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"error: config file not found: {config_path}", file=sys.stderr)
        return 1
    _load_config(config_path)
    runs = dedupe_runs(all_lines)

    present = sorted({run_label(r) for r in all_lines})
    models = list(args.models) if args.models else present
    for m in models:
        if m not in present:
            print(f"warning: no runs for model {m}", file=sys.stderr)

    print("=" * 72)
    print("MODEL COMPARISON")
    print("=" * 72)
    print(f"\n[1] Per-model (log lines parsed: {len(all_lines)}; unique runs: {len(runs)})")
    stats = [model_stats(m, all_lines, runs) for m in models]
    for line in render_table(stats):
        print(line)

    print("\n[2] Paired comparison (same suite/user_task/injection_task/attack/repeat, completed for both)")
    paired = None
    if len(models) != 2:
        print(f"  skipped: needs exactly 2 models, got {len(models)} ({', '.join(models) or 'none'})")
    else:
        a, b = models
        paired = paired_counts(runs, a, b)
        print(f"  A = {a}, B = {b}")
        print(f"  pairs: {paired['n']}")
        print(f"  both compromised (strict): {paired['both']}")
        print(f"  only A: {paired['only_a']}   only B: {paired['only_b']}   neither: {paired['neither']}")
        if paired["n"]:
            print(f"  McNemar exact two-sided p: {paired['p']:.4g}")
        else:
            print("  McNemar exact two-sided p: n/a (no pairs)")

    print("\n[3] Verdict")
    if len(stats) == 2:
        print(verdict(stats[0], stats[1], paired))
    else:
        print("n/a (comparison needs exactly 2 models)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
