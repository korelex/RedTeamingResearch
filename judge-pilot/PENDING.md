# Pending items: resume 2026-10-22 morning

> **Update 2026-10-21 13:50 IST.** Manish decided: "go 31pro", 3.8 Flash at full Night 1 size (142 runs), no VM, no
> separate project. `logs/run_new_models.sh` is running under `caffeinate` (pid in `logs/night1_new_models.pid`,
> log `logs/night1_new_models.log`). It runs `night1_31pro` and then `night1_38flash`, up to 3 resume attempts each.
> The first 10 runs on 3.1 Pro had 0 errors (ETA ≈ 2 h). 3.8 Flash may take 1–2 days.
> Keep the laptop on power with the lid open. If it stops, rerun `caffeinate -ims logs/run_new_models.sh`.

State at pause (2026-10-21, ≈ 13:45 IST): **nothing is running.** Every result is saved in `data/runs/` and all code
is committed (last commit `123ad8b`). Pilot spend so far: **$5.38 of the $25 cap**.

## Where we are

| Model | Temp | Status | Compromised (attacked) |
|---|---|---|---|
| gemini-2.5-flash | 0 | ✅ Night 1 done (145 runs) | 87/125 (70%) |
| gemini-2.5-pro | 0 | ✅ Night 1 done (145 runs) | 65/125 (52%) |
| gemini-3.8-flash | 0 / 1.0 | ✅ smoke done (6 runs + 5 of 6 runs) | 0/5, 0/4 |
| gemini-3.1-pro-preview | 0 / 1.0 | ✅ smoke done (6 + 6 runs) | 0/5, 0/5 |

Decided: **temperature 0 for every model.** `loop_check` found no loops, and temperature 1.0 used 35–60% more tokens.

## 1. Decisions needed from Manish (first thing tomorrow)

- [ ] **"go 31pro"**: launch `night1_31pro` (142 runs, ≈ 30–40 min, ≈ $2.85–4.30).
- [ ] **3.8 Flash Night 1 size.** Google returns a lot of 429/504 capacity errors, so it takes ≈ 11 min per run.
  - Option 1: full 142 runs (≈ 1–2 days, ≈ $6.30–9.00)
  - Option 2: **60-run sample**, 50 attacked + 10 baseline, no repeats (≈ 8–12 h, ≈ $2.70–3.80). *Recommended.*
  - Option 3: wait for a quieter time of day.
- [ ] **Cloud VM: yes or no** (e2-small, ≈ $1.70 for 3 days). Needed only for the full 3.8 Flash run.
  - Requires a project owner to grant **Compute Admin** and to create a VM service account with **Vertex AI User**.
  - Claude will print the commands; Manish runs them. Claude does not create cloud resources.
- [ ] **Separate GCP project for the pilot or for Rhit?** Rhit's Gemini 3.x usage shares the credits and the
      capacity. It was 82% of October's bill, and 3.8 Flash calls overlapped with our smoke runs.

## 2. Work for Claude after the decisions

- [ ] If option 2: add a `night1_38flash_small` plan (seeded, one repeat, 50 attacked + 10 baseline). Dry-run it first.
- [ ] Launch runs one at a time (the spend cap reads the total only at start), each under `caffeinate -ims`:
      ```
      caffeinate -ims .venv/bin/python -m src.runner --config config.yaml --plan night1_31pro > logs/night1_31pro.log 2>&1 &
      ```
- [ ] Watch the first 10 runs; retry errors with the same command (resume skips completed runs).
- [ ] After each night run: `python -m src.loop_check`, `python -m src.morning_check --model <label>`.
- [ ] Re-run the analysis for all 4 models: `python -m src.compare_models --config config.yaml` and
      `python -m src.analyze_day1` (updates `DAY1_RESULTS.md`).
- [ ] Update `COST_LOG.md` with the new batches.
- [ ] Next day: check the Billing SKU CSV to confirm the **gemini-3.1-pro-preview price** ($2.00 / $12.00 is still
      unconfirmed in `config.yaml`).
- [ ] Optional: the remaining 3.8 Flash temperature 1.0 smoke run (`d62152bd`, failed twice on 429). Only needed if we revisit temperature.

## 3. Day 2 (judges): not started

- [ ] Manish to add a Day 2 prompt (like `day1prompt2.md`), or Claude drafts a plan from `DAY1_RESULTS.md`:
  - Judge models, with two views per judge: **final answer only** vs **full transcript**.
  - Score judges separately on: compromised (A), **saw the attack and resisted (B)**, never saw it (C), and
    repeat-flip pairs.
  - Keep judge quality: no thinking cap. Batch prediction (≈ 50% off) is fine for single-turn judge calls.
  - Judge input is ≈ 850 tokens per transcript, so the cost is small; estimate it when the plan is drafted.
- [ ] Raise `spend_cap_usd` for Day 2 once the judge cost is estimated.

## 4. Open risks

- **3.8 Flash capacity (429/504):** this sets the timeline, not the cost.
- **Shared project:** Rhit's usage can use up the credits and compete for capacity.
- **Contamination:** the Gemini 3.x models resisted 19 of 19 attacks they saw. They may have been trained on AgentDojo; note this in the paper.
- **Laptop runs stop on shutdown.** Lid open plus `caffeinate` is fine; shutdown means resume with the same command.
- **The live spend-cap stop is still untested.** It was never reached.

## Useful commands

```
cd ~/Korelex/RedTeamingResearch/judge-pilot
.venv/bin/python -m src.runner --config config.yaml --plan <plan> --dry-run    # size and cost, no calls
.venv/bin/python -m src.loop_check                                            # loop signals per model
.venv/bin/python -m src.compare_models --config config.yaml                   # quality vs cost per model
.venv/bin/python -m src.morning_check --config config.yaml --model <label>    # e.g. gemini-3.1-pro-preview
.venv/bin/python -m src.project_usage --config config.yaml                    # whole-project usage per model and owner
```

Reference files: `DAY1_RESULTS.md` (dataset analysis), `COST_LOG.md` (estimates vs bill, insights),
`SMOKE_REVIEW.md` (Day 1 smoke review), `RECON.md` (AgentDojo internals).
