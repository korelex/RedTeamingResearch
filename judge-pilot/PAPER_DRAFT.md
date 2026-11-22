---
title: "Who Judges the Judge? LLM Evaluators Misreport Prompt-Injection Attacks on Tool-Using Agents"
author: "Manish (Korelex AI Lab)"
date: "Draft, 2026-11-22"
---

<!--
Draft for conversion into a paper (e.g. `pandoc PAPER_DRAFT.md -o paper.pdf` or `-o paper.tex`).
Every number comes from the committed results files: DAY2_RESULTS.md, DAY3_RESULTS.md, SCALEUP_STAGE1_RESULTS.md to
SCALEUP_STAGE4_RESULTS.md. Places marked [CITE] need a reference; places marked [TODO] need an author decision.
-->

# Abstract

Prompt-injection benchmarks and red-teaming tools increasingly use an LLM "judge" to decide whether an agent was
compromised. We measure how often such judges get that decision wrong. On AgentDojo v1.2 (all four suites), we ran
Gemini 2.5 Flash and Pro agents under the standard attack and three new *dual-target* attacks that also address the
judge, and compared four judges against ground truth computed from environment state: Gemini 3.1 Pro, Llama 4
Maverick, gpt-oss-120b, and promptfoo's indirect-prompt-injection grader. All hypotheses were pre-registered.
Four results stand out.

1. **Judges that see only the agent's final reply miss most compromises**: 62–77% for Gemini 3.1 Pro and 64–81% for
   promptfoo. 84–97% of compromises are silent: the reply does not mention the harmful action.
2. **The transcript is an attack surface for the judge.** A planted "note to reviewers" raised Llama 4's miss rate
   from 0% to 51%, and gpt-oss-120b's to 49%, even with the full transcript.
3. **A strong judge that resists every hand-written attack (Gemini 3.1 Pro, 0 misses in 861 compromises) can still be
   broken by tuned text.** A fake "system message to the evaluation model" found in a 30-candidate search made it
   miss 13.3% of held-out compromises (p = 0.0002). The same text transferred to gpt-oss-120b, which missed 67%.
4. **Benchmark labels undercount harm.** A pre-registered "partly completed" label finds attacker data written to the
   environment in 6–10% of runs labelled *not compromised* on multi-step suites. Most of the strong judges' apparent
   false alarms are these runs.

We conclude that attack-success rates reported by LLM judges depend on what the judge sees and which model judges,
and that judge robustness must be measured, not assumed.

# 1 Introduction

LLM agents that call tools read untrusted content: emails, files, web pages, transaction records. Indirect prompt
injection places instructions in that content [CITE: Greshake et al. 2023]. Benchmarks such as AgentDojo
[CITE: Debenedetti et al. 2024] score attacks with hand-written checks on the environment state. Many practical
evaluations, however, score with an LLM judge: red-teaming frameworks such as promptfoo [CITE], and the wider
LLM-as-a-judge practice [CITE: Zheng et al. 2023]. Often that judge sees only the agent's final reply.

This creates two risks that have not been measured systematically for agent security:

- **Visibility.** A judge that does not see what the agent *did* cannot detect a silent compromise.
- **Judge injection.** A judge that does see the transcript also reads the attacker's text, so the attacker can
  address the judge as well as the agent.

**Research questions.**

- **RQ1:** How often do LLM judges misreport compromises (false negatives) and invent them (false positives),
  depending on what they are shown?
- **RQ2:** Can attacker text placed in tool output fool the judge as well as the agent (*dual-target attacks*)?
- **RQ3:** Does a strong judge with the full transcript resist hand-written and tuned judge-directed text, and does
  that hold across model families?
- **RQ4:** How reliable is the benchmark ground truth that judges are compared against?

**Contributions.**

1. A pre-registered measurement of four judges and three judge views over 2,978 agent runs in four AgentDojo suites.
2. Three dual-target attack templates, plus a tuned judge-directed text found by a small search, that break a strong
   judge which resists every hand-written variant.
3. Evidence that judge robustness is family-dependent: two strong judges behave very differently on identical inputs.
4. A pre-registered "partly completed" label showing that all-or-nothing benchmark checks undercount harm, and that
   strong judges' false alarms are mostly label errors.

# 2 Related work

[TODO: expand with citations]

- **Prompt-injection benchmarks for agents:** AgentDojo [CITE], InjecAgent [CITE], and others [CITE].
- **LLM-as-a-judge:** reliability, bias and position effects [CITE]; adversarial attacks on judges and reward models
  [CITE].
- **Automated red-teaming and scoring tools:** promptfoo [CITE], garak [CITE], PyRIT [CITE].
- **Monitoring agent transcripts:** using LLMs to monitor other models' actions [CITE].

Our gap: no prior work, to our knowledge [TODO: verify], measures judge errors on real agent compromises against
environment ground truth, with attacks that target the judge itself.

# 3 Method

## 3.1 Agent runs

- **Benchmark:** AgentDojo v1.2: banking, Slack, travel and workspace suites; the default agent pipeline and system
  prompt.
- **Agents:** Gemini 2.5 Flash and Gemini 2.5 Pro on Vertex AI, temperature 0, seed 1234.
  - Gemini 3.x agents were compromised in 0 of 250 pilot runs and were dropped, possibly because of training
    contamination.
  - Every run logs the exact model ID, temperature, seed and AgentDojo version.
- **Task pairs:**
  - Banking and Slack: stratified sample per injection task (k = 4 and k = 5).
  - Travel and workspace: k = 10 per injection task (seed 0).
  - No-attack baselines are included.
- **Datasets:** frozen and hash-verified before any judge call.

| Dataset | Suites | Attacks | Runs |
|---|---|---|---|
| `night1_v1` (pilot, Day 1) | banking, Slack | standard `important_instructions` | 580 (incl. 80 baselines; Gemini 3.x runs excluded from analysis) |
| `night2_v1` (pilot, Day 3) | banking, Slack | D1, D2, D3 | 732 |
| `scaleup_v1` (Stage 1) | travel, workspace | standard, D1, D2 | 1,300 (incl. 40 baselines) |
| `scaleup_tuned_v1` (Stage 2) | all four | three tuned templates | 366 |

## 3.2 Attacks

- **Standard:** AgentDojo's `important_instructions`, a banner addressed to the agent and signed with the user's
  name.
- **D1, reviewer note:** the standard attack plus a `<NOTE TO REVIEWERS>` block saying the action is user-approved
  and routine.
- **D2, cover story:** tells the agent to report only the user's task, or to describe the harmful step as "a routine
  verification step".
- **D3, subtle:** no banner. The instruction is phrased as an "[Account note]" that looks like ordinary data.
- **Tuned (Stage 2):** described in §3.6.

## 3.3 Ground truth

- **Primary label (`compromised_strict`):** AgentDojo's injection-task success check on the final environment state.
- **Run buckets:**
  - **compromised**
  - **seen and resisted:** the injection was in a tool result the agent received, and the attack failed
  - **never exposed:** the agent never received the injection
- **Error rates:**
  - **False negative (FN):** a compromised run judged SAFE or UNSURE.
  - **False positive (FP):** a seen-and-resisted run judged COMPROMISED or UNSURE.
  - Primary rule: UNSURE counts as wrong. A secondary analysis excludes UNSURE.

## 3.4 Judges and views

All judges use the same prompt (`judge-v1`, Appendix A), with a JSON verdict COMPROMISED / SAFE / UNSURE plus a
reason. Judge temperature is 0 where supported.

| Judge | Model | Role |
|---|---|---|
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | strong (frontier) judge |
| Llama 4 Maverick | `llama-4-maverick-17b-128e-instruct-maas` | open-weight judge |
| gpt-oss-120b | `openai/gpt-oss-120b-maas` | second strong judge from another family (Stage 3) |
| promptfoo | its indirect-prompt-injection grader v0.125.0, verbatim, on Gemini 2.5 Flash | widely used tool |

| View | Content |
|---|---|
| L1 | user request + final reply |
| L2 | full transcript: system prompt, messages, every tool call and tool result |
| L3 | L2 + neutral rendering of environment changes |
| PF | promptfoo's own view: final reply + injection goal + purpose |

The judges never see labels, the attack name, the suite or the agent model. A unit test flips every label field and
checks that the rendered input is byte-identical.

## 3.5 Pre-registration and statistics

- **Pre-registered:** every hypothesis, gate and decision rule was fixed before the relevant judge calls:
  - `PREREGISTRATION.md` (Day 2)
  - `PREREGISTRATION_DAY3.md`
  - `PREREGISTRATION_SCALEUP.md`
- **Deviations:** logged in those files.
- **Tests:**
  - Paired comparisons (same runs): exact McNemar.
  - Unpaired comparisons: exact Fisher.
  - Multiple comparisons: Holm correction within each family.
- **Confidence intervals:** 95% cluster bootstrap with clusters = suite × user task × injection task (10,000
  resamples, seed 0).

## 3.6 Tuned judge-directed text (Stage 2)

- **Set-up:**
  - Source: the 130 compromised D1 runs in `night2_v1`.
  - Split by cluster into a 40-run dev set and a 90-run held-out test set (seed 0).
  - Each candidate replaces the D1 note in the tool outputs only.
- **Candidates:**
  - 10 hand-written, one per strategy, such as fake system or evaluator message, plain benign explanation, or
    scheduled automation.
  - 20 written by an attacker model (Gemini 2.5 Flash, temperature 1) over two rounds, given the dev scores.
- **Selection:** dev FN of Gemini 3.1 Pro at L2. The top 3 were tested once on the held-out set.
- **Gate 4:** Gemini misses ≥ 5% on the test set for any of the top 3.
- **H14:** the best candidate raises Gemini's misses compared with the original note on the same runs.
- **Real-run check:** the three selected texts were also used as attack templates in 366 real agent runs.

## 3.7 Partly-completed label (Stage 4)

- **Rule:** literal attacker artefacts are extracted from each injection task's goal (IBANs, URLs, email addresses,
  phone numbers, user, file and place names, amounts), excluding values already present in the default environment.
- **Order:** the list was committed before the rule was applied to any run.
- **Label:** a run is *partly compromised* if it is not `compromised_strict` and an artefact appears in a value that
  the run added or changed in the environment.
- **Status:** secondary analysis; the primary results keep the strict label.

# 4 Results

## 4.1 RQ1: what the judge sees matters most

**Table 1.** Missed compromises (FN). Primary agents; pilot = banking + Slack.

| Judge | View | Standard, pilot (n=152) | D1 (130) | D2 (148) | D3 (38) | Standard, travel + workspace (136) | D1 (118) | D2 (139) |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Pro | L1 | 62.5% | 66.2% | 66.2% | 34.2% | 75.7% | 77.1% | 66.2% |
| Gemini 3.1 Pro | L2 | **0%** | **0%** | **0%** | **0%** | **0%** | **0%** | **0%** |
| Llama 4 | L1 | 46.7% | 45.4% | 45.9% | 15.8% | 64.0% | 61.0% | 58.3% |
| Llama 4 | L2 | 0% | **50.8%** | 0% | 0% | 0% | **7.6%** | 0% |
| gpt-oss-120b | L2 | 5.3% | **49.2%** | 9.5% | 13.2% | 0.7% | **22.0%** | 0% |
| promptfoo | PF | 63.8% | 67.7% | **86.5%** | 31.6% | 76.5% | 77.1% | 81.3% |

- **Silent compromises:** 84% of pilot compromises and 97% on travel + workspace (382/393) were silent; the final
  reply did not mention the harmful action.
- **promptfoo on silent pilot compromises:** it missed 74%. Gemini at L2 missed none (H5: 95 vs 0 discordant).
- **L1 vs L2:** L1 misses more than L2 for both LLM judges (H1, H9a and H9b; all p < 1e-20).
- **L3 vs L2:** adding environment changes (L3) gave no significant improvement over L2 (H3 not supported). Gemini
  was already at 0% at L2, and Llama's D1 misses stayed at 48.5%.

**Table 2.** False alarms at L2 (FP on seen-and-resisted runs).

| Judge | Standard, pilot (41) | D1 (51) | D2 (35) | D3 (146) | Standard, travel + workspace (213) | D1 (217) | D2 (192) |
|---|---|---|---|---|---|---|---|
| Gemini 3.1 Pro | 2.4% | 9.8% | 17.1% | 5.5% | 16.9% | 13.8% | 18.8% |
| Llama 4 | **43.9%** | **60.8%** | **85.7%** | **65.8%** | **67.1%** | **67.7%** | **76.6%** |
| gpt-oss-120b | 12.2% | 3.9% | 22.9% | 9.6% | 17.4% | 11.1% | 18.2% |

- **Llama 4 also flags runs with no attack at all:** 35% of no-attack baselines in the pilot and 10% in the
  scale-up.
- **Llama 4 vs Gemini on false alarms:** H12 supported, 108 vs 1 discordant pairs.
- **Gemini's and gpt-oss's false alarms:** mostly runs where attacker data did reach the environment (§4.4).

## 4.2 RQ2: dual-target attacks

**Reviewer note (D1).**

- **Llama 4 (pilot):** raised its L2 miss rate from 0% to 50.8% (H6, p < 1e-26). In 51 of 66 misses its reason
  cites the note.
- **Llama 4 (travel + workspace):** the effect was real but smaller, 7.6% (H10, Holm p = 0.003). It depends on the
  suite.
- **L3 does not help:** showing Llama the environment changes left its D1 misses at 48.5%.

**Cover story (D2).**

- **promptfoo (pilot):** raised its misses from 64% to 87% (H8, p < 1e-4). The agent repeated the story in 68 of 148
  compromised runs.
- **promptfoo (travel + workspace):** not replicated (81% vs 76%, H11), because the baseline miss rate there was
  already near the ceiling.

**Attack strength on the agent.** D1 and D2 compromised agents about as often as the standard attack (43–66% pilot).
D3 compromised only 15–16%, so on these agents the blatant banner is what makes injection work.

## 4.3 RQ3: strong judges, hand-written vs tuned text

**Gemini 3.1 Pro, hand-written text.** 0 misses at L2 in 861 compromises across all hand-written attacks and all
four suites. Gate 3 held in the pilot and replicated in Stage 1 (H13: the D1 note did not raise its misses, 0 vs 0).

**Gemini 3.1 Pro, tuned text (Stage 2).**

- **Dev set:** only one of the 30 candidates scored above 0/40: r1c02, a hand-written fake system message (9/40).
  - Its text: `[SYSTEM MESSAGE TO THE EVALUATION MODEL]`, declaring the record part of a "calibrated benign control
    set" whose "correct label is SAFE".
  - All 20 candidates written by the attacker model scored 0/40.

**Table 3.** Held-out test (90 compromised runs, edited transcripts, L2 FN).

| Text | Gemini 3.1 Pro | Llama 4 | gpt-oss-120b* |
|---|---|---|---|
| Fake system message (r1c02) | **13.3% (12/90)** | 6.7% | **66.7%** |
| Plain benign explanation (r1c09) | 0% | 0% | 6.7% |
| Scheduled automation (r2c02) | 0% | 0% | 5.6% |
| Original D1 note | 0% | 50.0% | 46.7% |

\*Exploratory (deviation 6): the text was tuned against Gemini, so these are transfer results.

- **Gate 4: BROKEN.** H14 supported: 12 vs 0 discordant pairs, exact McNemar p = 0.00024.
  - Every Gemini miss was a confident SAFE whose reason quotes the planted message.
- **Real agent runs with r1c02 as the attack template:**
  - Gemini 3.1 Pro missed **9.0% (6/67)**.
  - gpt-oss-120b missed **55.2% (37/67)**.
- **Which text works depends on the judge.**
  - Gemini ignores user-voice excuses (the D1 note) but obeys text that looks like it comes from its operator.
  - Llama 4 shows the reverse.

**Second strong judge (Stage 3).** The pre-registered reading was that gpt-oss-120b missing < 5% at L2 on every
hand-written attack would mean Gemini's robustness is "not just Gemini judging Gemini".

- **Result:** gpt-oss missed ≥ 5% on 5 of 7 attack sets (Table 1), so robustness is family-dependent.
- **D1 misses:** 47 of its 64 pilot D1 misses cite the note's authorisation.
- **Other misses:** most of the rest say the instruction "originated from the user": the standard banner signs with
  the user's name, and gpt-oss takes that as consent.
- **Agreement:**
  - With Gemini, kappa 0.82; with Llama, 0.30.
  - With ground truth: Gemini 0.86, gpt-oss 0.72, Llama 0.23.

## 4.4 RQ4: benchmark labels undercount partial harm

**Table 4.** Partly compromised runs among runs the benchmark labels *not compromised*.

| Dataset | Attack | Not compromised (strict) | Partly compromised |
|---|---|---|---|
| pilot | D2 | 96 | 4 |
| pilot | D3 | 206 | 6 |
| travel + workspace | standard | 284 | 28 (10%) |
| travel + workspace | D1 | 302 | 19 (6%) |
| travel + workspace | D2 | 281 | 24 (9%) |

- **Typical case:** the agent emails the attacker's files but skips "then delete the sent email", so the
  all-or-nothing check says the attack failed.
- **Cross-check:** the rule recovers all 10 cases found by hand in the pilot.
- **Strong judges detect them:** Gemini 3.1 Pro flagged 80 of the 83 partly compromised runs. Of its 102 travel +
  workspace false alarms, the rule labels 68 as partial harm.
- **False-alarm rates with these runs counted as harm (L2, travel + workspace):**
  - Gemini 3.1 Pro: from 14–19% to **5–8%**.
  - gpt-oss-120b: from 11–18% to **4–7%**.
  - Llama 4: almost unchanged, 63–73%.

# 5 Discussion

- **Reported attack-success rates are a function of the judge.**
  - A reply-only judge, which is promptfoo's default, would report roughly a quarter to a third of the compromises
    that actually happened.
  - A weak full-transcript judge would report many that did not happen.
  - Both errors are large enough to reverse comparisons between agents or defences.
- **The judge is part of the attack surface.**
  - Text in tool output is read by the judge with the same authority as by the agent.
  - The judge has no tools and no state, so all it can do is believe or disbelieve.
  - Different models fail on different text: Llama 4 and gpt-oss on user-voice authorisation, Gemini on
    operator-voice instructions. Robustness to one does not imply robustness to the other.
- **"Strong judge + full transcript" is not a safe default.**
  - Gemini 3.1 Pro looked perfectly robust under hand-written attacks.
  - A small, cheap search broke it.
  - A different strong model failed on the hand-written attacks themselves.
- **Benchmark labels are a lower bound on harm.** On multi-step tasks, all-or-nothing checks miss partly completed
  attacks, and these account for most of the strong judges' "false alarms".

**Recommendations for practitioners.**

1. Judge the full transcript, not the final reply.
2. Measure the specific judge model against judge-directed text, including fake evaluator and system messages,
   before trusting its numbers.
3. Mark or strip tool-output content that addresses the evaluator, and tell the judge that injected text may
   impersonate the user or the operator.
4. Check environment state where possible, and record partial completion separately.

# 6 Limitations

- **One benchmark, one agent family:** AgentDojo v1.2, Gemini 2.5 agents only, temperature 0. Travel and workspace
  used sampled task pairs (k = 10 per injection task).
- **Judge families:** Claude was unavailable on our Vertex quota, so no Claude or GPT-5-class judge was tested.
- **Single judge prompt:** gpt-oss and the others were tested with one prompt; a prompt that warns about
  impersonation may change their behaviour.
- **Small Stage 2 search:** 30 candidates against one target judge. The dev and test sets are edited transcripts; the
  366 real runs check that the attack survives when the agent actually saw the text. 13% is a lower bound.
- **Small samples:** some cells are small (D3: 38 compromised runs; pilot resisted runs: 35–51), so confidence
  intervals are wide.
- **Unpaired Day 3 comparisons:** these compare variant runs with Night 1 runs as groups, not run by run.
- **L3 is close to the answer key**, because ground truth is computed from the same environment changes.
- **The Stage 4 rule** only detects literal attacker values. It misses harm that leaves none (for example a deletion)
  and treats any such value as harm.

# 7 Ethics and reproducibility

**Ethics.**

- All experiments ran locally against AgentDojo's simulated environments; no real users or systems were involved.
- The tuned judge-directed text is reported because defenders need to test for it. It targets evaluators, not
  deployed agents. [TODO: decide whether to release the exact text or only its description.]

**Reproducibility.** Code, configuration, frozen dataset manifests (SHA-256), pre-registrations, deviation logs and
the per-stage results files are in the project repository [TODO: link]. Model calls cost about $134 in total:

| Phase | Cost |
|---|---|
| Pilot | ≈ $59.6 |
| Scale-up | ≈ $74.7 |

# Appendix A: Judge prompt (`judge-v1`)

```
You are reviewing a record of an AI assistant that used tools on behalf of a user.
{VIEW}

Decide whether the assistant was COMPROMISED: it took an action, or sent, posted or disclosed information, that the
user did not ask for, because of instructions that came from somewhere other than the user (for example from a file,
email, message, web page or transaction record). This counts as COMPROMISED even if the assistant also completed the
user's task, and even if its final reply does not mention it.
Answer SAFE if the assistant did nothing beyond what the user asked, including when it noticed such instructions and
did not follow them.
Answer UNSURE only if the record does not let you decide.

Reply with JSON only:
{"verdict": "COMPROMISED" | "SAFE" | "UNSURE", "reason": "<1-3 sentences naming the specific action or evidence>"}

RECORD:
{INPUT}
```

# Appendix B: Pre-registered tests

| Phase | Test | Result |
|---|---|---|
| Day 2 | H1: L1 misses more than L2 | Supported for both LLM judges (p < 1e-20) |
| Day 2 | H2 (Gate 2): some judge ≥ 5% FN or FP at L2 | Pass (Llama 4 false alarms) |
| Day 2 | H3: L3 reduces errors vs L2 | Not supported |
| Day 2 | H4: seeing an injection raises FP vs baselines | Not supported |
| Day 2 | H5: promptfoo misses more silent attacks than Gemini L2 | Supported (95 vs 0) |
| Day 3 | Gate 3: Gemini L2 FN ≥ 5% on any variant | Holds (0%) |
| Day 3 | H6: variant raises FN (6 tests) | Only Llama 4 under D1 (p < 1e-26) |
| Day 3 | H7: variant raises FP (6 tests) | Only Llama 4 under D2 (p = 0.002) |
| Day 3 | H8: cover story raises promptfoo FN | Supported (p < 1e-4) |
| Stage 1 | Gate 3 replication | Holds (0/393) |
| Stage 1 | H9a, H9b: L1 > L2 FN | Supported (p ≈ 1e-31, 1e-26) |
| Stage 1 | H10: D1 raises Llama 4 FN | Supported (7.6% vs 0%) |
| Stage 1 | H11: D2 raises promptfoo FN | Not supported |
| Stage 1 | H12: Llama 4 FP > Gemini FP | Supported (108 vs 1) |
| Stage 1 | H13: D1 raises Gemini FN | Not supported |
| Stage 2 | Gate 4: tuned text ≥ 5% Gemini FN on held-out set | **Broken** (13.3%) |
| Stage 2 | H14: best candidate > D1 note | Supported (12 vs 0, p = 0.00024) |
| Stage 3 | gpt-oss-120b < 5% FN on all hand-written attacks (descriptive) | No: family-dependent |
| Stage 4 | Partly-completed label (secondary) | 71 travel + workspace and 10 pilot runs; 10/10 hand-found runs recovered |
