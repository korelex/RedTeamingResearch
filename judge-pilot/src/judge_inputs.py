"""Judge input levels: what a judge is shown for one run.

  L1  final answer only:  user task + final assistant reply
  L2  full transcript:    every message, tool call and tool result (incl. the system prompt)
  L3  grounded:           L2 + the environment changes (state_diff) rendered as neutral text

Rendering reads ONLY transcript, user_task_prompt and state_diff. It never reads ground-truth or metadata
fields (compromised*, injection_*, utility, model_id, suite, ...), so the label cannot leak into the input.
tests/test_judge_inputs.py checks this by mutating those fields.

Usage (from the project root): python -m src.judge_inputs [--run-id ID] [--level L1|L2|L3] [--stats]
"""

from __future__ import annotations

import argparse
import json
import sys

LEVELS = ("L1", "L2", "L3")
INPUT_FORMAT_VERSION = "inputs-v1"

# The only record fields a renderer may read.
ALLOWED_FIELDS = ("transcript", "user_task_prompt", "state_diff")


def _text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(str(b.get("content", "")) for b in content if isinstance(b, dict) and b.get("content"))


def _call(tc: dict) -> str:
    return f"{tc.get('function')}({json.dumps(tc.get('args') or {}, ensure_ascii=False, sort_keys=True)})"


def final_reply(rec: dict) -> str:
    for m in reversed(rec.get("transcript") or []):
        if m.get("role") == "assistant":
            t = _text(m.get("content")).strip()
            if t:
                return t
    return ""


def render_transcript(rec: dict) -> str:
    out = []
    for m in rec.get("transcript") or []:
        role = m.get("role")
        text = _text(m.get("content")).strip()
        if role == "system":
            out.append(f"[SYSTEM]\n{text}")
        elif role == "user":
            out.append(f"[USER]\n{text}")
        elif role == "assistant":
            if text:
                out.append(f"[ASSISTANT]\n{text}")
            for tc in m.get("tool_calls") or []:
                out.append(f"[ASSISTANT TOOL CALL]\n{_call(tc)}")
        elif role == "tool":
            name = (m.get("tool_call") or {}).get("function", "?")
            err = f"\nERROR: {m['error']}" if m.get("error") else ""
            out.append(f"[TOOL RESULT: {name}]\n{text}{err}")
    return "\n\n".join(out)


def _path(p: str) -> str:
    parts = [x for x in p.split("/") if x]
    return " > ".join(f"item {x}" if x.isdigit() else x for x in parts)


def _value(v) -> str:
    if isinstance(v, dict):
        return "\n".join(f"    {k}: {_value(x)}" for k, x in sorted(v.items()))
    if isinstance(v, str) and "\n" in v:
        return "\n" + "\n".join(f"    | {line}" for line in v.splitlines())
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v


def render_state_diff(rec: dict) -> str:
    """Neutral, suite-agnostic rendering: no judgement words, no domain knowledge, original order."""
    diff = rec.get("state_diff") or []
    if not diff:
        return "No changes were made to the environment."
    lines = []
    for d in diff:
        before, after, path = d.get("before"), d.get("after"), _path(d.get("path", ""))
        if before is None:
            head, body = f"ADDED {path}", _value(after)
        elif after is None:
            head, body = f"REMOVED {path}", _value(before)
        else:
            head, body = f"CHANGED {path}", f"{_value(before)} -> {_value(after)}"
        sep = "" if body.startswith("\n") else "\n" if body.startswith("    ") else " "
        lines.append(f"- {head}:{sep}{body}")
    return "\n".join(lines)


def render(rec: dict, level: str) -> str:
    if level == "L1":
        return f"USER TASK:\n{(rec.get('user_task_prompt') or '').strip()}\n\nFINAL REPLY TO THE USER:\n{final_reply(rec)}"
    if level == "L2":
        return f"FULL TRANSCRIPT:\n\n{render_transcript(rec)}"
    if level == "L3":
        return (f"{render(rec, 'L2')}\n\nENVIRONMENT CHANGES AFTER THE RUN (recorded by the system, "
                f"compared with the state before the run):\n{render_state_diff(rec)}")
    raise ValueError(f"unknown level {level!r}")


def main(argv: list[str] | None = None) -> int:
    from src.freeze import load_frozen

    ap = argparse.ArgumentParser(description="Render judge inputs from the frozen dataset.")
    ap.add_argument("--dataset", default="night1_v1")
    ap.add_argument("--run-id")
    ap.add_argument("--level", choices=LEVELS, default="L3")
    ap.add_argument("--stats", action="store_true", help="input size per level (chars/4)")
    args = ap.parse_args(argv)
    runs = [r for r in load_frozen(args.dataset) if r.get("error") is None]
    if args.stats:
        for lv in LEVELS:
            sizes = sorted(len(render(r, lv)) // 4 for r in runs)
            print(f"{lv}: runs={len(sizes)} avg={sum(sizes) // len(sizes):,} median={sizes[len(sizes) // 2]:,} "
                  f"max={sizes[-1]:,} total={sum(sizes):,} tokens (chars/4)")
        return 0
    rec = next(r for r in runs if r["run_id"] == args.run_id)
    print(render(rec, args.level))
    return 0


if __name__ == "__main__":
    sys.exit(main())
