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
| | **Total** | | | | **159** | | | | **513,864** | **215,942** | **$0.8114** |

**Notes on each batch**
- **Smoke:** the 12 lines are the original 6 runs plus a later backfill re-run of each. Both attempts were billed.
- **Night 1:** the plan has 142 runs. 3 were already done during the smoke test, so 139 ran, and 141 lines were logged. The 2 errors were a `MalformedResponse` (`fbe03f07…`) and a Vertex `504 DEADLINE_EXCEEDED` after 926 s (`41f4001b…`). Their attempts cost $0.0035, and both succeeded when retried by the resume command.
- **Smoke Pro:** 6 runs (5 attacked + 1 baseline), the same runs as the Flash smoke test.

### Per model (to compare with Billing grouped by SKU)

| Model | Tokens in | Tokens out | Est. input cost | Est. output cost | **Est. total** | Actual (Billing) | Difference |
|---|---|---|---|---|---|---|---|
| gemini-2.5-flash | 497,091 | 202,421 | $0.1491 | $0.5061 | **$0.6552** | | |
| gemini-2.5-pro | 16,773 | 13,521 | $0.0210 | $0.1352 | **$0.1562** | | |
| **Total** | 513,864 | 215,942 | | | **$0.8114** | | |

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
| 2026-10-20 | $0.8114 | $6.00 | |

## Change log

- 2026-10-20: log created. Prices are still unconfirmed.
