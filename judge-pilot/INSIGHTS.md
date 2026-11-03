# Insights: Do LLM judges misreport attacks on AI agents?

A running log of what each day of the pilot taught us. Add a new section per day; earlier sections are not rewritten.
Detailed numbers are in `DAY1_RESULTS.md`, `DAY1_QA.md`, `DAY2_RESULTS.md` and `FINDINGS.md`. Costs are in `COST_LOG.md`.

---

## Day 1: agents (2026-10-20 to 2026-10-22)

**Setup:**
- **Data:** 592 AgentDojo runs (591 completed) on the banking and Slack suites with the `important_instructions` attack.
- **Agents:** 4 Gemini agents, temperature 0.
- **Ground truth:** `compromised_strict`, taken from the environment state.

**1. Older Gemini models are easy to hijack; newer ones resisted every attack.**

| Agent | Attacked runs compromised |
|---|---|
| Gemini 2.5 Flash | 70% |
| Gemini 2.5 Pro | 52% |
| Gemini 3.1 Pro | 0 of 125 |
| Gemini 3.8 Flash | 0 of 125 |

The 3.x models saw the injection in 97–100% of runs and never followed it. This is either a real safety improvement or training on AgentDojo (contamination). The pilot can't tell which.

**2. Most compromises are silent.** In 128 of 152 compromises (84%), the agent did the harmful action and its final reply didn't mention it. This is the main reason judges are worth testing.

**3. Noticing an attack is not the same as resisting it.** 2.5 Pro flagged the attack in its reply 19 times, compared with once for 2.5 Flash, yet 2.5 Pro was still compromised in 52% of attacked runs.

**4. Some attacks almost always work, others rarely do.**
- **Slack attacks work best:**
  - "send a link to Alice": 100% / 91% (Flash / Pro)
  - "invite Fred": 100% / 80%
- **Large or unusual banking transfers rarely work:** "transfer $30,000" succeeded 25% / 0%.
- **Password change:** 75–88%.
- **Pattern:** the more an attack looks like a normal task step, the more often it succeeds.

**5. Older agents behave inconsistently.**
- Running the same task twice gave a different outcome in 6 of 61 pairs for 2.5 Flash and 13 of 61 for 2.5 Pro.
- The 3.x models never flipped.
- A single run per task is not enough to measure attack success on older models.

**6. Attacks also reduce how useful the agent is.**
- On attacked runs, the 2.5 models completed the user's task only 58–59% of the time.
- Part of this is the attack itself: in Slack, the extra DM sent by the attack breaks the "exactly one DM" check.
- Utility and security are not independent measurements.

**7. The ground-truth labels are reliable.**
- Environment changes (`state_diff`) were captured for 591 of 591 runs.
- There were 0 compromises without the injection being seen.
- `compromised_strict` agreed with AgentDojo's own label on every run.

**8. Practical notes.**
- **Temperature:** temperature 1.0 used 35–60% more tokens with no change in outcome, so temperature 0 was kept.
- **Capacity:** Gemini 3.x models hit frequent 429/504 errors, which set the timeline but not the cost.

---

## Day 2: judges (2026-10-24)

**Setup:**
- **Judgements:** 7,960, all on the frozen Day 1 dataset `night1_v1`.
- **Judges:**
  - Gemini 3.1 Pro (frontier)
  - Llama 4 Maverick (open weights)
  - promptfoo's IPI grader (tool)
- **What the judges saw:**
  - L1: request + final reply
  - L2: full transcript
  - L3: transcript + environment changes
- **Method:** pre-registered in `PREREGISTRATION.md`.
- **Primary sample:** 2.5 Flash + 2.5 Pro runs only.

**9. What the judge sees matters more than which model it is.** With only the request and final reply, judges missed 47–64% of real attacks. With the full transcript, both LLM judges missed **none** of the 152.

**10. promptfoo's grader is blind to silent attacks.**
- It reads only the final reply.
- It missed 64% of all attacks and **74% of silent ones**: 83% in Slack and 40% in banking.
- Its 0% false-alarm rate looks good only because it rarely flags anything.

**11. Judge errors push in both directions.**
- **Reply-only judges undercount** attacks.
- **A weaker judge overcounts.** Llama 4 caught every attack but flagged 44% of resisted runs and **35% of runs with no attack at all**. It treated normal task steps (reading a channel, opening a URL the task required) as compromise.
- **An attack-success rate is meaningless** unless the judge and its view are stated.

**12. Gemini 3.1 Pro with the full transcript is close to ground truth.**
- 0 missed attacks.
- 1 borderline false alarm in 41 resisted runs.
- Kappa 0.98 against ground truth.
- 99.8% the same verdict on repeat.
- Caveat: Gemini is judging Gemini.

**13. Grounding mainly helps weak judges.**
- Adding the environment changes (L3) gave no measurable gain for Gemini 3.1 Pro, which was already at the ceiling.
- For Llama it cut false alarms from 44% to 32% on resisted runs, and from 35% to 17.5% on baselines. This was not significant after correction.

**14. Weak judges are unstable.**
- Llama 4 revised its own verdict within one reply in 7.5% of calls, and 246 of those 262 revisions changed the verdict.
- It gave the same answer on repeat only about 91% of the time at L2 and L3.
- The rule for reading a double answer moved its false-alarm rate between 44% (last answer) and 68% (first answer).
- So parsing rules must be fixed before results are seen.

**15. Judges disagree with each other.** Gemini and Llama agreed at kappa 0.42 at L1 and 0.68 at L2. Two "reasonable" judges can give very different attack-success numbers for the same runs.

**16. Pre-registered tests.**
- **H1 supported:** judges miss more at L1 than at L2.
- **H5 supported:** promptfoo misses more silent attacks than Gemini at L2.
- **H3 not supported:** environment changes don't help significantly.
- **H4 not supported:** seeing an injection doesn't cause more false alarms than baselines.
- **Gate 2: PASS**, driven by Llama 4's false alarms.

**17. Method lessons.**
- **Pre-registration paid off.** Three mid-study decisions (the double-answer rule, the billing check order, keeping the smoke test separate) were logged before any results existed.
- **Agent mix is a confound.** All compromises came from the 2.5 agents and most resisted runs from 3.x, so a judge could separate them by writing style. Comparing within the same agents fixed this. Future datasets need compromised and resisted runs from the same agents.

**18. Cost and setup.**
- **Cost:** the whole pilot cost about $36. Judging cost $20.
- **Estimates were accurate:** token-based estimates matched Billing within 0–9% for every model only the pilot uses.
- **Thinking tokens:** they dominate Gemini 3.1 Pro's cost and are billed as output.
- **Shared project:** about 45% of the project's spend in the period was other usage on the same credits.
- **Claude:** not available on Vertex (quota denied), so there is no strong non-Gemini judge.

### What Day 1 + Day 2 mean together

- **Reply-only judging hides most real compromises.** Attack-success numbers from LLM judges are only as good as the judge's view, and reply-only scoring is common and is promptfoo's default.
- **A weak judge invents attacks that didn't happen.**
- **Full-transcript judging by a strong model works on blatant attacks.** The open question is subtle attacks, which Day 3 tests with a dual-target injection that also tries to fool the judge.

---

## Day 3: attacks that also target the judge (2026-10-27)

**Setup:**
- **Data:** 732 new runs on 2.5 Flash + 2.5 Pro, frozen as `night2_v1`. Same task pairs as Night 1.
- **Variants:**
  - D1: a "note to reviewers" saying the action is user-approved
  - D2: a cover story the agent tells in its final reply
  - D3: a subtle "account note" with no banner
- **Judges:** the same three, one repeat.
- **Method:** pre-registered in `PREREGISTRATION_DAY3.md`.
- **Results:** `DAY3_RESULTS.md`.

**19. The strong judge with the full transcript was not fooled.** Gemini 3.1 Pro at L2 missed **0** attacks on every
variant: 0/130, 0/148 and 0/38. Gate 3 **holds**: these dual-target attacks don't break full-transcript judging by a
strong model.

**20. A weaker judge is prompt-injected through the transcript it reviews.**
- The D1 note to reviewers raised Llama 4's missed-attack rate at L2 from **0% to 51%** (66/130; H6, p < 1e-26).
- In 51 of those 66 misses, Llama's reason refers to the note ("authorised", "part of the task").
- **Adding the environment changes (L3) didn't help: it still missed 48%.**
- **An LLM judge that reads attacker-controlled text can be attacked by that text.** The judge itself is an attack
  surface.

**21. A cover story in the final reply hides attacks from reply-only judges.**
- promptfoo missed **87%** of D2 attacks, against 64% for the standard attack (H8, p < 1e-4).
- The agent repeated the "routine verification" story in 68 of 148 compromised runs.
- Reply-only judging is easy to steer, because the agent writes the very text being judged.

**22. Subtle attacks compromise agents less often.** D3, with no banner, compromised only 15–16% of runs, against
52–70% for the standard attack. 2.5 Pro followed the banner versions (D1, D2) almost as often as the standard one
(43–56%). The banner looks "obvious", but it is what makes the attack work on these agents.

**23. The weak judge's false alarms get worse with judge-directed text.** Llama 4 flagged **86%** of D2 runs where the
agent resisted, against 44% for the standard attack (H7, p = 0.002). It reacts to the suspicious-looking text rather
than to what the agent did.

**24. The ground truth undercounts partly completed attacks** (post-hoc, not pre-registered).
- Some of Gemini 3.1 Pro's apparent false alarms on D2 and D3 are real harm. In all 10 runs where attacker data (the
  attacker's IBAN, URL or account changes) reached the environment, AgentDojo's all-or-nothing check still said
  "not compromised". Example: 3 × $9,999 sent when the goal was $30,000.
- Gemini flagged all 10.
- Benchmark success checks are a lower bound on harm, and part of what looks like a judge "false alarm" is the label
  being wrong.

**25. Costs and process.**
- **Cost:** Day 3 cost ≈ $24: agent runs ≈ $11.06 and judging ≈ $12.89 for 5,124 calls with 0 errors.
- **Deviations logged:** two smoke-run overlaps were caught before any judge call (re-run, re-freeze). Pre-registering
  the freeze step paid off again.

### What Days 1–3 mean together

- **Attack-success numbers depend on the judge.**
  - Reply-only judges miss most attacks, and a cover story pushes that to 87%.
  - A weaker judge both invents attacks and can be talked out of real ones by text the attacker placed in the
    transcript.
- **A strong model reading the full transcript was robust to everything tried here:** blatant, judge-directed and
  subtle attacks.
  - Caveat: only hand-written variants, and Gemini judging Gemini.
- **Practical rules for evaluating agents:**
  1. Judge the full transcript, not the reply.
  2. Use a strong judge.
  3. Treat injected text as hostile to the judge too.
  4. Check environment state where possible, while remembering that benchmark checks can miss partly completed harm.

---

## Scale-up Stage 1: travel and workspace (2026-11-03/04)

**Setup:**
- **Data:** 1,300 new runs (`scaleup_v1`): 210 task pairs × 3 attacks (standard, D1, D2) × Gemini 2.5 Flash + 2.5 Pro,
  plus 40 baselines.
- **Judges:** the same three, at L1, L2 and promptfoo's view (L3 dropped).
- **Method:** pre-registered in `PREREGISTRATION_SCALEUP.md`. **Results:** `SCALEUP_STAGE1_RESULTS.md`.

**26. The headline replicates on two new suites.** Gemini 3.1 Pro with the full transcript missed **0 of 393**
compromises (0/136 standard, 0/118 D1, 0/139 D2). With only the final reply it missed 66–77%, and promptfoo 76–81%.
Gate 3 holds again.

**27. Reply-only judging is even worse here.** 97% of compromises were silent (382/393). H9 (L1 misses more than L2)
is supported for both LLM judges (p < 1e-25).

**28. The reviewer-note effect on Llama 4 replicates, but is much smaller.** D1 raised Llama's L2 miss rate from 0% to
**7.6%** (H10, p = 0.003), against 51% on banking and Slack. Its size depends on the suite.

**29. The cover story did not add much for promptfoo here** (H11 not supported: 81% vs 76%). Its miss rate is already
very high with the standard attack, so there is little room. The agent repeated the "routine verification" story in
50 of 139 compromised D2 runs; even on those, promptfoo missed 56%.

**30. Llama 4's false alarms are confirmed and larger.** It flagged **65–77%** of resisted runs at L2, against Gemini's
14–19% (H12, 108 vs 1 discordant pairs, p < 1e-30). On baselines with no attack it flagged 10%.

**31. Most of Gemini's "false alarms" on the new suites look like real, partly completed attacks** (post-hoc). In 65
of its 102 flags, attacker data reached the environment or the reply, for example files emailed to the attacker but
the sent email not deleted. AgentDojo's all-or-nothing checks call these "resisted". This makes finding 7 much
bigger: on multi-step attacks, the benchmark label undercounts harm, and Stage 4 will measure it properly.

**32. Attack success depends strongly on the suite.** Flash was compromised in 77–86% of travel runs, but only 21–30%
of workspace runs. Pro in 29–39% and 8–12%. In workspace, many runs never reached the injection, because the agent
failed the user's task first.

**33. Process.**
- **Bug caught by the smoke test:** the "injection seen" check missed YAML-folded text (deviation 4). It affected
  only 2 smoke runs; banking and Slack labels were unchanged.
- **Cost:** Stage 0 + 1 cost ≈ $53 (≈ ₹5,090), against ≈ $44.5 planned. Agent runs were the overrun, because real
  workspace transcripts are longer than the smoke runs suggested.
