# Assessment of the `origin/Case1` branch (2026-10-30)

Branch `origin/Case1`, one commit `b2cf2d8` by Rishwanth (2026-10-11), "Case1: Implement research-grade improvements, benchmarks, and fallbacks". It shares **no common history** with `main` or `review-eval-updates` and moves the project from `mcp-hallucination-checker/` to the repository root, so the raw diff (105 files, +9,772 -830) is mostly a move. Nothing from it has been merged.

## What the code actually changes (five modules)
| Change | Assessment |
|---|---|
| NLI and NER loaders return `None` when weights are not in the local Hugging Face cache (`local_files_only=True`); entailment then falls back to a substring check (0.95 if the span occurs in the premise, else 0.05) | Silent degradation of a safety gate: no flag in the output, no download on first run, thresholds behave as binary. Acceptable only with an explicit `degraded` field and a warning |
| `run_verification`: any span below the entailment threshold forces `is_consistent = False` | Makes NLI the decider (our `grounded` mode already does this); raises recall and false blocks |
| Regex "Source 3" attaches numbers and times to the first predicate | Duplicates and is weaker than `server/pipeline/arg_ground.py` |
| `spacy.blank("en")` fallback | Silent degradation again |

## What it adds besides code
Template-generated datasets (`mcpevol.json` 30 cases, `dataset_v2.json` 129 cases and their generator), `baselines.py`, a `configs/thresholds.yaml`, docs (`architecture`, `evaluation`, `limitations`), a Makefile, a CI workflow, and three test files (`test_contradiction.py`, `test_hard_negatives.py`, `test_multi_error.py`, about 620 lines; **not run or reviewed by us**).

## Our measurement
The shipped hybrid pipeline (`verify_logic.run_verification`) from each tree, run with the real cached NLI and NER models on our held-out generated set (`mcpevol_v3.json`, 214 text cases, never seen by Case1):

| Pipeline | Accuracy | Detection | False-block rate | Balanced accuracy |
|---|---|---|---|---|
| Ours (original hybrid) | 52.8% | 90.7% | 85.0% | 52.8% |
| Case1 hybrid | 53.7% | 71.0% | 63.6% | 53.7% |

Paired comparison: 22 cases only ours correct, 24 only Case1 correct, exact McNemar p = 0.88. Both are near chance; the changes do not make the hybrid pipeline work. (Script used: `eval_hybrid_tree.py`, a throw-away file in the session scratchpad that calls only `run_verification` of the chosen tree; the temporary worktree was removed.)

## Their own claims
- "90% accuracy" on `mcpevol.json` was measured on a 30-case set also used to find the fixes, no held-out split; the schema score going from 0% to 100% came from adding `agent_args` and `tool_schema` fields to the dataset.
- On their 129-case set the full pipeline reaches F1 78.9% with a 43% false-positive rate, against 77.1% for entity-and-value matching alone: the graph and NLI machinery add about 1.8 points, with no interval.
- Their "embedding" baseline ran on a Jaccard fallback (`backend: jaccard_fallback` in the result file).

## Recommendation
Do not merge. If wanted, cherry-pick (with authorship preserved) the three test files and the docs after reading them, adapted to the `mcp-hallucination-checker/` folder layout, and add an explicit degraded-mode flag instead of silent fallbacks.
