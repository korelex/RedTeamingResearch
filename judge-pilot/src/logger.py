"""JSONL run logger plus the serialization helpers it needs.

One JSON object per line in data/runs/<run_date>.jsonl. Each line is written with a single
write() of the full line + "\\n", then flushed and fsynced, under a threading.Lock.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Field order of every logged line. Readers (judges, inspect/morning scripts) rely on these names.
RUN_FIELDS = [
    "run_id",
    "timestamp",
    "agentdojo_version",
    "benchmark_version",
    "model_id",
    "temperature",
    "seed",
    "suite",
    "user_task_id",
    "injection_task_id",
    "attack",
    "repeat",
    "is_baseline",
    "compromised",
    "compromised_strict",
    "utility",
    "user_task_prompt",
    "injection_task_goal",
    "transcript",
    "tool_calls",
    "injection_text",
    "injection_seen",
    "state_available",
    "state_snapshot_omitted",
    "state_pre",
    "state_post",
    "state_diff",
    "tokens_in",
    "tokens_out",
    "finish_reasons",
    "malformed",
    "est_cost_usd",
    "duration_s",
    "error",
]

SNAPSHOT_MAX_BYTES = 50_000


def make_run_id(
    suite: str | None,
    user_task_id: str | None,
    injection_task_id: str | None,
    attack: str | None,
    repeat: int | None,
    model_id: str | None,
) -> str:
    parts = [suite, user_task_id, injection_task_id, attack, repeat, model_id]
    key = "|".join("none" if p is None else str(p) for p in parts)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def to_jsonable(obj: Any) -> Any:
    """Convert AgentDojo messages / content blocks / FunctionCall / pydantic objects to plain JSON."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, BaseModel):
        return to_jsonable(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    # Mappings that are not dicts (e.g. MutableMapping implementations)
    if hasattr(obj, "items") and callable(obj.items):
        try:
            return {str(k): to_jsonable(v) for k, v in obj.items()}
        except Exception:
            pass
    return str(obj)


_MISSING = object()


def state_diff(before: Any, after: Any, path: str = "") -> list[dict]:
    """Recursive dict/list compare. Returns [{path, before, after}] for each changed leaf.

    Paths are "/"-joined keys and list indices (e.g. "/bank_account/transactions/5/amount").
    A key or list item that only exists on one side is reported with null on the other side.
    """
    changes: list[dict] = []
    _diff(before, after, path, changes)
    return changes


def _diff(a: Any, b: Any, path: str, out: list[dict]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a.keys()) + [k for k in b.keys() if k not in a]:
            _diff(a.get(k, _MISSING), b.get(k, _MISSING), f"{path}/{k}", out)
        return
    if isinstance(a, list) and isinstance(b, list):
        for i in range(max(len(a), len(b))):
            _diff(a[i] if i < len(a) else _MISSING, b[i] if i < len(b) else _MISSING, f"{path}/{i}", out)
        return
    if a is _MISSING and b is _MISSING:
        return
    if a is _MISSING or b is _MISSING or a != b or type(a) is not type(b):
        out.append(
            {
                "path": path or "/",
                "before": None if a is _MISSING else a,
                "after": None if b is _MISSING else b,
            }
        )


def snapshot_or_none(state: Any) -> tuple[Any, bool]:
    """Return (snapshot, omitted). Snapshot is None (omitted=True) when its JSON is >= SNAPSHOT_MAX_BYTES."""
    if state is None:
        return None, False
    size = len(json.dumps(state, ensure_ascii=False).encode("utf-8"))
    if size >= SNAPSHOT_MAX_BYTES:
        return None, True
    return state, False


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type", "text") == "text":
            parts.append(str(block.get("content", "")))
    return "\n".join(parts)


def extract_tool_calls(transcript: list[dict]) -> list[dict]:
    """Flatten tool calls from a JSON transcript, pairing each call with its tool-result message.

    Pairing: a tool message is matched to the earliest unmatched call with the same id (when ids exist),
    otherwise the earliest unmatched call with the same function name and args. Calls that never got a
    result keep result=None.
    """
    calls: list[dict] = []
    for msg in transcript:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or []:
                calls.append(
                    {
                        "order": len(calls),
                        "name": tc.get("function"),
                        "args": tc.get("args"),
                        "result": None,
                        "_id": tc.get("id"),
                        "_matched": False,
                    }
                )
        elif msg.get("role") == "tool":
            tc = msg.get("tool_call") or {}
            tc_id = msg.get("tool_call_id") or tc.get("id")
            result = msg.get("error") if msg.get("error") is not None else _content_text(msg.get("content"))
            target = None
            for c in calls:
                if c["_matched"]:
                    continue
                if tc_id is not None and c["_id"] == tc_id:
                    target = c
                    break
            if target is None:
                for c in calls:
                    if not c["_matched"] and c["name"] == tc.get("function") and c["args"] == tc.get("args"):
                        target = c
                        break
            if target is not None:
                target["result"] = result
                target["_matched"] = True
    return [{k: v for k, v in c.items() if not k.startswith("_")} for c in calls]


class RunLogger:
    def __init__(self, runs_dir: Path, run_date: str | None = None):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.runs_dir / f"{run_date or utc_date()}.jsonl"
        self._lock = threading.Lock()

    def write(self, record: dict) -> None:
        missing = [f for f in RUN_FIELDS if f not in record]
        if missing:
            raise ValueError(f"record missing fields: {missing}")
        ordered = {f: record[f] for f in RUN_FIELDS}
        line = json.dumps(ordered, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())


def iter_logged_runs(runs_dir: Path):
    """Yield parsed records from every data/runs/*.jsonl. Unparseable lines are skipped."""
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return
    for p in sorted(runs_dir.glob("*.jsonl")):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def completed_run_ids(runs_dir: Path) -> set[str]:
    return {r["run_id"] for r in iter_logged_runs(runs_dir) if r.get("run_id") and r.get("error") is None}
