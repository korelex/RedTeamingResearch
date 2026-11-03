"""Day 2 judge runner: LLM judges over the frozen Day 1 dataset, as pre-registered (PREREGISTRATION.md).

Usage (from the project root):
    python -m src.judge_runner --config config.yaml --plan judge_smoke --dry-run
    python -m src.judge_runner --config config.yaml --plan judge_smoke [--judges frontier_gemini31pro ...]

- Reads runs only via src.freeze.load_frozen() (hash-verified). Excludes errored runs and temperature != 0 runs.
- One line per judge call is appended to data/judgements/<UTC date>.jsonl (fields: src.judge_schema.JUDGEMENT_FIELDS).
- Resumable: a judgement_id with an error-free line is skipped. Failed calls are logged with `error` and retried on
  the next invocation, never dropped.
- Stops submitting new calls once the cumulative cost over all judgement lines reaches judging.judge_spend_cap_usd.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
from google import genai
from google.genai import types as genai_types

from src.cost import estimate_cost, get_prices
from src.freeze import load_frozen
from src.inspect_run import run_label
from src.judge_inputs import INPUT_FORMAT_VERSION
from src.judge_prompts import build, parse_promptfoo, promptfoo_shortcut_safe
from src.judge_schema import JUDGEMENT_FIELDS, parse_verdict
from src.runner import is_transient, load_cfg
from src.vertex_setup import _prepare_env

JUDGEMENTS_DIR = Path("data/judgements")
PRIMARY_AGENTS = {"gemini-2.5-flash", "gemini-2.5-pro"}


# --- sample ----------------------------------------------------------------------------------------------------------
def bucket(rec: dict) -> str:
    if rec.get("is_baseline"):
        return "baseline"
    if rec.get("compromised_strict"):
        return "compromised"
    return "seen_resisted" if rec.get("injection_seen") else "never_exposed"


def eligible_runs(dataset: str) -> list[dict]:
    """Pre-registered exclusions: errored runs and temperature 1.0 smoke runs."""
    return [r for r in load_frozen(dataset) if r.get("error") is None and run_label(r) == r.get("model_id")]


def select_runs(runs: list[dict], plan: dict) -> list[dict]:
    sample = plan.get("sample")
    if not sample:
        return runs
    rng = random.Random(sample.get("seed", 0))
    chosen: list[dict] = []
    for key, n in sample.items():
        if key == "seed":
            continue
        if key == "secondary_resisted":
            pool = [r for r in runs if r["model_id"] not in PRIMARY_AGENTS and bucket(r) == "seen_resisted"]
        else:
            pool = [r for r in runs if r["model_id"] in PRIMARY_AGENTS and bucket(r) == key]
        chosen += rng.sample(sorted(pool, key=lambda r: r["run_id"]), n)
    return chosen


def judgement_id(judge_id: str, prompt: str, level: str, run_id: str, repeat: int) -> str:
    return hashlib.sha256(f"{judge_id}|{prompt}|{level}|{run_id}|{repeat}".encode()).hexdigest()[:16]


def plan_jobs(cfg: dict, plan: dict, runs: list[dict], judges: list[str]) -> list[dict]:
    jc = cfg["judging"]
    jobs = []
    for jid in judges:
        j = jc["judges"][jid]
        for rec in runs:
            if j["prompt"].startswith("promptfoo") and rec.get("is_baseline"):
                continue  # no injection goal to grade against (pre-registered)
            for level in [lv for lv in j["levels"] if lv in plan.get("levels", j["levels"])]:
                for rep in range(int(plan.get("repeats", 1))):
                    jobs.append({"judge_id": jid, "judge": j, "rec": rec, "level": level, "repeat": rep,
                                 "judgement_id": judgement_id(jid, j["prompt"], level, rec["run_id"], rep)})
    return jobs


# --- log -------------------------------------------------------------------------------------------------------------
def load_judgements(path: Path = JUDGEMENTS_DIR) -> list[dict]:
    out = []
    for p in sorted(path.glob("*.jsonl")):
        with open(p, encoding="utf-8") as f:
            out += [json.loads(line) for line in f if line.strip()]
    return out


class Log:
    def __init__(self, cap: float):
        JUDGEMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.path = JUDGEMENTS_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
        self.lock = threading.Lock()
        self.cap = cap
        self.spend = sum(float(r.get("cost_usd") or 0) for r in load_judgements())

    def write(self, row: dict) -> None:
        with self.lock:
            self.spend += float(row.get("cost_usd") or 0)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({k: row.get(k) for k in JUDGEMENT_FIELDS}, ensure_ascii=False) + "\n")

    def over_cap(self) -> bool:
        with self.lock:
            return self.spend >= self.cap


# --- model calls -----------------------------------------------------------------------------------------------------
class Callers:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.project, self.default_location = _prepare_env()
        self._gemini: dict[str, genai.Client] = {}
        self._creds = None
        self._lock = threading.Lock()

    def gemini(self, model: str, system: str | None, user: str) -> tuple[str, int, int]:
        jc = self.cfg["judging"]
        loc = (self.cfg["vertex"].get("model_locations") or {}).get(model, self.default_location)
        with self._lock:
            if loc not in self._gemini:
                self._gemini[loc] = genai.Client(vertexai=True, project=self.project, location=loc)
            client = self._gemini[loc]
        config = genai_types.GenerateContentConfig(
            temperature=jc["temperature"], seed=jc["seed"], system_instruction=system,
            http_options=genai_types.HttpOptions(timeout=int(jc["request_timeout_s"] * 1000)))
        resp = client.models.generate_content(model=model, contents=user, config=config)
        u = resp.usage_metadata
        out = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)  # thinking is billed as output
        return resp.text or "", u.prompt_token_count or 0, out

    def _token(self) -> str:
        import google.auth
        from google.auth.transport.requests import Request
        with self._lock:
            if self._creds is None:
                self._creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            if not self._creds.valid:
                self._creds.refresh(Request())
            return self._creds.token

    def openai_compat(self, j: dict, system: str | None, user: str) -> tuple[str, int, int]:
        jc = self.cfg["judging"]
        region = j["region"]
        host = "aiplatform.googleapis.com" if region == "global" else f"{region}-aiplatform.googleapis.com"
        url = f"https://{host}/v1/projects/{self.project}/locations/{region}/endpoints/openapi/chat/completions"
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        body = {"model": j["model"], "messages": messages, "temperature": jc["temperature"], "seed": jc["seed"],
                "max_tokens": j.get("max_tokens", 512)}
        r = httpx.post(url, json=body, headers={"Authorization": f"Bearer {self._token()}"},
                       timeout=jc["request_timeout_s"])
        if r.status_code in (408, 429) or r.status_code >= 500:
            raise TransientHTTP(f"{r.status_code} {r.text[:300]}")
        r.raise_for_status()
        d = r.json()
        d = d[0] if isinstance(d, list) else d
        u = d.get("usage") or {}
        return d["choices"][0]["message"].get("content") or "", u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


class TransientHTTP(Exception):
    pass


def call_with_retry(fn, retry: dict):
    tries, base, cap = int(retry["max_tries"]), float(retry["base_delay_s"]), float(retry["max_delay_s"])
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if attempt == tries or not (isinstance(e, TransientHTTP) or is_transient(e)):
                raise
            time.sleep(min(cap, base * 2 ** (attempt - 1)) * (0.5 + random.random()))


def run_job(job: dict, cfg: dict, callers: Callers, dataset: str) -> dict:
    j, rec, level = job["judge"], job["rec"], job["level"]
    system, user = build(j["prompt"], rec, level)
    row = {"judgement_id": job["judgement_id"], "run_id": rec["run_id"], "dataset": dataset, "judge_id": job["judge_id"],
           "model_id": j["model"], "temperature": cfg["judging"]["temperature"], "seed": cfg["judging"]["seed"],
           "prompt_version": j["prompt"], "input_level": level, "input_format_version": INPUT_FORMAT_VERSION,
           "repeat": job["repeat"], "error": None,
           "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if j["prompt"].startswith("promptfoo"):
        from src.judge_inputs import final_reply
        row["promptfoo_shortcut_safe"] = promptfoo_shortcut_safe(final_reply(rec))
    t0 = time.time()
    try:
        if j["kind"] == "gemini":
            raw, tin, tout = call_with_retry(lambda: callers.gemini(j["model"], system, user), cfg["judging"]["retry"])
        else:
            raw, tin, tout = call_with_retry(lambda: callers.openai_compat(j, system, user), cfg["judging"]["retry"])
    except Exception as e:  # noqa: BLE001
        row.update(error={"type": type(e).__name__, "message": str(e)[:500]}, duration_s=round(time.time() - t0, 1))
        return row
    parse = parse_promptfoo if j["prompt"].startswith("promptfoo") else parse_verdict
    verdict, reason, perr = parse(raw)
    pin, pout = get_prices(cfg, j["model"])
    row.update(verdict=verdict, reason=reason, raw_response=raw, parse_error=perr, tokens_in=tin, tokens_out=tout,
               cost_usd=round(estimate_cost(tin, tout, pin, pout), 6), duration_s=round(time.time() - t0, 1))
    return row


def _guarded(job: dict, cfg: dict, callers: Callers, dataset: str, log: Log) -> dict | None:
    """Checked when a worker picks the job up, so the cap holds even though all jobs are queued at once."""
    return None if log.over_cap() else run_job(job, cfg, callers, dataset)


# --- main ------------------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run pre-registered LLM judges over the frozen dataset.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--judges", nargs="+", help="subset of judging.judges (default: all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_cfg(args.config)
    jc = cfg["judging"]
    plan = jc["plans"][args.plan]
    judges = args.judges or list(jc["judges"])
    dataset = plan.get("dataset", jc["dataset"])
    runs = select_runs(eligible_runs(dataset), plan)
    jobs = plan_jobs(cfg, plan, runs, judges)
    done = {r["judgement_id"] for r in load_judgements() if r.get("error") is None}
    todo = [x for x in jobs if x["judgement_id"] not in done]
    log = Log(float(jc["judge_spend_cap_usd"]))

    est = 0.0
    for x in todo:
        sys_t, user_t = build(x["judge"]["prompt"], x["rec"], x["level"])
        pin, pout = get_prices(cfg, x["judge"]["model"])
        est += estimate_cost((len(sys_t or "") + len(user_t)) // 4, x["judge"]["est_output_tokens"], pin, pout)
    print(f"plan={args.plan} dataset={dataset} runs={len(runs)} judges={judges} jobs={len(jobs)} "
          f"done={len(jobs) - len(todo)} to_run={len(todo)} est_cost=${est:.2f} "
          f"judge_spend_so_far=${log.spend:.4f} cap=${log.cap:.2f}")
    if args.dry_run or not todo:
        return 0
    if log.over_cap():
        print("STOP: judge spend cap reached")
        return 1

    callers = Callers(cfg)
    n_done = n_err = 0
    with ThreadPoolExecutor(max_workers=int(jc["concurrency"])) as pool:
        futures = {}
        for x in todo:
            futures[pool.submit(_guarded, x, cfg, callers, dataset, log)] = x
        skipped = 0
        for fut in as_completed(futures):
            row = fut.result()
            if row is None:
                skipped += 1
                continue
            log.write(row)
            n_done += 1
            n_err += row.get("error") is not None
            if n_done % 10 == 0 or n_done == len(futures):
                print(f"PROGRESS {n_done}/{len(futures)} errors={n_err} judge_spend=${log.spend:.4f}", flush=True)
    if skipped:
        print(f"STOP: judge spend cap reached; {skipped} jobs not started (resume after raising the cap)")
    print(f"DONE {n_done}/{len(futures)} errors={n_err} judge_spend=${log.spend:.4f} log={log.path}")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
