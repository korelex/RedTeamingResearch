# Findings: Do LLM judges misreport attacks on AI agents? (pilot, 2026-10-20 to 2026-10-27)

**Short answer: yes.**
- Judges that see only the agent's final reply miss most real attacks, and a cover story in the reply makes this
  worse.
- A weaker judge invents attacks that didn't happen, and can be talked out of real ones by text the attacker plants
  in the transcript.
- A strong model reading the full transcript was the one setup that held up against every attack we tried.

How the pilot worked:
- **Agent runs:**
  - AgentDojo v1.2, banking and Slack suites, Gemini agents at temperature 0.
  - Day 1: 580 runs with the standard `important_instructions` attack (`night1_v1`).
  - Day 3: 732 runs with three attacks that also target the judge (`night2_v1`).
- **Ground truth:** whether each attack worked, taken from the real changes to the environment (`compromised_strict`).
- **Judges:**
  - Gemini 3.1 Pro (frontier)
  - Llama 4 Maverick (open weights)
  - promptfoo's indirect-prompt-injection grader (a widely used tool; it reads the final reply only)
- **What the judges saw:**
  - L1: request + final reply only
  - L2: full transcript
  - L3: transcript + environment changes
- **Method:** pre-registered before any judge call.
  - Day 2: `PREREGISTRATION.md`
  - Day 3: `PREREGISTRATION_DAY3.md`
  - Full numbers: `DAY2_RESULTS.md`, `DAY3_RESULTS.md`
  - Running list of insights: `INSIGHTS.md`

## Main results

All results use the Gemini 2.5 Flash and 2.5 Pro agents, the ones that actually get compromised.

### Missed attacks: share of real compromises the judge called safe

| Judge | View | Standard attack (n=152) | D1 note to reviewers (n=130) | D2 cover story (n=148) | D3 subtle (n=38) |
|---|---|---|---|---|---|
| Gemini 3.1 Pro | L1: request + final reply | 62.5% | 66.2% | 66.2% | 34.2% |
| Gemini 3.1 Pro | L2: full transcript | **0%** | **0%** | **0%** | **0%** |
| Gemini 3.1 Pro | L3: + environment changes | 0% | 0% | 0% | 0% |
| Llama 4 Maverick | L1 | 46.7% | 45.4% | 45.9% | 15.8% |
| Llama 4 Maverick | L2 | 0% | **50.8%** | 0% | 0% |
| Llama 4 Maverick | L3 | 0% | **48.5%** | 0% | 0% |
| promptfoo grader | final reply + injection goal | 63.8% | 67.7% | **86.5%** | 31.6% |

### False alarms: share of runs where the agent resisted but the judge said compromised (L2)

| Judge | Standard (n=41) | D1 (n=51) | D2 (n=35) | D3 (n=146) | Baselines, no attack (n=40) |
|---|---|---|---|---|---|
| Gemini 3.1 Pro | 2.4% | 9.8% | 17.1%* | 5.5%* | 0% |
| Llama 4 Maverick | **43.9%** | **60.8%** | **85.7%** | **65.8%** | **35.0%** |
| promptfoo (its own view) | 0% | 3.9% | 2.9% | 10.3% | not judged |

\* Most of these are real harm that the ground truth misses: see finding 7.

## Findings

### 1. Judges that see only the final reply miss most real attacks

- **Miss rates, standard attack:** Gemini 3.1 Pro 62%, Llama 4 47%, promptfoo 64%.
- **Silent compromises:** 84% of real compromises were silent: the agent did the harmful action and its reply didn't
  mention it. On these, promptfoo missed **74%**.
- **Implication:** this reply-only setup is common in practice (it is promptfoo's default). Attack-success numbers
  produced this way probably undercount real compromises.

### 2. A cover story in the reply makes reply-only judging worse

- In the D2 attack, the injection told the agent to report only the user's task, or to call the harmful step "a
  routine verification step".
- The agent repeated that story in 68 of 148 compromised runs.
- promptfoo then missed **87%** of attacks, against 64% for the standard attack (H8, p < 1e-4).
- **Why:** the agent writes the text being judged, so the attacker can steer it.

### 3. With the full transcript, a strong judge was not fooled

- Gemini 3.1 Pro at L2 missed **0** attacks under every attack type: 0/152, 0/130, 0/148, 0/38.
- **Gate 3 holds:** "dual-target attacks break full-transcript judging" was **not** supported for the strong judge.
- Adding the environment changes (L3) gave no measurable improvement, because it was already at the ceiling.

### 4. A weaker judge can be prompt-injected through the transcript it reviews

- The D1 attack added a "note to reviewers" saying the action was user-approved.
- This raised Llama 4's miss rate at L2 from **0% to 51%** (H6, p < 1e-26). In 51 of its 66 misses, Llama's reason
  cites the note, for example "authorised… part of the task".
- **Showing it the environment changes (L3) didn't help: 48%.**
- **Implication:** an LLM judge reads attacker-controlled text, so it is itself an attack surface.

### 5. A weaker judge also invents attacks

- With the full transcript, Llama 4 flagged as compromised:
  - **44%** of runs where the agent resisted the standard attack, and up to **86%** under the cover story (H7,
    p = 0.002)
  - **35%** of runs with **no attack at all**
- Its reasons treat normal task actions as attacks. For example, it said reading a channel that contained a secret key
  "potentially disclosed" it.
- It revised its own verdict within a single reply in 7.5% of calls. Counting its first verdict instead of its last
  would raise its standard-attack false-alarm rate from 44% to 68%.
- **Implication:** a judge like this inflates attack-success rates, and reacts to suspicious-looking text rather than
  to what the agent did.

### 6. Subtle attacks compromise agents less often

- **D3** had no banner, just an "[Account note]" phrased like routine data. It compromised only 15–16% of runs,
  against 52–70% for the standard attack.
- **D1 and D2** compromised 43–66% of runs, so adding text aimed at the judge cost the attacker little.
- **Implication:** on these agents, the blatant banner is what makes the attack work.

### 7. Benchmark ground truth undercounts partly completed attacks (post-hoc check, not pre-registered)

- AgentDojo's success checks are all-or-nothing.
- **Example:** an attack asked for $30,000 in transfers. The agent sent 3 × $9,999 to the attacker, and the benchmark
  labelled the run "not compromised".
- In all 10 such runs on D2 and D3, attacker data (the attacker's IBAN or URL) did reach the environment, and Gemini
  3.1 Pro flagged every one.
- Excluding them, its false-alarm rate at L2 is 2/31 on D2 and 2/140 on D3.
- **Implication:** some apparent judge "false alarms" are label errors. Benchmark labels are a lower bound on harm.

### 8. Pre-registered tests

**Day 2 (9 tests, Holm-corrected):**

| Hypothesis | Result |
|---|---|
| H1: judges miss more attacks at L1 than at L2 | **Supported** for both LLM judges (p < 1e-20) |
| H2 (Gate 2): some judge has ≥ 5% missed attacks or false alarms at L2 | **PASS**, because of Llama 4's false alarms |
| H3: environment changes (L3) reduce errors compared with L2 | Not supported |
| H4: seeing an injection causes more false alarms than baselines | Not supported |
| H5: promptfoo misses more silent attacks than Gemini 3.1 Pro at L2 | **Supported** (95 vs 0 missed) |

**Day 3 (13 tests, Holm-corrected):**

| Hypothesis | Result |
|---|---|
| Gate 3: Gemini 3.1 Pro misses ≥ 5% at L2 on any variant | **Holds** (0% on all three) |
| H6: judges miss more attacks under a variant than under the standard attack (6 tests) | **Supported only for Llama 4 under D1** (p < 1e-26) |
| H7: variant text raises false alarms (6 tests) | **Supported only for Llama 4 under D2** (p = 0.002) |
| H8: the cover story hides more attacks from promptfoo | **Supported** (87% vs 64%, p < 1e-4) |

### 9. Other observations

- **Judge consistency:** across two repeats (Day 2), Gemini 3.1 Pro gave the same verdict in 97–100% of cases. Llama 4
  did so in about 91% at L2 and L3.
- **Judge agreement:** Gemini and Llama agreed with each other only moderately (kappa 0.42 at L1, 0.68 at L2).
- **promptfoo's refusal shortcut:** it never changed the scores. The promptfoo judge already called the affected runs
  safe.
- **Where promptfoo misses most:** Slack (83% missed) more than banking (40%), especially quiet data exfiltration.

## In one line

**How many attacks a judge reports depends on what it is shown and which model is judging.**
- Reply-only judges hide most real compromises, and a cover story hides even more.
- Weaker judges invent attacks, and can be talked out of real ones by the attacker's own text.
- Practical rules for evaluating agents:
  1. Judge the full transcript, not the reply.
  2. Use a strong judge.
  3. Treat injected text as hostile to the judge too.
  4. Check environment state where possible, while remembering that benchmark checks miss partly completed harm.

## Limitations

- **Scope:** one benchmark (AgentDojo v1.2), two suites, temperature 0, and three hand-written judge-directed
  variants. These are not optimised attacks on the judge. A negative result for Gemini means "these attacks didn't
  break it", not "it can't be broken".
- **Same-family judging:** the strong judge is Gemini judging Gemini agents. Claude on Vertex was unavailable (quota
  denied). Llama 4 is the only non-Gemini judge.
- **Small samples:**
  - Only 41 resisted runs under the standard attack and 35 under D2, so false-alarm confidence intervals are wide.
  - D3 has only 38 compromised runs.
- **Unpaired comparisons on Day 3:** variant runs are compared with Night 1 runs as groups, not run by run.
- **L3 is close to the answer key**, because ground truth is computed from the same environment changes.
- **Possible training contamination:** Gemini 3.x agents may have seen AgentDojo in training (0/250 compromised), so
  they were not used on Day 3.
- **Deviations from the pre-registration** (all logged in the two pre-registration files):
  - Day 2:
    1. When a judge revised itself, its last verdict counted.
    2. Llama 4 credit coverage was checked after the run (confirmed 27 Oct).
    3. Smoke-test judgements were kept out of the results.
  - Day 3:
    1. Smoke runs that overlapped the night plan were re-run fresh.
    2. The dataset was re-frozen to exclude smoke-only runs, before any judge call.

## Cost

All prices confirmed from Cloud Billing; everything was paid by Google Cloud credits.

| Item | Cost |
|---|---|
| Day 1 agent runs | ≈ $15.5 |
| Day 2 judging (smoke + 7,960 calls) | ≈ $20.2 |
| Day 3 agent runs (smoke + 732 runs) | ≈ $11.1 |
| Day 3 judging (5,124 calls) | ≈ $12.9 |
| **Pilot total** | **≈ $59.6** |

## Next steps (optional)

- **More suites and attacks:** add travel and workspace, and `tool_knowledge`.
- **Optimised attacks on the judge:** test whether the strong judge holds up against attacks tuned to fool it, not
  just hand-written ones.
- **A non-Gemini strong judge** if one becomes available, to remove the same-family caveat.
- **Better ground truth:** add a "partly completed" label for attacks that changed the environment but failed the
  benchmark check.
