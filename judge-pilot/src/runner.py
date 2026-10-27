"""Resumable AgentDojo experiment runner (Gemini on Vertex AI).

Usage (from project root):
    .venv/bin/python -m src.runner --config config.yaml --plan smoke [--dry-run] [--limit N]

Each run is logged as one JSON line in data/runs/<UTC date at start>.jsonl (see src/logger.py).
Resume: run_ids that already have an error==null line in data/runs/*.jsonl are skipped; errored ones are retried.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import random
import signal
import sys
import threading
import time
import traceback
import warnings
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv
from google.genai import errors as genai_errors
from google.genai import types as genai_types

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from agentdojo.agent_pipeline.errors import AbortAgentError  # noqa: E402
from agentdojo.agent_pipeline.llms import google_llm as _google_llm  # noqa: E402
from agentdojo.agent_pipeline.llms.google_llm import GoogleLLM  # noqa: E402
from agentdojo.attacks import load_attack  # noqa: E402
import src.dual_attacks  # noqa: E402,F401  (registers the Day 3 attacks with AgentDojo)
from agentdojo.base_tasks import BaseUserTask  # noqa: E402
from agentdojo.functions_runtime import FunctionsRuntime  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402
from agentdojo.task_suite.task_suite import (  # noqa: E402
    functions_stack_trace_from_messages,
    model_output_from_messages,
)

from src.cost import CostTracker, estimate_cost, get_prices  # noqa: E402
from src.derived import add_derived  # noqa: E402
from src.logger import (  # noqa: E402
    RunLogger,
    completed_run_ids,
    extract_tool_calls,
    iter_logged_runs,
    make_run_id,
    snapshot_or_none,
    state_diff,
    to_jsonable,
    utc_date,
    utc_now_iso,
)
from src.vertex_setup import build_pipeline  # noqa: E402

RUNS_DIR = PROJECT_ROOT / "data" / "runs"
AGENTDOJO_VERSION = importlib.metadata.version("agentdojo")


# --------------------------------------------------------------------------------------------
# Runtime patch: GoogleLLM wraps generate_content in its own tenacity retry (3 tries, retries any
# non-ClientError). We do retries ourselves in the client wrapper (max 5 tries, transient errors only),
# so replace the module-level request function with a single plain call. The installed package is not
# modified; GoogleLLM.query looks the function up in its module globals at call time.
# --------------------------------------------------------------------------------------------
def _chat_completion_request_no_retry(model, client, contents, generation_config):
    return client.models.generate_content(model=model, contents=contents, config=generation_config)


_google_llm.chat_completion_request = _chat_completion_request_no_retry


# --------------------------------------------------------------------------------------------
# Runtime patch: Gemini 3.x requires each function call's thought_signature to be sent back on later turns
# ("400 Function call is missing a thought_signature"). AgentDojo rebuilds model turns from its own message
# dicts and drops the signatures. When enabled (vertex.preserve_thought_signatures lists the model), the model's
# original Content is kept on the assistant message under GOOGLE_CONTENT_KEY and sent back unchanged. The key is
# stripped from logged transcripts. Off for other models, so Gemini 2.5 requests stay as on Day 1.
# --------------------------------------------------------------------------------------------
GOOGLE_CONTENT_KEY = "_google_content"
PRESERVE_THOUGHT_SIGNATURES = False
_orig_google_to_assistant_message = _google_llm._google_to_assistant_message
_orig_message_to_google = _google_llm._message_to_google


def _google_to_assistant_message_keep(response):
    message = _orig_google_to_assistant_message(response)
    if PRESERVE_THOUGHT_SIGNATURES and response.candidates and response.candidates[0].content is not None:
        message[GOOGLE_CONTENT_KEY] = response.candidates[0].content
    return message


def _message_to_google_keep(message):
    if message.get("role") == "assistant" and message.get(GOOGLE_CONTENT_KEY) is not None:
        return message[GOOGLE_CONTENT_KEY]
    return _orig_message_to_google(message)


_google_llm._google_to_assistant_message = _google_to_assistant_message_keep
_google_llm._message_to_google = _message_to_google_keep


# --------------------------------------------------------------------------------------------
# Instrumented genai client: per-run token accounting, seed/timeout injection, transient retries
# --------------------------------------------------------------------------------------------
class UsageAccumulator:
    def __init__(self) -> None:
        self.tokens_in = 0
        self.tokens_out = 0
        self.calls = 0
        self.temperatures: list[Any] = []
        self.seeds: list[Any] = []
        self.finish_reasons: list[str | None] = []  # one entry per API call that returned a response
        self.malformed_returned: list[str | None] = []  # finish reasons of malformed responses handed to the agent
        self._lock = threading.Lock()

    def record_finish(self, reason: str | None) -> None:
        with self._lock:
            self.finish_reasons.append(reason)

    def record_malformed_returned(self, reason: str | None) -> None:
        with self._lock:
            self.malformed_returned.append(reason)

    @property
    def malformed(self) -> bool:
        return len(self.malformed_returned) > 0

    def record_config(self, cfg: genai_types.GenerateContentConfig | None) -> None:
        with self._lock:
            self.temperatures.append(None if cfg is None else cfg.temperature)
            self.seeds.append(None if cfg is None else cfg.seed)

    def add(self, usage: Any) -> None:
        with self._lock:
            self.calls += 1
            if usage is None:
                return
            self.tokens_in += usage.prompt_token_count or 0
            # thinking tokens are billed as output
            self.tokens_out += (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)

    def sent_value(self, values: list[Any]) -> Any:
        """The value actually sent on every call; None if no call was sent or values differed."""
        distinct = {repr(v) for v in values}
        if len(distinct) != 1:
            return None
        return values[0]


# Finish reasons that count as a normal completion. Anything else with an empty candidate (SAFETY, RECITATION,
# OTHER, ...) is malformed, and MALFORMED_RESPONSE / MALFORMED_FUNCTION_CALL are malformed regardless of content.
NORMAL_FINISH_REASONS = {"STOP", "MAX_TOKENS"}
ALWAYS_MALFORMED = {"MALFORMED_RESPONSE", "MALFORMED_FUNCTION_CALL"}
MALFORMED_MAX_RETRIES = 2


def response_finish_reason(response: Any) -> str | None:
    cands = getattr(response, "candidates", None) or []
    if not cands:
        return None
    fr = getattr(cands[0], "finish_reason", None)
    if fr is None:
        return None
    return str(getattr(fr, "value", fr))


def is_malformed_response(response: Any) -> bool:
    cands = getattr(response, "candidates", None) or []
    if not cands:
        return True
    reason = response_finish_reason(response)
    if reason in ALWAYS_MALFORMED:
        return True
    content = getattr(cands[0], "content", None)
    empty = content is None or not (getattr(content, "parts", None) or [])
    return empty and reason not in NORMAL_FINISH_REASONS


def malformed_error(acc: "UsageAccumulator") -> dict | None:
    if not acc.malformed:
        return None
    return {
        "type": "MalformedResponse",
        "message": f"malformed responses returned to agent: {acc.malformed_returned}; "
                   f"all finish_reasons: {acc.finish_reasons}",
        "traceback": None,
    }


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError) and getattr(exc, "code", None) in (408, 429):
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, TimeoutError, ConnectionError)):
        return True
    return False


class _InstrumentedModels:
    def __init__(self, models: Any, acc: UsageAccumulator, seed: int | None, timeout_ms: int | None, retry: dict):
        self._models = models
        self._acc = acc
        self._seed = seed
        self._timeout_ms = timeout_ms
        self._max_tries = int(retry.get("max_tries", 5))
        self._base = float(retry.get("base_delay_s", 2.0))
        self._cap = float(retry.get("max_delay_s", 60.0))
        self.retries = 0
        self.malformed_retries = MALFORMED_MAX_RETRIES
        self.malformed_sleep_s = 1.0

    def generate_content(self, *, model: str, contents: Any, config: genai_types.GenerateContentConfig | None = None):
        update: dict[str, Any] = {}
        if config is None:
            config = genai_types.GenerateContentConfig()
        if self._seed is not None:
            update["seed"] = self._seed
        if self._timeout_ms is not None:
            http_options = (config.http_options or genai_types.HttpOptions()).model_copy(
                update={"timeout": self._timeout_ms}
            )
            update["http_options"] = http_options
        if update:
            config = config.model_copy(update=update)
        self._acc.record_config(config)
        for malformed_attempt in range(self.malformed_retries + 1):
            response = self._call_with_retries(model, contents, config)
            self._acc.add(getattr(response, "usage_metadata", None))
            self._acc.record_finish(response_finish_reason(response))
            if not is_malformed_response(response):
                return response
            if malformed_attempt < self.malformed_retries:
                time.sleep(self.malformed_sleep_s * random.uniform(0.5, 1.5))
        # Still malformed after retries: hand it to the agent (AgentDojo turns it into an empty message) and
        # flag the run so it is logged as an error.
        self._acc.record_malformed_returned(response_finish_reason(response))
        return response

    def _call_with_retries(self, model: str, contents: Any, config: genai_types.GenerateContentConfig):
        for attempt in range(1, self._max_tries + 1):
            try:
                return self._models.generate_content(model=model, contents=contents, config=config)
            except Exception as e:  # noqa: BLE001
                if attempt < self._max_tries and is_transient(e):
                    self.retries += 1
                    delay = min(self._cap, self._base * 2 ** (attempt - 1)) * random.uniform(0.5, 1.5)
                    time.sleep(delay)
                    continue
                raise
        raise RuntimeError("unreachable")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._models, name)


class InstrumentedClient:
    def __init__(self, client: Any, acc: UsageAccumulator, seed: int | None, timeout_ms: int | None, retry: dict):
        self._client = client
        self.models = _InstrumentedModels(client.models, acc, seed, timeout_ms, retry)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _google_llms(element: Any, found: list) -> list:
    if isinstance(element, GoogleLLM):
        if not any(e is element for e in found):
            found.append(element)
    for child in getattr(element, "elements", None) or []:
        _google_llms(child, found)
    return found


def build_instrumented_pipeline(cfg: dict, model_id: str, acc: UsageAccumulator):
    """Fresh pipeline per run (via vertex_setup.build_pipeline) with the per-run accumulator wired in."""
    pipeline = build_pipeline(model_id)
    vcfg = cfg.get("vertex", {})
    llms = _google_llms(pipeline, [])
    if not llms:
        raise RuntimeError("No GoogleLLM element found in pipeline")
    timeout_s = vcfg.get("request_timeout_s")
    for llm in llms:
        if "temperature" in vcfg:
            llm.temperature = vcfg["temperature"]
        llm.client = InstrumentedClient(
            llm.client,
            acc,
            seed=vcfg.get("seed"),
            timeout_ms=int(timeout_s * 1000) if timeout_s else None,
            retry=cfg.get("retry", {}),
        )
    return pipeline


# --------------------------------------------------------------------------------------------
# Reimplementation of TaskSuite.run_task_with_pipeline (agentdojo 0.1.35, task_suite.py:339-420)
# Same calls in the same order; additionally keeps pre/post env and messages.
# --------------------------------------------------------------------------------------------
def run_task_capture(suite, agent_pipeline, user_task, injection_task, injections: dict[str, str], capture: dict):
    """Returns (utility, security). Fills `capture` with pre_environment, task_environment, messages as they
    become available so the caller still has them if something raises."""
    environment = suite.load_and_inject_default_environment(injections)
    if isinstance(user_task, BaseUserTask):
        task_environment = user_task.init_environment(environment)
    else:
        task_environment = environment

    pre_environment = task_environment.model_copy(deep=True)
    capture["pre_environment"] = pre_environment
    if isinstance(user_task, BaseUserTask):
        prompt = user_task.PROMPT
    else:
        prompt = user_task.GOAL

    runtime = FunctionsRuntime(suite.tools)
    model_output = None
    messages = []
    for _ in range(3):
        try:
            _, _, task_environment, messages, _ = agent_pipeline.query(prompt, runtime, task_environment)
        except AbortAgentError as e:
            task_environment = e.task_environment
            messages = e.messages
        capture["messages"] = messages
        capture["task_environment"] = task_environment

        model_output = model_output_from_messages(messages)
        if model_output is not None:
            break

    if model_output is None:
        warnings.warn(f"Model output was None for task {user_task.ID}")

    functions_stack_trace = functions_stack_trace_from_messages(messages)
    utility = suite._check_task_result(
        user_task,
        model_output or [],
        pre_environment,
        task_environment,
        functions_stack_trace,
    )

    if injection_task is None:
        return utility, True

    security = suite._check_task_result(
        injection_task,
        model_output or [],
        pre_environment,
        task_environment,
        functions_stack_trace,
    )
    return utility, security


# --------------------------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RunSpec:
    suite: str
    user_task_id: str
    injection_task_id: str | None
    attack: str | None
    repeat: int

    @property
    def is_baseline(self) -> bool:
        return self.injection_task_id is None

    def run_id(self, model_id: str) -> str:
        return make_run_id(self.suite, self.user_task_id, self.injection_task_id, self.attack, self.repeat, model_id)


def _task_sort_key(task_id: str):
    head, _, tail = task_id.rpartition("_")
    return (head, int(tail)) if tail.isdigit() else (task_id, -1)


def stratified_per_injection_pairs(
    suite_name: str, user_tasks: list[str], injection_tasks: list[str], k: int, seed: Any
) -> list[tuple[str, str, str]]:
    """k user tasks per injection task. The sorted user tasks are shuffled once (seeded per suite) and read as a
    cyclic stream; each injection task (sorted) takes the next k. Every injection task is covered, no user task
    repeats within an injection task, and per-user-task counts differ by at most 1."""
    if not 1 <= k <= len(user_tasks):
        raise SystemExit(f"stratified_per_injection: k={k} for {suite_name} must be in [1, {len(user_tasks)}]")
    stream = list(user_tasks)
    random.Random(f"{seed}|{suite_name}|stratified_per_injection").shuffle(stream)
    pairs: list[tuple[str, str, str]] = []
    pos = 0
    for it in injection_tasks:
        for _ in range(k):
            pairs.append((suite_name, stream[pos % len(stream)], it))
            pos += 1
    return pairs


def expand_plan(cfg: dict, plan_name: str) -> list[RunSpec]:
    plans = cfg.get("plans") or {}
    if plan_name not in plans:
        raise SystemExit(f"Unknown plan {plan_name!r}. Available: {sorted(plans)}")
    plan = plans[plan_name]
    version = cfg["benchmark_version"]
    suites: list[str] = list(plan["suites"])
    attacks: list[str] = list(plan.get("attacks") or [])
    repeats = int(plan.get("repeats", 1))
    baseline_repeats = int(plan.get("baseline_repeats", repeats))
    baseline_count = int(plan.get("baseline_count", 0))

    # Attacked (user_task, injection_task) pairs
    pairs: list[tuple[str, str, str]] = []
    if plan.get("pairs"):
        for p in plan["pairs"]:
            suite = get_suite(version, p["suite"])
            suite.get_user_task_by_id(p["user_task"])  # validate
            suite.get_injection_task_by_id(p["injection_task"])
            pairs.append((p["suite"], p["user_task"], p["injection_task"]))
    else:
        sampling = plan.get("sampling")
        for s in suites:
            suite = get_suite(version, s)
            all_pairs = [
                (s, ut, it)
                for ut in sorted(suite.user_tasks, key=_task_sort_key)
                for it in sorted(suite.injection_tasks, key=_task_sort_key)
            ]
            if sampling:
                rule = sampling.get("rule", "uniform_per_suite")
                if rule == "uniform_per_suite":
                    rng = random.Random(f"{sampling.get('seed', 0)}|{s}")
                    n = min(int(sampling["n"]), len(all_pairs))
                    chosen = set(rng.sample(range(len(all_pairs)), n))
                    all_pairs = [p for i, p in enumerate(all_pairs) if i in chosen]
                elif rule == "stratified_per_injection":
                    all_pairs = stratified_per_injection_pairs(
                        s,
                        sorted(suite.user_tasks, key=_task_sort_key),
                        sorted(suite.injection_tasks, key=_task_sort_key),
                        int(sampling["k"][s]),
                        sampling.get("seed", 0),
                    )
                else:
                    raise SystemExit(
                        f"Unknown sampling rule {rule!r} (supported: uniform_per_suite, stratified_per_injection)"
                    )
            pairs.extend(all_pairs)

    # Baselines: deterministic round-robin across suites, tasks in numeric order
    baselines: list[tuple[str, str]] = []
    if baseline_count:
        task_lists = {s: sorted(get_suite(version, s).user_tasks, key=_task_sort_key) for s in suites}
        idx = {s: 0 for s in suites}
        i = 0
        while len(baselines) < baseline_count:
            if all(idx[s] >= len(task_lists[s]) for s in suites):
                break
            s = suites[i % len(suites)]
            if idx[s] < len(task_lists[s]):
                baselines.append((s, task_lists[s][idx[s]]))
                idx[s] += 1
            i += 1

    specs: list[RunSpec] = []
    for r in range(max(repeats, baseline_repeats)):
        if r < baseline_repeats:
            specs.extend(RunSpec(s, ut, None, None, r) for s, ut in baselines)
        if r < repeats:
            for attack in attacks:
                specs.extend(RunSpec(s, ut, it, attack, r) for s, ut, it in pairs)
    return specs


# --------------------------------------------------------------------------------------------
# Single run
# --------------------------------------------------------------------------------------------
_ATTACK_CACHE: dict[tuple[str, str, str], Any] = {}
_ATTACK_LOCK = threading.Lock()


def get_attack(cfg: dict, model_id: str, suite_name: str, attack_name: str):
    key = (model_id, suite_name, attack_name)
    with _ATTACK_LOCK:
        if key not in _ATTACK_CACHE:
            suite = get_suite(cfg["benchmark_version"], suite_name)
            # The attack only uses the pipeline's name (for MODEL_NAMES lookup); no model calls happen here.
            _ATTACK_CACHE[key] = load_attack(attack_name, suite, build_pipeline(model_id))
        return _ATTACK_CACHE[key]


def _scrub(text: str) -> str:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        text = text.replace(project, "<project>")
    return text


def execute_run(spec: RunSpec, cfg: dict, model_id: str, costs: CostTracker, run_key: str | None = None) -> dict:
    t0 = time.monotonic()
    acc = UsageAccumulator()
    capture: dict[str, Any] = {}
    rec: dict[str, Any] = {
        "run_id": spec.run_id(run_key or model_id),
        "timestamp": utc_now_iso(),
        "agentdojo_version": AGENTDOJO_VERSION,
        "benchmark_version": cfg["benchmark_version"],
        "model_id": model_id,
        "temperature": None,
        "seed": None,
        "suite": spec.suite,
        "user_task_id": spec.user_task_id,
        "injection_task_id": spec.injection_task_id,
        "attack": spec.attack,
        "repeat": spec.repeat,
        "is_baseline": spec.is_baseline,
        "compromised": None,
        "compromised_strict": None,
        "utility": None,
        "user_task_prompt": None,
        "injection_task_goal": None,
        "transcript": [],
        "tool_calls": [],
        "injection_text": None,
        "injection_seen": None,
        "state_available": False,
        "state_snapshot_omitted": False,
        "state_pre": None,
        "state_post": None,
        "state_diff": None,
        "tokens_in": 0,
        "tokens_out": 0,
        "finish_reasons": [],
        "malformed": False,
        "est_cost_usd": 0.0,
        "duration_s": None,
        "error": None,
    }
    try:
        suite = get_suite(cfg["benchmark_version"], spec.suite)
        user_task = suite.get_user_task_by_id(spec.user_task_id)
        rec["user_task_prompt"] = user_task.PROMPT
        injection_task = None
        injections: dict[str, str] = {}
        if not spec.is_baseline:
            injection_task = suite.get_injection_task_by_id(spec.injection_task_id)
            rec["injection_task_goal"] = injection_task.GOAL
            attack = get_attack(cfg, model_id, spec.suite, spec.attack)
            injections = attack.attack(user_task, injection_task)
            rec["injection_text"] = dict(injections)
        pipeline = build_instrumented_pipeline(cfg, model_id, acc)
        utility, security = run_task_capture(suite, pipeline, user_task, injection_task, injections, capture)
        rec["utility"] = bool(utility)
        rec["compromised"] = None if spec.is_baseline else bool(security)
        # Scores are kept for reference, but a malformed model response makes the run an error (retried on resume).
        rec["error"] = malformed_error(acc)
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exception(type(e), e, e.__traceback__)
        rec["error"] = {
            "type": f"{type(e).__module__}.{type(e).__name__}",
            "message": _scrub(str(e))[:2000],
            "traceback": _scrub("".join(tb[-6:]))[-4000:],
        }
    finally:
        msgs = capture.get("messages")
        if msgs is not None:
            rec["transcript"] = to_jsonable(
                [{k: v for k, v in m.items() if k != GOOGLE_CONTENT_KEY} for m in msgs]
            )
            rec["tool_calls"] = extract_tool_calls(rec["transcript"])
        pre = capture.get("pre_environment")
        post = capture.get("task_environment") if (rec["error"] is None or rec["error"]["type"] == "MalformedResponse") else None
        pre_json = pre.model_dump(mode="json") if pre is not None else None
        post_json = post.model_dump(mode="json") if post is not None else None
        if pre_json is not None and post_json is not None:
            rec["state_available"] = True
            rec["state_diff"] = state_diff(pre_json, post_json)
        rec["state_pre"], om1 = snapshot_or_none(pre_json)
        rec["state_post"], om2 = snapshot_or_none(post_json)
        rec["state_snapshot_omitted"] = om1 or om2
        rec["temperature"] = acc.sent_value(acc.temperatures)
        rec["seed"] = acc.sent_value(acc.seeds)
        rec["tokens_in"] = acc.tokens_in
        rec["tokens_out"] = acc.tokens_out
        rec["finish_reasons"] = list(acc.finish_reasons)
        rec["malformed"] = acc.malformed
        if rec["error"] is None and acc.malformed:
            rec["error"] = malformed_error(acc)
        add_derived(rec)
        rec["est_cost_usd"] = round(costs.cost_of(acc.tokens_in, acc.tokens_out), 8)
        rec["duration_s"] = round(time.monotonic() - t0, 3)
    return rec


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------
def load_cfg(path: str) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    with open(p) as f:
        return yaml.safe_load(f)


def pending_specs(
    specs: list[RunSpec], model_id: str, runs_dir: Path, rerun_ids: set[str] | None = None
) -> list[RunSpec]:
    """Resume filter: drop specs whose run_id already has an error==null line; errored ones are kept (retried).
    run_ids in `rerun_ids` are always kept."""
    done_ids = completed_run_ids(runs_dir) - (rerun_ids or set())
    return [s for s in specs if s.run_id(model_id) not in done_ids]


def dry_run(specs: list[RunSpec], todo: list[RunSpec], model_id: str, prices: tuple[float, float]) -> None:
    counts: dict[tuple[str, str], int] = {}
    for s in specs:
        k = (s.suite, s.attack or "baseline")
        counts[k] = counts.get(k, 0) + 1
    print(f"model_id={model_id}")
    print(f"{'suite':<12} {'attack':<28} runs")
    for (suite, attack), n in sorted(counts.items()):
        print(f"{suite:<12} {attack:<28} {n}")
    print(f"total runs in plan: {len(specs)}; already completed (skipped on resume): {len(specs) - len(todo)}; "
          f"to run: {len(todo)}")
    with_tokens = [r for r in iter_logged_runs(RUNS_DIR) if (r.get("tokens_in") or 0) > 0
                   and isinstance(r.get("est_cost_usd"), (int, float))]
    if not with_tokens:
        print("estimated cost: no token data yet")
        return
    # Prefer token averages from this model's own runs; fall back to all models' runs (tokens only, priced
    # at this model's rates). Thinking-heavy models can use far more output tokens, so treat that as a floor.
    own = [r for r in with_tokens if r.get("model_id") == model_id]
    basis = own or with_tokens
    avg_in = sum(r["tokens_in"] for r in basis) / len(basis)
    avg_out = sum(r["tokens_out"] for r in basis) / len(basis)
    avg_cost = estimate_cost(avg_in, avg_out, *prices)
    source = f"{len(basis)} logged {model_id} runs" if own else f"{len(basis)} logged runs of other models (floor)"
    print(f"estimated cost: ${avg_cost * len(todo):.4f} for {len(todo)} runs "
          f"(avg over {source}: {avg_in:.0f} in / {avg_out:.0f} out tokens, ${avg_cost:.5f}/run)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Resumable AgentDojo runner (Vertex AI)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="run at most N of the remaining runs")
    ap.add_argument("--rerun-ids", nargs="+", default=[], metavar="RUN_ID",
                    help="treat these run_ids as not completed (existing lines are ignored for resume)")
    args = ap.parse_args(argv)

    cfg = load_cfg(args.config)
    plan = cfg["plans"].get(args.plan) or {}
    cfg = {**cfg, **(plan.get("overrides") or {})}
    # A plan picks its agent model by naming a key under `vertex:` (default: flash_model).
    model_key = plan.get("model", "flash_model")
    if model_key not in cfg["vertex"]:
        raise SystemExit(f"plan {args.plan!r}: model key {model_key!r} not found under vertex: in config")
    model_id = cfg["vertex"][model_key]
    # A plan may set `temperature:`; non-default temperatures get their own run_ids (model_id@t<temp>) so they never
    # collide with, or resume from, runs of the same model at the config default.
    default_temp = cfg["vertex"].get("temperature", 0.0)
    if "temperature" in plan:
        cfg = {**cfg, "vertex": {**cfg["vertex"], "temperature": plan["temperature"]}}
    temp = cfg["vertex"].get("temperature", 0.0)
    run_key = model_id if temp == default_temp else f"{model_id}@t{float(temp):g}"
    prices = get_prices(cfg, model_id)  # fail fast if pricing is missing
    global PRESERVE_THOUGHT_SIGNATURES
    PRESERVE_THOUGHT_SIGNATURES = model_id in (cfg["vertex"].get("preserve_thought_signatures") or [])

    specs = expand_plan(cfg, args.plan)
    remaining = pending_specs(specs, run_key, RUNS_DIR, rerun_ids=set(args.rerun_ids))
    todo = remaining if args.limit is None else remaining[: args.limit]

    if args.dry_run:
        dry_run(specs, todo, model_id, prices)
        print(f"temperature={temp} run_key={run_key}")
        return 0

    costs = CostTracker(cfg, model_id, RUNS_DIR)
    run_logger = RunLogger(RUNS_DIR, utc_date())
    concurrency = int(cfg.get("concurrency", 1))
    print(f"plan={args.plan} model={model_id} temperature={temp} benchmark={cfg['benchmark_version']} planned={len(specs)} "
          f"skipped_completed={len(specs) - len(remaining)} to_run={len(todo)} concurrency={concurrency} "
          f"spend_so_far=${costs.total:.4f} cap=${costs.spend_cap_usd:.2f} "
          f"log={run_logger.path.relative_to(PROJECT_ROOT)}", flush=True)

    stop = threading.Event()

    def on_sigint(signum, frame):
        if stop.is_set():
            raise KeyboardInterrupt
        stop.set()
        print("\nSIGINT: no new runs will be scheduled; waiting for in-flight runs (Ctrl-C again to abort).",
              flush=True)

    signal.signal(signal.SIGINT, on_sigint)

    t_start = time.monotonic()
    n_done = n_err = n_comp = 0
    cap_hit = False
    pending: set[Future] = set()
    queue = list(todo)

    def report(fut: Future) -> None:
        nonlocal n_done, n_err, n_comp
        rec = fut.result()
        costs.add(rec["est_cost_usd"])
        n_done += 1
        if rec["error"] is not None:
            n_err += 1
        elif rec["compromised"] is True:
            n_comp += 1
        err = f" ERROR {rec['error']['type']}: {rec['error']['message'][:120]}" if rec["error"] else ""
        print(f"[{n_done}/{len(todo)}] {rec['run_id']} {rec['suite']}/{rec['user_task_id']}/"
              f"{rec['injection_task_id'] or 'baseline'} r{rec['repeat']} utility={rec['utility']} "
              f"compromised={rec['compromised']} tok={rec['tokens_in']}/{rec['tokens_out']} "
              f"${rec['est_cost_usd']:.5f} {rec['duration_s']:.1f}s{err}", flush=True)
        if n_done % 10 == 0:
            elapsed = time.monotonic() - t_start
            remaining = len(todo) - n_done
            eta = elapsed / n_done * remaining
            print(f"PROGRESS {n_done}/{len(todo)} errors={n_err} compromised={n_comp} "
                  f"est_spend=${costs.total:.4f} ETA={eta / 60:.1f}min", flush=True)

    def task(spec: RunSpec) -> dict:
        rec = execute_run(spec, cfg, model_id, costs, run_key)
        run_logger.write(rec)
        return rec

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while queue or pending:
            while queue and len(pending) < concurrency and not stop.is_set():
                if costs.should_stop():
                    cap_hit = True
                    stop.set()
                    break
                pending.add(pool.submit(task, queue.pop(0)))
            if not pending:
                break
            finished, pending = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
            for fut in finished:
                report(fut)
            if stop.is_set() and not pending:
                break

    elapsed = time.monotonic() - t_start
    if cap_hit or costs.should_stop():
        print(f"SPEND CAP REACHED at ${costs.total:.4f} after {n_done} runs", flush=True)
    print(f"DONE {n_done}/{len(todo)} errors={n_err} compromised={n_comp} "
          f"session_spend=${costs.total - costs.starting_total:.4f} total_spend=${costs.total:.4f} "
          f"elapsed={elapsed:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
