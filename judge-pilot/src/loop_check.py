"""Loop detector over logged runs: did the agent repeat itself (tool loops) or think without end (reasoning loops)?

Usage (from the project root):
    python -m src.loop_check [--data-dir data/runs] [--models LABEL ...] [--all]

Signals per run (last line per run_id):
  model_calls     number of API calls (len(finish_reasons))
  dup_calls       tool calls whose (name, args) already appeared earlier in the run
  max_streak      longest run of consecutive identical tool calls
  out_per_call    output tokens (incl. thinking) per API call
  max_tokens      any call that stopped on MAX_TOKENS
A run is flagged when dup_calls >= 2, max_streak >= 3, model_calls >= 15, out_per_call >= 4000, or MAX_TOKENS
occurred. Wall-clock duration is NOT a loop signal: it mostly reflects 429/504 retry waits.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.inspect_run import dedupe_runs, load_records, run_label

THRESHOLDS = {"dup_calls": 2, "max_streak": 3, "model_calls": 15, "out_per_call": 4000}


def signals(rec: dict) -> dict:
    calls = [(c.get("name"), json.dumps(c.get("args"), sort_keys=True)) for c in rec.get("tool_calls") or []]
    seen: set = set()
    dup = streak = best = 0
    prev = None
    for c in calls:
        dup += c in seen
        seen.add(c)
        streak = streak + 1 if c == prev else 1
        best = max(best, streak)
        prev = c
    n_calls = len(rec.get("finish_reasons") or [])
    out = rec.get("tokens_out") or 0
    s = {
        "model_calls": n_calls,
        "tool_calls": len(calls),
        "dup_calls": dup,
        "max_streak": best,
        "out_per_call": out // n_calls if n_calls else 0,
        "max_tokens": "MAX_TOKENS" in (rec.get("finish_reasons") or []),
    }
    s["flags"] = [k for k, t in THRESHOLDS.items() if s[k] >= t] + (["max_tokens"] if s["max_tokens"] else [])
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Detect tool-call and reasoning loops in logged runs.")
    ap.add_argument("--data-dir", default="data/runs")
    ap.add_argument("--models", nargs="+", default=None, help="run labels, e.g. gemini-3.1-pro-preview@t1")
    ap.add_argument("--all", action="store_true", help="print every run, not only flagged ones")
    args = ap.parse_args(argv)

    runs = [r for r in dedupe_runs(load_records(args.data_dir)) if r.get("error") is None]
    labels = sorted({run_label(r) for r in runs}) if not args.models else args.models
    print(f"{'model (label)':<30} {'runs':>5} {'flagged':>8} {'avg calls':>9} {'max calls':>9} "
          f"{'dup tool calls':>14} {'max out/call':>12}")
    flagged_rows = []
    for label in labels:
        rs = [r for r in runs if run_label(r) == label]
        if not rs:
            continue
        sig = [(r, signals(r)) for r in rs]
        fl = [(r, s) for r, s in sig if s["flags"]]
        flagged_rows += fl if not args.all else sig
        print(f"{label:<30} {len(rs):>5} {len(fl):>8} {sum(s['model_calls'] for _, s in sig) / len(sig):>9.1f} "
              f"{max(s['model_calls'] for _, s in sig):>9} {sum(s['dup_calls'] for _, s in sig):>14} "
              f"{max(s['out_per_call'] for _, s in sig):>12,}")
    if flagged_rows:
        print("\nruns:" if args.all else "\nflagged runs:")
        for r, s in flagged_rows:
            print(f"  {r['run_id']} {run_label(r)} {r['suite']}/{r['user_task_id']}/{r.get('injection_task_id') or 'baseline'} "
                  f"calls={s['model_calls']} tools={s['tool_calls']} dup={s['dup_calls']} streak={s['max_streak']} "
                  f"out/call={s['out_per_call']:,} flags={','.join(s['flags']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
