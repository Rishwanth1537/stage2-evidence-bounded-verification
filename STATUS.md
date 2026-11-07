# Project Status

**Date:** 2026-10-31 (research section refreshed; implementation sections date from 2026-10-01)
**Project:** MCP Hallucination Checker
**Status:** Research prototype. Components implemented; evaluation is preliminary.

## Summary

The project provides MCP verification tools (`verify_logic_chain`, `verify_schema_alignment`, `verify_argument_grounding`), a proxy gate with risk tiers, and benchmark tooling. Evaluation so far shows that the deterministic schema validator works, that overlapping-window NLI scoring improves external grounding detection, and that the graph-edit-distance stage does not help on text cases. **The main research finding of October 2026**: on natural tool-call errors, LLM judges beat the deterministic checker, and judge detection is limited by the information the judge sees (the tool definition lifts detection by 16 to 20 points; model size changes it by 3 to 6). The project is therefore being re-scoped as a study of evidence-bounded verification of tool-call arguments and of asking the user instead of blocking, with a calibrated interruption budget (`review/PAPER_PLAN_V2.md`). Everything new is development-half and exploratory. It should not be described as a validated or production-ready system. Read `review/PROJECT_BRIEF.md` first.

## Implemented

- `verify_logic_chain`: semantic frames (NER plus dependency heuristics, not a trained SRL model), semantic graph, value-aware GED (Hungarian matching; degree-sequence approximation above 80 nodes), span-level DeBERTa-v3-base NLI with overlapping premise windows (180 words, 40 overlap, max over windows), taxonomy, optional constraint check, session drift tracking.
- `verify_schema_alignment`: deterministic JSON-Schema subset validation.
- Proxy gate (`server/proxy/interceptor.py`) with LOW / MEDIUM / HIGH tiers and a guarded FastMCP example. Logic verification at HIGH tier runs only when both reasoning and source context are supplied; otherwise the schema check applies.
- Evaluation tooling: `benchmarks/mcpevol_runner.py`, `ablation_local.py`, `aggrefact_sample.py`, `external_eval.py`; Kaggle notebooks in `kaggle/`.
- 13 test files; CI on Python 3.10 to 3.12 with a ruff lint job.

## Results (preliminary; all re-runnable)

### Internal MCPEvol-Bench (60 hand-written cases)

75.0% accuracy, precision 0.82, recall 0.62 (consistent = positive class). Schema 100% and format 100% (deterministic validator on constructed violations); content 60% (recall 0.25), negation 60%, role-swap 40%. This replaces the older 83.3% figure, which could not be tied to a saved result file.

### Component ablation (35 text-based cases, fixed thresholds)

| Variant | Accuracy |
|---|---|
| NLI only (whole claim) | 80.0% |
| GED only | 54.3% |
| Hybrid (current) | 57.1% |
| Hybrid + asymmetric GED (experimental) | 62.9% |

NLI-only beats the current hybrid (exact McNemar p = 0.008). The asymmetric variant's improvement is not significant at n = 35. Command: `PYTHONPATH=. python benchmarks/ablation_local.py`.

### Argument-level grounding (new)

`verify_argument_grounding` / `InterceptingToolProxy(logic_mode="arguments")`: per-argument, type-aware, deterministic grounding with an optional conformal threshold for a false-block budget. On ArgGround-Bench (public LLM-generated Glaive v2 conversations; one injected argument change per hallucinated case; held-out half, 1,751 calls):

| Method | False-block rate [95% CI] | Detection of injected errors | Balanced acc. |
|---|---|---|---|
| Exact string match (our implementation of the idea) | 14.0% [11.9%, 16.3%] | 96.4% | 0.912 |
| **Type-aware matching** | **7.3%** [5.6%, 9.0%] | 96.5% | 0.946 |
| + ignore ungrounded optional arguments (lower risk tier) | 5.7% | 84.6% | 0.895 |
| Calibrated, false-block budget 5% (tau = 0.62) | 3.7% | 87.5% | - |
| Calibrated, false-block budget 10% (tau = 1.00) | 7.3% | 97.8% | - |

Findings: type-aware matching halves false blocks versus exact matching at the same detection; calibrated gates stayed below their budgets on this split (a marginal guarantee under exchangeability; the realised rate for one calibration set is random, so staying below budget is partly chance and score ties); a 2% budget is infeasible at this stage. A DeBERTa NLI second stage did not help on the dev half (AUROC 0.69 separating legitimate from injected ungrounded values; it rescued ~18% of legitimate values while passing 2.5 to 4.5% of injected ones), so the remaining ~7% need a stronger model or world knowledge. Caveats: synthetic injected errors, LLM-generated conversations, own exact-match baseline, test half run twice (bug fix).

**Natural (model-made) errors: exploratory, dev half only.** On the public DeRef data (Ma et al., arXiv 2610.18497; `lm2445/DeRef`, Apache-2.0; BFCL-based `fcrb`, ComplexFuncBench-based `cfb`) the call score separates wrong from correct calls at roughly chance level: call-level AUROC 0.48 (fcrb, 630 calls) and 0.56 (cfb, 507 calls); at tau 0.88, 52% / 43% of *correct* calls would be blocked and 44% / 50% of wrong calls (`benchmarks/eval_deref.py`, `benchmarks/explore_deref_dev.py`). Reasons: many wrong values are visible in the context but are the wrong choice (a grounding check cannot see this), and many correct values have no textual source (translation, defaults, inferred), so "unsupported" does not mean "wrong" (only 44% / 62% of unsupported values are wrong, per the dataset's own path labels). The injected-error result above therefore applies only to injected absent-value substitutions. A bug was found and fixed: the number matcher ignored minus signs, so negative values such as longitudes were flagged even when verbatim in the context (19% of cfb "visible" correct arguments); after the fix 0% are flagged, cfb scoring takes 12 s instead of 9 min, and the call-level AUROC is 0.57 (cfb) and 0.48 (fcrb), so the conclusion is unchanged. The ArgGround-Bench test-half numbers above were computed before this fix (dev-half false-block rate 7.0% became 6.8%); they will be recomputed once, and logged, in the final protocol. **LLM-judge pilot (dev halves only, exploratory; full table in `review/DEV_PILOT_RESULTS.md`).** With the frozen prompt, Groq-hosted gpt-oss-120b beats the checker on natural errors (fcrb, n=200: false blocks 31.9% vs 56.4%, detection 59.4% vs 43.4%, paired p<0.001; cfb, n=100 with context truncated to 3,000 characters: detection 71.7% vs 53.3%, p=0.155) and ties it on injected absent-value errors (5.0% / 97.0% vs 6.9% / 98.0%, p=1.0). The 20B judge is similar on fcrb (37.2% / 54.7%) and on injected errors (11.9% / 100%). As a first stage in front of the judge the checker loses detection (cascade 35.8% vs 59.4%). Claude Haiku, Sonnet and Opus run in agent mode (no API; batched, not temperature 0; see `review/DEV_PILOT_RESULTS.md` addendum) are all clearly better than the checker on fcrb (false blocks 9.6 to 28.7% vs 56.4%, detection 53 to 55% vs 43.4%, p<0.0001) and tie it on injected errors (2 to 5% / 98% vs 6.9% / 98%). So the claim 'as good as an LLM judge' is not supported; the project is positioned as a cheap, deterministic, calibrated first line of defence for values absent from the context, with the comparison reported honestly. Cost and speed (dev, exploratory; `review/DEV_PILOT_RESULTS.md` addendum 2): the checker takes 0.3 to 0.9 ms per call on short contexts (18.7 ms on 9.6k-character cfb contexts), uses no tokens and sends nothing off the machine, against 1.0 to 1.3 s and about 520 tokens per hosted-judge call (a local call versus a network call). As a cascade stage in front of a judge it clears about half of the calls on injected errors (the judge then sees 11.5% of calls at a 5% error rate) with a 1 to 2 point detection loss, but on natural errors (fcrb) every tau loses 13 to 24 points of detection. Determinism, robustness, an end-to-end false-block guarantee and test-half results are not yet measured. Earlier note: the closest paper reports plain-input judge argument AUROC of 72.5 to 91.95 on fcrb and 63.4 to 78.9 on cfb.

### Redesign: grounded mode (text-based cases, fixed thresholds)

| Variant | Dev (35) | Design (210) | Held-out (214) |
|---|---|---|---|
| Shipped hybrid | 57.1% | 53.3% | 52.8% |
| NLI whole claim, date template | 80.0% | 76.2% | 76.6% |
| NLI whole claim, raw | 88.6% | 91.9% | 94.4% |
| Grounded (raw NLI + value check) | 88.6% | 94.3% | 95.3% |

`verify_logic_chain(mode="grounded")` (and `InterceptingToolProxy(logic_mode="grounded")`) uses whole-claim windowed NLI plus a deterministic value check; the default remains `hybrid`. The value check was motivated by errors on the design set; the held-out set (different seed, not inspected before design) shows +0.9 points over raw NLI (2 fixes, 0 breaks, McNemar p = 0.5, not significant). Both generated sets are template-based and synthetic. Graph distance alone is near chance (AUROC 0.52 to 0.53 vs 0.96 for raw NLI on the design set).

### External: LLM-AggreFact test split (NLI component only)

Full test split (29,320 claims; 77.9% supported), Kaggle T4. Windowed scoring vs the earlier truncation run:

- Like-for-like (same model, raw claims, dev-calibrated thresholds): truncation AUROC 0.672 and balanced accuracy 0.616 versus windowed 0.745 (95% CI 0.738 to 0.751) and 0.673. Paired bootstrap: AUROC +0.0725 (95% CI 0.068 to 0.077), balanced accuracy +0.057 (95% CI 0.051 to 0.063).
- The earlier CPU run (templated claims, fixed 0.40) had AUROC 0.675 and balanced accuracy 0.585. At the fixed 0.40 threshold windowed scoring gives 0.636.
- Dev-chosen thresholds are extreme (0.002 truncation, 0.005 windowed), indicating strongly peaked scores; AUROC is the more robust figure.
- Per source, AUROC ranges from 0.92 (Reveal) to 0.59 (ExpertQA); RAGTruth (0.66) is 56% of the split.
- A seeded 500-claim CPU sample gives AUROC 0.740, consistent with the full run (`benchmarks/aggrefact_sample.py`).

These runs do not exercise GED, so they are not results for the whole pipeline. `benchmarks/kaggle_full_run_summary.json` was checked against the executed notebook outputs; the notebook's own results JSON (12.8 MB, on Kaggle) is the authoritative record.

## Experiments of 2026-10-30 (dev halves, exploratory; details in `review/EXPERIMENTS_2026-10-30.md`)
- Claude Haiku, Sonnet and Opus (agent mode) and Groq gpt-oss judges all beat the context checker on natural errors (fcrb) and tie it on injected errors; the checker answers in 0.3 to 0.9 ms with no tokens versus about 1.1 s and 520 tokens per hosted judge call.
- Information, not scale: showing the judge the tool's own definition raises detection from 50 to 54% to 66 to 72% for all three Claude models (n = 168); the deterministic contract tier alone detects 25.6% at 15.9% false blocks.
- State lookups on tau-bench catch 0 of 538 errors the environment accepted (negative). An NLI role-contrast check on visible-but-wrong values is weak (AUROC about 0.6).
- Cross-model consensus on BFCL (30 models, all 200 single-turn cases) has AUROC 0.93, but against an Opus judge that sees the tool definition on 924 calls the detection gain at matched false blocks (56.0% vs 45.9%) is not significant.
- Label quality (2026-11-01): an LLM pre-audit and revised rules show that 63% of BFCL 'wrong' arguments are weak labels (format variants, optional arguments); on strong errors Opus with the tool definition detects 65% at 8% false blocks and consensus 74% (not significant), and the contract flag is uninformative on BFCL. See `review/PAPER_PLAN_V2.md` section 12.
- Open: no test half, no human label audit, no confidence intervals for the cascade, agent-mode judges are batched and not temperature 0.

## Known issues

- GED (symmetric or asymmetric) is close to chance as a classifier on generated cases (AUROC 0.52 to 0.53); the symmetric version also penalises premise-only content (consistent cases: 0.22 to 0.34 with an extra premise sentence). The shipped hybrid is therefore weaker than whole-claim NLI; the grounded mode is the response.
- In `run_verification`, any span below the entailment threshold overrides the GED verdict.
- `entailment._make_hypothesis` uses substring date matching, so most spans get the date template. On a 2,000-claim sample this changed AUROC little (0.753 raw vs 0.749 templated).
- `configs/thresholds.yaml` sets the entailment threshold to 0.40 while the `config.py` default is 0.50.
- spaCy model fallback (trf to sm) is not recorded in result files.
- Proxy: `@guarded` enforces nothing unless calls are routed through `proxy.call()`.
- MCPEvol-Bench is small (60 cases) and self-written; thresholds were not tuned on it.

## In progress / next (2026-10-31)

See `review/PROJECT_BRIEF.md` section 7 and `handoff/03_NEXT_STEPS_DETAILED.md`. In short: finish the NVIDIA size ladder; the user's 100-item blind audit (`review/audit/`); call-level decidability and the evidence-bound check; a judge panel at temperature 0 from at least three API providers; new untouched benchmark slices (AgentHallu BFCL subset, tau2/tau3 or ToolSandbox, AgentDojo); the ask-policy with real self-consistency and the shift study; freeze and a single locked test run; theory appendix; then update the deck, speaker guide and README claims, and commit.

(The older list below is kept for the implementation side: MiniCheck inside the pipeline, grounded-mode default, pinning versions.)

### Older implementation backlog

1. MiniCheck baseline: done on a seeded subset (3,000 dev / 5,000 test, batch 4; the first full-split attempt ran out of GPU memory). On the same rows: MiniCheck AUROC 0.821 [0.807, 0.836] vs windowed DeBERTa 0.744 [0.727, 0.760] vs truncation 0.674 [0.656, 0.693]; paired AUROC difference windowed minus MiniCheck -0.078 (95% CI -0.095 to -0.059). MiniCheck costs about 0.40 s per claim vs 0.028 s on a T4 (about 14x). Next: test MiniCheck as the grounding model inside the pipeline, with DeBERTa as a fast first pass.
2. Done (preliminary): grounded mode added (whole-claim NLI + deterministic value check). Remaining: decide whether to make it the default, and rework or drop the graph stage.
3. Evaluate on an external tool-call benchmark and human-check a larger test set; the generated v2/v3 sets are template-based and synthetic. Run `benchmarks/llm_judge_eval.py` (LLM-as-judge baseline) and `kaggle/minicheck_in_pipeline.ipynb` (MiniCheck inside the pipeline); neither has been run.
4. Pin model and package versions; document hardware and runtime; add input limits and failure-mode policy.
5. Run `kaggle/ablation_mcpevol.ipynb` (with `kaggle/package_for_kaggle.py`) for the larger ablation with threshold grids.

## Next for argument grounding

1. Second stage for the ungrounded remainder: MiniCheck or an LLM judge (needs GPU / API key), evaluated on the same ArgGround-Bench split.
2. Natural (model-made) argument errors instead of injected substitutions, and a human-checked subset.
3. Ablate each normaliser; add checks for booleans from cue words.

## Reproduction

```bash
make bench                                              # internal benchmark
PYTHONPATH=. python benchmarks/ablation_local.py        # ablation, ~2 min CPU
PYTHONPATH=. python benchmarks/aggrefact_sample.py --n 500 --seed 42   # ~35 min CPU
```

The full AggreFact run is `kaggle/aggrefact_windowed_eval.ipynb` on a GPU; it needs the two LLM-AggreFact parquet shards uploaded as a private Kaggle dataset (license CC-BY-ND-4.0).

## Safe claim

> A research prototype of a pre-execution gate for MCP tool calls, together with a preliminary measurement study of what evidence decides whether a tool-call argument is wrong. Judges are limited by the information they see more than by their size, a cheap deterministic stage helps for values absent from the context, and the remaining errors call for asking the user. All new results are development-set findings.

Avoid "first", "novel method", "state of the art", or production-readiness claims.
