# judge-pilot

Runs AgentDojo tasks against Gemini on Vertex AI.

## Why the adapter exists

The AgentDojo CLI's `--model` only accepts a fixed enum (`agentdojo/models.py`, `ModelsEnum`),
and `gemini-2.5-flash` is not in it. `src/vertex_setup.py` builds the pipeline directly instead:

- `GoogleLLM(model_id, genai.Client(vertexai=True, project=..., location=...))`
- `AgentPipeline.from_config(PipelineConfig(llm=<that object>, defense=None, ...))`, named `<model_id>-vertex`
- adds `model_id -> "AI model developed by Google"` to `agentdojo.models.MODEL_NAMES` at runtime, because attacks need it.
  The installed package is not modified.

`build_pipeline(model_id=None)` uses `vertex.flash_model` from `config.yaml` when no model ID is passed.

## Vertex environment (`.env`)

```
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=<project>
GOOGLE_CLOUD_LOCATION=us-central1
```

Authentication uses Application Default Credentials. `GCP_PROJECT` and `GCP_LOCATION` are unset at startup.

## Run the baseline (no injections)

```
.venv/bin/python src/run_baseline.py --suite banking --user-tasks user_task_0
```

Options: `--user-tasks` (one or more IDs), `--logdir` (default `runs`), `--model`, `-f/--force-rerun`.
Logs are written to `runs/<pipeline>/<suite>/<user_task>/none/none.json`.

## Caveats

1. `security=True` means the **attack succeeded** (the injection goal was met). It does not mean "secure".
   For runs without injections, `security` is always True and means nothing.
2. `ApiError` ("internal server error") and `ServerError` from the model are caught and logged as
   `utility=False, security=True`. In attack runs, that looks like a successful attack. Check the `error` field
   and the messages before counting a result.
3. Results are cached per path (`pipeline name / suite / task / attack / injection task`). A second run with
   the same path skips the task and returns the cached result. Pass `-f` (`force_rerun=True`) to overwrite it.

## Experiment commands

All commands run from the project root with `.venv/bin/python` (or an activated venv). Plans live in
`config.yaml` under `plans:`. Each run writes one JSON line to `data/runs/<UTC date>.jsonl` (see `src/logger.py`).
A plan uses `vertex.flash_model` unless it sets `model: <key under vertex:>` (`smoke_pro` and `night1_pro` use `pro_model`).

### Smoke test
```
python -m src.runner --config config.yaml --plan smoke        # 5 attacked + 1 baseline, Flash
python -m src.runner --config config.yaml --plan smoke_pro    # same runs on Pro
```

### Dry run (no model calls)
```
python -m src.runner --config config.yaml --plan night1 --dry-run
```
Prints runs per suite/attack, how many are already done, and an estimated cost from logged token averages
(priced at the plan model's rates from `pricing:`).

### Night 1
```
mkdir -p logs
nohup python -m src.runner --config config.yaml --plan night1 > logs/night1.log 2>&1 &
echo $! > logs/night1.pid
```
Use `--plan night1_pro` (and `logs/night1_pro.log`) for Pro. The runner stops scheduling new runs once total
logged spend reaches `spend_cap_usd`, and prints a `PROGRESS` line every 10 runs.

### Resume
Run the same command again. Runs with an `error: null` line are skipped; errored runs are retried.
`--rerun-ids ID ...` forces specific runs again. Stop safely with `kill -INT $(cat logs/night1.pid)`
(in-flight runs finish first).

### Inspect a run
```
python -m src.inspect_run <run_id>
python -m src.inspect_run --all
```

### Morning check
```
python -m src.morning_check --config config.yaml [--model gemini-2.5-flash]
```
Counts, errors, compromise rate (AgentDojo and strict) with a 95% Wilson CI, injection-seen rate, utility,
repeat agreement, state_diff availability, spend vs cap, hand-review picks and a Day 2 verdict.

### Compare models (Flash vs Pro)
```
python -m src.compare_models --config config.yaml
```

### Derived fields
`compromised_strict` (fixes the banking injection_task_0/1/3 checks) and `injection_seen` are added by the
runner. Older lines are backfilled with `python -m src.derived --backfill` (keeps a `.jsonl.bak`).

### Gemini 3.x models and temperature
Plans can set `model: <key under vertex:>` and `temperature:`. Runs at a non-default temperature get their own run_ids
and show as `<model>@t<temp>` in the reports. Gemini 3.x models are served only from the `global` location
(`vertex.model_locations`), and their function-call thought signatures are passed back unchanged
(`vertex.preserve_thought_signatures`). Their plans use `gemini3_throttle` (2 workers, longer backoff) because of
shared-capacity 429 errors. Wrap long runs in `caffeinate -ims` so the Mac doesn't sleep.

### Loop check
```
python -m src.loop_check [--models LABEL ...] [--all]
```
Flags repeated identical tool calls, 15 or more model calls, and 4,000 or more output tokens per call (thinking loops).

### Day 1 analysis
```
python -m src.analyze_day1        # writes DAY1_RESULTS.md
```
Per model: compromise rate, judge-relevant categories, success per injection task, repeat flips, transcript size.

### Whole-project usage and cost
```
python -m src.project_usage --config config.yaml [--start 2026-10-15]
```
Read-only Cloud Monitoring token counts per model, priced from `pricing:`, with the possible owner from
`usage_owners:`. Compare with the Billing SKU CSV (see `COST_LOG.md`).
