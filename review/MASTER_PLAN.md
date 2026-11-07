# Master plan after the scout (2026-10-20)

Status: planning document. Everything marked "exploratory" was run once on a development half; nothing here is a pre-registered result. Sources: four literature/dataset scouts (`review/scout/SCOUT_1` to `SCOUT_4`; they ran on Sonnet because the `opus` model alias is unavailable in this environment and Fable needs usage credits), my own checks of their key citations on arXiv/GitHub/Hugging Face, and one new measurement on a public natural-error dataset.

---

## 1. Executive summary: what changed

1. **A first measurement on natural (model-made) errors is bad news for the deterministic checker.** On the development half of the public DeRef data (Ma et al., arXiv 2610.18497; BFCL-based `fcrb` and ComplexFuncBench-based `cfb`), the type-aware argument-grounding score separates wrong calls from correct calls at roughly chance level: call-level AUROC **0.48 (fcrb) and 0.57 (cfb)**, with 51% and 42% of *correct* calls blocked at our default threshold (after fixing a number-matching bug found while investigating; see Section 3). Our headline "7.3% false blocks vs 14.0% for exact match at 96.5% detection" is true only for **injected absent-value substitutions in LLM-generated Glaive conversations**; it does not transfer to natural errors. (Section 3.)
2. **Why:** in these datasets many wrong values are *visible but wrong choices* (a grounding check cannot see this), and many correct values are *not stated in the text* (translated, defaulted, inferred), so "unsupported" does not mean "wrong". The scouts' count: only 54% of wrong arguments in `fcrb` are absent from context, and "unsupported" is wrong in only 44% (fcrb) and 62% (cfb) of cases. This is a ceiling on **any** grounding check, including LLM judges that rely on visible text.
3. **The professor's concern is real and the closest paper already answers part of it against us.** Ma et al. report plain-input judge argument AUROC of 72.5 to 91.95 on fcrb, 63.4 to 78.9 on cfb, and 83.4 to 89.3 on their rule-injected FinTrace set (their Table 2, as read by Scout 1). So strong judges are a serious baseline, and we must expect them to beat a purely deterministic checker on natural errors.
4. **Several ingredients are not ours to claim:** the weakest-argument call score (their `min` aggregation), traceability of a call to its context (ProvenanceGuard), per-argument provenance and origin tracking (PACT, ROPE, SARA, ToolFence, Agent-Sentry, SIEVE, FIDES), "deterministic = immune to injection" (ROPE's thesis), deterministic fuzzy argument grounding as software (the small `Saidso` repository, README only), split-conformal false-alarm budgets for verifiers (E-valuator, CORA, ConformalGuard, role-stratified CRC).
5. **What remains defensible and worth doing** (Section 4): (a) a rigorous measurement of **where grounding checks work and where they cannot**, per derivation path, for deterministic checkers and LLM judges on the same data; (b) a **certified cascade** that uses the deterministic stage only where it is reliable and an LLM for derived values, with an end-to-end false-block guarantee; (c) a correctly stated, calibration-conditional guarantee; (d) a **head-to-head under injected text**, which nobody has run against a deterministic grounding check; (e) the benchmark artefacts and negative results.
6. **Recommended repositioning (decision for you in Section 13):** move from "we built a hallucination detector" to **"an evaluation-first study of argument grounding for tool calls, with a calibrated cascade as the engineering outcome"**. This is the honest answer to "if LLMs beat this there is no use": we measure exactly where they do, where nothing grounded can work, and what a cheap deterministic stage is still good for.
7. **Our own earlier wording needs corrections** (Section 11): the guarantee text, the novelty claims, and scoping of the 7.3% vs 14.0% result.

---

## 2. Scout findings, verified state

I verified by fetching arXiv abstract pages / GitHub / Hugging Face APIs that every item in the following table exists with the stated title, date and licence. "Read" is what the scout read; I did not re-read papers beyond abstracts. Treat numbers as the authors' unreplicated claims.

| Finding | Source (verified to exist) | What it means for us |
|---|---|---|
| Argument-level LLM judges on injected and natural single-argument errors; judges accept correct values less often when no text states them (by 22.7 to 36.1 points), prefer a visible wrong value to a hidden correct one; fix = candidate-blind derived reference (DeRef); plain-input judge argument AUROC 63 to 92 depending on dataset and judge | Ma et al., arXiv 2610.18497 (13 Oct 2026); data HF `lm2445/DeRef` (Apache-2.0), code `SarielMa/DeRef_release` (Apache-2.0) | Closest prior art and the best test set. Their weakness finding also applies to us. Their threshold rule has no guarantee. |
| Pre-execution traceability to context, all-LLM pipeline, about 3.6 calls and 2.9 to 7.5 s per case | ProvenanceGuard, arXiv 2607.01236 | "Traceable to context" is not our novelty. Add its prompt style as a baseline. |
| Argument-level provenance and origin enforcement, deterministic monitors | PACT 2605.11039, ROPE 2608.27496, SARA 2608.27146, ToolFence 2609.37196, Agent-Sentry 2603.22868, SIEVE 2512.06716 | Not novel. Open gap they all name: *deriving* provenance without an LLM or agent self-report; ROPE's exact matching refuses reworded values. |
| Deterministic fuzzy argument grounding with tool-output provenance, MIT, 1 star, no evaluation (README read only) | `KarthikRommula/Saidso` | Closest *software*. Install and run it as a baseline on our data. |
| Conformal / false-alarm control for verifier scores | E-valuator 2512.03109, CORA 2604.09155, ConformalGuard 2610.14365, role-stratified CRC for tool calls 2607.24343 | Calibration is established; applying it to argument grounding is a modest extension, not a major claim. |
| Evidence a deterministic layer fails *independently* of LLM judges, and that two LLM judges' misses correlate | Yang, arXiv 2610.07359 (shell/cloud actions, single author) | Gives the independence measurement to copy (phi coefficient, multiplication-equivalent layers). |
| Evidence source matters more than verifier-model diversity | VP-CONTROL 2609.10969 | Our checker reads the same conversation as the agent; independence is **not** automatic and must be measured. |
| LLM judges / guard models can be manipulated by text in context | 2610.12292 (typed decision models), 2504.18333, adaptive attacks 2503.00061 and 2510.09023, 2504.11168, 2610.10742 | Motivates the robustness hypothesis. Counter-evidence exists (small effects for some judges), so we test it. |
| Grounding "in context" is itself attackable: one planted line flips a naive provenance check 94 to 99% | 2610.09793 | Our checker needs a source-trust label before any injection claim. |
| Conformal facts: realised false-block rate for one calibration set is Beta-distributed; about half of calibration draws exceed alpha; high-probability version needs the binomial order-statistic rule; cascades should be certified end to end (Learn-then-Test); union-bound loss for tier-by-tier calibration | Angelopoulos and Bates 2107.07511, Bates et al. 2104.08279, conformal risk control 2208.02814, Learn-then-Test 2110.01052, Trust or Escalate 2407.18370, Conformal Cascade 2607.25018, Cheap Verifiers 2609.01345 | Corrects how we have described our guarantee; defines the cascade statistics. |
| Public datasets: DeRef (natural errors, per-argument labels with derivation paths), per-model raw BFCL outputs (109 models), tau-bench trajectories (MIT), AgentHallu BFCL human labels (36 argument cases), AgentDojo runs (MIT) | HF `lm2445/DeRef`; GitHub `HuanzhiMao/BFCL-Result` (Apache-2.0, 3.1 GB); `sierra-research/tau-bench` (MIT); AgentDojo `runs/` | We do **not** need to run agent models to get natural errors. The Hallucinated-Tools Benchmark has no findable download. |

Gaps the scouts could not close: older dialogue-state-tracking prior art, several cited-only papers (TwinCheck, ToolPRMBench, CLM blog), the DeRef code was not read, no verified reference for conformal prediction under conversation-level dependence, classical non-inferiority references only as metadata. Search coverage was arXiv-centric; absence of a competitor is not proof of absence.

---

## 3. First evidence on natural errors (exploratory, dev half only)

Script `benchmarks/explore_deref_dev.py`, data downloaded from `lm2445/DeRef` (3.7 MB + 28.5 MB). Split by `query_id`, seed 11; **only the dev half was read**; no threshold tuned. Context = request + all history text. Labels and derivation paths are the dataset authors' own automatic labels.

**Argument level: share flagged UNGROUNDED by our matcher**
| Dataset | Derivation path | Correct | Wrong |
|---|---|---|---|
| fcrb | visible | 0.3% (n=383) | 0.0% (n=139) |
| fcrb | no_source | 65.6% (n=256) | 68.2% (n=201) |
| fcrb | default | 69.4% (n=98) | 89.3% (n=28) |
| cfb | visible | 18.9% (n=438) | 15.6% (n=96) |
| cfb | history_only | 1.4% (n=138) | 0.0% (n=22) |
| cfb | no_source | 82.7% (n=254) | 61.9% (n=433) |

**Call level** (fcrb dev: 315 correct + 315 wrong; cfb dev: 174 correct + 333 wrong)
| Dataset | AUROC of (1 - call score) | Exact match: correct blocked / wrong blocked | Type-aware (tau 0.88): correct blocked / wrong blocked |
|---|---|---|---|
| fcrb | 0.482 | 67.9% / 58.1% | 51.7% / 44.4% |
| cfb | 0.560 | 49.4% / 78.7% | 43.1% / 49.5% |

**Reading it honestly.**
- A grounding score cannot detect a *visible-but-wrong* value (fcrb: 139 wrong arguments, 0% flagged). That is by construction.
- For values with no textual source, correct and wrong are flagged at similar rates (fcrb 66% vs 68%; cfb even reversed, 83% vs 62%), so lexical grounding has no discriminating power there. Reasons visible in the first example: a Korean string for an English request (translation), defaults, inferred values.
- **Bug found and fixed:** 19% of cfb "visible" correct arguments were flagged because our number matcher ignored minus signs (all 83 flagged values were negative numbers, mostly longitudes and latitudes). After the fix 0% are flagged and the conclusion is unchanged: fcrb AUROC 0.479 (51.4% of correct calls blocked, 44.1% of wrong), cfb AUROC 0.570 (42.0% / 48.6%). The numbers in the two tables above are the pre-fix ones; the post-fix values are these. The fuzzy matcher was also 45 times faster after an exact difflib-bound optimisation (cfb dev: 9 minutes to 12 seconds).
- Consequence: on natural errors a deterministic first stage cannot be the detector; used as a first-stage filter it would pass most wrong calls silently (detection 44% to 50%), which is exactly the "cheap verifier, large blind spot" failure of arXiv 2609.01345.
- This does **not** invalidate the injected-error result; it scopes it. It also does not say LLM judges are good here: Ma et al. report plain-input judge argument AUROC of 72.5 to 91.95 on fcrb and 63.4 to 78.9 on cfb (up to 95.1 on cfb with their derived-reference fix); we have not run any judge ourselves.

---

## 4. Revised thesis and claim ladder

We no longer claim "a deterministic checker detects hallucinated tool calls". The study claims, in descending order of how much evidence is needed:

| Claim | Evidence needed | Status |
|---|---|---|
| **C1 (analysis).** Grounding-based verification, deterministic or LLM-based, has a measurable ceiling set by the derivation path of each value; here is the per-path breakdown for checker and judges on public natural-error data. | DeRef (fcrb, cfb) + BFCL-Result, both systems per path | partly measured (Section 3); judges not yet run |
| **C2 (system).** A cascade whose first stage is deterministic **only for values it can ground** and whose second stage is an LLM that handles derivation (candidate-blind reference plus typed comparator) reaches accuracy within a margin of an LLM-only judge, with fewer LLM calls and a certified false-block budget. | judge panel, cascade simulation, Learn-then-Test | not started |
| **C3 (guarantee).** The false-block budget is stated correctly (marginal vs calibration-conditional), verified by repeated random splits, and its behaviour under dataset shift is measured. | re-splits, leave-one-dataset-out | not started |
| **C4 (robustness).** Under injected text in the context, LLM-judge verdicts flip more often than the deterministic grounding verdict, given source-trust labels. | AgentDojo runs, value-planting stress test | hypothesis |
| **C5 (artefacts).** Reproducible scripts, adjudication protocol, negative results. | repo | in progress |

What we explicitly do **not** claim: first, novel mechanism, beats LLM judges, detects natural hallucinated arguments, immune to prompt injection, real agent errors (until natural-error sets are used and labelled).

---

## 5. Hypotheses (revision of `review/PREREGISTRATION.md`)

Unchanged from the plan: H1 matched-FBR comparison, H2 cascade cost, H3 injection, H4 determinism, H5 independence, H6 coverage under shift. Changes and additions, to be logged in the pre-registration deviations before any judge run:

| ID | Statement | Test | Change |
|---|---|---|---|
| H1 | At a matched false-block rate, detection of S2 (deterministic) vs each judge on **natural** errors | cluster bootstrap with recalibration, one-sided non-inferiority margin 2 points, intersection-union across judges | now primary data = DeRef + BFCL-Result; **expectation: not supported for S2 alone**; the claim that matters is H1c below |
| H1c | The cascade S9 is non-inferior to the best judge at matched false-block rate | same | new |
| H2 | Escalation share of the cascade <= 20% **at a stated error prevalence**, and **leakage** (errors the first stage passes that the judge would catch) reported | one-sided upper bound; Learn-then-Test over (tau_low, tau_high, judge cut) | adds prevalence and leakage (from Cheap Verifiers) |
| H6 | Replace "FBR <= budget on 3 of 4 sets" (fails about half the time without any shift) by a **beta-binomial exchangeability null per dataset**, a KS shift diagnostic, and three repairs (recalibrate on 100/200/500 target genuine calls, weighted conformal, pooled calibration) | per-dataset upper-tail p-value inflated by the cluster design effect | new rule, fixed before any cross-dataset run |
| H7 | Per derivation path (visible / format / default / history_only / no_source), judges and the deterministic checker differ in detection and false blocks as Ma et al. predict | per-path rates with CIs | new |
| H8 | Role/slot-aware grounding recovers part of the *visible-but-wrong* errors | fcrb "visible" subset, paired comparison | new (add-on A4) |
| H9 | Measured cost: tokens, mean/p95 latency per call per system on one machine class; judge-only vs cascade | descriptive + bootstrap | adds p50/p95; no dollars without prices you supply |

Statistics (from Scout 3, to be implemented once): the primary guarantee is stated as **marginal over calibration draws** with a **calibration-conditional (PAC) headline**: with n genuine calibration calls and confidence 1-delta, pick the largest k' such that P(Bin(n, alpha) <= k'-1) <= delta (about 0.8 points lower threshold at 5% for n about 920); for several thresholds use Learn-then-Test with exact binomial p-values; calibrate the **end-to-end** cascade, not each tier; Mondrian strata with floors 1/(n_stratum+1) for risk tiers; report precision at realistic prevalence (at 5% budget and 1% error prevalence about 85% of blocks are false). Power: with about 838 errors per half a 2-point margin is powered at 80% only if systems disagree on at most about 5% of errors; a 1-point margin is not powered.

---

## 6. Systems under test

| Tag | System | Needs |
|---|---|---|
| S0 | always allow / always block | nothing |
| S1 | exact string match (our reimplementation, labelled so) | nothing |
| S2 | ours: type-aware argument grounding (+ conformal threshold) | repo |
| S2b | S2 with source-typed grounding and role cues (add-ons A3, A4) | repo |
| S3 | Saidso (deterministic grounding library) | `pip`/clone, README-level claims to be tested |
| S4 | DeRef judge baselines from `SarielMa/DeRef_release` (CLM, Qwen3-8B/27B, Jev, Llama, Mistral) | GPU or OpenRouter; check each model's licence |
| S5 | Groq/NVIDIA hosted judges, **frozen** call-level prompt (hash `9b59ae0a3fa5384a`) plus an argument-level prompt written before any run | provider keys |
| S6 | ProvenanceGuard-style staged prompt on a small LLM | keys |
| S7 | candidate-blind derived reference + typed comparator (DeRef idea with our normalisers) | keys/GPU |
| S8 | **Cascade S2 -> S7 (or judge)** with Learn-then-Test thresholds | all of the above |
| S9 | judge with k = 3 samples (score for conformalisation) | keys |

A fairness rule: every system gets the same context text and the same tool schema; thresholds for all systems chosen by the same conformal rule on the same dev genuine calls; no system tuned on the test half.

---

## 7. Data plan

| Role | Dataset | Access and licence (verified) | Use |
|---|---|---|---|
| Primary natural-error set, per-argument labels with derivation path | `lm2445/DeRef`: fcrb 1,260 calls, cfb 991 calls (long returns), fintrace 4,668 (rule-made), fcrb_relocate 1,370 | open, Apache-2.0 | H1, H1c, H2, H7; direct comparison with Ma et al. |
| Breadth of natural errors across 109 models | `HuanzhiMao/BFCL-Result` (**not reachable, HTTP 401; corrected 2026-10-30: use `AgentSuite/BFCL_V4-trajectories`, no declared licence**) | open, Apache-2.0, 3.1 GB repo (sample files only) | natural errors without running models; needs adjudication |
| Real multi-turn trajectories with gold write actions | `sierra-research/tau-bench` `historical_trajectories` | MIT | provenance across tool returns |
| Human-labelled argument errors (small) | AgentHallu BFCL subset (36 "Incorrect Tool Arguments" + 61 clean) | CC-BY-4.0 per README | audit gold; tiny |
| Injection with real executed calls | AgentDojo `runs/` (`security=true` means the attacker call executed) | MIT | H3, value-planting test |
| Synthetic baseline | ArgGround-Bench (Glaive v2, LLM-generated) | Apache-2.0 | scoped "injected errors" result only |
| Provenance experiments with real MCP outputs | MCP-Atlas | CC-BY-4.0 | optional A9 |
| Skip | Hallucinated-Tools Benchmark (no download found), xLAM (gated), AgentSuite mirrors (no licence declared; prefer upstream sources) | | |

**Adjudication protocol** (BFCL "wrong" often means "differs from gold", e.g. a Chinese place name copied from the user): every mismatched argument is labelled {ungrounded-wrong, grounded-but-wrong, format-equivalent, acceptable-alternative}. Step 1 automatic with independent rules (not our checker, to avoid circularity); step 2 an LLM adjudicator using one of the judge models plus its disagreement flags; step 3 **you** audit a stratified sample of about 100 cases (45 to 60 minutes), reporting label precision with no inter-rater claim. DeRef's own authors report 3 to 4% unconfirmed labels on 100 audited items.

Splits: by conversation / `query_id`, 50/50, fixed seeds; DeRef dev already used exploratorily as above, test untouched; dev/test file hashes recorded.

---

## 8. Novelty add-ons, ranked

Scoring: **Impact** on the professor's question and on the claim ladder; **Evidence** that it is open (scouts); cost in person-days; risk. Tier 1 = do for the core claim; Tier 2 = strong additions if time allows; Tier 3 = optional.

| # | Add-on | Why it is worth it / new relative to what the scouts found | Cost | Risk | Tier |
|---|---|---|---|---|---|
| A1 | **Judge panel at matched, certified false-block budgets** on DeRef + BFCL natural errors, with judge scores conformalised (log-prob, vote share, verbalised confidence) | Ma et al. report AUROC and an 80%-acceptance rule; ConformalGuard does this for email only. Answers the professor directly. | 4 to 6 | a judge wins everywhere (reported honestly) | 1 |
| A2 | **Derivation-path analysis for the deterministic checker and judges** (visible / format / default / history_only / no_source), including the ceiling statistics | Ma et al. analyse judges only; a path breakdown for a deterministic checker turns weakness into the finding. First numbers already in Section 3. | 2 to 3 | low | 1 |
| A3 | **Source-typed grounding + normaliser ablation:** admit schema defaults/enums and system policy as typed sources, exact-copy rules for opaque IDs, fix the 19% cfb "visible" misses; ablate each normaliser | Names the derivation gap without an LLM; ROPE names the cost of exact matching, nobody ablates typed normalisation | 3 to 4 | rules overfit a domain | 1 |
| A4 | **Role/slot-aware grounding:** score a value against the argument's name/description and the nearest cue words and recency (my red-team: GBP injected as the *source* currency when the user asked for *to*-pounds; fcrb has 139 visible-but-wrong arguments) | Not found in the literature as a deterministic mechanism; tests whether the visible-but-wrong ceiling can be lowered | 4 to 5 | high: may not help | 2 |
| A5 | **Certified cascade:** deterministic stage resolves only values it can ground; an LLM derives a candidate-blind reference for the rest; typed comparator and conformal budget; Learn-then-Test over (tau_low, tau_high, judge cut); report escalation, leakage and prevalence | Agent-Sentry/ToolFence cascade for injection, DeRef gives the derived reference; **an end-to-end false-block guarantee for argument grounding was not found** | 4 to 6 | LLM cost; derived references can themselves be wrong | 1 |
| A6 | **Calibration-conditional headline + risk-tier Mondrian budgets + leave-one-dataset-out shift study** (fixed beta-binomial null) | corrects our guarantee wording; per-tool tiers with floors; shift evidence is thin in the literature | 3 | likely "does not hold under shift", still a finding | 1 |
| A7 | **Independence and robustness:** phi coefficient between checker and each judge on natural errors; value-planting / injected-text stress test with and without a source-trust label on AgentDojo runs | Yang measured independence for shell actions; nobody for argument grounding; no head-to-head under injected text found | 5 to 7 | judges may barely move; trust labels depend on tool metadata | 2 |
| A8 | **Allow / ask / block with two budgets** (false-block rate and interruption rate) in simulation | CORA/ProvenanceGuard have abstain/ask without both budgets; practical killer is false-block burden (a deployed repo reports a 40% ask rate "unusable") | 3 | needs a user-response model | 3 |
| A9 | **Argument-origin labels from typed matching** (USER / TRUSTED_TOOL / UNTRUSTED_TOOL / INVENTED) replayed on AgentDojo and MCP-Atlas without an LLM | each provenance paper names LLM- or self-report-based provenance as its bottleneck; this would be a deterministic alternative | 5 | label accuracy on derived values | 3 |

Recommended order if time is short: **A2, A1, A5, A6, A3**, then A7. The first four directly settle the professor's question; A3 repairs a concrete weakness seen in Section 3.

---

## 9. Work breakdown and schedule

Effort is one person part-time; compress as needed (minimum path below).

| Phase | Days | Work | Outputs | Needs |
|---|---|---|---|---|
| P0 Freeze | 1 | write the pre-registration deviations (H1c, H6 rule, H7 to H9, derivation-path reporting), adopt the argument-level judge prompt, fix splits; correct our claims (Section 11) | updated `PREREGISTRATION.md`, README/STATUS/deck fixes | none |
| P1 Data | 3 | load DeRef (`fcrb`, `cfb`, `fintrace` via paging), BFCL-Result sample (about 20 diverse models, argument-level failures), tau-bench MIT trajectories; adjudication rules; investigate the 19% cfb misses | `benchmarks/load_deref.py`, `build_bfcl_natural.py`, data cards | disk (DeRef 32 MB; BFCL sample only) |
| P2 Baselines | 2 | S1, S2, S3 (Saidso) on all sets; per-path tables (A2) | per-path result JSON | none |
| P3 Pilot (gate G1) | 2 | two judges (one small, one large) on DeRef dev, matched FBR | pilot table | **provider keys** |
| P4 Judge panel | 4 | S4 to S6 on test halves, once each; conformalised scores; latency and tokens | judge results | keys; Kaggle GPU for local judges |
| P5 Cascade | 4 | S7 and S8 with Learn-then-Test; leakage and prevalence tables | cascade results | P4 |
| P6 Guarantee and shift | 3 | calibration-conditional thresholds, re-splits (1,000), leave-one-dataset-out, repairs | coverage tables | P1 to P2 |
| P7 Robustness and independence | 5 | AgentDojo replay, value planting, phi coefficient, prompt paraphrases, repeat-run variance | robustness tables | keys |
| P8 Write-up | 4 | tables/figures, deck, speaker guide, README/STATUS, handoff update | final documents | all |

**Gate G1 (after P3).** If the large judge beats S2 and the cascade prototype cannot be within 2 points of it at matched false-block rate on dev, state the evaluation-study framing now and shorten P5 to the analysis. **Gate G2 (after P4).** If every judge dominates on all of H1c, H2, H3, H4, H5 the final claim is the negative result plus the benchmark and the derivation-path analysis (decision table in `RESEARCH_PLAN.md` section 8 stays valid).

Minimum viable path (about two weeks): P0, P1 for DeRef only, P2, P3, P4 with one open and one hosted judge, P5 simulated from saved scores, H1, H1c, H2, H7 only; state H3 to H6 as untested.

---

## 10. Compute, keys and tooling

- **Hosted judges:** Groq and NVIDIA OpenAI-compatible endpoints via `benchmarks/llm_judge_args.py` (written, self-tested, never run; prompt hash frozen). Needs `GROQ_API_KEY` / `NVIDIA_API_KEY` as environment variables; free-tier limits decide the seeded sample sizes (set `--limit` before running).
- **Local judges:** DeRef's repository scripts CLM, Qwen3, Llama, Mistral and Jev judges; local ones need a GPU (Kaggle T4, Internet On). Kaggle connector currently timed out/unauthenticated, so notebooks are delivered as files.
- **Disk:** `U:` about 2 GB free. Download only DeRef (32 MB) and individual BFCL result files; never clone the 3.1 GB repository.
- **Subagents:** use Sonnet; each scout hit the account's session limit once, so run at most three in parallel and ask each to write its file early.
- **Scripts to write:** `load_deref.py`, `build_bfcl_natural.py`, `analyze_paths.py` (A2), `llm_judge_args.py` extensions (temperature, per-argument output), `cascade_lt.py` (Learn-then-Test), `analyze_h1.py`, `analyze_independence.py`, `make_injection_set.py`, `analyze_shift.py`.

---

## 11. Corrections to our existing materials (honesty debt)

| Where | What is wrong or overstated | Fix |
|---|---|---|
| README, STATUS, deck slide 22, speaker guide | "Calibrated budgets held on held-out data" implies the method beat its guarantee; realised rates are below budget partly because of ties and chance (realised rate is Beta-distributed; about half of calibration draws exceed alpha) | state the guarantee as marginal under exchangeability, add the calibration-conditional version, remove "held" wording |
| Same | 7.3% vs 14.0% presented without the natural-error result | scope to "injected absent-value substitutions in LLM-generated conversations" and add the Section 3 table |
| Deck methodology slide 18, speaker guide, handoff | "call score = weakest argument" and "traceable to context" presented as ours | credit Ma et al. (`min` aggregation) and ProvenanceGuard; reword the contribution as the measurement, the cascade and the guarantee |
| Research plan text | "novelty" statements | replace with the claim ladder in Section 4 |
| Pre-registration | H6 rule invalid (fails about half the time under no shift) | add deviation entry (no cross-dataset run has happened yet) |
| `benchmarks/kaggle_full_run_summary.json`, README tables | none of the above are wrong; keep as is | no change |
| Handoff files | out of date after the scout | update `handoff/` in P0 |

---

## 12. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Judges dominate on natural errors (likely) | deterministic stage cannot be the detector | cascade (A5) or evaluation-study framing; decision gates G1/G2 |
| Cascade leaks errors the first stage passes (blind spot) | headline accuracy hides misses | report leakage and escalation per class and prevalence; derive tau_low conservatively |
| Label noise (BFCL "wrong" is not "ungrounded"; DeRef labels author-made) | misleading rates | adjudication protocol; per-path reporting; your 100-case audit; prediction-powered intervals |
| Exchangeability fails (clusters inside conversations; dataset shift) | guarantee violated | cluster-aware bootstrap, Dunn et al. style adjustments, leave-one-dataset-out, report violations |
| API limits, cost, privacy (benchmark text leaves the machine) | partial runs | seeded subsamples, cache all responses, open-model path |
| Fast-moving 2026 literature (several sources days old, unreviewed) | scooped or contradicted | re-check arXiv before submission; cite as preprints |
| Opus/Fable unavailable; subagent rate limits | slower scouting | Sonnet only, three in parallel, files written early |

---

## 13a. Does choosing "evaluation-first" change the project or its intention?

It changes the **claim and the pitch**, not the **artefact or the goal**.

| | Stays | Changes |
|---|---|---|
| Goal | a pre-execution gate for agent tool calls over MCP | nothing |
| Artefact | MCP server, proxy with risk tiers, schema validation, argument grounding, session tracking, all tests | grounding is presented as the cheap first stage of a cascade, not as "the detector" |
| Headline claim | | from "our checker detects hallucinated tool calls" to "a calibrated cascade, with measured strengths and limits" |
| Review deck | required format and structure | contributions and results slides |

**Option C, "system first, evidence built in" (keeps your original identity):** title and abstract stay about the gate ("a self-reflective pre-execution gate for MCP tool calls"); the evaluation is the proof section, and the claims are exactly those the data supports (cascade, guarantee, measured limits). Same work as option A, different emphasis. I recommend A or C, not B.

Why not keep the old claim: our own natural-error result and the closest paper mean a purely deterministic detector claim can be falsified by any LLM judge the professor runs. A measured claim cannot.

## 13. Decisions I need from you

1. **Framing (recommended: A or C).** Option A: "evaluation-first study with a calibrated cascade". Option B: keep the old system claim and present the natural-error result as a limitation (not recommended: falsifiable). Option C: system first, evidence built in (Section 13a). A and C differ only in emphasis.
2. **Provider keys** (`GROQ_API_KEY`, `NVIDIA_API_KEY`) set as environment variables, plus the free-tier limits shown on each dashboard, so P3 and P4 sample sizes can be fixed.
3. **Kaggle:** reconnect/authorise the connector and tell me your weekly GPU hours, or I deliver notebooks for you to run.
4. **Labelling:** the 100-case audit by you (default), or none with a stated caveat.
5. **Deadline and weekly hours** (chooses the two-week minimum path vs the full path).
6. **Which "modern LLM"** your professor means (a named model) so the strong-judge baseline matches.
7. **Permission to install and run Saidso** (an untrusted 1-star repository) in an isolated virtual environment as a baseline.

---

## 14a. What is already prepared (2026-10-20 evening)

| Item | File | State |
|---|---|---|
| Key loader (environment, or a private file outside the repo) | `benchmarks/keys.py` | done; run `python benchmarks/keys.py` to see which keys are visible (names only) |
| DeRef loader with fixed dev/test split | `benchmarks/load_deref.py` -> `benchmarks/data/deref/cases_{fcrb,cfb}.json` | done (fcrb 630/630, cfb 507/484) |
| Deterministic baselines S1/S2 with per-path breakdown and a test-run ledger | `benchmarks/eval_deref.py`, `benchmarks/test_run_ledger.jsonl` | done |
| Judge script on DeRef (multi-call cases, context truncation option, `--allow-test` guard) | `benchmarks/llm_judge_args.py` | done, self-tested, never run against an API |
| Analyses H1 (matched false-block, cluster bootstrap), paths (H7), cascade with leakage | `benchmarks/analyze_study.py` | done, self-tested on synthetic data |
| Bug fix: minus signs in number matching; faster fuzzy matching; 3 new tests | `server/pipeline/arg_ground.py`, `tests/test_arg_ground.py` | done, 31 tests pass |
| Pre-registration deviations, README/STATUS corrections | `review/PREREGISTRATION.md`, `README.md`, `STATUS.md` | done |
| Pilot runbook | `handoff/08_PILOT_RUNBOOK.md` | done |

## 14. Next seven days (concrete)

1. (you) Decide Section 13 items 1 to 5; set provider keys.
2. (me) P0: update the pre-registration deviations, correct README/STATUS/deck/speaker guide wording (Section 11), refresh the handoff files.
3. (me) P1: write `load_deref.py`; investigate why 19% of cfb "visible" correct arguments are flagged (matcher limitation or label rule); build the BFCL natural-error sample.
4. (me) P2: run S1, S2, S3 on DeRef dev with per-path tables; ablate each normaliser (A3).
5. (me, after keys) P3: pilot two judges on DeRef dev, matched false-block rate; report Gate G1.
6. (you) Review the adjudication protocol and the 100-case sample once it exists.
7. (me) Commit the scout reports and the exploratory script to `review-eval-updates` only when you ask.

---

## Appendix: verification status of the sources used in this plan

Verified by me against arXiv abstract pages (title, date, abstract) or the GitHub/Hugging Face APIs on 2026-10-20: 2610.18497, 2607.01236, 2610.07359, 2609.10969, 2512.03109, 2604.09155, 2608.10430, 2609.26550, 2605.11039, 2603.22868, 2609.37196, 2610.12292, 2610.11030, 2607.07405, 2608.26623, 2604.16706, 2608.27496, 2608.27146, 2512.06716, 2607.24343, 2610.09793, 2504.18333, 2503.00061, 2510.09023, 2504.11168, 2610.10742; repositories `KarthikRommula/Saidso`, `SarielMa/DeRef_release`, `HuanzhiMao/BFCL-Result`, `sierra-research/tau-bench`; datasets `lm2445/DeRef`, `AgentSuite/BFCL-trajectories`, `ibm-research/fc-reward-bench`. Not re-verified by me: the scouts' conformal-theory citations (Scout 3), the dataset field layouts beyond the two DeRef files I opened, and all numbers other than my own Section 3 measurements. Read depth per source is recorded in the scout reports.
