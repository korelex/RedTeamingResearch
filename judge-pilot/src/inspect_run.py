"""Read-only inspection of recorded runs in data/runs/*.jsonl.

Usage (from the project root):
    python -m src.inspect_run <run_id> [<run_id> ...] [--data-dir data/runs]
    python -m src.inspect_run --all [--data-dir data/runs]

Also exposes load_records / dedupe_runs / is_baseline / summarize / one_line
for reuse by src.morning_check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = "data/runs"
RESULT_TRUNC = 200
MAX_STATE_ENTRIES = 15


def _warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def load_records(data_dir: str | Path) -> list[dict[str, Any]]:
    """Parse every line of every *.jsonl file in data_dir, in file/line order.

    Lines that are not valid JSON objects with a run_id are skipped with a warning.
    A missing directory yields an empty list.
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    _warn(f"{path}:{lineno}: unparseable JSON, skipped ({exc.msg})")
                    continue
                if not isinstance(rec, dict) or "run_id" not in rec:
                    _warn(f"{path}:{lineno}: not a run record (no run_id), skipped")
                    continue
                records.append(rec)
    return records


def dedupe_runs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per run_id.

    Keeps the latest line with error == null if one exists, otherwise the latest
    line. "Latest" means last in file/line order (the logs are append-only).
    Returned in order of each run_id's chosen record.
    """
    last_any: dict[str, dict[str, Any]] = {}
    last_ok: dict[str, dict[str, Any]] = {}
    for rec in records:
        rid = str(rec["run_id"])
        last_any[rid] = rec
        if rec.get("error") is None:
            last_ok[rid] = rec
    chosen = {rid: last_ok.get(rid, rec) for rid, rec in last_any.items()}
    return list(chosen.values())


def is_baseline(rec: dict[str, Any]) -> bool:
    flag = rec.get("is_baseline")
    if isinstance(flag, bool):
        return flag
    return rec.get("injection_task_id") is None


def text_of_content(content: Any) -> str:
    """Message content may be a string or a list of blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                val = block.get("content", block.get("text", ""))
                if isinstance(val, str):
                    parts.append(val)
                elif val is not None:
                    parts.append(json.dumps(val, ensure_ascii=False, default=str))
        return "\n".join(p for p in parts if p)
    return str(content)


def _fmt_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _trunc(text: str, limit: int) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [{len(text)} chars total]"


def _final_reply(rec: dict[str, Any]) -> str:
    transcript = rec.get("transcript") or []
    if not isinstance(transcript, list):
        return "(transcript not a list)"
    for msg in reversed(transcript):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            text = text_of_content(msg.get("content")).strip()
            if text:
                return text
    return "(no assistant text found)"


def _sorted_tool_calls(rec: dict[str, Any]) -> list[dict[str, Any]]:
    calls = [c for c in (rec.get("tool_calls") or []) if isinstance(c, dict)]
    return sorted(
        calls,
        key=lambda c: c.get("order") if isinstance(c.get("order"), int) else 10**9,
    )


def _target(rec: dict[str, Any]) -> str:
    return str(rec.get("injection_task_id") or "baseline")


def one_line(rec: dict[str, Any]) -> str:
    names = [str(c.get("name")) for c in _sorted_tool_calls(rec)]
    return (
        f"{rec.get('run_id')} {rec.get('suite')}/{rec.get('user_task_id')}/{_target(rec)} "
        f"compromised={rec.get('compromised')} utility={rec.get('utility')} "
        f"tools=[{', '.join(names)}]"
    )


def summarize(rec: dict[str, Any]) -> str:
    out: list[str] = []
    baseline = is_baseline(rec)
    out.append(
        f"=== run {rec.get('run_id')} | suite={rec.get('suite')} "
        f"user_task={rec.get('user_task_id')} "
        f"injection_task={rec.get('injection_task_id') or 'none'} "
        f"attack={rec.get('attack') or 'none'} repeat={rec.get('repeat')} ==="
    )

    out.append("\n1. User task")
    out.append(f"   {rec.get('user_task_prompt') or '(none)'}")

    out.append("\n2. Injection")
    if baseline:
        out.append("   baseline: no injection")
    else:
        inj = rec.get("injection_text")
        if isinstance(inj, dict) and inj:
            out.append(f"   placed in vectors: {', '.join(str(k) for k in inj)}")
            for vid, text in inj.items():
                out.append(f"   [{vid}] {text}")
        else:
            out.append("   injection text not recorded")

    out.append("\n3. Attacker goal")
    out.append(f"   {rec.get('injection_task_goal') or '(none)'}")

    calls = _sorted_tool_calls(rec)
    out.append(f"\n4. Tool calls ({len(calls)})")
    if not calls:
        out.append("   (none)")
    for i, call in enumerate(calls, start=1):
        args = _fmt_json(call.get("args"))
        result = _trunc(_fmt_json(call.get("result")), RESULT_TRUNC)
        out.append(f"   [{i}] {call.get('name')}({args})")
        out.append(f"       -> {result}")

    out.append("\n5. Final assistant reply")
    out.append(f"   {_final_reply(rec)}")

    out.append("\n6. Outcome")
    out.append(f"   compromised: {rec.get('compromised')}")
    out.append(f"   utility: {rec.get('utility')}")
    diff = rec.get("state_diff")
    if rec.get("state_available") is not True or diff is None:
        out.append("   state_diff: state not available")
    else:
        out.append(f"   state_diff ({len(diff)} entries):")
        for entry in diff[:MAX_STATE_ENTRIES]:
            if isinstance(entry, dict):
                out.append(
                    f"     {entry.get('path')}: {_trunc(_fmt_json(entry.get('before')), 80)}"
                    f" -> {_trunc(_fmt_json(entry.get('after')), 80)}"
                )
            else:
                out.append(f"     {_trunc(_fmt_json(entry), 160)}")
        if len(diff) > MAX_STATE_ENTRIES:
            out.append(f"     ... {len(diff) - MAX_STATE_ENTRIES} more not shown")

    err = rec.get("error")
    if err:
        if isinstance(err, dict):
            out.append(f"\nERROR: {err.get('type')}: {err.get('message')}")
        else:
            out.append(f"\nERROR: {err}")
    return "\n".join(out)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect recorded AgentDojo runs (read-only).")
    parser.add_argument("run_ids", nargs="*", help="one or more run_ids")
    parser.add_argument("--all", action="store_true", help="print every run")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    if not args.all and not args.run_ids:
        parser.error("give one or more run_ids, or --all")

    runs = dedupe_runs(load_records(args.data_dir))
    if args.all:
        if not runs:
            print("no runs yet")
            return 0
        selected = runs
        rc = 0
    else:
        index = {str(r["run_id"]): r for r in runs}
        selected = []
        rc = 0
        for rid in args.run_ids:
            if rid in index:
                selected.append(index[rid])
            else:
                print(f"run not found: {rid}", file=sys.stderr)
                rc = 1

    print(("\n" + "-" * 72 + "\n").join(summarize(r) for r in selected))
    return rc


if __name__ == "__main__":
    sys.exit(_main())
