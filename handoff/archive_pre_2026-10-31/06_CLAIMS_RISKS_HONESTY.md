# 06 Claims, risks and honesty rules

## What may be claimed today (safe wording)
> A research prototype that checks planned MCP tool calls before execution. It combines deterministic JSON-Schema validation with argument-level grounding (type-aware matching of each argument value against the conversation, with a conformal threshold that controls the false-block rate) and an NLI-based text check. On public LLM-generated function-calling conversations with injected single-argument errors, type-aware matching blocked 7.3% of genuine calls against 14.0% for exact string matching, at about 96.5% detection. Windowed NLI scoring improved grounding detection on LLM-AggreFact (AUROC 0.672 to 0.745). Comparison with LLM judges is the next step and has not been done.

## What must NOT be claimed
| Claim | Why not |
|---|---|
| "first", "novel method", "state of the art" | the literature check found each ingredient already exists; only a combination at the tool-call boundary is possibly new, from a limited search |
| "beats LLMs" / "no need for LLM verification" | no LLM judge has ever been run on any case |
| "detects hallucinated tool calls in real agents" | all errors are injected substitutions or hand-written/generated cases; no real agent traces |
| "guarantees a false-block rate" without qualification | the guarantee is split-conformal: it needs exchangeability between calibration and deployment calls, and was verified on one held-out split of one LLM-generated dataset |
| "100% on schema/format" as a result about hallucination | those cases are constructed violations caught by a validator by design |
| "hybrid works" | the shipped hybrid performs near chance on held-out generated cases (52.8%) and below NLI alone |
| "real conversations" | Glaive v2 is LLM-generated |
| which normaliser drives the gain | not ablated |
| MiniCheck comparison on tool calls | the MiniCheck result is on LLM-AggreFact (text-level), not on tool calls |

## Known weaknesses and bugs (current)
1. **Hybrid mode is weak** (GED AUROC about 0.52). It is still the default for backward compatibility; consider switching the default after the judge study.
2. **`proxy` fails open** when source context is missing; `@guarded` enforces nothing unless calls go through `proxy.call()`.
3. **Threshold inconsistency:** `configs/thresholds.yaml` sets entailment 0.40 while the `config.py` default is 0.50.
4. **spaCy model fallback** (trf to sm) is silent and unrecorded in outputs.
5. **Test-half reuse:** the ArgGround-Bench test half was evaluated twice (regex bug fix in between); the pre-registration records this. The value check in grounded mode was designed after seeing errors on the v2 set; v3 is the clean test but shares templates.
6. **Label noise:** genuine-call labels are assumed (gold calls), not human-checked; some gold arguments are legitimately unstated defaults. The automatic natural-error labelling plan has a defined audit.
7. **Synthetic injection:** substitutions are drawn from other examples' values for the same argument; real model errors differ (omissions, hallucinated optional arguments, wrong formats).
8. **Exact-match baseline is our own reimplementation** of a published idea (SAAG-style), not the original code.
9. **Booleans are unchecked**; no world knowledge (tickers), no arithmetic, English only.
10. The Kaggle `aggrefact_windowed_results.json` (per-claim scores) was never downloaded.
11. Subagent outputs (literature report, notebooks) were checked only partly: SAAG, the Hallucinated-Tools Benchmark and AgentHallu were spot-verified from their arXiv pages; other citations in `NOVELTY.md` and the deck's reference slides were fetched by a subagent and have not been re-read by the main session. Re-verify before submitting.

## Risks to the study (see `review/RESEARCH_PLAN.md` section 11 for mitigations)
LLM judges may win everywhere (then reframe as an evaluation study; decision table in the plan); natural errors may differ from injected ones; judge prompts must stay frozen; free-tier rate limits may force subsampling; hosted-model behaviour can change between runs (record model id and date for every run); labelling effort is uncertain; the conformal guarantee may not transfer across datasets.

## Honesty rules for slides and writing
- Every number in a slide should be read from a result file by script (`python-pptx` helpers did this) or typed with its source in the notes.
- State caveats on the slide that shows the number (dataset type, synthetic errors, run twice, subset).
- Prefer AUROC/balanced accuracy over raw accuracy when classes are imbalanced (AggreFact is 78% supported).
- Report negative results (hybrid weak, NLI second stage did not help) as findings, not footnotes.
- Do not describe weaknesses as "pessimistic"; the user's review wants confident but truthful framing: achievements first, "scope and future work" for limits.
