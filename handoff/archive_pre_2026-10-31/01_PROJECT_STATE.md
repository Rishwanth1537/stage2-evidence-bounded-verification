# 01 Project state

## What the system is
An MCP server (`server/main.py`, FastMCP) exposing tools an agent can call before acting, plus a proxy that can enforce them. Research prototype; not production-validated.

### Tools (MCP)
| Tool | Module | What it does |
|---|---|---|
| `verify_logic_chain` | `server/tools/verify_logic.py` (mode `hybrid`, default) | NER + dependency "SRL-style" frames, semantic graph, value-aware GED, span-level NLI, taxonomy, constraints, session drift |
| `verify_logic_chain` with `mode="grounded"` | `server/tools/verify_grounded.py` | consistent iff whole-claim windowed NLI >= 0.40 AND every number-like token in the plan occurs in the source AND user-query constraints are preserved |
| `verify_schema_alignment` | `server/tools/schema.py` | deterministic JSON-Schema subset validation (required, type, enum, pattern, range, length) |
| `verify_argument_grounding` (new) | `server/tools/verify_arguments.py`, `server/pipeline/arg_ground.py` | per-argument, type-aware matching of each value against the conversation; call score = weakest argument; block iff score < tau |

### Proxy (`server/proxy/interceptor.py`)
`InterceptingToolProxy(tool_fn, tool_schema, risk_level, logic_mode, arg_tau, ...)`. Risk tiers LOW (no checks), MEDIUM (schema), HIGH (schema, then logic). `logic_mode` is `"hybrid"` (default), `"grounded"` or `"arguments"`. The HIGH-tier logic check only runs when source context is supplied (and, for hybrid/grounded, reasoning context too); otherwise only the schema check applies (**fails open**). The `@guarded` decorator does not enforce anything unless calls go through `proxy.call()`.

## The three verification ideas, and where each stands
| Idea | Status | Evidence |
|---|---|---|
| Hybrid (GED + span NLI) | kept as default for backward compatibility; **performs poorly** | 52.8% accuracy on 214 held-out generated cases; GED alone AUROC about 0.52 |
| Grounded text mode (raw NLI + value check) | implemented, preliminary | 95.3% on held-out generated cases (94.4% for raw NLI alone; difference not significant) |
| Argument-level grounding | implemented, **the current main contribution candidate** | on ArgGround-Bench held-out half: 7.3% false blocks vs 14.0% exact match at about 96.5% detection |

## Verified numbers (all taken from result files in `benchmarks/`; see file 02 for protocols)
| Result | Value | Source file |
|---|---|---|
| Internal MCPEvol-Bench, shipped pipeline (60 hand-written cases) | 75.0% accuracy (schema 100%, format 100%, content 60%, negation 60%, role swap 40%) | `benchmarks/results.json` |
| Ablation, 35 text cases: NLI templated / NLI raw / GED / hybrid / hybrid+asym GED | 80.0% / 88.6% / 54.3% / 57.1% / 62.9% | `ablation_results.json` |
| Held-out generated set v3 (214 cases): hybrid / NLI templated / NLI raw / grounded | 52.8% / 76.6% / 94.4% / 95.3% | `ablation_results_v3.json`, `grounded_mcpevol_v3_results.json` |
| LLM-AggreFact full test split (29,320 claims), NLI only: truncation vs windowed AUROC | 0.672 vs 0.745 (paired difference +0.0725, 95% CI 0.068 to 0.077) | `kaggle_full_run_summary.json` |
| MiniCheck vs windowed DeBERTa vs truncation (5,000-claim subset) AUROC | 0.821 / 0.744 / 0.674 | `kaggle_full_run_summary.json` |
| ArgGround-Bench held-out half (1,751 calls): exact match FBR / detection | 14.0% / 96.4% | `argground_test_results.json` |
| Same, type-aware matching | 7.3% [5.6, 9.0] / 96.5% | same |
| Conformal gate, budget 5% / 10% / 2% | FBR 3.7% (det 87.5%) / 7.3% (det 97.8%) / infeasible | same |
| Argument-level, ignoring optional arguments (lower tier) | FBR 5.7%, detection 84.6% | same |
| DeBERTa NLI as second stage on remaining false blocks (dev) | AUROC 0.69; does not help | `argground_rescue_dev.json` |

"FBR" = false-block rate (genuine calls wrongly blocked). "Detection" = share of injected errors blocked.

## What is NOT done
- **No LLM judge (Groq, NVIDIA, Kaggle open model, or any other) has been run on anything.** This is the professor's question and the main gap.
- No natural (model-made) argument errors; all injected errors are synthetic single-argument substitutions.
- No evaluation on real agent traces; all conversations are LLM-generated public data (Glaive v2) or hand-written.
- Cross-dataset checks (Hermes, ToolACE, BFCL) not built; the conformal guarantee is untested under shift.
- Each normaliser in `arg_ground.py` has not been ablated separately.
- MiniCheck-in-pipeline and the MCPEvol Kaggle ablation notebook were written but never run on Kaggle.
- The LLM-judge script for text-level cases (`benchmarks/llm_judge_eval.py`, Anthropic API) is superseded by `llm_judge_args.py` and was never run.

## Deliverables already produced for the user's project review
- Deck: `review/MCP_Hallucination_Checker_Review_v9.pptx` (27 slides, required format: background, problem, literature, gap, objectives, dataset, methodology by module, preliminary results, references). Earlier decks v1 to v8 are obsolete.
- Speaker guide (slide-by-slide script, defence questions, abbreviations): `review/SPEAKER_GUIDE.md` and `review/Speaker_Guide.pdf` (matches deck v9).
- Research plan and pre-registration: `review/RESEARCH_PLAN.md`, `review/Research_Plan.pdf`, `review/PREREGISTRATION.md`.
- Novelty/literature check: `review/NOVELTY.md` (a subagent used `curl` against arXiv/GitHub because the web-search tools errored; partial coverage; claims there were spot-verified for SAAG, the Hallucinated-Tools Benchmark and AgentHallu).
