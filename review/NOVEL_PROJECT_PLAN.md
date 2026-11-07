# Novel project plan: evidence-grounded pre-execution verification of tool-call arguments (v1, 2026-10-30)

> **Status update 2026-10-30 (after the first experiments; see `EXPERIMENTS_2026-10-30.md`).**
> - E0 state tier: negative on tau-bench (0 of 538 environment-accepted errors caught). The MCP read-only-probe mechanism (claim C2 as written) has no supporting evidence on public benchmarks; keep it only as future work for stateful systems where agents invent ids.
> - Contract tier: works as a cheap complement (16% false blocks, 22 to 26% detection) and adds 16 to 19 points to a judge that lacks the definition.
> - Decidability/information (C1): supported on dev data; judges of three sizes plateau at 50 to 54% and gain 16 to 20 points when shown the tool definition.
> - Consensus: AUROC 0.93 on all 200 BFCL cases but not significantly better than a schema-aware Opus judge at matched false blocks (56.0% vs 45.9%, CI -0.14 to +0.31); partly measures format convention; needs 29 extra calls.
> - Certified cascade (C3) and robustness (C4) not yet attempted; no test half read.
> - Revised lead: a measurement study of what information decides tool-argument correctness (decidability map, contract tier, consensus) plus the cheap deterministic tiers, with the certified cascade as the system contribution if time allows.


Status: proposal for decision. It supersedes the "what to do next" parts of `MASTER_PLAN.md` (sections 8 and 9) but keeps its statistics, data rules and honesty rules. Nothing in this file has been run except where it cites the dev-half results in `DEV_PILOT_RESULTS.md`.

## 0. One-paragraph summary
Our own measurements show that checking a tool call only against the conversation cannot work as a detector: seven judges (Groq 20B/120B, Claude Haiku/Sonnet/Opus) and our checker all miss a large part of natural argument errors, and the judges' detection stays at 53 to 59% on fcrb whatever their size. The reason is that many wrong values are *not decidable from the conversation at all*. The project therefore asks a sharper question: **which evidence is needed to decide that an argument value is wrong, how much of the error mass each evidence source can decide, and can a cheap, deterministic MCP gate that uses the right evidence (conversation, tool contract, live read-only server state) plus a certified LLM fallback match the best judge at a fraction of the cost?** The deliverables are (1) a measured decidability map on standard benchmarks, (2) an open MCP gate that uses MCP's own tool metadata to find read-only "resolver" probes, (3) a calibrated cascade with an end-to-end false-block guarantee, and (4) an adjudicated benchmark/harness. A cheap feasibility experiment (E0) decides within about a week whether the central mechanism has headroom; if not, the project becomes the measurement study (1)+(4), which is still defensible.

## 1. What the evidence so far forces
| Fact (dev halves, exploratory) | Consequence |
|---|---|
| Context-grounding checker is near chance on natural errors (AUROC 0.48 fcrb, 0.57 cfb) | context alone is not the right evidence for natural errors |
| Seven judges beat it on fcrb (false blocks 10 to 37% vs 56%) but all detect only 53 to 59% | a ceiling set by information, not by model size |
| By derivation path: visible-but-wrong values are flagged 0% by the checker and 14 to 36% by Claude judges; correct values with no text source are flagged 76% by the checker, 7 to 18% by judges | the errors are a *selection* problem (which of several visible values) and a *derivation* problem (value computed or looked up) |
| Checker answers in 0.3 to 0.9 ms on short contexts, no tokens; judges 1.0 to 1.3 s and about 520 tokens | the cheap-local argument is real, but only worth it if the cheap stage is accurate on something |
| As an allow-gate before a judge, the checker saves about 88% of judge calls on absent-value errors (1 to 2 points lost) but loses 13 to 24 points on natural errors | the cascade works only where the first stage has real evidence |

## 2. Landscape (read abstracts only; several are days-old preprints, re-check before any submission)
| Work | What it does | Where it stops, relative to this plan |
|---|---|---|
| [Ma et al. 2610.18497](https://arxiv.org/abs/2610.18497) (DeRef) | argument-level LLM judges, `min` aggregation, derivation-path labels, public data | analyses judges only; no deterministic evidence, no state, no certified cascade |
| [StateMirror 2610.32648](https://arxiv.org/abs/2610.32648) (23 Oct 2026) | deterministic pre-execution check of coding-agent actions against the *live repository* (paths, packages); beats best LLM judge by 35% F1 at 1.5 ms | coding-agent predicates extracted by AST/command analysis; not general MCP tools; no argument-value semantics, no judge fallback, no guarantee |
| [Closed-World Resolution 2609.19425](https://arxiv.org/abs/2609.19425) | registry and signature check for non-existent tools/arguments, MCP namespace taxonomy | names and schemas, not values; says the borrowed-argument residue is schema-indistinguishable |
| [NOMOS 2610.11030](https://arxiv.org/abs/2610.11030) | compiles written policies into deterministic tool-call gates (tau2-bench) | policy rules, not argument-value correctness |
| [Prefix Executability 2610.40444](https://arxiv.org/abs/2610.40444) (29 Oct 2026) | evaluation protocol: is every prefix executable under schemas, state preconditions, data dependencies (BFCL-v3 multi-turn, ToolSandbox, tau3) | evaluates agents offline; not a gate, no judge comparison, no value-level decidability map |
| [Benchmarking the Benchmarks 2607.02577](https://arxiv.org/abs/2607.02577) | audits BFCL v4, tau2-bench, LiveMCPBench, MCP-Atlas; Tool-Veritas: state checks first, LLM judge only for the rest | grading of benchmark outcomes, not runtime gating of arguments |
| [TwinCheck 2609.26911](https://arxiv.org/abs/2609.26911), [RubricRefine 2605.09730](https://arxiv.org/abs/2605.09730) | inference-time verification/repair on BFCL V4 and code-mode tool use | repair policies; no deterministic evidence tiers or false-block budgets |
| [Latent Critic 2608.10430](https://arxiv.org/abs/2608.10430) | white-box LoRA critic for specification-grounding failures | needs model internals; not an MCP gate |
| [ProvenanceGuard 2607.01236](https://arxiv.org/abs/2607.01236), PACT/ROPE/SARA, Saidso | argument provenance / traceability to context | context only; LLM- or self-report-based provenance |
| [EffectWorld 2610.35981](https://arxiv.org/abs/2610.35981), [ASU 2610.21063](https://arxiv.org/abs/2610.21063) | effect-typed tools; effect binding for approvals | effect safety and approval integrity, not value correctness |
| Practice: MCP tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`), see [WebMCP surface-poisoning 2606.06387](https://arxiv.org/abs/2606.06387) | the protocol already marks which tools are read-only | web search found no work that uses these annotations to auto-discover verification probes for a pending call (absence of evidence from a short search, not proof) |

Honest reading: every ingredient exists somewhere (context grounding, schema gates, state predicates for coding agents, judge fallback, conformal budgets). **Not found:** (a) a decidability map of argument errors by evidence source across standard tool benchmarks, (b) automatic discovery of read-only resolver probes from MCP metadata to verify argument values for general MCP tools, (c) an end-to-end false-block-certified cascade over those evidence tiers compared head-to-head with judges at matched false-block rate and cost. Novelty is therefore in the *combination, the measurement and the MCP-native mechanism*, not in any single check; claim it that way.

## 3. Thesis and claim ladder (what the paper may say if the data support it)
| ID | Claim | Needs | Novelty risk |
|---|---|---|---|
| C1 | **Decidability map.** On standard benchmarks, X% of natural argument errors are decidable from the conversation, Y% from the tool contract (schema, enum, format, cross-argument constraints), Z% from live state via read-only probes, W% from none of these; judge detection plateaus at the context-decidable share | E1, E2 | medium (closest: DeRef paths, Prefix Executability) |
| C2 | **MCP-native resolver probes.** A gate that discovers read-only tools (`readOnlyHint`, naming and schema match) and uses them to verify id, name and enum arguments catches Q more natural errors than context grounding at the same false-block rate | E3, E4 | medium-high (StateMirror in coding; MCP-generic version open) |
| C3 | **Certified cascade.** Deterministic tiers + judge fallback, calibrated end-to-end (Learn-then-Test), is within 2 points of the best judge's detection at matched false-block rate with at most 25% of judge calls at 5% error prevalence | E5, E6 | medium (conformal cascades exist, argument grounding not found) |
| C4 | **Robustness.** Deterministic evidence is invariant to injected text; judge verdicts flip | E7 | medium-high (provenance literature is crowded) |
| C5 | **Artefacts.** Open MCP gate, adjudicated benchmark with evidence-source and derivation labels, frozen harness, ledger, negative results | all | low (but real impact) |

Kill rule: if E0 shows the added evidence tiers lift deterministic detection by fewer than 5 points at matched false-block rate, drop C2/C3 as headline and publish C1+C4(if supported)+C5 as a measurement study.

## 4. Systems under test
| Tag | System | Status |
|---|---|---|
| S0 | allow-all / block-all | trivial |
| S1 | exact string match (our reimplementation) | exists |
| S2 | type-aware context grounding (current checker) | exists |
| S3 | S2 + contract tier: schema types, enums, formats, ranges, cross-argument rules, defaults as allowed sources | to build (about 3 days) |
| S4 | S3 + role/slot-aware grounding (value vs argument name/description and cue words; candidate competition) | to build (about 4 days; high risk) |
| S5 | S4 + state tier: auto-discovered read-only resolver probes, replayed on recorded environments | to build (about 6 days; E0 decides) |
| S6 | judge panel: Groq gpt-oss 20B/120B, Claude Haiku/Sonnet/Opus (agent mode), NVIDIA/Gemini/other API judges when keys exist | exists (dev) |
| S7 | DeRef published judge baselines (CLM, Qwen3, ...) | optional, needs GPU |
| S8 | cascade S5 -> S6 with Learn-then-Test thresholds | to build (about 4 days) |
| S9 | Saidso and StateMirror-style baselines where runnable | optional, isolated environment, only with your permission |
Fairness rule (unchanged): same context, same tool schema, thresholds chosen by the same conformal rule on dev genuine calls, nothing tuned on test.

## 5. Datasets (standard benchmarks first)
| Role | Dataset | Access / licence (as recorded in the scouts; verify before use) | Used for |
|---|---|---|---|
| Natural errors with per-argument derivation labels | DeRef `lm2445/DeRef` (fcrb from BFCL, cfb from ComplexFuncBench) | Apache-2.0, loaded | E1, E2, E4, E5 |
| Natural errors across 109 models | `AgentSuite/BFCL_V4-trajectories` (30 models; `HuanzhiMao/BFCL-Result` is not reachable) + BFCL v4 data and executable multi-turn environments (gorilla repo) | Apache-2.0; 3.1 GB, download single files | E1 (breadth), E3 (state replay) |
| Stateful customer-service tool use with databases | tau-bench / tau2-bench (`sierra-research/tau-bench`, historical trajectories) | MIT | E3, E4, E6 |
| Stateful tools with milestones | ToolSandbox | licence not yet checked | E3 (optional) |
| Real MCP servers | MCP-Atlas | CC-BY-4.0 per scout | E8 live demo (optional) |
| Human-labelled argument errors (small) | AgentHallu BFCL subset | CC-BY-4.0 per README | audit gold |
| Injection with executed attacker calls | AgentDojo runs | MIT | E7 |
| Synthetic absent-value substitutions | ArgGround-Bench (Glaive v2, LLM-generated) | Apache-2.0, built | ceiling for the context tier; scoped claims only |
Splits: by conversation/query id, 50/50, fixed seeds, hashes recorded; dev halves already used exploratorily; test halves untouched; ledger records every look.

Labelling: automatic from gold (`equivalent(pred, gold)` written independently of the checker), with an adjudication label per mismatched argument {ungrounded-wrong, grounded-but-wrong, format-equivalent, acceptable-alternative}; you audit about 100 stratified cases (45 to 60 minutes) and we report label precision, not inter-rater agreement.

## 6. Experiments
Each experiment states purpose, data, procedure, primary metric, and the decision it feeds. All use cluster bootstrap by conversation, exact McNemar for pairs, Holm correction across the confirmatory set, and matched-false-block-rate comparisons via conformal thresholds.

**E0. Feasibility of the new evidence tiers (about 1 week, dev only, go/no-go).**
Purpose: does anything beyond context grounding add detection? Data: fcrb/cfb dev (contract tier, role-aware tier) and a 300-call sample from tau-bench and BFCL multi-turn replayed against recorded state (state tier). Procedure: for every wrong argument, record which tier (if any) would have decided it, with the tier's false-block rate on correct arguments. Metric: detection at matched false-block rate versus S2; share of errors decidable per tier. Gate: at least 5 points over S2 at matched rate for some tier, else apply the kill rule.

**E1. Decidability map (core of C1).** Data: DeRef plus the AgentSuite BFCL trajectories (30 models) plus tau-bench trajectories. Procedure: label each wrong argument by the weakest evidence source that decides it (conversation, contract, state, none) using rules independent of the systems, then adjudicate a sample. Metric: share per class, per dataset, per model family; correlation between judge detection and context-decidable share. Output: the table that explains the 53 to 59% plateau (or refutes it).

**E2. Judge panel at matched, certified false-block rates (C1, C3 baseline).** Data: dev and then test halves of fcrb, cfb, BFCL sample, tau-bench sample. Systems: S1, S2, S6 (7 judges so far, more when keys exist; add k=3 sampling for a continuous score), S7 optional. Metric: detection at matched false-block rate (conformal thresholds on dev genuine calls), per derivation path, with tokens and latency. Status: dev numbers exist; needs matched-rate analysis (`analyze_study.py h1`), a continuous judge score, and the test run once.

**E3. Contract and state tiers (C2).** Build S3 then S5. State tier: classify tools by MCP annotations and schema (read-only, identifier-returning); match argument names/types to resolver tool outputs (list/search/get); verify a pending id/name/enum value by replaying the read-only call on the recorded environment (tau-bench database, BFCL environment classes). Metrics: detection at matched false-block rate by error class, probe cost (calls and ms), failure modes (stale state, side effects). Safety rule: the gate only issues tools marked `readOnlyHint` (or whitelisted read-only), never a write.

**E4. Role/slot-aware grounding (C2, high risk).** Targets visible-but-wrong values (fcrb has 139 of them). Method: candidate competition among type-compatible values in context, score by argument-name/description match, nearest cue words, recency; deterministic first, small local model as an ablation. Metric: paired comparison on the fcrb "visible" subset. A negative result is reported.

**E5. Certified cascade (C3).** Cascade S5 -> S6. Choose (tau_low, tau_high, judge cut) by Learn-then-Test with exact binomial p-values on dev; calibrate the end-to-end false-block rate; report escalation share at 5% error prevalence, leakage, cost saved, and the marginal vs calibration-conditional (PAC) guarantee verified with 1,000 random re-splits. Gate: within 2 points of the best judge at matched false-block rate and at most 25% escalation, otherwise report the achievable frontier.

**E6. Shift (C3).** Leave-one-dataset-out; per-dataset beta-binomial exchangeability null and a KS shift diagnostic; recalibration on 100/200/500 target genuine calls; weighted conformal. Metric: realised false-block rate versus budget, coverage violations.

**E7. Robustness and independence (C4).** AgentDojo executed attacker calls plus a value-planting stress test (inject a plausible wrong value into a tool result; check whether context-grounding is fooled, and whether source-trust labels from typed matching fix it); judge flip rate under injected instructions; prompt-paraphrase variance (frozen variants 1 to 4); phi coefficient between checker and judge errors. Metric: detection drop per system and attack family.

**E8. MCP reference implementation and live demo (C5).** The gate as a drop-in proxy in front of a real MCP server pair (for example a filesystem or SQLite MCP server where `list`/`read` probes are real) plus latency and overhead measurements; optional MCP-Atlas tasks.

**E9. Cost and speed.** Done on dev (checker 0.3 to 0.9 ms, judges about 1.1 s and 520 tokens); repeat on the final configuration for tiers S3 to S5 including probe latency, on one machine class, p50/p95.

## 7. Schedule (one person part-time; compress by dropping E6, E7 first)
| Phase | Days | Work | Gate |
|---|---|---|---|
| P0 | 2 | freeze: log new hypotheses (H-A decidability, H-B tier lift, H-C certified cascade, H-D robustness) in `PREREGISTRATION.md`; fix deck/README claims; choose framing | none |
| P1 | 6 | E0: contract tier, candidate-competition prototype, state-replay feasibility on tau-bench and BFCL multi-turn | **G-E0** (5 points) |
| P2 | 5 | E1 decidability map with adjudication protocol; user audits 100 cases | |
| P3 | 4 | E2 matched-rate analysis, more judges (keys), continuous judge score | |
| P4 | 8 | E3/E4 full tiers (if G-E0 passes) | |
| P5 | 5 | E5 certified cascade and E6 shift | **G-C3** |
| P6 | 3 | single test-half run per frozen configuration; recompute ArgGround test once | |
| P7 | 5 | E7 robustness (optional), E8 demo, E9 cost | |
| P8 | 5 | write-up, deck, speaker guide, README, handoff | |
About 6 to 7 weeks at part-time pace; the minimum path (P0, P1, P2, P3, P6, P8) is about 3 weeks and yields the measurement study.

## 8. What already exists and is reused
Checker (S1, S2), DeRef loader and per-path analysis, judge harness (Groq, NVIDIA, Gemini, Anthropic, OpenRouter, custom; agent mode), cascade and cost scripts, conformal threshold code, pre-registration and test ledger, 59+ tests, dev results for 7 judges.

## 9. Risks
| Risk | Mitigation |
|---|---|
| State tier adds little on public benchmarks (their environments are simulated, errors may not be state-decidable) | E0 gate; fallback to measurement study; report honestly |
| StateMirror-like or MCP-probe work appears before submission | re-check arXiv monthly; position as MCP-generic with judge fallback and certified budgets |
| Replay of recorded state is brittle (BFCL environments, tau-bench DB) | start with tau-bench (database lookups), 300-call sample; document unsupported tool types |
| Label noise (BFCL "wrong" differs from gold but may be acceptable) | adjudication protocol and your audit; per-path reporting |
| Exchangeability breaks across datasets | E6; cluster-aware bootstrap; report violations |
| Free-tier limits and API costs | seeded subsamples, caches, agent-mode judges; billed APIs only with your approval |
| Overclaiming | claim ladder above; every result keeps its dev/test status |

## 10. Decisions needed from you
1. Approve the thesis and the E0 gate (or choose the measurement-study-only path).
2. Deadline and weekly hours (selects the 3-week or 6 to 7-week path).
3. Permission to download the benchmark data in section 5 (sizes: BFCL trajectory slices by range request (about 1 GB transferred, 24 MB kept); tau-bench repo; ToolSandbox if its licence allows) and to run isolated baselines.
4. The 100-case label audit (45 to 60 minutes).
5. Keys (NVIDIA, other judges), kept in the private key file, never in chat.

## 11. Sources checked in this planning pass
arXiv listing queries (export API, 2026-10-30) and abstracts for 2610.32648, 2609.19425, 2605.09730, 2610.17125, 2603.10060, 2604.07223, 2608.10430, 2610.11030, 2609.26911, 2610.40444, 2610.35981, 2607.02577, 2610.21063; web searches for MCP read-only probes and deterministic-versus-judge MCP benchmarks returned practitioner material and the validity audit above, and did not surface StateMirror (found via the arXiv API only). Abstracts were read, full papers were not; treat the "where it stops" column as provisional.
