# Scale-up Stage 3 results: a second strong judge (gpt-oss-120b)

Descriptive, as pre-registered in `PREREGISTRATION_SCALEUP.md` §5 (model choice note, 2026-11-11). Judge view L2 (full transcript), repeat 0, primary UNSURE rule. Brackets: 95% cluster-bootstrap CIs. Gemini 3.1 Pro and Llama 4 are shown on the same runs for comparison.

## Error rates at L2, pre-registered sets

| Dataset | Attack | Judge | FN: compromised | FP: seen and resisted |
|---|---|---|---|---|
| night1_v1 | important_instructions | gpt-oss-120b | 5.3% (8/152) [0.7–11.7] | 12.2% (5/41) [2.4–24.4] |
| night1_v1 | important_instructions | Gemini 3.1 Pro | 0.0% (0/152) [0.0–0.0] | 2.4% (1/41) [0.0–8.3] |
| night1_v1 | important_instructions | Llama 4 Maverick | 0.0% (0/152) [0.0–0.0] | 43.9% (18/41) [24.4–63.0] |
| night2_v1 | dual_cover_story | gpt-oss-120b | 9.5% (14/148) [3.8–16.1] | 22.9% (8/35) [5.7–42.4] |
| night2_v1 | dual_cover_story | Gemini 3.1 Pro | 0.0% (0/148) [0.0–0.0] | 17.1% (6/35) [2.9–34.3] |
| night2_v1 | dual_cover_story | Llama 4 Maverick | 0.0% (0/148) [0.0–0.0] | 85.7% (30/35) [73.3–95.2] |
| night2_v1 | dual_reviewer_note | gpt-oss-120b | 49.2% (64/130) [37.3–61.4] | 3.9% (2/51) [0.0–10.0] |
| night2_v1 | dual_reviewer_note | Gemini 3.1 Pro | 0.0% (0/130) [0.0–0.0] | 9.8% (5/51) [1.9–20.4] |
| night2_v1 | dual_reviewer_note | Llama 4 Maverick | 50.8% (66/130) [37.6–63.9] | 60.8% (31/51) [43.4–76.4] |
| night2_v1 | subtle_account_note | gpt-oss-120b | 13.2% (5/38) [0.0–30.3] | 9.6% (14/146) [4.7–15.5] |
| night2_v1 | subtle_account_note | Gemini 3.1 Pro | 0.0% (0/38) [0.0–0.0] | 5.5% (8/146) [1.2–11.4] |
| night2_v1 | subtle_account_note | Llama 4 Maverick | 0.0% (0/38) [0.0–0.0] | 65.8% (96/146) [53.2–77.9] |
| scaleup_v1 | dual_cover_story | gpt-oss-120b | 0.0% (0/139) [0.0–0.0] | 18.2% (35/192) [12.8–23.8] |
| scaleup_v1 | dual_cover_story | Gemini 3.1 Pro | 0.0% (0/139) [0.0–0.0] | 18.8% (36/192) [13.4–24.2] |
| scaleup_v1 | dual_cover_story | Llama 4 Maverick | 0.0% (0/139) [0.0–0.0] | 76.6% (147/192) [69.6–83.1] |
| scaleup_v1 | dual_reviewer_note | gpt-oss-120b | 22.0% (26/118) [13.8–31.1] | 11.1% (24/217) [7.1–15.4] |
| scaleup_v1 | dual_reviewer_note | Gemini 3.1 Pro | 0.0% (0/118) [0.0–0.0] | 13.8% (30/217) [9.4–18.4] |
| scaleup_v1 | dual_reviewer_note | Llama 4 Maverick | 7.6% (9/118) [2.7–13.2] | 67.7% (147/217) [60.4–74.8] |
| scaleup_v1 | important_instructions | gpt-oss-120b | 0.7% (1/136) [0.0–2.3] | 17.4% (37/213) [12.1–23.1] |
| scaleup_v1 | important_instructions | Gemini 3.1 Pro | 0.0% (0/136) [0.0–0.0] | 16.9% (36/213) [12.1–22.0] |
| scaleup_v1 | important_instructions | Llama 4 Maverick | 0.0% (0/136) [0.0–0.0] | 67.1% (143/213) [60.6–73.7] |

## Reading (pre-registered)

gpt-oss-120b missed **≥ 5%** at L2 on: night1_v1 / important_instructions (5.3% (8/152) [0.7–11.7]); night2_v1 / dual_cover_story (9.5% (14/148) [3.8–16.1]); night2_v1 / dual_reviewer_note (49.2% (64/130) [37.3–61.4]); night2_v1 / subtle_account_note (13.2% (5/38) [0.0–30.3]); scaleup_v1 / dual_reviewer_note (22.0% (26/118) [13.8–31.1]). Reported as a **family-dependent result**: "a strong judge with the full transcript is not fooled" does not hold for every strong model.

## Agreement (all pre-registered runs)

| Pair | Kappa | n |
|---|---|---|
| gpt-oss-120b vs Gemini 3.1 Pro | 0.82 | 1756 |
| gpt-oss-120b vs Llama 4 Maverick | 0.30 | 1756 |
| gpt-oss-120b vs ground truth | 0.72 | 1756 |
| Gemini 3.1 Pro vs ground truth | 0.86 | 1756 |
| Llama 4 Maverick vs ground truth | 0.23 | 1756 |

## Exploratory (deviation 6): the Stage 2 tuned text

Not pre-registered tests. The text was tuned against Gemini, so these are transfer results.

### Held-out test transcripts (edited)

| Candidate | gpt-oss-120b FN | Gemini 3.1 Pro FN | Llama 4 Maverick FN |
|---|---|---|---|
| #1 r1c02 (fake system or evaluator message) | 66.7% (60/90) [55.1–77.8] | 13.3% (12/90) [3.5–25.6] | 6.7% (6/90) [0.0–17.2] |
| #2 r1c09 (plain benign explanation) | 6.7% (6/90) [0.0–16.7] | 0.0% (0/90) [0.0–0.0] | 0.0% (0/90) [0.0–0.0] |
| #3 r2c02 (Scheduled routine or automation) | 5.6% (5/90) [0.0–15.7] | 0.0% (0/90) [0.0–0.0] | 0.0% (0/90) [0.0–0.0] |
| Original D1 note | 46.7% (42/90) [31.5–61.8] | 0.0% (0/90) [0.0–0.0] | 50.0% (45/90) [34.4–65.6] |

### Real runs (`scaleup_tuned_v1`)

| Dataset | Attack | Judge | FN: compromised | FP: seen and resisted |
|---|---|---|---|---|
| scaleup_tuned_v1 | tuned_r1c02 | gpt-oss-120b | 55.2% (37/67) [41.5–68.4] | 0.0% (0/23) [0.0–0.0] |
| scaleup_tuned_v1 | tuned_r1c02 | Gemini 3.1 Pro | 9.0% (6/67) [1.6–17.5] | 4.3% (1/23) [0.0–14.3] |
| scaleup_tuned_v1 | tuned_r1c02 | Llama 4 Maverick | 3.0% (2/67) [0.0–7.6] | 52.2% (12/23) [30.8–73.1] |
| scaleup_tuned_v1 | tuned_r1c09 | gpt-oss-120b | 7.6% (6/79) [1.4–14.9] | 18.8% (3/16) [0.0–40.0] |
| scaleup_tuned_v1 | tuned_r1c09 | Gemini 3.1 Pro | 0.0% (0/79) [0.0–0.0] | 12.5% (2/16) [0.0–31.2] |
| scaleup_tuned_v1 | tuned_r1c09 | Llama 4 Maverick | 0.0% (0/79) [0.0–0.0] | 50.0% (8/16) [26.7–73.3] |
| scaleup_tuned_v1 | tuned_r2c02 | gpt-oss-120b | 10.0% (7/70) [1.5–20.3] | 8.0% (2/25) [0.0–20.8] |
| scaleup_tuned_v1 | tuned_r2c02 | Gemini 3.1 Pro | 0.0% (0/70) [0.0–0.0] | 12.0% (3/25) [0.0–25.0] |
| scaleup_tuned_v1 | tuned_r2c02 | Llama 4 Maverick | 0.0% (0/70) [0.0–0.0] | 52.0% (13/25) [32.0–72.0] |

## Calls and cost

2306 calls (incl. 20 smoke), 1 parse errors, est. $1.18 at $0.15 / $0.60 per 1M tokens (to be confirmed in Billing).

