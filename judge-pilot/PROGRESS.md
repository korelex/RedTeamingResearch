# Pilot progress: "Do LLM judges misreport attacks on AI agents?" (as of 2026-10-24)

Legend: ✅ done · 🟡 partly done · ⏳ waiting on something external · ❌ not started

## Summary

| Day | Scope | Status |
|---|---|---|
| Day 1 | Agent runs with attacks; ground truth from environment state | ✅ Done (Phases 0–6, plus two extra models) |
| Day 2 | LLM judges compared with ground truth | ✅ Done (pre-registered, run, analysed, written up) |
| Day 3 | Grounding + dual-target attack | 🟡 Grounding done (as L3 in Day 2); dual-target attack ❌ |

**Spend so far:** ≈ $35.7 estimated (Day 1 agent runs ≈ $15.45, Day 2 judges ≈ $20.22), all on Vertex AI credits.
Some prices are still unconfirmed.

## Day 1: agent runs (`day1prompt2.md`)

| Phase | Item | Status | Evidence |
|---|---|---|---|
| 0 | AgentDojo 0.1.35 installed and pinned; recon of the source code | ✅ | `RECON.md`, `requirements.txt` |
| 1 | Vertex AI via ADC; connection and tool-calling tests; 1-task AgentDojo run | ✅ | `src/vertex_check.py`, `src/vertex_setup.py` (adapter) |
| 2 | Logger (JSONL, deterministic run_id, transcript, tool calls, `state_pre/post/diff`) | ✅ | `src/logger.py` |
| 2 | Cost tracking with prices in config and a spend cap | ✅ | `src/cost.py`, `config.yaml` |
| 2 | Resumable runner (dry run, retries with backoff, concurrency, cap check, progress) | ✅ | `src/runner.py` |
| 2 | Tests (run_id, resume, JSONL) | ✅ | `tests/` |
| 3 | Smoke test (5 attacked + 1 baseline), `inspect_run`, hand review | ✅ | `SMOKE_REVIEW.md`, `src/inspect_run.py` |
| 4 | Cost estimate and sampling rule (`stratified_per_injection`) | ✅ | `COST_LOG.md`, `config.yaml` |
| 5 | Night 1 run, unattended under the cap | ✅ | `data/runs/`, `logs/` |
| 6 | `morning_check` (rates, Wilson CI, repeat agreement, state_diff, verdict line) | ✅ | `src/morning_check.py` |
| Extra | Stricter labels: `compromised_strict`, `injection_seen` | ✅ | commit 783b404 |
| Extra | Extra models: Gemini 2.5 Pro, 3.1 Pro, 3.8 Flash (Gemini 3.x support, thought signatures) | ✅ | commits 7810a30, 99f2b8c |
| Extra | `loop_check`, `compare_models`, `analyze_day1`, `project_usage` | ✅ | `src/` |
| Extra | Billing reconciliation (pilot ≈ 14% of the October bill; the rest was another project) | ✅ | `COST_LOG.md` |
| Extra | Day 1 review Q&A (11 questions) | ✅ | `DAY1_QA.md`, `DAY1_RESULTS.md` |

**Day 1 result:** 592 runs (591 completed).
- Gemini 2.5 Flash compromised in 70% of attacked runs, 2.5 Pro in 52%.
- Gemini 3.x was compromised in 0 of 250.
- 84% of compromises were silent (the reply hides them).
- `state_diff` is available for 591/591 runs.
- Morning-check verdict: READY FOR DAY 2.

## Day 2: judges

| Item | Status | Evidence |
|---|---|---|
| Freeze the Day 1 dataset (SHA-256 verified, read-only) | ✅ | `src/freeze.py`, `frozen_manifests/night1_v1/` |
| Judge input views L1 / L2 / L3 and the output schema | ✅ | `src/judge_inputs.py`, `src/judge_schema.py`, `JUDGE_INPUTS.md` |
| Recon of existing scorers (promptfoo, PyRIT, garak) | ✅ | `SCORER_RECON.md` |
| Judge selection | ✅ | Gemini 3.1 Pro (frontier), Llama 4 Maverick (open weights), promptfoo grader (tool) |
| Claude as a non-Gemini judge | ❌ blocked | Vertex quota 0; increase request denied automatically |
| Pre-registration, approved before any judge call | ✅ | `PREREGISTRATION.md` (commit 1c3f8f2) |
| Judge runner (resumable, spend cap, promptfoo prompts copied verbatim) | ✅ | `src/judge_runner.py`, `src/judge_prompts.py` |
| Smoke test (69 calls, $0.21) | ✅ | `data/judgements_smoke/` |
| Deviations 1–3 logged (last verdict counts; Llama credit check after the run; smoke kept separate) | ✅ | `PREREGISTRATION.md` (commit 3854af1) |
| Full run: 7,960 judgements, 0 errors, $20.01 | ✅ | `data/judgements/2026-10-24.jsonl` |
| Pre-registered analysis (FN/FP, bootstrap CIs, McNemar/Fisher, Holm, kappa, splits) | ✅ | `src/analyze_day2.py`, `DAY2_RESULTS.md` |
| Findings write-up | ✅ | `FINDINGS.md` |

**Day 2 result:** Gate 2 PASS.
- Judges that see only the final reply miss about 47–64% of attacks; promptfoo misses 74% of silent attacks.
- With the full transcript, both LLM judges miss 0%. Gemini 3.1 Pro raises 1 false alarm in 41 resisted runs.
- Llama 4 raises false alarms on 44% of resisted runs and 35% of runs with no attack.
- Supported: H1 and H5. Not supported: H3 and H4.

## Day 3: grounding and dual-target attack

| Item | Status | Notes |
|---|---|---|
| Grounding: give the judge the environment changes | ✅ (inside Day 2) | View L3, tested as H3. No gain for Gemini (already at ceiling); Llama false alarms fell from 44% to 32% (not significant) |
| Dual-target attack: injection that also tries to fool the judge | ❌ | Needs a design, a pre-registration addendum, new agent runs (2.5 Flash/Pro), then judging. Rough cost $5–25 |

## Pending

| # | Item | Owner | When |
|---|---|---|---|
| 1 | ✅ Credit coverage confirmed 27 Oct (₹6.35k cost, ₹0.00 after credits). Still open: per-SKU prices for Llama 4 ($0.35/$1.15) and Gemini 3.1 Pro ($2/$12) | Manish (Reports by SKU or CSV) → Claude updates `config.yaml` | optional |
| 2 | Day 3 dual-target attack: design, pre-registration addendum, runs, judging, analysis | Claude drafts → Manish approves | after 1 |
| 3 | Budget alerts at 50% and 90% of credits (Cloud Billing console) | Manish | not yet confirmed |
| 4 | Separate GCP project from Rhit's usage (shared credits and capacity) | Manish | open decision |
| 5 | `PENDING.md` is out of date (from 21 Oct); replace it with this file or update it | Claude | on request |
| 6 | Optional: the remaining 3.8 Flash temperature 1.0 smoke run (`d62152bd`) | Claude | only if temperature is revisited |
| 7 | Optional (Gate 2 PASS → scale up): more suites (travel, workspace) and attacks (e.g. `tool_knowledge`) | Claude drafts → Manish approves | after Day 3 |

## Known limitations to carry into the write-up

- **Same-family judging:** Gemini judges Gemini agents. Llama 4 is the only non-Gemini judge.
- **Blatant attack text:** AgentDojo's `important_instructions` is easy to spot, so the perfect L2 scores may not hold for subtle attacks. This is the motivation for Day 3.
- **Small resisted sample:** only 41 resisted runs in the primary sample.
- **Possible contamination:** Gemini 3.x may have seen AgentDojo in training.
