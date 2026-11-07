# 04 File map

Repository root: `U:\txt\mcp-hallucination-checker` (git root is the parent `U:\txt`). Branch with the pushed work: `review-eval-updates` (commit `5707a45`). `main` is untouched. "C" = committed in `5707a45`; "U" = present but uncommitted; "G" = git-ignored (regenerate).

## Source code (`server/`)
| File | Purpose | State |
|---|---|---|
| `main.py` | FastMCP server; tools `verify_logic_chain` (modes hybrid/grounded), `verify_schema_alignment`, `verify_argument_grounding` | C + U changes (new mode, new tool) |
| `main_guarded.py` | example guarded server | C |
| `config.py` | loads `configs/thresholds.yaml` (GED 0.35, entailment 0.40, fast-mode limit 80 nodes) | C |
| `models/schemas.py` | Pydantic I/O; `VerifyRequest.mode`; `ArgumentGroundingRequest/Response` | C + U |
| `pipeline/srl.py`, `dep_parser.py`, `negation.py`, `graph_builder.py` | NER + dependency "SRL-style" frames, graph with negation flags | C |
| `pipeline/ged.py` | value-aware GED (Hungarian; fast mode > 80 nodes) | C (known weak, see file 01) |
| `pipeline/entailment.py` | windowed DeBERTa NLI (`score_spans`, new `score_claim` raw whole-claim) | C + U (`score_claim`) |
| `pipeline/taxonomy.py`, `constraints.py` | typed mismatch labels; query constraints | C |
| `pipeline/value_check.py` | deterministic "every number-like token must occur in the premise" | U |
| `pipeline/arg_ground.py` | **argument-level grounding**: typed matchers, `check_arguments`, `call_score`, `conformal_threshold`, policy `required_only` | U |
| `session/tracker.py` | rolling-mean drift tracker (LRU, TTL) | C |
| `tools/verify_logic.py`, `schema.py` | hybrid logic chain; JSON-Schema validator | C |
| `tools/verify_grounded.py`, `verify_arguments.py` | grounded mode; argument grounding tool | U |
| `proxy/interceptor.py` | risk-tier gate; `logic_mode` hybrid/grounded/arguments; `arg_tau` | C + U |

## Tests (`tests/`)
15 test files. Fast, model-free ones used constantly: `test_arg_ground.py` (10), `test_grounded.py` (7), `test_proxy.py` (11), `test_server.py`, `test_schema_alignment.py`, `test_session.py`, `test_constraints.py`, `test_taxonomy.py`; last full fast run: **56 passed**. `test_integration.py` needs real models.

## Benchmarks and evaluation (`benchmarks/`)
| File | Purpose | State |
|---|---|---|
| `mcpevol.json`, `mcpevol_runner.py`, `threshold_sweep.py`, `results.json` | original 60-case benchmark and runner | C |
| `external_eval.py`, `aggrefact_sample.py` | AggreFact evaluators (CPU) | C |
| `ablation_local.py` | NLI/GED/hybrid ablation; `--dataset`, `--output`, `--veto-threshold` | C + U changes |
| `make_mcpevol_v2.py`, `mcpevol_v2.json`, `mcpevol_v3.json` | seeded generated text cases (v2 seed 7 design set, v3 seed 11 held-out) | U |
| `eval_grounded.py` | evaluates grounded mode | U |
| `make_argground_bench.py` | builds ArgGround-Bench from Glaive v2 (network) | U |
| `argground_bench.json` | built benchmark (3,504 cases) | G |
| `eval_argground.py` | exact vs type-aware vs schema-policy vs conformal; dev/test split | U |
| `argground_rescue_dev.py`, `argground_rescue_dev.json` | negative-result experiment (NLI second stage) | U |
| `judge_prompts.py` | **frozen** judge prompts (hash `9b59ae0a3fa5384a`) | U |
| `llm_judge_args.py` | Groq/NVIDIA argument-level judge (cache, rate-limit handling, metrics, McNemar vs our checker, `--self-test`, `--dry-run`, `--list-models`) | U |
| `llm_judge_eval.py` | older Anthropic text-level judge script, never run | U |
| `ablation_results*.json`, `grounded_*_results.json`, `argground_*_results.json`, `aggrefact_*_results.json`, `external_results.json` | result files | mostly G (pattern `*_results.json`) |
| `kaggle_full_run_summary.json` | verified summary of the Kaggle runs (hand-transcribed from executed notebooks, then checked) | C (older) + U |
| `DATASET_CARD.md` | MCPEvol-Bench card | C |

## Kaggle (`kaggle/`)
| File | Purpose | State |
|---|---|---|
| `aggrefact_windowed_eval.ipynb` | windowed DeBERTa eval + truncation baseline + MiniCheck subset comparison; **ran on Kaggle T4** (executed copies: `notebook841f5404bb.ipynb`, `notebook841f5404bb (1).ipynb` in the user's Downloads folder) | C + U (MiniCheck subset patch) |
| `ablation_mcpevol.ipynb`, `package_for_kaggle.py` | MCPEvol component ablation; packager makes a 37 KB repo zip | C |
| `minicheck_in_pipeline.ipynb` | five variants incl. MiniCheck and cascade; never run on Kaggle | U |

## Review materials (`review/`)
| File | Purpose | State |
|---|---|---|
| `MCP_Hallucination_Checker_Review_v9.pptx` | **current deck**, 27 slides | U |
| `..._v1` to `_v8.pptx` | obsolete earlier decks; v6 is committed in `review/`, the others were moved to `review/archive/` (local only, excluded via `.git/info/exclude`) | C / local |
| `SPEAKER_GUIDE.md`, `Speaker_Guide.pdf` | slide-by-slide script, defence Q&A, abbreviations (matches v9) | C older + U |
| `RESEARCH_PLAN.md`, `Research_Plan.pdf`, `PREREGISTRATION.md` | study plan, frozen protocol | U |
| `NOVELTY.md` | literature check (partial coverage; subagent used `curl`) | C |

## Project docs
`README.md` (user-facing, results tables), `STATUS.md` (status, results, known issues), `handoff/` (this folder), `configs/thresholds.yaml`, `Makefile` (`make bench`, `make test`, ...), `.github/workflows/ci.yml`.

## Data in the repo root (git-ignored)
`dev-00000-of-00001.parquet`, `test-00000-of-00001.parquet`: LLM-AggreFact shards (CC-BY-ND-4.0; keep private). `*.log`, `ablation_v*.log`, `aggrefact_sample.log`: run logs.

## Outside the repo
- `C:\Users\GOVARDHAN SATYA\Downloads\notebook841f5404bb*.ipynb`: executed Kaggle notebooks (source of the verified Kaggle numbers). The notebook's own `aggrefact_windowed_results.json` (12.8 MB, per-claim scores) lives in the Kaggle notebook output and was **never downloaded**; it is needed for error analysis on the full set.
- `C:\Users\GOVARDHAN SATYA\.cache\huggingface\hub\`: cached models (`cross-encoder/nli-deberta-v3-base`, `dslim/bert-base-NER`, others).
- The session scratchpad (build scripts for decks v3 to v6, helper scripts) was **wiped between days and is gone**; the later decks (v7 to v9) were produced by editing the previous deck with `python-pptx`.

## Added 2026-10-20
| File | Purpose | State |
|---|---|---|
| `review/MASTER_PLAN.md`, `review/Master_Plan.pdf` | full plan after the scout, claim ladder, ranked add-ons, schedule, decisions | U |
| `review/scout/SCOUT_1..4_*.md` | four scout reports (Sonnet; `opus` alias unavailable); citations spot-checked by the main session | U |
| `benchmarks/keys.py` | key lookup: environment, then private file outside the repo | U |
| `benchmarks/load_deref.py`, `eval_deref.py`, `analyze_study.py` | DeRef loader, deterministic baselines with per-path breakdown and test ledger, H1/paths/cascade analyses | U |
| `benchmarks/explore_deref_dev.py`, `debug_visible_flags.py` | exploratory dev-half diagnostics (the second found the minus-sign bug) | U |
| `benchmarks/data/deref/` | downloaded DeRef files and built cases | G |
| `benchmarks/test_run_ledger.jsonl` | every look at a test half | U (commit it) |
| `handoff/08_PILOT_RUNBOOK.md` | what to run when the keys exist | U |

## Added 2026-10-30
| File | Purpose | State |
|---|---|---|
| `review/EXPERIMENTS_2026-10-30.md`, `DEV_PILOT_RESULTS.md`, `INFORMATION_ABLATION_FINDINGS.md`, `CONSENSUS_FINDINGS.md`, `NOVEL_PROJECT_PLAN.md` | results and plan | U |
| `review/scout/SCOUT_5_new_ideas.md`, `TASK_taubench_state_probe.md`, `TASK_bfcl_consensus_data.md` | novelty check, tau-bench probe report, BFCL data report | U |
| `benchmarks/agent_judge.py` | judge with Claude subagents (make batches, ingest answers into the response cache) | U |
| `benchmarks/run_judge_panel.py`, `judge_panel.json` | API judge panel runner (Groq, NVIDIA, Gemini, Anthropic, OpenRouter, custom) | U |
| `benchmarks/measure_cost.py`, `analyze_cascade.py` | latency/cost and cascade sweep | U |
| `benchmarks/contract_tier.py`, `contract_complement.py`, `analyze_schema_ablation.py`, `make_ablation_benches.py` | contract tier, its complement analysis, information ablation, benchmark builders | U |
| `benchmarks/load_bfcl_consensus.py`, `analyze_consensus.py`, `compare_consensus_judge.py` | BFCL consensus data (200 cases, 30 models), analysis, judge control | U |
| `benchmarks/taubench_state_probe.py`, `explore_role_contrast.py` | tau-bench lookup probe; NLI role-contrast exploration | U |
| `tests/test_judge_providers.py` | tests for the Anthropic/OpenRouter/custom providers | U |

