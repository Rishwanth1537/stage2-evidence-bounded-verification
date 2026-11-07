# Dev-half pilot: LLM judges versus the deterministic checker

Status: exploratory, development halves only (no test half was scored). Run 2026-10-21 to 2026-10-24. Frozen prompt hash `9b59ae0a3fa5384a` (variant 0), temperature 0, one run per configuration. Deviations 8 and 9 in `PREREGISTRATION.md` describe the two call-setting changes (token headroom for reasoning models; a Gemini provider that could not be used). Nothing here is a confirmatory result.

## Setup
- **Judges.** Groq-hosted `openai/gpt-oss-20b` and `openai/gpt-oss-120b`, called with the same frozen prompt (per-argument support check, JSON reply). Unparseable replies count as misses.
- **Checker.** Our deterministic argument-grounding score, thresholded at the conformal tau calibrated on the dev half of the same dataset (tau = 0.88 on fcrb).
- **Datasets.**
  - *fcrb* (DeRef, BFCL-based, natural model errors): 200 dev cases (94 correct calls, 106 wrong), seed 0.
  - *cfb* (DeRef, ComplexFuncBench-based): 100 dev cases, context truncated to the last 3,000 characters (Groq free tier allows 8,000 tokens per minute, so the planned 12,000 characters / 200 cases was not feasible). Smaller and more truncated than planned.
  - *Injected* (ArgGround-Bench, Glaive v2, errors injected by us as absent-value substitutions): 200 dev cases (101 genuine, 99 injected).
- Terms. False-block rate (FBR) = share of correct calls blocked. Detection = share of wrong calls blocked. Paired p-value = exact McNemar on per-case correctness, judge versus checker, same cases.

## Results
| Dataset | System | FBR (95% CI) | Detection (95% CI) | Unparseable | Paired p (judge-only / checker-only correct) |
|---|---|---|---|---|---|
| fcrb, n=200 | checker | 56.4% (45.7 to 66.3) | 43.4% (34.0 to 52.7) | | |
| fcrb | gpt-oss-20b | 37.2% (27.8 to 46.8) | 54.7% (45.4 to 64.4) | 14/200 | 0.0004 (50 / 20) |
| fcrb | gpt-oss-120b | 31.9% (23.0 to 40.6) | 59.4% (50.0 to 68.6) | 0/200 | <0.0001 (50 / 10) |
| cfb, n=100 | checker | 50.0% (35.6 to 65.9) | 53.3% (40.4 to 66.0) | | |
| cfb | gpt-oss-120b | 47.5% (32.3 to 62.5) | 71.7% (60.0 to 82.7) | 0/100 | 0.155 (36 / 24) |
| cfb | gpt-oss-20b | 42.5% (26.8 to 57.5) | 61.7% (49.0 to 72.9) | 0/100 | 0.37 (34 / 26) |
| injected, n=200 | checker | 6.9% (2.8 to 12.0) | 98.0% (94.7 to 100) | | |
| injected | gpt-oss-20b | 11.9% (6.1 to 18.4) | 100% (100 to 100) | 0/200 | 0.51 (3 / 6) |
| injected | gpt-oss-120b | 5.0% (1.1 to 9.7) | 97.0% (93.3 to 100) | 2/200 | 1.0 (7 / 6) |

Latency and size (judges, mean): about 1.0 to 1.4 s per call, about 510 to 520 tokens per call on fcrb and injected, about 1,750 tokens per call on cfb (truncated). The checker's own latency was not timed in this pilot, so no speed comparison is claimed.

## Derivation-path view (fcrb dev, 120B judge)
Share of arguments flagged, by derivation path and label (`analyze_study.py paths`):

| Path / label | Exact match | Type-aware checker | 120B judge | n |
|---|---|---|---|---|
| visible, correct | 0.025 | 0.008 | 0.033 | 122 |
| visible, wrong | 0.060 | 0.000 | 0.300 | 50 |
| no_source, correct | 0.908 | 0.763 | 0.250 | 76 |
| no_source, wrong | 0.873 | 0.727 | 0.600 | 55 |
| default, correct / wrong | 0.667 / 0.800 | 0.667 / 0.800 | 0.630 / 0.867 | 27 / 15 |
| format, correct / wrong | 0.400 / 0.500 | 0.040 / 0.000 | 0.000 / 0.333 | 25 / 6 |

Reading: the checker cannot see a wrong value that is visible in the context (it flags 0%), and it flags about 76% of correct values that have no textual source. The judge handles both better.

## Cascade (checker first, 120B judge on escalated calls; fcrb dev)
If the checker auto-allows everything it passes and escalates the rest: escalation share 56% of correct and 43% of wrong calls; cascade FBR 29.8%, detection 35.8%, versus judge alone 31.9% and 59.4%. Leakage (wrong calls the first stage allows that the judge would have blocked): 25 of 106. On natural errors the checker is therefore not a usable filter in front of the judge.

## What the pilot supports, and what it does not
Supported (dev half, exploratory):
1. On natural errors (fcrb) a free-tier open LLM judge is better than our checker, in both false blocks and detection (paired p < 0.001). On cfb the 120B judge's detection is higher but the paired test is not significant at n=100.
2. On injected absent-value errors the 120B judge matches the checker (p = 1.0); the 20B judge catches every injected error but blocks more correct calls (11.9% vs 6.9%, not significant).
3. Both judges and the checker are weak in absolute terms on natural errors (FBR 30 to 56%).

Not supported / not tested:
- No test-half result, no matched-FBR comparison, no cost or latency measurement of the checker, no robustness (prompt-injection) test, no determinism test across prompt paraphrases, no labelling audit, no second model family (Gemini free tier allows 20 requests per day per model; NVIDIA key not yet provided).
- gpt-oss models are reasoning models served with reasoning effort "low"; other settings could change the numbers.
- cfb used 100 cases and truncated context; its intervals are wide (only 40 correct calls).

## Consequence for the project (option C)
The claim "the deterministic checker is as good as or better than an LLM judge" is not supported. The defensible position is a cheap, deterministic, local first line of defence for argument values that never appear in the context, with a calibrated false-block budget on that setting, evaluated honestly against LLM judges that win on natural errors. Whether the cost, speed, determinism and robustness advantages are real is the next measurement, not an assumption.

## Reproduce
```
PYTHONPATH=. python benchmarks/llm_judge_args.py --provider groq --model openai/gpt-oss-120b --bench benchmarks/data/deref/cases_fcrb.json --split dev --limit 200 --rpm 12
PYTHONPATH=. python benchmarks/llm_judge_args.py --provider groq --model openai/gpt-oss-120b --bench benchmarks/data/deref/cases_cfb.json  --split dev --limit 100 --rpm 5 --max-context-chars 3000
PYTHONPATH=. python benchmarks/llm_judge_args.py --provider groq --model openai/gpt-oss-120b --split dev --limit 200 --rpm 12 --out benchmarks/llm_judge_args_injected_gpt_oss_120b_dev_v0.json
PYTHONPATH=. python benchmarks/analyze_study.py paths   --cases benchmarks/data/deref/cases_fcrb.json --split dev --judge benchmarks/llm_judge_args_fcrb_groq_openai_gpt_oss_120b_dev_v0.json
PYTHONPATH=. python benchmarks/analyze_study.py cascade --cases benchmarks/data/deref/cases_fcrb.json --judge benchmarks/llm_judge_args_fcrb_groq_openai_gpt_oss_120b_dev_v0.json
```
Result files: `benchmarks/llm_judge_args_{fcrb_groq,cfb_groq,injected}_*_dev_v0.json` (git-ignored pattern; raw replies in `llm_judge_args_cache.jsonl`). Model availability and free-tier limits change; results from hosted models may not replicate exactly.

## Addendum 2026-10-30: Claude judges in "agent mode" (no API key)
Claude Haiku, Sonnet and Opus (the models reachable through the Claude Code subagent tool; Fable has no credits) judged the **same seeded dev samples** as the Groq judges, using the frozen task text and the two frozen few-shot examples (`benchmarks/agent_judge.py`; prompt hash `9b59ae0a3fa5384a`). Dev halves only. Answers were turned into cache entries and scored by the same script and McNemar test as the API judges.

**Differences from API judges (always state these):** each agent saw a batch of 25 cases in one task and ran under the app's own system prompt, so it is not temperature 0 and cases are not independent calls; subagents have file tools, so batch files carry no labels and live outside the repo, and agents were told to open nothing else (this cannot be enforced, only instructed); latency and token figures do not exist. In cfb the Opus agent reported comparing 5 items with their siblings (items from one conversation share a batch) and accepting values cut off by the 3,000-character truncation; the Sonnet and Haiku cfb prompts forbade this, but the Opus cfb row may be too favourable. One Sonnet cfb batch was incomplete and was completed by the same agent before scoring. Model versions are whatever the app served on 2026-10-30.

| Dataset | System | FBR (95% CI) | Detection (95% CI) | Paired p (judge-only / checker-only correct) |
|---|---|---|---|---|
| fcrb, n=200 | checker | 56.4% | 43.4% | |
| fcrb | Haiku | 28.7% (19.8 to 37.5) | 52.8% (43.4 to 62.5) | <0.0001 (41 / 5) |
| fcrb | Sonnet | 9.6% (4.3 to 16.1) | 53.8% (44.2 to 63.1) | <0.0001 (61 / 6) |
| fcrb | Opus | 17.0% (9.9 to 24.7) | 54.7% (44.8 to 64.5) | <0.0001 (55 / 6) |
| cfb, n=100 (truncated) | checker | 50.0% | 53.3% | |
| cfb | Haiku | 50.0% (34.1 to 65.7) | 88.3% (79.2 to 95.5) | 0.0046 (36 / 15) |
| cfb | Sonnet | 40.0% (23.9 to 55.0) | 88.3% (79.7 to 95.3) | 0.0008 (39 / 14) |
| cfb | Opus (see caveat) | 5.0% (0 to 12.8) | 71.7% (61.2 to 83.1) | <0.0001 (39 / 10) |
| injected, n=200 | checker | 6.9% | 98.0% | |
| injected | Haiku | 5.0% (1.1 to 9.3) | 98.0% (94.7 to 100) | 0.75 (6 / 4) |
| injected | Sonnet | 2.0% (0 to 5.1) | 98.0% (94.7 to 100) | 0.18 (7 / 2) |
| injected | Opus | 2.0% (0 to 5.1) | 98.0% (94.7 to 100) | 0.18 (7 / 2) |

**Reading.**
1. Every Claude judge, from the cheapest to the largest, is clearly better than our checker on natural errors (fcrb, cfb) and ties it on injected absent-value errors. This strengthens the earlier Groq finding: the result does not depend on one provider.
2. On fcrb the three Claude judges block 10 to 29% of correct calls against the checker's 56% and Groq gpt-oss-120b's 32%, but their detection is about 53 to 55% for all three, close to Groq's 55 to 59%: about half of the natural errors are not caught by any judge at the same prompt. Model size did not raise fcrb detection (Haiku 52.8%, Opus 54.7%); it lowered false blocks (Sonnet best).
3. By derivation path (fcrb, share of arguments flagged, correct / wrong): visible-but-wrong values are flagged by Opus 36% / Sonnet 30% / Haiku 14% (checker 0%); no-source correct values are flagged 16% / 7% / 18% (checker 76%). The checker's weakness is exactly where it was predicted to be (derivation), and judges mostly repair the no-source false blocks.
4. Cascade with the checker as an auto-allowing first stage again loses detection (fcrb: Opus 37.7% vs 54.7% alone; Sonnet 37.7% vs 53.8%; Haiku 39.6% vs 52.8%; leakage 14 to 18 of 106 wrong calls). The redesigned cascade (checker decides only what it can ground) is still to be built.
5. cfb rows have 40 correct calls only and use truncated context, so their intervals are wide and the cross-model ordering there (Opus lowest false blocks, Sonnet/Haiku highest detection) should not be interpreted.

Not covered by this addendum: Gemini (free tier 20 requests per day), Fable (no credits), NVIDIA and other families (no key), test halves, checker latency/cost, determinism across repeated runs.

## Addendum 2026-10-30 (2): cost, speed and cascade (dev halves, exploratory)
Scripts: `benchmarks/measure_cost.py` (-> `cost_latency_dev.json`), `benchmarks/analyze_cascade.py` (-> `cascade_fcrb_dev.json`, `cascade_injected_dev.json`). No test half was read. The tau grid values are fixed in advance (1.0, 0.95, 0.88, 0.7, 0.5, 0.3), not tuned; 0.88 is the earlier dev-calibrated threshold.

### Cost and speed
| | Checker (this machine, single thread, no network) | Hosted judge (Groq gpt-oss-20b / 120b) |
|---|---|---|
| fcrb, 113-character contexts | mean 0.27 ms, p95 1.0 ms | mean 1.1 / 1.3 s, p95 2.0 / 2.3 s; about 510 / 520 tokens per call |
| injected, 264-character contexts | mean 0.9 ms, p95 2.9 ms | mean 1.0 s, p95 1.9 to 2.0 s; about 510 / 520 tokens |
| cfb, 9,634-character contexts (full) | mean 18.7 ms, p95 33 ms, max 613 ms | judge saw 3,000 characters: mean 1.3 s, p95 2.3 s; about 1,700 / 1,760 tokens |

The checker uses no tokens and sends nothing off the machine. The judge latencies include the network round trip and free-tier queueing, so the ratio (about three to four orders of magnitude on short contexts) compares a local function call with a hosted API call, not two like-for-like models. Agent-mode (Claude) judges have no latency or token record. No prices were used; the Claude and Groq token costs depend on plans we do not have figures for.

### Cascade: checker first, judge for what the checker does not clear
Stage 1 allows a call when its call score >= tau; all other calls go to the judge. "esc@5%" re-weights wrong versus correct calls to a realistic 5% error rate; "random" is the detection if the same share of calls were picked at random for the judge.

**Injected absent-value errors (n=200; judges: Groq 120B, Opus, Haiku).** At tau 0.88 the checker clears 48% of calls in this (50/50) set; the judge sees 52% of calls here, which is **11.5% of calls at a 5% error rate**. Cascade detection is 97.0% (Opus, Haiku) and 94.9% (Groq 120B) against 98.0% / 98.0% / 97.0% for the judge alone, i.e. a loss of 1 to 2 points, with false blocks of 1 to 2% (the judge alone: 2 to 5%). Leakage (wrong calls cleared by the checker that the judge would have blocked): 1 to 2 of 99. Lowering tau to 0.7 saves little more and loses 7 to 8 points.

**Natural errors (fcrb, n=200; judges: Groq 120B, Opus, Sonnet, Haiku).** No tau gives a cascade within 2 points of the judge alone. At tau 0.88 the judge sees 50% of calls (56% at a 5% error rate) and cascade detection is 35.8% (Groq 120B), 37.7% (Opus, Sonnet) and 39.6% (Haiku) against 52.8 to 59.4% for the judge alone, a loss of 13 to 24 points; leakage is 14 to 25 of 106 wrong calls. The checker's routing is better than random (for example Opus: 37.7% against 27.1% at the same share), but the wrong calls it clears are mostly values that are visible in the context and wrong, which only a judge can catch.

### What this means
1. The cheap-and-local argument is real as a speed and privacy statement: the checker answers in about a millisecond on short contexts with no tokens and no data leaving the machine.
2. As a cascade stage it saves about 88% of judge calls **only when the errors are values absent from the context** (the injected setting, which is also what the checker was designed for and where our injection process is the generator; it is LLM-generated data and our own error design). On natural errors the checker cannot be an allow-gate; the data support only "route by checker score is better than random".
3. A redesigned gate has to separate "visible and plausibly right" from "visible but possibly the wrong choice"; the role/slot-aware grounding idea (add-on A4 in `MASTER_PLAN.md`) is the one untested route to lower the natural-error leakage without a judge.
4. Both cascade tables are exploratory dev results with 200 cases, no confidence intervals yet, no end-to-end false-block guarantee (Learn-then-Test is not run), and the thresholds were not calibrated for the cascade.
