# Cost log: estimated vs actual Vertex AI spend

Project `korelex-ai-lab`, region `us-central1`. Estimates come from `est_cost_usd` in `data/runs/*.jsonl`. Each
one is token counts (from Vertex `usage_metadata`) × the prices in `config.yaml`. Thinking tokens count as
output. Errored attempts are included, because Vertex billed them too.

The "Actual" columns are filled in by hand from Cloud Billing once the data has landed (usually the next day).

## Prices used (UNCONFIRMED; check the Vertex AI pricing page)

| Model | Input $/1M tokens | Output $/1M tokens (incl. thinking) | Note |
|---|---|---|---|
| gemini-2.5-flash | 0.30 | 2.50 | |
| gemini-2.5-pro | 1.25 | 10.00 | prompts ≤ 200k tokens tier (all our prompts are far smaller) |

## Batches run on 2026-10-20

Billing days follow **US Pacific time**, so the Pacific (PT) column shows which billing day each batch falls on.
The times are when each batch's runs started.

| # | Plan | Model | Start → last run start (UTC) | PT (billing day) | Log lines | Completed / errored | Baseline / attacked | Compromised | Tokens in | Tokens out | **Est. cost** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | smoke | gemini-2.5-flash | 04:52 → 04:57 | 19 Oct 21:52 → 21:57 | 12 | 12 / 0 | 2 / 10 | 6 | 37,546 | 10,822 | **$0.0383** |
| 2 | night1 (+ resume) | gemini-2.5-flash | 13:04 → 13:27 | 20 Oct 06:04 → 06:27 | 141 | 139 / 2 | 19 / 120 | 83 | 459,545 | 191,599 | **$0.6169** |
| 3 | smoke_pro | gemini-2.5-pro | 13:27 → 13:28 | 20 Oct 06:27 → 06:28 | 6 | 6 / 0 | 1 / 5 | 3 | 16,773 | 13,521 | **$0.1562** |
| 4 | night1_pro (+ resume) | gemini-2.5-pro | 13:44 → 14:08 | 20 Oct 06:44 → 07:08 | 140 | 139 / 1 | 19 / 120 | 62 | 437,566 | 316,268 | **$3.7096** |
| | **Total** | | | | **299** | | | | **951,430** | **532,210** | **$4.5210** |

**Notes on each batch**
- **Smoke:** the 12 lines are the original 6 runs plus a later backfill re-run of each. Both attempts were billed.
- **Night 1:** the plan has 142 runs. 3 were already done during the smoke test, so 139 ran, and 141 lines were logged. The 2 errors were a `MalformedResponse` (`fbe03f07…`) and a Vertex `504 DEADLINE_EXCEEDED` after 926 s (`41f4001b…`). Their attempts cost $0.0035, and both succeeded when retried by the resume command.
- **Smoke Pro:** 6 runs (5 attacked + 1 baseline), the same runs as the Flash smoke test.
- **Night 1 Pro:** the same 142-run sample as Night 1 Flash; 3 were already done by smoke_pro, so 139 ran. The one
  error was a `MalformedResponse` (`9c6cf39f…`, $0.0294), which succeeded on resume. It took 23 minutes (the
  dry run estimated $3.62).

### Per model (to compare with Billing grouped by SKU)

| Model | Tokens in | Tokens out | Est. input cost | Est. output cost | **Est. total** | Actual (Billing) | Difference |
|---|---|---|---|---|---|---|---|
| gemini-2.5-flash | 497,091 | 202,421 | $0.1491 | $0.5061 | **$0.6552** | | |
| gemini-2.5-pro | 454,339 | 329,789 | $0.5679 | $3.2979 | **$3.8658** | | |
| **Total** | 951,430 | 532,210 | | | **$4.5210** | | |

**Calls that are not logged here.** Billing will also include `src/vertex_check.py` connection checks and the
Day 1 part 1 `run_baseline.py` runs. These were a handful of short Flash calls, well under $0.01.
Billing also counts the hung `504` request as Vertex measures it, which may differ from our count.

## How to fill in "Actual" (next day)

1. Go to Console → **Billing → Reports**.
2. Set the **Time range** to 19–21 Oct 2026, and the **Project** filter to `korelex-ai-lab`.
3. Set **Group by** to **SKU**.
4. Under **Credits**, untick **"Promotions and others"**. Otherwise the credits cancel the cost to $0.
5. Add up the Gemini 2.5 Flash SKUs (input and output) and the Gemini 2.5 Pro SKUs, and enter the totals above.
6. Compare with the estimate:
   - **Within ±10–20%:** the prices in `config.yaml` are right.
   - **Further off:** check the SKU prices. A common cause is thinking tokens or the >200k-token tier being
     priced differently. Correct `pricing:` in `config.yaml` and note the change below.

## Running total vs cap

| Date | Cumulative est. spend | spend_cap_usd | Credits left (Billing → Credits) |
|---|---|---|---|
| 2026-10-20 | $4.5210 | $6.00 | |

## Change log

- 2026-10-20: log created. Prices are still unconfirmed.
- 2026-10-20: added the night1_pro batch.
- 2026-10-21: first Billing figures (Reports screenshot, before credits; date range not yet confirmed):
  "Gemini on Agent Platform" ₹850.90 and "Agent Platform Model Garden" ₹1,935.72 (marked "New"), ₹2,786.62 in total
  (user: ≈ $27 for 20 Oct). That is about 6× our $4.52 estimate. **Open discrepancy, see below.**

## Discrepancy under investigation (2026-10-21)

| Billing product | Actual (before credits) | Our estimate | Ratio |
|---|---|---|---|
| Gemini on Agent Platform | ₹850.90 | $4.52 (Flash + Pro, all batches) | ≈ 2× (exchange rate to be confirmed) |
| Agent Platform Model Garden | ₹1,935.72 | $0 (our code only calls gemini-2.5-flash / gemini-2.5-pro) | n/a |

Things to check:
1. The SKU breakdown (Reports, grouped by SKU, project `korelex-ai-lab`, 19–21 Oct): which SKUs make up each line.
2. Whether anything else uses the project. Earlier metrics showed StreamGenerateContent calls that were not from
   this code. Claude Code on this machine does not use Vertex (no `CLAUDE_CODE_USE_VERTEX` is set).
3. Whether the Gemini 2.5 Pro SKUs bill under "Model Garden" rather than "Gemini".

## Quality vs cost (Night 1, same 125 attacked + 20 baseline runs per model)

| | Flash | Pro |
|---|---|---|
| Est. cost per run | $0.0045 | $0.0267 (5.9×) |
| Cost per judge-ready run (injection reached the agent) | $0.0074 | $0.0372 (5.0×) |
| Attack success (strict) | 70% [61–77%] | 52% [43–61%] |
| Compromised when the injection was seen | 98% | 62.5% |
| Injection reached the agent | 71% | 83% |
| Baseline / attacked utility | 50% / 58% | 70% / 59% |
| Repeat agreement | 90% | 79% |
| Avg duration per run | 23 s | 38 s |

Paired over the 125 attacked runs: both compromised in 58, only Flash in 29, only Pro in 7, neither in 31
(exact McNemar p = 0.0003). Source: `python -m src.compare_models --config config.yaml`.

### Finding (2026-10-21): our token logs match Vertex; most of the bill is other usage in the same project

Source: Cloud Monitoring `aiplatform.googleapis.com/publisher/online_serving/token_count`, summed per model.

| Model | Vertex-counted tokens (in / out) | Our logs (in / out) | Ours? |
|---|---|---|---|
| gemini-2.5-flash | 498,349 / 202,857 (+630 at 18–19 UTC) | 497,091 / 202,421 | yes (difference = vertex_check / Day 1 calls) |
| gemini-2.5-pro | 454,339 / 329,789 | 454,339 / 329,789 | yes, exact |
| gemini-3.8-flash | ≈ 39.2M / 89k (20 Oct 12–14 and 17–18 UTC) | none | **no** |
| gemini-3-flash-preview | ≈ 40.1M / 47k (20 Oct 18–22 UTC) | none | **no** |
| gemini-4-argon, gemini-3.1-flash-lite, gemini-nano-banana-2.1 | small (console-style tests on 19–20 Oct) | none | **no** |

Request counts (serviceruntime `api/request_count`, 19–21 Oct): GenerateContent 1,264 (our runs), StreamGenerateContent
280, StreamRawPredict 20, SetPublisherModelConfig 1 (19 Oct 18:00 UTC), plus console UI calls. Our code makes only
non-streaming GenerateContent calls. StreamRawPredict is the method used by partner models in Model Garden, which
have no token metric here.

Conclusion: the pilot's token accounting is right. Billing also includes about 79M input tokens on Gemini 3.x models,
plus partner-model (Model Garden) calls, made by another client that uses `korelex-ai-lab`. The SKU breakdown is still
needed to confirm the prices and to split the ₹ lines.
