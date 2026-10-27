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

## Whole-project breakdown per model, with estimated cost (2026-10-21)

Command: `python -m src.project_usage --config config.yaml` (read-only Cloud Monitoring, 15 Oct → 21 Oct 03:30 UTC).
Prices are in `config.yaml` `pricing:`. The prices for the Gemini 3.x models come from secondary sources and are not confirmed.
Owners are guesses from timing, not audit data.

| Model | Possible owner | Calls | Input tokens | Output tokens | $/1M in / out | **Est. cost** | Hours (UTC, 20 Oct unless noted) |
|---|---|---|---|---|---|---|---|
| gemini-3.8-flash | Rhit (possible) | 169 | 39,196,404 | 89,338 | 0.75 / 3.75 | **$29.73** | 12:00–17:00 |
| gemini-3-flash-preview | Rhit (possible) | 98 | 40,058,214 | 46,755 | 0.50 / 3.00 | **$20.17** | 17:00–22:00 |
| gemini-2.5-pro | Manish (judge-pilot) | 602 | 454,339 | 329,789 | 1.25 / 10.00 | **$3.87** | 13:00–14:00 |
| gemini-2.5-flash | Manish (judge-pilot) | 662 | 498,349 | 202,857 | 0.30 / 2.50 | **$0.66** | 04:00–14:00 (+630 tokens at 18:00) |
| gemini-4-argon | Manish/Rhit | 5 | 61,686 | 136 | n/a | n/a (tiny) | 19 Oct 17:00 – 20 Oct 18:00 |
| gemini-3.1-flash-lite | Manish/Rhit | 1 | 17,960 | 83 | n/a | n/a (tiny) | 19 Oct 17:00 |
| gemini-nano-banana-2.1 | Manish/Rhit | 5 | 2,451 | 12 | n/a | n/a (tiny) | 19 Oct 17:00 – 20 Oct 04:00 |
| gemini-3.5-flash-lite | Manish/Rhit | 2 | 0 | 0 | n/a | $0 | – |
| Model Garden partner model (StreamRawPredict) | Manish/Rhit | 20 | not reported | not reported | n/a | in Billing: ₹1,935.72 line? | 19–20 Oct |

**Estimated cost by owner:** Rhit (possible) ≈ **$49.90**, Manish (judge-pilot) ≈ **$4.52**, total ≈ **$54.42** before
Model Garden partner calls.

**This estimate is higher than Billing's ≈ $27–32.** The likely reasons:
1. **Cached input.** A coding agent sending about 300k tokens per call usually reuses a cached context, which is
   billed about 90% cheaper. The token metric doesn't separate cached tokens, so the Rhit estimate is an **upper bound**.
2. **Billing lag.** The 3-flash-preview usage at 17:00–22:00 UTC may not yet appear in the screenshot.
3. **Unconfirmed prices** for the Gemini 3.x models.

The Billing CSV grouped by SKU will settle the actual figures per model.

## Reconciliation with the actual bill (2026-10-21)

The actual total in Billing (before credits) is **₹2,786.62**: "Gemini on Agent Platform" ₹850.90 plus "Agent Platform
Model Garden" ₹1,935.72. That is about $32 at an assumed ₹88/$, not $27. The exact rate is in the Billing CSV.

The pilot's share can be stated with confidence. Its token counts match Vertex exactly, and the pilot uses no
context caching, so its cost is simply tokens × price (assuming the Gemini 2.5 prices are right). Everything else
in the bill is other usage.

| Owner | Models | Est. cost | ≈ ₹ (at ₹88/$) | Share of ₹2,786.62 |
|---|---|---|---|---|
| Manish (judge-pilot) | gemini-2.5-pro | $3.87 | ₹340 | 12% |
| Manish (judge-pilot) | gemini-2.5-flash | $0.66 | ₹58 | 2% |
| **Manish (judge-pilot) subtotal** | | **$4.52** | **≈ ₹398** | **≈ 14%** |
| **Rhit (possible) + other usage** | gemini-3.8-flash, gemini-3-flash-preview, Model Garden partner calls, small console tests | the rest | **≈ ₹2,389** | **≈ 86%** |
| **Total (actual)** | | | **₹2,786.62** | 100% |

The list-price estimate for Rhit's Gemini 3.x usage ($49.90 ≈ ₹4,390) is higher than the ₹2,389 left over. That
fits most of Rhit's 79M input tokens being cached (billed about 90% cheaper). The Billing CSV grouped by SKU will
give the exact split.

## ACTUAL cost per model from the Billing SKU CSV (October 2026, downloaded 2026-10-21)

Source: `~/Downloads/My Billing Account_Reports, 2026-10-01 — 2026-10-31.csv` (grouped by SKU, before credits).
The exchange rate implied by the SKU prices is **₹96 = $1**.

| Model | Possible owner | Input tokens | Cached input | Output tokens (incl. thinking) | **Actual ₹** | ≈ $ | Our estimate | Share |
|---|---|---|---|---|---|---|---|---|
| gemini-3.8-flash | Rhit (possible) | 8,689,902 | 30,506,502 | 89,338 | **₹1,754.76** | $18.28 | $29.73 at the wrong price (upper bound) | 69.6% |
| gemini-2.5-pro | Manish (judge-pilot) | 429,699 | 20,810 | 328,519 | **₹367.15** | $3.82 | $3.87 | 14.6% |
| gemini-3-flash-preview | Rhit (possible) | 2,368,403 | 37,689,811 | 46,755 | **₹308.02** | $3.21 | $20.17 (no caching) | 12.2% |
| gemini-2.5-flash | Manish (judge-pilot) | 503,997 | 31,178 | 211,105 | **₹65.26** | $0.68 | $0.66 | 2.6% |
| gemini-4-argon | Manish/Rhit | 61,686 | – | 136 | **₹23.94** | $0.25 | n/a | 0.9% |
| gemini-3.1-flash-lite | Manish/Rhit | 35,036 | – | 1,718 | **₹1.09** | $0.01 | n/a | 0.0% |
| gemini-nano-banana-2.1 | Manish/Rhit | 2,451 | – | 12 | **₹0.36** | $0.00 | n/a | 0.0% |
| Application Topology | – | – | – | – | ₹0.00 | $0 | – | 0% |
| **Total (October)** | | | | | **₹2,520.58** | **$26.26** | | 100% |

### By owner

| Possible owner | Models | **Actual ₹** | ≈ $ | Share |
|---|---|---|---|---|
| Rhit (possible) | gemini-3.8-flash, gemini-3-flash-preview | **₹2,062.78** | $21.49 | 81.8% |
| Manish (judge-pilot) | gemini-2.5-pro, gemini-2.5-flash | **₹432.41** | $4.50 | 17.2% |
| Manish/Rhit (console tests) | gemini-4-argon, gemini-3.1-flash-lite, gemini-nano-banana-2.1 | **₹25.39** | $0.26 | 1.0% |

### Findings
- **The pilot's estimate was accurate:** $4.52 estimated against $4.50 billed (−0.4%). The Gemini 2.5 Flash and Pro
  prices in `config.yaml` are confirmed. Vertex also applied a small implicit-caching discount to about 52k pilot tokens.
- **The Gemini 3.8 Flash price from secondary sources was wrong:** it bills at **$1.50 / $7.50**, not $0.75 / $3.75. Fixed in `config.yaml`.
- **Rhit's usage was mostly cached input** (68M of 79M input tokens). That is why the list-price estimate was too high.
- **The bill has no partner-model (Claude, Llama and so on) SKUs.** The "Agent Platform Model Garden" product in the earlier
  screenshot contains newer Gemini models, not partner models. The 20 `StreamRawPredict` calls cost nothing.
- **Running total:** ₹2,520.58 ≈ $26.26 of the ≈ $290 credits used in October; the pilot accounts for $4.50 of it.

## Insights from the 24 SKU rows (October, ₹2,520.58)

**Cost by token type**

| Type | Tokens | Cost | Share |
|---|---|---|---|
| Uncached input | 12.1M | ₹1,455.81 | **57.8%** |
| Cached input | 68.2M | ₹620.47 | 24.6% |
| Thinking output | 0.49M | ₹339.64 | 13.5% |
| Visible output | 0.19M | ₹104.66 | 4.2% |

- **Input is 82% of the bill.** Large prompts cost money, not long answers.
- **Concentration:** the top 3 SKUs are 79% of the bill. Gemini 3.8 Flash uncached input alone is **49.6%**
  (₹1,251 for 8.7M tokens).
- **Per call, Rhit's usage averaged about 232k tokens (3.8 Flash) and 409k tokens (3 Flash)**, which looks like a
  coding agent sending large codebases.
- **Cache hit rate:** 3.8 Flash 78%, 3 Flash 94%. Cached tokens cost 10% of the normal price.
- **The model premium is large:** 3.8 Flash costs 3× 3 Flash per token ($1.50 vs $0.50 input, $7.50 vs $3.00 output).
  gemini-4-argon is the most expensive per input token ($4.00/1M), so keep it away from bulk work.
- **The pilot's Pro cost is mostly thinking:** 307,654 of 328,519 output tokens (94%) were thinking, ₹295 of the
  ₹367 Pro cost. Flash's output was 88% thinking.
- **The pilot costs ≈ ₹1.49 per run** (₹432 for 290 runs): Flash ≈ ₹0.45, Pro ≈ ₹2.53.

**What-if savings (same work)**

| Change | Est. cost | Saving |
|---|---|---|
| Rhit's 3.8 Flash work on 3 Flash (same cache rate) | ≈ ₹589 instead of ₹1,755 | **≈ ₹1,166 (66%)** |
| 3.8 Flash cache hit rate 78% → 94% (same as 3 Flash) | input ≈ ₹869 instead of ₹1,690 | **≈ ₹821** |
| Pilot Pro thinking halved (thinking budget) | ≈ ₹220 instead of ₹367 | ≈ ₹148 per Night 1 (changes agent behaviour, so a research trade-off) |
| Day 2 judge calls through Batch prediction (≈ 50% off, single-turn calls) | half of the judge cost | ≈ 50% of Day 2 |

**Controls**
1. **One project per person or workload** (pilot / Rhit), each with its own budget alert. This bill only made sense after per-model forensics.
2. **Per-model quotas:** in IAM & Admin → Quotas, cap tokens per minute for expensive models (3.8 Flash, 4-argon) in shared projects.
3. **Coding agents:** default to 3 Flash and use 3.8 Flash only when needed. Keep the prompt prefix stable so caching hits,
   and limit how much context gets attached.
4. **Pilot:** keep Flash for bulk runs, use Pro where its behaviour matters, set judge thinking budgets explicitly,
   and batch the Day 2 judge calls.
5. **Daily check:** `python -m src.project_usage --config config.yaml` (per model and owner, read-only). For an automated view,
   turn on Billing export to BigQuery.

## Credit-coverage test calls (2026-10-24)

| Time (UTC) | Model | Region | Result | Tokens in / out | Check in Billing (25 Oct, group by SKU) |
|---|---|---|---|---|---|
| 03:39 | Claude Haiku 5.5 (`claude-haiku-5-5`) | global | 429, quota 0; increase request denied automatically | 0 / 0 (not billed) | n/a |
| 04:20 | Llama 4 Maverick, Qwen3 235B | us-east5, us-south1, global | 404, model not enabled | 0 / 0 (not billed) | n/a |
| 04:34 | Llama 4 Maverick (`meta/llama-4-maverick-17b-128e-instruct-maas`), after Enable + license | us-east5 | **200 OK** ("OK") | 16 / 2 | Does a Llama 4 SKU appear, and does the credit line cancel it? |

## Day 2 judge runs (2026-10-24, estimated from token counts and config.yaml prices)

| Run | Time (UTC) | Calls | Errors | Gemini 3.1 Pro | Llama 4 Maverick | promptfoo on 2.5 Flash | Total |
|---|---|---|---|---|---|---|---|
| `judge_smoke` | morning | 69 | 0 | $0.185 | $0.011 | $0.012 | $0.21 |
| `judge_full` | 11:14–13:22 | 7,960 | 0 | $17.52 | $1.11 | $1.38 | $20.01 |

Llama 4 and Gemini 3.1 Pro prices are UNCONFIRMED; check both SKUs and credit coverage in Billing on 25 Oct
(PREREGISTRATION.md deviation 2).

## Credit coverage confirmed (Billing overview, screenshot 2026-10-27 15:43 IST)

Billing → Overview, "Your total cost (1–27 October 2026)": **Cost ₹6.35k − Savings ₹6.35k = Total cost ₹0.00**;
forecast ₹0.00. Every October charge, including the Day 2 judge run on 24 Oct (Llama 4 Maverick, Gemini 3.1 Pro,
Gemini 2.5 Flash), was paid by credits. This closes PREREGISTRATION.md deviation 2.
Still open: per-SKU prices for Llama 4 Maverick and Gemini 3.1 Pro (needs Reports grouped by SKU or the CSV).
October usage rose from ₹2,786.62 (21 Oct) to ≈ ₹6.35k (27 Oct); the pilot's estimate for that period is ≈ $31
(Day 1 Gemini 3.x runs ≈ $11, Day 2 judges ≈ $20), the rest is other usage on the shared project.

## Llama 4 Maverick price confirmed (Billing → Reports by SKU, last 15 days, screenshot 2026-10-27 15:47 IST)

| SKU | Billed | Credits | Our tokens (smoke + full + test call) | Implied price at ₹96/$ | config.yaml |
|---|---|---|---|---|---|
| Cloud Vertex AI Model Garden MaaS Llama 4 Maverick Input Tokens (AD03-50E7-3706) | ₹86.05 | −₹86.05 | 2,561,299 | **$0.350 / M** | $0.35 ✅ |
| Llama 4 Maverick Output Tokens (7516-25FC-9009) | ₹21.81 | −₹21.81 | 197,534 | **$1.150 / M** | $1.15 ✅ |

Llama 4 total ₹107.86 ≈ $1.12, matching our estimate ($1.11 full + $0.011 smoke); fully paid by credits. The ₹96/$
rate is the one implied by the earlier SKU reconciliation (₹2,520.58 = $26.26). Gemini 3.1 Pro SKUs were not in the
visible part of the report; its price ($2 / $12) is still unconfirmed.

## Gemini 3.1 Pro price confirmed (same report, screenshot 2026-10-27 15:48 IST)

| SKU | Billed (all credited) | Our tokens (Day 1 agent runs + Day 2 judges) | Implied price at ₹96/$ | config.yaml |
|---|---|---|---|---|
| Gemini 3.0 / 3.1 Pro Text Input - Predictions (EAC4-305F-1249) | ₹746.11 | 3,929,142 (1,035,891 + 2,893,251) | **$1.98 / M** | $2.00 ✅ |
| Gemini 3.0 / 3.1 Pro Text Output - Predictions (2737-2D33-D986) | ₹1,341.02 | 1,164,215 (171,350 + 992,865) | **$12.00 / M** | $12.00 ✅ |
| Gemini 3.0 / 3.1 Pro Text Input Caching (8308-9CED-8950) | ₹0.82 | not logged separately | – | – |

The small input gap (1%) is cached input billed on the caching SKU. Output includes thinking tokens, as the runner
assumes. All model prices used by the pilot are now confirmed from Billing; every charge was paid by credits.
Coverage: the Billing overview for 1–27 Oct shows total cost ₹0.00 after credits (see above).

## Estimated vs actual, whole pilot (Billing → Reports by SKU, last 15 days, read 2026-10-27; ₹96/$)

Estimates are from logged tokens × config.yaml prices, counting every call made (retries, smoke runs, errored runs).
"Billed" sums all SKUs of that model in the report (input + output + thinking + caching), before credits.

| Model | Used for | Pilot estimate | Billed (whole project) | Difference | Verdict |
|---|---|---|---|---|---|
| gemini-3.1-pro-preview | Day 1 agent ($4.13) + Day 2 judge ($17.70) | ₹2,095.57 ($21.83) | ₹2,087.95 ($21.75) | −0.4% | ✅ exact |
| Llama 4 Maverick | Day 2 judge | ₹107.86 ($1.12) | ₹107.86 ($1.12) | 0% | ✅ exact |
| gemini-2.5-flash | Day 1 agent ($0.66) + Day 2 promptfoo judge ($1.39) | ₹196.31 ($2.04) | ₹214.61 ($2.24) | +9% (₹18) | ✅ close; gap = setup/test calls not logged as runs |
| gemini-2.5-pro | Day 1 agent | ₹371.12 ($3.87) | ₹770.78 ($8.03) | +₹400 | ⚠️ pilot part matched on 21 Oct (₹367.15); the extra ≈ ₹400 came after the pilot's last 2.5 Pro run, so it is other usage on the project |
| gemini-3.8-flash | Day 1 agent | ₹667.83 ($6.96) | ₹2,404.46 ($25.05) | +₹1,737 | ⚠️ shared SKU; mostly other usage (see 21 Oct reconciliation) |
| Other SKUs (Gemini 3 Flash, 4 Argon, Nano Banana, 3.1 Flash Lite, networking) | not the pilot | – | ≈ ₹700 | – | not pilot |

**Pilot total:** ≈ ₹3,439 ($35.8) estimated. Where the pilot is the only user of a model (3.1 Pro, Llama 4, 2.5 Flash),
estimate and bill agree within 0–9%. The project's 15-day bill (≈ ₹6,288, all paid by credits) is ≈ 55% pilot and
≈ 45% other usage, mainly Gemini 3.8 Flash, Gemini 3 Flash and extra Gemini 2.5 Pro.
To split 2.5 Pro and 3.8 Flash by user exactly: `python -m src.project_usage --start 2026-10-22T00:00:00Z`
(needs a fresh ADC login).
