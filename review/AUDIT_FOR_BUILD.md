# AUDIT FOR BUILD: Baseline Repository Audit (Prompt 0)
**Date:** 2026-11-07  
**Scope:** Read-only audit of `mcp-hallucination-checker` workspace before applying build prompts.

---

## 1. Git State and Repository Status

Commands executed:
```powershell
git status
git branch --show-current
git log --oneline -10
```

Raw Output:
```text
fatal: not a git repository (or any of the parent directories): .git
fatal: not a git repository (or any of the parent directories): .git
fatal: not a git repository (or any of the parent directories): .git
```

**Observation:**
The current workspace directory (`c:\Users\rishw\OneDrive\Desktop\herculus` and subfolder `mcp-hallucination-checker`) is **not a git repository**. No `.git` metadata directory was transferred or unpacked with these files. In historical project files, the repository lived at `U:\txt\mcp-hallucination-checker` with its `.git` root at `U:\txt`. 

---

## 2. Directory Tree & Path Verification

### Real Directory Tree (Depth 3, excluding caches)
```text
[mcp-hallucination-checker/]
  .gitignore
  Makefile
  README.md
  STATUS.md
  ablation_v2.log
  ablation_v3.log
  aggrefact_sample.log
  debug_visible.log
  download_models.py
  pyproject.toml
  requirements.txt
  test_client.py
  test_nli.py
  tests_fast.log
  [.github/]
    [workflows/]
      ci.yml
  [.kiro/]
    [specs/]
      [mcp-hallucination-checker/]
  [benchmarks/]
    DATASET_CARD.md
    __init__.py
    ablation_local.py
    ablation_results.json
    ablation_results_v2.json
    ablation_results_v3.json
    agent_judge.py
    agentdojo_value_planting_dev.json
    agenthallu_confirmatory.json
    aggrefact_local_results.json
    aggrefact_local_sample_results.json
    aggrefact_local_windowed_sample_results.json
    aggrefact_sample.py
    aggrefact_sample_results.json
    aggregate_ai_audit.py
    analyze_agentdojo.py
    analyze_agenthallu.py
    analyze_cascade.py
    analyze_consensus.py
    analyze_ladder.py
    analyze_schema_ablation.py
    analyze_study.py
    argground_bench.json
    argground_dev_results.json
    argground_rescue_dev.json
    argground_rescue_dev.py
    argground_test_results.json
    ask_policy.py
    ask_policy_dev.json
    ask_policy_strong_dev.json
    build_agenthallu_eval.py
    cascade_fcrb_dev.json
    cascade_injected_dev.json
    compare_audit.py
    compare_consensus_judge.py
    compare_two_audits.py
    consensus_results.json
    consensus_results_200.json
    contract_complement.py
    contract_complement_dev.json
    contract_tier.py
    contract_tier_dev.json
    cost_latency_dev.json
    debug_visible_flags.py
    decidability.py
    decidability_dev.json
    deref_cfb_dev_results.json
    deref_fcrb_dev_results.json
    eval_argground.py
    eval_deref.py
    eval_grounded.py
    explore_deref_dev.py
    explore_role_contrast.py
    external_eval.log
    external_eval.py
    external_results.json
    finalize_manual_audit.py
    grounded_mcpevol_results.json
    grounded_mcpevol_v2_results.json
    grounded_mcpevol_v3_results.json
    judge_panel.json
    judge_prompts.py
    kaggle_full_run_summary.json
    keys.py
    ladder_dev.json
    llm_judge_args.py
    llm_judge_args_cache.jsonl
    llm_judge_eval.py
    load_agentdojo.py
    load_agenthallu.py
    load_bfcl_consensus.py
    load_deref.py
    load_mcpatlas.py
    make_ablation_benches.py
    make_argground_bench.py
    make_cfb_schema_bench.py
    make_mcpevol_v2.py
    mcpatlas_false_block.py
    mcpevol_runner.py
    measure_cost.py
    merge_audit_round2.py
    results.json
    role_contrast_dev.json
    run_cfb_ablation.sh
    run_cfb_ablation_rerun.sh
    run_judge_panel.py
    run_nvidia_ladder.sh
    schema_ablation_dev.json
    selfconsistency_bfcl.py
    selfconsistency_dev.json
    selfconsistency_pool.py
    selfconsistency_pooled.json
    selfconsistency_run.log
    selfconsistency_sc120.json
    selfconsistency_sc120.log
    selfconsistency_sc30.json
    selfconsistency_sc30.log
    selfconsistency_sc4k8.json
    selfconsistency_sc4k8.log
    shift_scores_dev.json
    shift_study.py
    shift_study_dev.json
    shift_study_run.log
    taubench_state_probe.py
    test_run_ledger.jsonl
    threshold_sweep.py
    [data/]
      [agentdojo/]
      [agenthallu/]
      [bfcl/]
      [deref/]
      [mcpatlas/]
      [taubench/]
    [logs_cfb_ablation/]
  [configs/]
    thresholds.yaml
  [handoff/]
    00_START_HERE.md
    01_PROJECT_STATE.md
    02_EXPERIMENTS_AND_RESULTS.md
    03_NEXT_STEPS_DETAILED.md
    04_FILE_MAP.md
    05_ENVIRONMENT_AND_COMMANDS.md
    06_CLAIMS_RISKS_HONESTY.md
    07_OPEN_DECISIONS.md
    08_PILOT_RUNBOOK.md
    09_PIPELINES_HOWTO.md
    10_NEXT_STAGE_PLAYBOOK.md
    RESUME_PROMPT.md
    [archive_pre_2026-10-31/]
  [kaggle/]
    ablation_mcpevol.ipynb
    aggrefact_windowed_eval.ipynb
    minicheck_in_pipeline.ipynb
    package_for_kaggle.py
  [review/]
    CASE1_ASSESSMENT.md
    CONSENSUS_FINDINGS.md
    DATA_DOWNLOAD_REQUEST.md
    DEV_PILOT_RESULTS.md
    EXPERIMENTS_2026-10-30.md
    INFORMATION_ABLATION_FINDINGS.md
    MASTER_PLAN.md
    MCP_Hallucination_Checker_Review_v6.pptx
    MCP_Hallucination_Checker_Review_v9.pptx
    Master_Plan.pdf
    NOVELTY.md
    NOVEL_PROJECT_PLAN.md
    PAPER_PLAN_V2.md
    PREREGISTRATION.md
    PROJECT_BRIEF.md
    README.md
    RESEARCH_PLAN.md
    Research_Plan.pdf
    SPEAKER_GUIDE.md
    Speaker_Guide.pdf
    UPDATE1_BRANCH_REVIEW.md
    [archive/]
    [audit/]
      AUDIT_INSTRUCTIONS.md
      audit_key_DO_NOT_OPEN.csv
      audit_key_v2.csv
      audit_sample_blind.csv
    [audit2/]
      AUDIT_INSTRUCTIONS.md
      ai_consensus_answers.json
      ai_consensus_answers_stats.json
      ai_consensus_final_answers.json
      ai_consensus_final_stats.json
      audit_key_DO_NOT_OPEN.csv
      audit_sample_ai_consensus.csv
      audit_sample_ai_consensus_final.csv
      audit_sample_blind.csv
      audit_sample_claude_manual.csv
      claude_manual_answers.json
      claude_manual_labels.json
      [ai_annotator_answers/]
      [ai_annotator_answers_r2/]
      [external_check/]
    [scout/]
  [server/]
    __init__.py
    config.py
    main.py
    main_guarded.py
    [models/]
      __init__.py
      schemas.py
    [pipeline/]
      __init__.py
      arg_ground.py
      constraints.py
      dep_parser.py
      entailment.py
      ged.py
      graph_builder.py
      negation.py
      srl.py
      taxonomy.py
      value_check.py
    [proxy/]
      __init__.py
      interceptor.py
    [session/]
      __init__.py
      tracker.py
    [tools/]
      __init__.py
      schema.py
      verify_arguments.py
      verify_grounded.py
      verify_logic.py
  [tests/]
    __init__.py
    test_agent_loop.py
    test_arg_ground.py
    test_constraints.py
    test_external_eval.py
    test_ged.py
    test_grounded.py
    test_integration.py
    test_judge_providers.py
    test_negation.py
    test_pipeline.py
    test_properties.py
    test_proxy.py
    test_schema_alignment.py
    test_server.py
    test_session.py
    test_taxonomy.py
```

### Path Existence Checks
| Path | Status |
|---|---|
| `server/main.py` | EXISTS |
| `server/main_guarded.py` | EXISTS |
| `server/config.py` | EXISTS |
| `server/models/schemas.py` | EXISTS |
| `server/pipeline/arg_ground.py` | EXISTS |
| `server/pipeline/constraints.py` | EXISTS |
| `server/pipeline/dep_parser.py` | EXISTS |
| `server/pipeline/entailment.py` | EXISTS |
| `server/pipeline/ged.py` | EXISTS |
| `server/pipeline/graph_builder.py` | EXISTS |
| `server/pipeline/negation.py` | EXISTS |
| `server/pipeline/srl.py` | EXISTS |
| `server/pipeline/taxonomy.py` | EXISTS |
| `server/pipeline/value_check.py` | EXISTS |
| `server/proxy/interceptor.py` | EXISTS |
| `server/session/tracker.py` | EXISTS |
| `server/tools/schema.py` | EXISTS |
| `server/tools/verify_arguments.py` | EXISTS |
| `server/tools/verify_grounded.py` | EXISTS |
| `server/tools/verify_logic.py` | EXISTS |
| `configs/thresholds.yaml` | EXISTS |
| `benchmarks/test_run_ledger.jsonl` | EXISTS |
| `requirements.txt` | EXISTS |
| `pyproject.toml` | EXISTS |
| `Makefile` | EXISTS |
| `review/` | EXISTS |
| `handoff/` | EXISTS |
| `tests/` | EXISTS |

### All Files in `tests/` (16 test files + `__init__.py`):
1. `tests/__init__.py`
2. `tests/test_agent_loop.py`
3. `tests/test_arg_ground.py`
4. `tests/test_constraints.py`
5. `tests/test_external_eval.py`
6. `tests/test_ged.py`
7. `tests/test_grounded.py`
8. `tests/test_integration.py`
9. `tests/test_judge_providers.py`
10. `tests/test_negation.py`
11. `tests/test_pipeline.py`
12. `tests/test_properties.py`
13. `tests/test_proxy.py`
14. `tests/test_schema_alignment.py`
15. `tests/test_server.py`
16. `tests/test_session.py`
17. `tests/test_taxonomy.py`

### All Scripts in `benchmarks/` (36 `.py` scripts + 4 `.sh` scripts):
- `benchmarks/ablation_local.py`
- `benchmarks/agent_judge.py`
- `benchmarks/aggrefact_sample.py`
- `benchmarks/aggregate_ai_audit.py`
- `benchmarks/analyze_agentdojo.py`
- `benchmarks/analyze_agenthallu.py`
- `benchmarks/analyze_cascade.py`
- `benchmarks/analyze_consensus.py`
- `benchmarks/analyze_ladder.py`
- `benchmarks/analyze_schema_ablation.py`
- `benchmarks/analyze_study.py`
- `benchmarks/argground_rescue_dev.py`
- `benchmarks/ask_policy.py`
- `benchmarks/build_agenthallu_eval.py`
- `benchmarks/compare_audit.py`
- `benchmarks/compare_consensus_judge.py`
- `benchmarks/compare_two_audits.py`
- `benchmarks/contract_complement.py`
- `benchmarks/contract_tier.py`
- `benchmarks/debug_visible_flags.py`
- `benchmarks/decidability.py`
- `benchmarks/eval_argground.py`
- `benchmarks/eval_deref.py`
- `benchmarks/eval_grounded.py`
- `benchmarks/explore_deref_dev.py`
- `benchmarks/explore_role_contrast.py`
- `benchmarks/external_eval.py`
- `benchmarks/finalize_manual_audit.py`
- `benchmarks/judge_prompts.py`
- `benchmarks/keys.py`
- `benchmarks/llm_judge_args.py`
- `benchmarks/llm_judge_eval.py`
- `benchmarks/load_agentdojo.py`
- `benchmarks/load_agenthallu.py`
- `benchmarks/load_bfcl_consensus.py`
- `benchmarks/load_deref.py`
- `benchmarks/load_mcpatlas.py`
- `benchmarks/make_ablation_benches.py`
- `benchmarks/make_argground_bench.py`
- `benchmarks/make_cfb_schema_bench.py`
- `benchmarks/make_mcpevol_v2.py`
- `benchmarks/mcpatlas_false_block.py`
- `benchmarks/mcpevol_runner.py`
- `benchmarks/measure_cost.py`
- `benchmarks/merge_audit_round2.py`
- `benchmarks/run_cfb_ablation.sh`
- `benchmarks/run_cfb_ablation_rerun.sh`
- `benchmarks/run_judge_panel.py`
- `benchmarks/run_nvidia_ladder.sh`
- `benchmarks/selfconsistency_bfcl.py`
- `benchmarks/selfconsistency_pool.py`
- `benchmarks/shift_study.py`
- `benchmarks/taubench_state_probe.py`
- `benchmarks/threshold_sweep.py`

---

## 3. Full Test Suite Baseline Run

Command:
```powershell
python -m pytest tests --tb=short
```

Raw Summary Output:
```text
=========================== short test summary info ===========================
FAILED tests/test_agent_loop.py::TestNumericHallucinationBlocked::test_correct_amount_allows_transfer
FAILED tests/test_agent_loop.py::TestVersionHallucinationBlocked::test_correct_version_allows_deploy
FAILED tests/test_agent_loop.py::TestNegationHallucinationBlocked::test_consistent_negation_passes
FAILED tests/test_agent_loop.py::TestSessionDriftDetection::test_drift_alert_fires_after_degrading_scores
FAILED tests/test_integration.py::test_int_consistent_paraphrase - AssertionError: Expected consistent; got score=0.6736, ged=0.3264
FAILED tests/test_integration.py::test_int_action_mismatch_detected - AssertionError: Expected inconsistent (action mismatch); got score=0.7041, ged=0.2959
FAILED tests/test_integration.py::test_int_consistent_tool_call - AssertionError: Expected consistent; got score=0.7143, ged=0.2857
============ 7 failed, 122 passed, 1 warning in 202.97s (0:03:22) =============
```

### Analysis of the 7 Baseline Failures:
1. `tests/test_agent_loop.py::TestNumericHallucinationBlocked::test_correct_amount_allows_transfer`:
   `AssertionError: Transfer should have been allowed. GED=0.2308, score=0.7692` (overridden by span entailment threshold).
2. `tests/test_agent_loop.py::TestVersionHallucinationBlocked::test_correct_version_allows_deploy`:
   `AssertionError: Correct version should pass. GED=0.7837, score=0.2163` (GED penalty on version format).
3. `tests/test_agent_loop.py::TestNegationHallucinationBlocked::test_consistent_negation_passes`:
   `AssertionError: Consistent negation should pass. GED=0.2946` (flagged span `'write'`).
4. `tests/test_agent_loop.py::TestSessionDriftDetection::test_drift_alert_fires_after_degrading_scores`:
   `AssertionError: Drift alert should fire after degrading scores. session_mean=0.6041`.
5. `tests/test_integration.py::test_int_consistent_paraphrase`:
   `AssertionError: Expected consistent; got score=0.6736, ged=0.3264` (flagged span `'20%'`).
6. `tests/test_integration.py::test_int_action_mismatch_detected`:
   `AssertionError: Expected inconsistent (action mismatch); got score=0.7041, ged=0.2959`.
7. `tests/test_integration.py::test_int_consistent_tool_call`:
   `AssertionError: Expected consistent; got score=0.7143, ged=0.2857` (flagged span `'456'`).

*Note:* All 7 failures reflect the documented weakness of the original `hybrid` GED + span NLI pipeline (as documented in `STATUS.md` and `handoff/01_PROJECT_STATE.md`), which falsely blocks consistent cases because any low entailment span overrides the verdict. All 13 unit tests in `test_arg_ground.py` and 7 tests in `test_grounded.py` passed cleanly.

---

## 4. Silent Fallbacks and Degraded Paths

Exact `file:line` locations where fallbacks occur silently:

1. **`server/pipeline/constraints.py:25-27`**:
   ```python
   try:
       return spacy.load("en_core_web_trf")
   except OSError:
       return spacy.load("en_core_web_sm")
   ```
   *Loss*: Transformer accuracy for constraint extraction is silently downgraded to the small English pipeline without any flag on responses.
2. **`server/pipeline/dep_parser.py:44-46`**:
   ```python
   try:
       return spacy.load("en_core_web_trf")
   except OSError:
       return spacy.load("en_core_web_sm")
   ```
   *Loss*: Dependency parsing silently switches from RoBERTa-based `en_core_web_trf` to rule/tagger `en_core_web_sm`.
3. **`server/pipeline/srl.py:39-41`**:
   ```python
   try:
       return spacy.load("en_core_web_trf")
   except OSError:
       return spacy.load("en_core_web_sm")
   ```
   *Loss*: Named entity recognition and argument frame construction silently drop to the small pipeline.
4. **`server/pipeline/ged.py:139-148`**:
   ```python
   try:
       from scipy.optimize import linear_sum_assignment
       row_ind, col_ind = linear_sum_assignment(cost_matrix)
       best_cost = cost_matrix[row_ind, col_ind].sum()
   except ImportError:
       # Fallback: greedy nearest-neighbour matching
   ```
   *Loss*: Hungarian optimal bipartite matching is silently replaced with a greedy approximation if `scipy` fails to import.
5. **`server/pipeline/arg_ground.py:77-78`**:
   ```python
   try:
       v = float(m.group(2).replace(",", ""))
   except ValueError:
       continue
   ```
   *Loss*: Silently ignores unparseable numeric regex matches.

---

## 5. Decision Flow, Blocking Logic & Conformal Math

### Where a Verdict Becomes a Block:
- In **`server/proxy/interceptor.py`**:
  - **Schema Step (lines 173-189)**:
    ```python
    if not schema_result.is_aligned:
        return InterceptionResult(blocked=True, block_reason=BlockReason.SCHEMA_MISMATCH, ...)
    ```
  - **Logic / Argument Step (HIGH risk only, lines 205-209 & 223-242)**:
    - In `"arguments"` mode (lines 205-209):
      ```python
      if not arg_result.is_grounded:
          return InterceptionResult(blocked=True, block_reason=BlockReason.LOGIC_INCONSISTENT, ...)
      ```
    - In `"grounded"` or `"hybrid"` mode (lines 223-242):
      ```python
      if logic_result is not None and not logic_result.is_consistent:
          return InterceptionResult(blocked=True, block_reason=BlockReason.LOGIC_INCONSISTENT, ...)
      ```

### Which Verdicts Can Block:
- Defined in `server/pipeline/arg_ground.py:4-7`:
  - `GROUNDED`: Supported $\to$ does not block.
  - `UNGROUNDED`: Checkable value unsupported by context $\to$ **the only argument verdict that can block**.
  - `UNCHECKABLE`: Booleans, nulls, empty strings $\to$ never blocks.

### Conformal Rank Index Calculation:
- In `server/pipeline/arg_ground.py:258-262`:
  ```python
  xs = sorted(gold_scores)
  k = math.floor(alpha * (len(xs) + 1))
  if k < 1:
      return 0.0
  return xs[k - 1]
  ```
  Quoted rank line:
  `k = math.floor(alpha * (len(xs) + 1))`

### Risk Levels vs. Executed Checks:
- `RiskLevel.LOW`: Read-only/reversible. Bypasses all checks; calls `tool_fn` immediately.
- `RiskLevel.MEDIUM`: Runs Step 1 (`verify_schema_alignment`) only. Blocks if schema is not aligned. Skips logic verification.
- `RiskLevel.HIGH`: Runs Step 1 (`verify_schema_alignment`) AND Step 2 (logic chain or argument grounding verification). Blocks if either fails.

---

## 6. Scripts Reading Locked Test Splits & Ledger Enforcement

Search results across `benchmarks/`:

1. **`benchmarks/eval_argground.py:95, 116`**:
   - Line 95: `ap.add_argument("--split", default="test", choices=["dev", "test", "all"])`
   - Line 116: `if a.split == "test":`
   - *Status*: Reads `argground_bench.json` test split. **Does not enforce an `--allow-test` guard and does NOT write to `test_run_ledger.jsonl`.**
2. **`benchmarks/eval_deref.py:84-95`**:
   - Line 84: `ap.add_argument("--split", choices=["dev", "test"], default="dev")`
   - Line 85: `ap.add_argument("--allow-test", action="store_true")`
   - Line 90-95: Enforces guard:
     ```python
     if a.split == "test":
         if not a.allow_test:
             sys.exit("test half requested without --allow-test (pre-registration guard)")
         with LEDGER.open("a", encoding="utf-8") as f:
             f.write(json.dumps({"timestamp": ..., "split": "test", ...}) + "\n")
     ```
   - *Status*: **Enforces `--allow-test` guard and appends to `test_run_ledger.jsonl`.**
3. **`benchmarks/llm_judge_args.py:302-336`**:
   - Line 302: `ap.add_argument("--allow-test", action="store_true")`
   - Line 303: `ap.add_argument("--split", choices=["dev", "test"], default="dev")`
   - Line 331-336: Enforces guard:
     ```python
     if a.split == "test" and not a.dry_run:
         if not a.allow_test:
             sys.exit("test half requested without --allow-test (pre-registration guard)")
         with (ROOT / "benchmarks" / "test_run_ledger.jsonl").open("a", encoding="utf-8") as f:
             ...
     ```
   - *Status*: **Enforces guard and appends to `test_run_ledger.jsonl`.**
4. **`benchmarks/analyze_study.py:101-127, 202-207`**:
   - Line 105: Guard function `guard_test(what, allow_test, note)`.
   - Line 108: Exits if `--allow-test` is omitted; writes to `test_run_ledger.jsonl`.
   - *Status*: **Enforces guard and appends to `test_run_ledger.jsonl`.**
5. **`benchmarks/external_eval.py:362`**:
   - Line 362: `parser.add_argument("--split", default="test", choices=("dev", "test"))`
   - *Status*: Directly loads `test-00000-of-00001.parquet`. **Does not enforce an `--allow-test` guard and does NOT log to `test_run_ledger.jsonl`.**

---

## 7. Distinct Per-Item Results Formats in `benchmarks/`

Existing result JSON formats exhibit substantial schema heterogeneity:

1. **`llm_judge_args_*.json`**:
   - Format: Top-level dictionary metadata (`provider`, `model`, `split`, `variant`, `prompt_hash`, `seed`, `judge`, `metrics`), with `rows`:
     `['id', 'query_id', 'label', 'parsed', 'supported', 'unsupported_arguments', 'latency_s', 'prompt_tokens', 'completion_tokens']`.
2. **`argground_dev_results.json` & `argground_test_results.json`**:
   - Format: Aggregate summary dictionary only:
     `['split', 'n', 'methods', 'conformal']`. No per-item rows stored.
3. **`argground_rescue_dev.json`**:
   - Format: Top-level array of item dictionaries:
     `['id', 'gold', 'argument', 'value', 'changed', 'ent']`.
4. **`role_contrast_dev.json`**:
   - Format: Top-level array of item dictionaries:
     `['wrong', 'own', 'contrast', 'has_other', 'name', 'value']`.
5. **`ablation_results*.json`**:
   - Format: Dictionary with aggregate metrics plus a `predictions` dictionary mapping case IDs to predicted labels.
6. **`selfconsistency_dev.json` & `selfconsistency_sc*.json`**:
   - Format: Dictionary with experiment metadata (`prompt`, `model`, `k`, `auroc`), with `rows` having `call_score`, `wrong`, and sample details.
7. **`shift_study_dev.json`**:
   - Format: Nested dictionary of matrices (`A_transfer`, `B_recalibration_and_guarantee_vs_n`).

**Inconsistencies:**
- Missing standardized `cluster_id` across datasets.
- Disagreement on naming: `id` vs. `item_id` vs. `query_id`.
- Ground truth represented as `label` (0/1) in some files, `wrong` (bool) in others, and `gold` in others.
- Decision strings vary between boolean `supported`, `is_consistent`, and discrete string tokens.

---

## 8. Dependency Audit

### `requirements.txt` vs. `pyproject.toml`
| Dependency | in `requirements.txt` | in `pyproject.toml` | Notes |
|---|---|---|---|
| `fastmcp` | `fastmcp>=2.0.0` | `fastmcp>=2.0.0` | Matches |
| `spacy` | `spacy>=3.7.0` | `spacy>=3.7.0` | Matches |
| `transformers` | `transformers>=4.40.0` | `transformers>=4.40.0` | Matches |
| `torch` | `torch>=2.2.0` | `torch>=2.2.0` | Matches |
| `networkx` | `networkx>=3.2` | `networkx>=3.2` | Matches |
| `pydantic` | `pydantic>=2.0.0` | `pydantic>=2.0.0` | Matches |
| `pyyaml` | `pyyaml>=6.0` | `pyyaml>=6.0` | Matches |
| `scipy` | `scipy>=1.11.0` | `scipy>=1.11.0` | Matches |
| `numpy` | `numpy>=1.24.0` | `numpy>=1.24.0` | Matches |
| `datasets` | `datasets>=2.18.0` | in `[project.optional-dependencies] benchmark` | Matches |
| `pytest` | `pytest>=8.0` | in `[project.optional-dependencies] dev` | Matches |
| `pytest-asyncio` | `pytest-asyncio>=0.23` | in `[project.optional-dependencies] dev` | Matches |
| `hypothesis` | `hypothesis>=6.0` | `hypothesis>=6.100.0` (in dev) | Pinned differently (6.0 vs 6.100.0) |
| `httpx` | **MISSING** | `httpx>=0.27` (in dev) | Present in `pyproject.toml` dev, missing from `requirements.txt` |
| `ruff` | **MISSING** | `ruff>=0.4.0` (in dev) | Present in `pyproject.toml` dev, missing from `requirements.txt` |
| `pandas` | **MISSING** | **MISSING** | Required for reading parquet benchmarks |
| `pyarrow` | **MISSING** | **MISSING** | Required for parquet backend |

---

## 9. Secret Scan & Gitignore Coverage

### Secret Scan Results:
- Searched all `.py`, `.json`, `.md`, `.yaml`, `.csv` files for secret patterns (`sk-`, `gsk_`, `nvapi-`, `AIza`, `Bearer `).
- Findings:
  - `benchmarks/llm_judge_args.py:62`: `"Authorization": f"Bearer {key}"` (Code parameterization, no literal key).
  - Documentation/markdown files contain English words matching `sk-` (`ask-policy`, `risk-`, `task-`, `desk-`).
  - **Zero hardcoded secret keys** were found in tracked source files.

### Key Loader Location:
- Implemented in `benchmarks/keys.py`:
  - Checks environment variables first (`GROQ_API_KEY`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).
  - Secondary fallback reads:
    `C:\Users\GOVARDHAN SATYA\.mcp_checker_keys.env` or root `.env`.

### `.gitignore` Coverage Check:
- `.env`: **Covered** (`.env*` in `.gitignore`).
- `audit_key_DO_NOT_OPEN.csv`: **NOT COVERED** by `.gitignore`.
- Key files (`.mcp_checker_keys.env`): Outside repository root; root `.env` is covered.

---

## 10. Dossier Claims vs. Actual Baseline Findings

1. **Git State Claim**:
   - *Dossier*: "Work is on branch `stage2-evidence-bounded-verification` (pushed to origin; three commits c019c62, 058fd19, 77a789c)".
   - *Finding*: Workspace is **not a git repository** (no `.git` directory exists in the folder).
2. **Audit Key Gitignore Claim**:
   - *Dossier*: `audit_key_DO_NOT_OPEN.csv` is gitignored.
   - *Finding*: `.gitignore` does not contain `audit_key_DO_NOT_OPEN.csv` or `audit_key*`.
3. **Test Suite Claim**:
   - *Dossier*: Mentions "56 passed on fast tests" and "13 test files".
   - *Finding*: There are 16 test files collecting 129 items; 122 passed and 7 failed (all in `test_agent_loop.py` and `test_integration.py` due to known GED/entailment over-vetoing).
4. **Dependencies Claim**:
   - *Dossier*: Parquet datasets (`dev-00000-of-00001.parquet`, `test-00000-of-00001.parquet`) and `external_eval.py` are part of the benchmark suite.
   - *Finding*: Neither `pandas` nor `pyarrow` is declared in `requirements.txt` or `pyproject.toml`.
