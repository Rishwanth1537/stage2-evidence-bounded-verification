> **Updated 2026-11-01.** This file keeps the older chronological record (October 2026 and before). For everything since 2026-10-16 use `review/EXPERIMENTS_2026-10-30.md` (17 experiments with data, results and caveats), `review/PROJECT_BRIEF.md` section 4 (the numbers to quote) and `review/PAPER_PLAN_V2.md` sections 8-14. Pre-registered protocol and deviations: `review/PREREGISTRATION.md`.

# 02 Experiments and results (chronological, with protocol and caveats)

Conventions: "positive class" is stated per experiment; FBR = false-block rate; detection = share of erroneous items blocked; AUROC = ranking quality (0.5 chance). All numbers are copied from result files. "Run twice" is flagged where it happened.

---

## E1. Internal benchmark MCPEvol-Bench (60 hand-written cases)
- Data: `benchmarks/mcpevol.json` (29 consistent, 31 hallucinated; content 25, format 13, schema 12, negation 5, role swap 5). Written by the user's project, not independent.
- Run: `make bench` (`benchmarks/mcpevol_runner.py`), fixed thresholds GED 0.35, entailment 0.40.
- Result (`benchmarks/results.json`): accuracy 75.0%, precision 0.82, recall 0.62, F1 0.71 with *consistent* as the positive class. Schema and format 100% (deterministic validator on constructed violations); content 60% (recall 0.25), negation 60%, role swap 40%.
- Note: older README/STATUS text said 83.3%; that figure could not be tied to a saved file and was replaced.

## E2. LLM-AggreFact (text-level NLI component only, no GED)
Data: `lytang/LLM-AggreFact`, gated, CC-BY-ND-4.0. Local parquet shards `dev-00000-of-00001.parquet` (30,420 claims) and `test-00000-of-00001.parquet` (29,320 claims) in the repo root (git-ignored; 51 MB). 77.9% of test claims are labelled supported, so raw accuracy is misleading; use AUROC and balanced accuracy.
1. **Original CPU run** (about 8 hours, truncation at 512 tokens, repo date template, fixed threshold 0.40): accuracy 42.3%, balanced accuracy 0.585, precision 0.893, recall 0.294; AUROC recomputed from saved scores 0.675 (`benchmarks/aggrefact_local_results.json`, git-ignored).
2. **Windowed scoring on Kaggle T4** (`kaggle/aggrefact_windowed_eval.ipynb`; 180-word windows, 40 overlap, max over windows; raw claims; dev-calibrated thresholds): windowed AUROC 0.745 (95% CI 0.738 to 0.751), balanced accuracy 0.673 at threshold 0.005; truncation re-run with the same raw claims AUROC 0.672, balanced accuracy 0.616; paired bootstrap windowed minus truncation: AUROC +0.0725 (95% CI 0.068 to 0.077). Threshold selected on dev is extreme (0.002 / 0.005) which means the model's probabilities are very peaked; AUROC is the robust figure.
3. **Date-template check** (2,000-claim sample): raw claims AUROC 0.753 vs repo-templated 0.749, so the substring-date template quirk matters little.
4. **500-claim laptop sample**, seed 42 (`benchmarks/aggrefact_sample.py`, about 35 min CPU): truncation AUROC 0.647, windowed 0.740. Error analysis on this sample: windowing helps mainly for documents over 180 words (AUROC 0.57 to 0.70 for 401 to 800 words; 0.54 to 0.69 above 800); AUROC falls with claim length (0.82 for claims of 10 words or fewer, 0.45 above 35 words, only 23 claims); 44% of supported claims score below 0.01.
5. **Per-source AUROC (full test):** Reveal 0.92, Lfqa 0.82, FactCheck-GPT 0.80 strongest; ExpertQA 0.59, AggreFact-CNN 0.62, RAGTruth 0.66 weakest; RAGTruth is 56% of the test split.
6. **MiniCheck flan-t5-large baseline** on a seeded stratified subset (3,000 dev for thresholds, 5,000 test; the first full-split attempt at batch 16 ran out of GPU memory after about 7,500 dev rows): AUROC 0.821 [0.807, 0.836]; windowed DeBERTa 0.744 [0.727, 0.760]; truncation 0.674. Paired AUROC difference windowed minus MiniCheck -0.078 (95% CI -0.095 to -0.059). Cost on a T4: about 0.395 s per claim for MiniCheck vs 0.028 s for DeBERTa (about 14 times slower).
- All of E2 is **NLI-only**; GED was not involved. It says nothing about tool calls.

## E3. Component ablation on text-based tool-call cases
Script: `benchmarks/ablation_local.py` (fixed thresholds; nothing tuned). Variants: `nli_only` (whole claim through the repo's span template), `nli_raw` (whole claim, no template, windowed), `ged_only`, `hybrid` (shipped `run_verification`), `hybrid_asym` (experimental asymmetric GED), `nli_raw_asym_veto`.
| Set | n (consistent) | hybrid | nli templated | nli raw | ged only |
|---|---|---|---|---|---|
| Dev: original MCPEvol text cases | 35 (16) | 57.1% | 80.0% | 88.6% | 54.3% |
| Design: `mcpevol_v2.json` (generated, seed 7) | 210 (105) | 53.3% | 76.2% | 91.9% | 51.9% |
| Held-out: `mcpevol_v3.json` (generated, seed 11) | 214 (107) | 52.8% | 76.6% | 94.4% | 56.1% |
- Exact McNemar: NLI-only beats the hybrid (p about 0.008 on dev; p < 0.001 on v2/v3). GED alone has AUROC 0.523 (symmetric) and 0.533 (asymmetric) on v2 vs 0.955 for raw NLI. The symmetric distance penalises a premise with an extra sentence (consistent-case mean 0.215 to 0.343); the asymmetric version removes that artifact but still does not separate classes.
- Generated sets: `benchmarks/make_mcpevol_v2.py` (template-based; labels hold by construction; half the premises get an unrelated extra sentence). **Synthetic; v3 shares v2's templates** (new random draws only).

## E4. Grounded text mode
Script: `benchmarks/eval_grounded.py`; code `server/tools/verify_grounded.py`, `server/pipeline/value_check.py`. Decision: raw NLI >= 0.40 and no number-like token missing from the premise.
| Set | nli raw | value check only | grounded |
|---|---|---|---|
| Dev (35) | 88.6% | 77.1% | 88.6% |
| Design v2 (210) | 91.9% | 65.7% | 94.3% |
| Held-out v3 (214) | 94.4% | 66.8% | 95.3% |
- On v3 the value check fixes 2 cases and breaks 0 (exact McNemar p = 0.5; not significant). **The value check was motivated by errors seen on v2**, so v2 is a design set and optimistic; v3 was generated afterwards with a different seed and not inspected before the design.
- Remaining errors: future-tense action plans ("The agent will download X as requested") judged not entailed by request-style premises; environment swaps.

## E5. ArgGround-Bench: argument-level grounding (current main result)
- Builder: `benchmarks/make_argground_bench.py --pages 40 --seed 5` pulls 40 random 100-row pages of `glaiveai/glaive-function-calling-v2` (Apache-2.0) through the HF datasets-server API. Each function call becomes a case: genuine (gold call) or the same call with exactly **one** argument value replaced by a value absent from the context (kinds: string swap, number scale, number shift, bool flip). Output `benchmarks/argground_bench.json` (git-ignored; regenerate). **The data are LLM-generated conversations, not real logs.** The last build gave 3,504 cases (1,828 genuine). Because pages can fail to fetch, the case count can differ slightly between builds (an earlier build had 3,557).
- 93.5% of genuine argument values occur verbatim in the context; the rest are legitimate but unstated (model-chosen defaults, ticker symbols for company names, derived dates).
- Split: by conversation premise, seed 11 (`split_cases` in `benchmarks/eval_argground.py`), dev/test halves.
- Methods (`python benchmarks/eval_argground.py --split test`): exact string match (our reimplementation of the idea); type-aware matching (`server/pipeline/arg_ground.py`: numbers incl. spelled-out/percent/k-m, ISO date-times vs written dates and clock times, ISO-4217 currency codes vs names, normalised/stemmed/fuzzy strings; FUZZY = 0.88); the same ignoring optional arguments (needs tool schema); conformal-calibrated tau.
- Held-out half, n = 1,751 (919 genuine, 832 injected):
| Method | FBR [95% CI] | Detection |
|---|---|---|
| exact match | 14.0% [11.9, 16.3] | 96.4% |
| type-aware | 7.3% [5.6, 9.0] | 96.5% |
| type-aware, optional args ignored (lower tier) | 5.7% | 84.6% |
| conformal alpha 5% (tau 0.615) | 3.7% | 87.5% |
| conformal alpha 10% / 15% (tau 1.0) | 7.3% | 97.8% |
| conformal alpha 2% | infeasible (never blocks): about 7% of genuine calls have values the context never states |
- Dev-half numbers (same code): exact FBR 14.4% (detection 96.0%), type-aware FBR 7.0% (detection 96.4%).
- **The test half was evaluated twice:** once with a regex bug (raw backspace characters instead of word boundaries in the clock-time pattern, inserted by a shell-quoting mistake) that a unit test exposed, once after the fix. The fix was not tuned on test numbers. The ablation of each normaliser was **not** done, so do not claim which normaliser drives the gain.
- Negative result: a DeBERTa NLI second stage on the remaining false blocks (`benchmarks/argground_rescue_dev.py`, one fixed template "The {argument} is {value}.") separated legitimate from injected ungrounded values with AUROC 0.69 on dev; it rescued about 18% of legitimate values while passing 2.5 to 4.5% of injected ones. Not used.
- Not detected: boolean flips (not checkable); values needing world knowledge (ticker symbols), arithmetic, non-English text.

## E6. Things written but never run
| Item | File | Why not run |
|---|---|---|
| LLM judge, argument level, Groq/NVIDIA | `benchmarks/llm_judge_args.py`, prompts `benchmarks/judge_prompts.py` (hash `9b59ae0a3fa5384a`) | needs provider keys; self-test passes, dry-run prints correct prompts |
| LLM judge, text level, Anthropic | `benchmarks/llm_judge_eval.py` | superseded; needs Anthropic key |
| MiniCheck inside the pipeline | `kaggle/minicheck_in_pipeline.ipynb` | needs a Kaggle GPU; runs end-to-end locally only with a stub for MiniCheck |
| MCPEvol component ablation on Kaggle | `kaggle/ablation_mcpevol.ipynb` + `kaggle/package_for_kaggle.py` | ran locally on CPU by a subagent; not on Kaggle |

## 2026-10-30 additions
See `review/EXPERIMENTS_2026-10-30.md` for the table of nine experiments, their data, results and caveats (judges, cost, cascade, tau-bench state probe, role-contrast, contract tier, information ablation, cross-model consensus and its judge control). All are development-half, exploratory results.

