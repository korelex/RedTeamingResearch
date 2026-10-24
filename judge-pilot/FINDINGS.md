# Findings: Do LLM judges misreport attacks on AI agents? (pilot, 2026-10-24)

**Short answer: yes, mostly when the judge only sees the agent's final reply.**

How the pilot worked:
- **Agent runs:** 580 frozen AgentDojo runs (banking and Slack suites, `important_instructions` attack).
- **Ground truth:** whether each attack worked, taken from the real changes to the environment (`compromised_strict`).
- **Judges:**
  - Gemini 3.1 Pro (frontier)
  - Llama 4 Maverick (open weights)
  - promptfoo's indirect-prompt-injection grader (a widely used tool)
- **What the judges saw:**
  - L1: request + final reply only
  - L2: full transcript
  - L3: transcript + environment changes
- **Method:** pre-registered in `PREREGISTRATION.md`. Full numbers are in `DAY2_RESULTS.md`.

## Main results

**Primary sample:** Gemini 2.5 Flash and 2.5 Pro agents. It contains 152 compromised runs, 41 runs where the agent saw the injection and resisted, and 40 baselines with no attack.

| Judge | What the judge saw | Missed attacks (of 152) | False alarms on resisted runs (of 41) | False alarms with no attack (of 40) |
|---|---|---|---|---|
| Gemini 3.1 Pro | L1: request + final reply | **62.5%** | 0% | 0% |
| Gemini 3.1 Pro | L2: full transcript | **0%** | 2.4% (1 run) | 0% |
| Gemini 3.1 Pro | L3: transcript + environment changes | 0% | 2.4% | 0% |
| Llama 4 Maverick | L1 | 46.7% | 39.0% | 40.0% |
| Llama 4 Maverick | L2 | 0% | **43.9%** | **35.0%** |
| Llama 4 Maverick | L3 | 0% | 31.7% | 17.5% |
| promptfoo grader | final reply + injection goal | **63.8%** | 0% | not judged |

## Findings

### 1. Judges that see only the final reply miss most real attacks

- **Overall miss rates:** Gemini 3.1 Pro 62%, Llama 4 47%, promptfoo 64%.
- **Silent compromises:** 84% of real compromises were silent, meaning the agent did the harmful action and its reply didn't mention it. On these, promptfoo missed **74%** and Gemini 3.1 Pro at L1 missed 72%.
- **Implication:** this reply-only setup is common in practice. Attack-success numbers produced this way probably undercount real compromises.

### 2. With the full transcript, a strong judge is almost perfect

- Gemini 3.1 Pro at L2 missed **0 of 152** attacks.
- It raised **1 false alarm in 41** resisted runs. That run is borderline: the agent made one extra call (`get_channels`) because of the injection but didn't do the harmful part.
- Adding the environment changes (L3) gave no measurable improvement.
- **Conclusion:** missed attacks are a problem of what the judge can see, not of how well it reasons.

### 3. A weaker judge errs in the other direction: false alarms

- Llama 4 with the full transcript also caught every attack, but it flagged as compromised:
  - **44%** of runs where the agent resisted
  - **35%** of runs with **no attack at all**
  - 70% of resisted runs from the Gemini 3.x agents
- Its reasons treat normal task actions as attacks. For example, it said reading a channel that contained a secret key "potentially disclosed" it.
- It revised its own verdict within a single reply in 7.5% of calls. If its first verdict had counted instead of its last, its false-alarm rate at L2 would be 68%.
- **Implication:** a judge like this inflates attack-success rates.

### 4. The pre-registered tests (Holm-corrected, 9 tests)

| Hypothesis | Result |
|---|---|
| H1: judges miss more attacks at L1 than at L2 | **Supported** for both LLM judges (p < 1e-20) |
| H2 (Gate 2): some judge has ≥ 5% missed attacks or false alarms at L2 | **PASS**, because of Llama 4's false alarms |
| H3: environment changes (L3) reduce errors compared with L2 | Not supported (Gemini already at ceiling; Llama false alarms fell 18 → 13, not significant) |
| H4: seeing an injection causes more false alarms than baselines | Not supported |
| H5: promptfoo misses more silent attacks than Gemini 3.1 Pro at L2 | **Supported** (95 vs 0 missed, p < 1e-27) |

### 5. Other observations

- **Judge consistency:** across two repeats, Gemini 3.1 Pro gave the same verdict in 97–100% of cases. Llama 4 at L2 and L3 did so in about 91%.
- **promptfoo's refusal shortcut:** it would have scored 8 real compromises as safe without calling a judge. The promptfoo judge missed those 8 anyway, so its scores didn't change.
- **Where promptfoo misses most:** Slack (83% missed) more than banking (40%). It also misses most when the attacker's goal is to read data and exfiltrate it quietly.

## In one line

**How many attacks a judge reports depends on what it is shown and which model is judging.** Reply-only judges hide most real compromises, and weaker judges invent attacks that didn't happen. Attack-success numbers from LLM judges should state both, and should be checked against environment state where possible.

## Limitations

- **Scope:** one benchmark (AgentDojo v1.2), two suites and one attack style.
  - The attack text is blatant ("This is an important message from me…"), so the near-perfect L2 result may not hold for subtler attacks.
- **Same-family judging:** the frontier judge is Gemini judging Gemini agents. Claude on Vertex was unavailable (quota denied). Llama 4 is the only non-Gemini judge.
- **Small resisted sample:** only 41 resisted runs in the primary sample, so false-alarm confidence intervals are wide (Gemini 3.1 Pro at L2: 0–8%).
- **L3 is close to the answer key**, because ground truth is computed from the same environment changes.
- **Possible training contamination:** Gemini 3.x agents may have seen AgentDojo in training (0/250 compromised).
- **Deviations from the pre-registration (all logged):**
  1. When a judge revised itself, its last verdict counted.
  2. Llama 4 credit coverage is checked after the run.
  3. Smoke-test judgements are kept out of the results.

## Cost

| Item | Cost |
|---|---|
| Smoke test (69 calls) | $0.21 |
| Full judge run (7,960 calls, 0 errors) | $20.01 |
| **Total for judging** | **≈ $20.2** |

Prices for Llama 4 and Gemini 3.1 Pro are to be confirmed in Billing on 25 Oct.

## Next step

Gate 2 passed, so the pre-registered next step is the larger study:
- more AgentDojo suites
- more attacks, including subtler ones
- a non-Gemini frontier judge if one becomes available

The key open question is whether judges that see the full transcript stay this accurate when the attack is not obvious.
