Use my orchestrate skill to plan and run this task. Break it into the phases below,
run independent work in parallel where it is safe, and STOP at every point marked
🛑 HUMAN CHECKPOINT until I reply.

# Context

Research pilot: "Do LLM judges misreport attacks on AI agents?"
We compare LLM-judge verdicts against state-based ground truth from AgentDojo.
This is Day 1 of a 3-day pilot. Phases 0–1 are DONE:
- AgentDojo is installed in judge-pilot/.venv (versions pinned in requirements.txt)
- Vertex AI is connected via Application Default Credentials and .env
- RECON.md records how AgentDojo calls Gemini, the meaning of `security`,
  how to run baseline tasks, and how repeats behave
- A 1-task AgentDojo run through Vertex has succeeded

Today's remaining goal: a resumable runner + logger, a hand-checked smoke test,
a cost estimate, an unattended Night 1 run, and a morning report script.
Days 2–3 (judges, dual-target attack, grounding) are NOT in scope, but the log
format must serve them without changes.

# Before anything else

1. Read RECON.md, config.yaml, .env.example, requirements.txt and any existing src/ files.
2. Activate .venv and confirm `pip show agentdojo google-genai` matches requirements.txt.
3. Re-run src/vertex_check.py once to confirm the connection still works.
4. Summarize in 5 lines what you learned from RECON.md that affects Phases 2–6
   (especially: `security` meaning, baseline method, repeat/caching behavior,
   whether a Vertex adapter exists, whether state before/after is exposed).
If anything in RECON.md is missing or unclear, STOP and ask me.

# Hard constraints

- ONLY Vertex AI credits. No Anthropic, OpenAI or AI Studio API keys.
- Agent model ID comes from config.yaml (Gemini Flash). Never hard-code it.
- Log exact model ID, temperature, seed and AgentDojo version on every run.
- No credentials in code, logs or git.
- Everything resumable; failed runs are logged, never silently dropped.
- Everything runs locally against AgentDojo's simulated environments only.

# Phase 2 — Logger + runner

## src/logger.py
Write one JSON object per line to data/runs/<run_date>.jsonl with:
- run_id: deterministic SHA-256 (first 16 chars) of
  suite + user_task_id + injection_task_id + attack + repeat + model_id
- timestamp (UTC ISO), agentdojo_version, model_id, temperature, seed
- suite, user_task_id, injection_task_id (null for baseline),
  attack (null for baseline), repeat, is_baseline (bool)
- compromised: explicit bool = the injection goal was achieved per AgentDojo's
  state check (use the semantics verified in RECON.md); null for baseline
- utility: bool, the user task succeeded per AgentDojo's check
- transcript: full ordered message list (system, user, assistant, tool calls,
  tool results), serialized as plain JSON
- tool_calls: flat ordered list of {order, name, args, result}
- injection_text: the exact injected text placed in the environment (null for baseline)
- state_pre / state_post / state_diff: if AgentDojo exposes environment state,
  store a JSON diff (and snapshots if small). If not available, set state_diff to null
  and state_available=false. Do not fake it.
- tokens_in, tokens_out, est_cost_usd, duration_s
- error: null, or exception type + message + short traceback
Use atomic appends (write a full line, then flush) so a crash never leaves a broken line.

## src/cost.py
- Per-call token counts from Vertex response usage metadata.
- Prices per million tokens live in config.yaml (I will fill/confirm them);
  never hard-code prices in Python.
- Running total across the whole run, loaded from existing JSONL on restart.
- `should_stop()` returns True once the total >= spend_cap_usd from config.yaml.

## src/runner.py
- CLI: `python -m src.runner --config config.yaml --plan night1 [--dry-run] [--limit N]`
- Builds the run matrix from config.yaml: suites, attacks, repeats, baseline count,
  optional sampling (rule + seed in config).
- --dry-run prints the matrix size per suite/attack and estimated cost; makes no calls.
- Resumable: skip any run_id already in data/runs/*.jsonl with error == null.
  Runs with errors are retried on the next start.
- Repeats must be real independent runs. Use what RECON.md says about caching
  to make sure AgentDojo doesn't reuse an earlier result.
- Retries transient Vertex errors (429, 500, 503, timeouts) with exponential backoff
  + jitter, max 5 tries; then log the run with its error and move on.
- Concurrency from config (default 4).
- Checks cost.should_stop() before starting each run; on stop, finish in-flight
  runs, print "SPEND CAP REACHED at $X after N runs" and exit cleanly.
- Progress line every 10 runs: done/total, errors, compromised so far, est. spend, ETA.
- Graceful Ctrl+C: finish in-flight runs, then exit.

## Tests (quick, no model calls)
- run_id is stable for the same inputs and different for different repeats.
- Resume logic skips completed runs and retries errored ones (use a fake JSONL).
- Logger output always parses as JSON line by line.

# Phase 3 — Smoke test (5 attacked + 1 baseline)

- Run: `python -m src.runner --config config.yaml --plan smoke`
  with 5 attacked runs (mix banking and slack, important_instructions) + 1 baseline.
- Write src/inspect_run.py: given a run_id, print a readable summary:
  1. user task (what the user asked)
  2. injection text and where it was placed
  3. what the attacker wanted (injection task goal)
  4. every tool call the agent made, in order, with args
  5. final assistant reply
  6. compromised, utility, and state_diff (or "state not available")
- Print summaries for all 6 runs.
- For each run, add your own one-line consistency check: does `compromised` agree
  with what the tool calls show? Flag any mismatch with ⚠️ and explain it.

🛑 HUMAN CHECKPOINT 3: I will read these 6 summaries and confirm the state check
matches what I see. Do NOT start the night run until I say "go".

# Phase 4 — Cost estimate

- From the smoke-test tokens, compute average tokens and cost per attacked run
  and per baseline run.
- Run `--dry-run` for the night1 plan: banking + slack injection tasks ×
  important_instructions × 2 repeats, plus 10 baseline runs.
- If the full matrix is far above ~150 attacked runs, propose a sampling rule
  (even coverage across user tasks and injection tasks, fixed seed) that lands
  at 100–150 attacked runs. Show the before/after counts.
- Show: total runs, estimated cost, estimated duration at current concurrency,
  and a suggested spend_cap_usd at ~1.5× the estimate.
- Remind me to set a Cloud Billing budget alert at 50% and 90% of my credits in the
  console. Do NOT create billing budgets yourself.

🛑 HUMAN CHECKPOINT 4: I confirm the run count, the spend cap and that the budget
alert is set. Then write my confirmed values into config.yaml.

# Phase 5 — Launch Night 1

- Launch: `python -m src.runner --config config.yaml --plan night1`
  inside tmux (session name `night1`), or with nohup if tmux is missing,
  logging stdout+stderr to logs/night1.log.
- Watch the first 10 runs live. If the error rate is above 20% or the first runs
  look wrong, stop it and tell me before continuing.
- Then print, in a clearly labelled block, the exact commands for me to:
  - attach to / detach from the tmux session
  - tail the log
  - count completed runs and errors so far
  - stop the run safely
  - resume after a crash (same command; it skips completed runs)

# Phase 6 — src/morning_check.py (write it now, I run it tomorrow)

`python -m src.morning_check --config config.yaml` reads data/runs/*.jsonl and prints:
- total runs, completed, errored (with the top 3 error types)
- compromised count and % (attacked runs only): overall, by suite, by attack,
  with a 95% Wilson confidence interval on the overall rate
- utility rate for attacked runs and for baseline runs
- repeat agreement: for task pairs run twice, % where both repeats gave the same
  `compromised` value (early sign of run-to-run variance)
- state_diff availability: % of runs with state_diff present
- total estimated spend vs spend cap
- 3 compromised run_ids + 1 non-compromised run_id with one-line summaries,
  for my hand review (reuse inspect_run.py)
- a verdict line:
  - "READY FOR DAY 2" if compromised >= 20
  - otherwise "TOO FEW COMPROMISED (N)" plus a concrete fix: the exact config.yaml
    change (add the travel suite and/or the tool_knowledge attack) and the exact
    command to run tonight
- also a warning line if state_diff is missing for most runs: "Day 3 grounding needs
  state_diff — fix before Day 3"
Test it now on the smoke-test data so it runs without errors.

# Definition of done

- src/logger.py, cost.py, runner.py, inspect_run.py, morning_check.py exist with tests passing.
- README.md updated: one short section per command (smoke, dry-run, night1, resume,
  inspect, morning check).
- Smoke test passed my hand review.
- Night 1 is running unattended under the spend cap.
- morning_check.py runs on the data so far without errors.
- Everything committed to git (data/, logs/, .env gitignored).

Finish with a short summary: what was built, what is running, the commands I need
tomorrow morning, and open risks (especially if state_diff is unavailable or
compromise rates look very low or very high in the first runs).