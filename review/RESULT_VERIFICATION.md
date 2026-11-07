# Prompt 5B: Comprehensive Result Verification Report

**Date:** 2026-11-07  
**Scope:** Read-only empirical verification of all artifacts, commits, logs, data files, and statistical models produced across Prompts 0 to 5.  
**Rules:** Prompt 0 rules strictly observed. No code changes under `server/`. No filtering or interpretive summaries away from raw data.

---

## A. Process Evidence

### 1. Git Repository State & Log Status

#### `git status`
```text
On branch stage2-evidence-bounded-verification
Your branch is up to date with 'origin/stage2-evidence-bounded-verification'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	benchmarks/verify_results.py
	review/RESULT_VERIFICATION.md

nothing added to commit but untracked files present
```

#### `git log --oneline -20`
```text
3185b16 P5: normalizer ablation harness
7186094 P4: two-tier gate with ASK decision
4d50c3e P3: results schema and statistics
4949068 P2: fail-closed degraded flags, key loader, split guard
2139009 P1: repo hygiene, xfail legacy tests, key requirements
2cc8af8 P1: baseline import
```

#### `git branch -vv`
```text
* stage2-evidence-bounded-verification 3185b16 [origin/stage2-evidence-bounded-verification] P5: normalizer ablation harness
```

#### `git log origin/stage2-evidence-bounded-verification --oneline -20`
```text
3185b16 P5: normalizer ablation harness
7186094 P4: two-tier gate with ASK decision
4d50c3e P3: results schema and statistics
4949068 P2: fail-closed degraded flags, key loader, split guard
2139009 P1: repo hygiene, xfail legacy tests, key requirements
2cc8af8 P1: baseline import
```

#### Commit Audit per Prompt:

| Stage / Prompt | Commit Hash | Present on Origin? | Uncommitted/Unpushed Work? |
|---|---|---|---|
| Prompt 2: Fail-closed flags & Split guard | `4949068` | **YES** | None |
| Prompt 3: Results schema & Statistics | `4d50c3e` | **YES** | None |
| Prompt 4: Two-Tier Gate (ASK / BLOCK) | `7186094` | **YES** | None |
| Prompt 5: Normalizer Ablation Harness | `3185b16` | **YES** | None |

All work for Prompts 2, 3, 4, and 5 is committed and pushed to origin.

### 2. Full Test Suite Execution

Command: `pytest -v`  

Raw summary:  
```text
FAILED tests/test_agent_loop.py::TestSessionDriftDetection::test_drift_alert_fires_after_degrading_scores
FAILED tests/test_integration.py::test_int_action_mismatch_detected - AssertionError: Expected inconsistent (action mismatch); got score=0.7041, ged=0.2959
======= 2 failed, 182 passed, 5 xfailed, 1 warning in 226.93s (0:03:46) =======
```

- **Passed:** 182 (grew from 124 at baseline by +58 new tests across Prompts 2–5)
- **XFailed:** 5 (pre-existing legacy tests xfailed in Prompt 1: `test_correct_amount_allows_transfer`, `test_correct_version_allows_deploy`, `test_consistent_negation_passes`, `test_int_consistent_paraphrase`, and `test_all_preserved`)
- **Failed:** 2 (pre-existing legacy failures from baseline before Prompt 2: `test_drift_alert_fires_after_degrading_scores`, `test_int_action_mismatch_detected`)
- **Errors:** 0

### 3. Verbatim Content of `review/TEST_SPLIT_USAGE.md`

```markdown
# Test-Split Usage & Ledger Reconciliation Audit

**Date:** 2026-11-07  
**Scope:** Pre-registration audit comparing `benchmarks/test_run_ledger.jsonl` against all benchmark result artifacts across `mcp-hallucination-checker`.

---

## 1. Executive Summary

A comprehensive scan of all benchmark outputs and data artifacts was conducted to verify pre-registration integrity and adherence to locked test-split rules.

### Key Finding:
**The ArgGround test partition was run prior to the introduction of split guards, and multiple public benchmark test runs exist without ledger entries.**
Because `benchmarks/eval_argground.py` historically defaulted to `--split test` with no `--allow-test` guard and no ledger logging, the 1,751 test cases of `argground_bench.json` were fully evaluated (including split-conformal calibration guarantees) without pre-registration tracking.

Consequently, **the ArgGround test half can no longer be claimed as unseen or untouched.** Future papers and benchmark reports must explicitly acknowledge this prior exposure.

---

## 2. Ledger Reconciliation Table

| Result Artifact | Apparent Split | Sample Size ($n$) | Present in `test_run_ledger.jsonl`? | Status / Verdict |
|---|---|---|---|---|
| `benchmarks/argground_test_results.json` | `test` | 1,751 | **NO** | **Unrecorded test run**: Evaluated prior to guard; test half is not pristine. |
| `benchmarks/aggrefact_local_results.json` | `test` | 2,864 | **NO** | **Unrecorded test run**: Local parquet evaluation on LLM-AggreFact test shard. |
| `benchmarks/aggrefact_local_sample_results.json` | `test` | 100 | **NO** | **Unrecorded test run**: Subsample of LLM-AggreFact test shard. |
| `benchmarks/aggrefact_local_windowed_sample_results.json` | `test` | 100 | **NO** | **Unrecorded test run**: Windowed subsample of LLM-AggreFact test shard. |
| `benchmarks/data/deref/cases_fcrb.json` | `dev+test mixed` | All | **YES** (Line 1) | Recorded accidental exposure (2026-10-20T22:19:46). |
| `benchmarks/data/deref/cases_fcrb.json` | `test` | N/A | **YES** (Line 2) | Recorded plumbing test with fake judge (2026-10-20T22:37:07). |
| `benchmarks/agenthallu_confirmatory.json` | `confirmatory` | 124 | **YES** (Line 3) | Pre-registered confirmatory slice (2026-10-31T15:02:53). |

---

## 3. Existing Ledger Contents (`benchmarks/test_run_ledger.jsonl`)

The repository ledger contains exactly 3 historical entries (lines preserved without modification):

1. **Entry 1 (2026-10-20T22:19:46)**:
   - Script: `analyze_study.py paths (before the split guard existed)`
   - Cases: `cases_fcrb.json`
   - Split: `dev+test mixed`
   - Note: `"ACCIDENTAL: no --split filter, so argument-level flag rates of S1/S2 on all fcrb calls (both halves) were printed; no judge, no tuning; fcrb test-half deterministic rates are no longer unseen"`
2. **Entry 2 (2026-10-20T22:37:07)**:
   - Script: `analyze_study.py h1`
   - Cases: `cases_fcrb.json`
   - Note: `"e2e plumbing test with a fake judge (not a result)"`
3. **Entry 3 (2026-10-31T15:02:53)**:
   - Script: `agenthallu confirmatory slice (Deviation 14)`
   - Cases: `cases_eval.json sha256 c0b3ef1d76baf28a`
   - Note: `"registered before running judges"`

---

## 4. Unrecorded Test Runs in Detail

### 1. `benchmarks/argground_test_results.json`
- **File Timestamp:** 2026-10-09 09:54:20
- **Contents:** Full evaluation of `exact`, `arg_ground`, and `arg_ground+schema` methods on 1,751 test items, along with split-conformal threshold evaluations ($\alpha \in \{0.02, 0.05, 0.10, 0.15\}$).
- **Cause:** `benchmarks/eval_argground.py` previously defined `parser.add_argument("--split", default="test")` and wrote directly to output without verifying `--allow-test` or checking `LOCKED_RUN=1`.
- **Implication for Claims:** The 1,751 test items were exposed to algorithm development and parameter tuning. This split must be categorized as a historical evaluation split, not an untouched holdout.

### 2. `benchmarks/aggrefact_local_*.json` (3 files)
- **Files:**
  - `aggrefact_local_results.json`
  - `aggrefact_local_sample_results.json`
  - `aggrefact_local_windowed_sample_results.json`
- **Contents:** Standalone DeBERTa entailment evaluations on LLM-AggreFact `test` parquet shards.
- **Cause:** `benchmarks/external_eval.py` previously defaulted to `--split test` with no guard.
- **Implication for Claims:** LLM-AggreFact test shard evaluations were performed unrecorded.

---

## 5. Remediation Implemented in Prompt 2

To prevent any further unrecorded test-split leakage:
1. **Centralized Split Guard (`benchmarks/splits.py`)**:
   - `load_split(dataset, split, ...)` raises `LockedSplitError` on any attempt to load a `test` split or the frozen `agenthallu_confirmatory` slice unless **both** `LOCKED_RUN=1` is present in the environment **and** a non-empty reason is supplied.
   - Every authorized test access appends a structured entry to `benchmarks/test_run_ledger.jsonl` with UTC timestamp, git commit hash, dirty flag, caller script, dataset name, file SHA-256, purpose, and reason.
2. **Default Switch to `dev`**:
   - `benchmarks/eval_argground.py`: Default changed from `test` to `dev`. CLI now requires `--allow-test` and `--note`.
   - `benchmarks/external_eval.py`: Default changed from `test` to `dev`. CLI now requires `--allow-test` and `--note`.
3. **No File Tampering**:
   - Historical result files and historical ledger entries have been preserved intact without deletion or retroactive alteration.
```

### 4. Ledger Modifications Audit (`benchmarks/test_run_ledger.jsonl`)

Command: `git diff 2cc8af8 -- benchmarks/test_run_ledger.jsonl`

```text
[No output returned - 0 lines modified, 0 lines added]
```

**Finding:** Plainly stated, **NO test-split access has been logged since the baseline commit `2cc8af8`**. The 3 ledger lines currently present date from October 2026 before this sprint began.

### 5. Gitignore & Tracked Files Hygiene

#### Current `.gitignore`:
```text
# Byte-compiled / optimized / test caches
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.hypothesis/
*.egg-info/

# Secrets and keys
.env
.env.*
!.env.example
audit_key*
*.mcp_checker_keys.env
*.env
.secrets/

# Large data and logs (unverified licenses / over 50 MB)
*.log
*.zip
*.parquet
benchmarks/data/

# Local benchmark outputs and caches
benchmarks/*_results.json
benchmarks/mcpevol_eval.log
benchmarks/external_eval.log
benchmarks/argground_bench.json
benchmarks/llm_judge_args_cache.jsonl
benchmarks/llm_judge_args_*.json
.huggingface/
```

#### Output of `git ls-files | Select-String -Pattern "audit_key|^\.env|\.parquet|^benchmarks/data/"`:

```text
.env.example
```

The result is strictly empty except `.env.example`.

### 6. Grep `benchmarks/keys.py` for `GOVARDHAN`

Command: `Select-String -Path benchmarks/keys.py -Pattern "GOVARDHAN"`

```text
[No output returned]
```

**Result:** The string `GOVARDHAN` does not appear anywhere in `benchmarks/keys.py`.

---

## B. Data Inventory (Read-Only)

### 1. Local Dataset Inventory Table

| Dataset Path | Size | Cases | Clusters | User Turn | Earlier Turns | Tool Outputs | Schema | Error Label Source |
|---|---|---|---|---|---|---|---|---|

| `benchmarks/data/mcpatlas/cases.json` | 2.67 MB | 2423 | 500 | present | absent | absent | absent | unclear |

| `benchmarks/data/taubench/cases.json` | 1.67 MB | 1037 | 110 | absent | absent | absent | absent | unclear |

| `benchmarks/data/agentdojo/cases.json` | 70.75 MB | 30143 | 2 | present | absent | absent | absent | unclear |

| `benchmarks/data/agenthallu/cases.json` | 0.87 MB | 434 | 434 | present | present | present | absent | unclear |

| `benchmarks/data/agenthallu/cases_eval.json` | 0.25 MB | 124 | 92 | present | present | present | absent | unclear |

| `benchmarks/data/deref/cases_fcrb.json` | 1.09 MB | 1260 | 630 | present | absent | absent | absent | unclear |

| `benchmarks/data/deref/cases_fcrb_schema.json` | 2.04 MB | 1260 | 630 | present | absent | absent | present | unclear |

| `benchmarks/data/deref/cases_fcrb_schema_note.json` | 2.18 MB | 1260 | 630 | present | absent | absent | present | unclear |

| `benchmarks/data/deref/cases_cfb.json` | 12.96 MB | 991 | 299 | present | absent | absent | absent | unclear |

| `benchmarks/data/deref/cases_cfb_schema_note.json` | 14.44 MB | 991 | 299 | present | absent | absent | present | unclear |

| `benchmarks/data/deref/fcrb.jsonl` | 3.56 MB | 1260 | 630 | present | absent | absent | present | unclear |

| `benchmarks/data/deref/cfb.jsonl` | 27.22 MB | 991 | 299 | present | present | absent | present | unclear |

| `benchmarks/data/bfcl/cases_bfcl_consensus.json` | 0.35 MB | 491 | 56 | present | absent | absent | absent | Berkeley Function-Calling Leaderboard ground truth function AST matching |

| `benchmarks/data/bfcl/cases_bfcl_consensus_200.json` | 0.61 MB | 924 | 197 | present | absent | absent | absent | Berkeley Function-Calling Leaderboard ground truth function AST matching |

| `benchmarks/data/bfcl/cases_bfcl_consensus_200_schema.json` | 1.45 MB | 924 | 197 | present | absent | absent | present | Berkeley Function-Calling Leaderboard ground truth function AST matching |

| `benchmarks/data/bfcl/cases_bfcl_consensus_schema.json` | 0.97 MB | 491 | 56 | present | absent | absent | present | Berkeley Function-Calling Leaderboard ground truth function AST matching |

| `benchmarks/data/bfcl/consensus_cases.json` | 19.48 MB | 1 | 1 | absent | absent | absent | absent | unclear |

| `benchmarks/data/bfcl/consensus_cases_56.json` | 4.0 MB | 1 | 1 | absent | absent | absent | absent | unclear |

| `benchmarks/argground_bench.json` | 2.29 MB | 3504 | 1 | present | absent | absent | absent | synthetic perturbation (rule-based argument mutation in make_argground_bench.py) |


### 2. Example Record Keys per Dataset

- **benchmarks/data/mcpatlas/cases.json**: `id`, `source`, `split`, `premise`, `call`, `label`

- **benchmarks/data/taubench/cases.json**: `src`, `domain`, `task_id`, `trial`, `reward`, `tool`, `kwargs`, `label`, `diff_class`, `diff_keys`, `flags`, `env_error`, `env_response`, `auth_user`, `context`

- **benchmarks/data/agentdojo/cases.json**: `id`, `source`, `split`, `premise`, `call`, `injected`, `attack_goal_call`, `run_utility`, `run_security`, `model`, `suite`, `attack_type`, `injection_task_id`

- **benchmarks/data/agenthallu/cases.json**: `id`, `source`, `split`, `premise`, `call`, `label`, `category`, `attributed_step`, `framework`

- **benchmarks/data/agenthallu/cases_eval.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `call`, `calls`, `label`, `category`

- **benchmarks/data/deref/cases_fcrb.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `mutation`, `args_meta`

- **benchmarks/data/deref/cases_fcrb_schema.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `mutation`, `args_meta`

- **benchmarks/data/deref/cases_fcrb_schema_note.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `mutation`, `args_meta`

- **benchmarks/data/deref/cases_cfb.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `mutation`, `args_meta`

- **benchmarks/data/deref/cases_cfb_schema_note.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `mutation`, `args_meta`

- **benchmarks/data/deref/fcrb.jsonl**: `dataset`, `item_id`, `query_id`, `state_id`, `call_label`, `request`, `history`, `plain_window`, `plain_rung`, `action`, `action_with_description`, `calls`, `functions`, `arguments`, `source_meta`

- **benchmarks/data/deref/cfb.jsonl**: `dataset`, `item_id`, `query_id`, `state_id`, `call_label`, `request`, `history`, `plain_window`, `plain_rung`, `action`, `action_with_description`, `calls`, `functions`, `arguments`, `source_meta`

- **benchmarks/data/bfcl/cases_bfcl_consensus.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `model`

- **benchmarks/data/bfcl/cases_bfcl_consensus_200.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `model`

- **benchmarks/data/bfcl/cases_bfcl_consensus_200_schema.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `model`

- **benchmarks/data/bfcl/cases_bfcl_consensus_schema.json**: `id`, `dataset`, `query_id`, `split`, `premise`, `calls`, `call`, `label`, `model`

- **benchmarks/data/bfcl/consensus_cases.json**: `meta`, `records`, `malformed`, `consensus_index`

- **benchmarks/data/bfcl/consensus_cases_56.json**: `meta`, `records`, `malformed`, `consensus_index`

- **benchmarks/argground_bench.json**: `premise`, `call`, `label`, `mutation`, `change`, `id`

### 3. Case Counts for Dev Splits Used in Prompts 4 and 5

| Dev Split | Total Cases ($n_{\text{total}}$) | Clean Cases ($n_{\text{clean}}$) | Buggy/Error Cases ($n_{\text{error}}$) |
|---|---|---|---|

| `argground` | 1753 | 909 | 844 |

| `deref_fcrb` | 630 | 315 | 315 |

| `deref_cfb` | 507 | 174 | 333 |

| `mcpatlas` | 2423 | 2423 | 0 |


### 4. `benchmarks/DATASET_CARD.md` Verbatim Scope & Acronym Audit

Quoting `benchmarks/DATASET_CARD.md`:

> "MCPEvol-Bench is a labeled evaluation dataset for hallucination detection in agentic tool-calling systems using the Model Context Protocol (MCP)... Total cases: 60..."


**Finding on Dataset Descriptions:**

- `benchmarks/DATASET_CARD.md` **only** documents `MCPEvol-Bench` (the 60-case smoke test). It contains **zero** mentions of ArgGround, fcrb, or cfb.

- In the earlier report, the datasets were labeled:

  - ArgGround: *"Financial / Arithmetic"*

  - fcrb: *"Free Code Reasoning"*

  - cfb: *"Complex Functions"*

- **Verification:** Those descriptions **do not exist in any file in the repository**. In the repo, `load_deref.py` cites Ma et al. (arXiv 2610.18497; Hugging Face `lm2445/DeRef`) where `fcrb.jsonl` and `cfb.jsonl` are file stems. The full phrase "Free Code Reasoning" and "Complex Functions" and "Financial / Arithmetic" were unsupported inferences generated in the prior conversation.

---

## C. MCP-Atlas Provenance and Leakage

1. **Is the 2,423-call set the entire local MCP-Atlas file?**  

   **YES.** `benchmarks/data/mcpatlas/cases.json` contains exactly 2,423 cases in total. Every single case has `'split': 'dev'`.

2. **Does the repo define any dev/test split for MCP-Atlas? Where?**  

   **NO.** `benchmarks/splits.py` does not register `mcpatlas`. The dataset loader falls through to generic path loading, which returns all cases matching `split=='dev'` (which is all 2,423 cases). There is no held-out split defined anywhere in the repository for MCP-Atlas.

3. **Origin of the 68.8% figure:**  

   The 68.8% figure originated on 2026-10-30 in `review/EXPERIMENTS_2026-10-30.md` (Row 23) and was formalized in `review/PAPER_PLAN_V2.md:200` and `benchmarks/mcpatlas_false_block.py`. It was computed on **all 2,423 reference calls** of `benchmarks/data/mcpatlas/cases.json` using `check_arguments` with strict blocking.

4. **Cluster & Server Distribution in MCP-Atlas:**  

   - **Distinct task clusters:** 500 (derived from the ID prefix `mcpatlas-<task_id>-<turn>`).

   - **Calls per cluster:** Minimum = 3, Median = 5.0, Maximum = 17.

   - **Inferred distinct tool server namespaces:** 36 (extracted from tool prefixes like `github_`, `slack_`, `airtable_`, `postgres_`).

---

## D. Oracle-Tier False Blocks on Clean Calls

In Prompt 4, an `ORACLE_EXACT` failure fired on **12.7%** (40 of 315) of clean DeRef fcrb dev calls (and 0.0% on cfb).


### Seeded Random Sample of 30 Clean Calls (Random Seed = 42)

Across the 30 sampled cases, 44 individual check failures occurred:


| # | Item ID | Argument Path | Value | Failed Schema Constraint | Check ID | Classification & Reason |
|---|---|---|---|---|---|---|

| 1 | `fcrb:live_multiple_170-70-0` | `experience_or_education_type` | `work_experience` | Field 'experience_or_education_type' value 'work_experience' is not one of the allowed enum values: ['experience', 'education']. | `schema_enum:experience_or_education_type` | **(b)** Implementation strictness: synonym/variant enum value ('work_experience' vs allowed ['experience', 'education']). |

| 2 | `fcrb:live_multiple_171-71-0` | `start_date` | `None` | Field 'start_date' expected type 'string' but got NoneType. | `schema_type:start_date` | **(b)** Implementation strictness: tool call explicitly passed None for an optional string parameter. |

| 3 | `fcrb:live_multiple_171-71-0` | `end_date` | `None` | Field 'end_date' expected type 'string' but got NoneType. | `schema_type:end_date` | **(b)** Implementation strictness: tool call explicitly passed None for an optional string parameter. |

| 4 | `fcrb:live_multiple_406-140-2` | `number_of_seats` | `None` | Required field 'number_of_seats' is missing from agent_args. | `schema_required:number_of_seats` | **(a)** True schema violation: tool call omitted a required argument declared in schema. |

| 5 | `fcrb:live_multiple_406-140-2` | `ride_type` | `None` | Required field 'ride_type' is missing from agent_args. | `schema_required:ride_type` | **(a)** True schema violation: tool call omitted a required argument declared in schema. |

| 6 | `fcrb:live_multiple_458-145-9` | `free_entry` | `True` | Field 'free_entry' expected type 'boolean' but got str. | `schema_type:free_entry` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 7 | `fcrb:live_multiple_458-145-9` | `good_for_kids` | `True` | Field 'good_for_kids' expected type 'boolean' but got str. | `schema_type:good_for_kids` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 8 | `fcrb:live_multiple_459-145-10` | `free_entry` | `True` | Field 'free_entry' expected type 'boolean' but got str. | `schema_type:free_entry` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 9 | `fcrb:live_multiple_459-145-10` | `good_for_kids` | `True` | Field 'good_for_kids' expected type 'boolean' but got str. | `schema_type:good_for_kids` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 10 | `fcrb:live_multiple_463-145-14` | `free_entry` | `True` | Field 'free_entry' expected type 'boolean' but got str. | `schema_type:free_entry` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 11 | `fcrb:live_multiple_463-145-14` | `good_for_kids` | `dontcare` | Field 'good_for_kids' expected type 'boolean' but got str. | `schema_type:good_for_kids` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 12 | `fcrb:live_multiple_464-145-15` | `free_entry` | `True` | Field 'free_entry' expected type 'boolean' but got str. | `schema_type:free_entry` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 13 | `fcrb:live_multiple_464-145-15` | `good_for_kids` | `True` | Field 'good_for_kids' expected type 'boolean' but got str. | `schema_type:good_for_kids` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 14 | `fcrb:live_multiple_476-146-1` | `year` | `2014` | Field 'year' expected type 'integer' but got str. | `schema_type:year` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 15 | `fcrb:live_multiple_482-146-7` | `year` | `dontcare` | Field 'year' expected type 'integer' but got str. | `schema_type:year` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 16 | `fcrb:live_multiple_640-161-8` | `year` | `2019` | Field 'year' expected type 'integer' but got str. | `schema_type:year` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 17 | `fcrb:live_multiple_830-178-5` | `year` | `2019` | Field 'year' expected type 'integer' but got str. | `schema_type:year` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 18 | `fcrb:live_multiple_835-178-10` | `year` | `2019` | Field 'year' expected type 'integer' but got str. | `schema_type:year` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 19 | `fcrb:live_multiple_835-178-10` | `genre` | `Reggaeton` | Field 'genre' value 'Reggaeton' is not one of the allowed enum values: ['Reggae', 'Holiday', 'Electropop', 'Pop', 'Asia', 'House', 'Electronica', 'Funk', 'Rock', 'Metal', 'Dubstep', 'Country', 'dontcare']. | `schema_enum:genre` | **(a)** True schema violation: value passed violates declared enum constraints. |

| 20 | `fcrb:live_multiple_839-178-14` | `year` | `dontcare` | Field 'year' expected type 'integer' but got str. | `schema_type:year` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 21 | `fcrb:live_multiple_841-178-16` | `year` | `dontcare` | Field 'year' expected type 'integer' but got str. | `schema_type:year` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 22 | `fcrb:live_multiple_851-179-5` | `price_range` | `dontcare` | Field 'price_range' value 'dontcare' is not one of the allowed enum values: ['cheap', 'moderate', 'pricey', 'ultra high-end']. | `schema_enum:price_range` | **(a)** True schema violation: value passed violates declared enum constraints. |

| 23 | `fcrb:live_multiple_859-181-0` | `number_of_adults` | `None` | Required field 'number_of_adults' is missing from agent_args. | `schema_required:number_of_adults` | **(a)** True schema violation: tool call omitted a required argument declared in schema. |

| 24 | `fcrb:live_multiple_873-182-10` | `genre` | `dontcare` | Field 'genre' value 'dontcare' is not one of the allowed enum values: ['World', 'Offbeat', 'Mystery', 'Supernatural', 'Horror', 'Animation', 'Sci-fi', 'Documentary', 'Drama', 'War', 'Family', 'Action']. | `schema_enum:genre` | **(a)** True schema violation: value passed violates declared enum constraints. |

| 25 | `fcrb:live_multiple_873-182-10` | `show_type` | `dontcare` | Field 'show_type' value 'dontcare' is not one of the allowed enum values: ['regular', '3d', 'imax']. | `schema_enum:show_type` | **(a)** True schema violation: value passed violates declared enum constraints. |

| 26 | `fcrb:live_multiple_876-183-1` | `free_entry` | `True` | Field 'free_entry' expected type 'boolean' but got str. | `schema_type:free_entry` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 27 | `fcrb:live_multiple_876-183-1` | `good_for_kids` | `True` | Field 'good_for_kids' expected type 'boolean' but got str. | `schema_type:good_for_kids` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 28 | `fcrb:live_multiple_881-183-6` | `free_entry` | `True` | Field 'free_entry' expected type 'boolean' but got str. | `schema_type:free_entry` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 29 | `fcrb:live_multiple_881-183-6` | `good_for_kids` | `True` | Field 'good_for_kids' expected type 'boolean' but got str. | `schema_type:good_for_kids` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 30 | `fcrb:live_multiple_971-212-0` | `service_id` | `None` | Required field 'service_id' is missing from agent_args. | `schema_required:service_id` | **(a)** True schema violation: tool call omitted a required argument declared in schema. |

| 31 | `fcrb:live_multiple_977-215-1` | `service_id` | `None` | Required field 'service_id' is missing from agent_args. | `schema_required:service_id` | **(a)** True schema violation: tool call omitted a required argument declared in schema. |

| 32 | `fcrb:live_simple_10-3-6` | `unit` | `celsius` | Field 'unit' value 'celsius' is not one of the allowed enum values: ['metric', 'imperial']. | `schema_enum:unit` | **(b)** Implementation strictness: unit case sensitivity or formatting variant. |

| 33 | `fcrb:live_simple_13-3-9` | `unit` | `celsius` | Field 'unit' value 'celsius' is not one of the allowed enum values: ['metric', 'imperial']. | `schema_enum:unit` | **(b)** Implementation strictness: unit case sensitivity or formatting variant. |

| 34 | `fcrb:live_simple_175-101-0` | `unit` | `session` | Field 'unit' expected type 'integer' but got str. | `schema_type:unit` | **(b)** Implementation strictness: string representation of numeric/boolean value (e.g. '2020' or 'true'). |

| 35 | `fcrb:live_simple_19-3-15` | `unit` | `celsius` | Field 'unit' value 'celsius' is not one of the allowed enum values: ['metric', 'imperial']. | `schema_enum:unit` | **(b)** Implementation strictness: unit case sensitivity or formatting variant. |

| 36 | `fcrb:live_simple_6-3-2` | `unit` | `fahrenheit` | Field 'unit' value 'fahrenheit' is not one of the allowed enum values: ['metric', 'imperial']. | `schema_enum:unit` | **(b)** Implementation strictness: unit case sensitivity or formatting variant. |

| 37 | `fcrb:live_simple_7-3-3` | `unit` | `fahrenheit` | Field 'unit' value 'fahrenheit' is not one of the allowed enum values: ['metric', 'imperial']. | `schema_enum:unit` | **(b)** Implementation strictness: unit case sensitivity or formatting variant. |

| 38 | `fcrb:live_simple_82-43-0` | `ContentItem` | `News` | Field 'ContentItem' value 'News' is not one of the allowed enum values: ['NewsItem', 'BlogPost', 'Event']. | `schema_enum:ContentItem` | **(a)** True schema violation: value passed violates declared enum constraints. |

| 39 | `fcrb:live_simple_82-43-0` | `MetaDescription` | `None` | Field 'MetaDescription' expected type 'string' but got NoneType. | `schema_type:MetaDescription` | **(b)** Implementation strictness: tool call explicitly passed None for an optional string parameter. |

| 40 | `fcrb:live_simple_82-43-0` | `UrlName` | `None` | Field 'UrlName' expected type 'string' but got NoneType. | `schema_type:UrlName` | **(b)** Implementation strictness: tool call explicitly passed None for an optional string parameter. |

| 41 | `fcrb:live_simple_82-43-0` | `MetaTitle` | `None` | Field 'MetaTitle' expected type 'string' but got NoneType. | `schema_type:MetaTitle` | **(b)** Implementation strictness: tool call explicitly passed None for an optional string parameter. |

| 42 | `fcrb:live_simple_9-3-5` | `unit` | `fahrenheit` | Field 'unit' value 'fahrenheit' is not one of the allowed enum values: ['metric', 'imperial']. | `schema_enum:unit` | **(b)** Implementation strictness: unit case sensitivity or formatting variant. |

| 43 | `fcrb:multiple_93` | `roomType` | `deluxe` | Argument 'roomType' is not declared in tool schema properties. | `schema_undeclared:roomType` | **(b)** Implementation strictness: strict JSON schema type enforcement. |

| 44 | `fcrb:multiple_93` | `additional_services` | `['breakfast']` | Argument 'additional_services' is not declared in tool schema properties. | `schema_undeclared:additional_services` | **(b)** Implementation strictness: strict JSON schema type enforcement. |


### Counts per Classification Category:

- **(a) True Schema Violations (Probable Label Noise):** 10 checks (e.g., omitted mandatory required fields like `number_of_seats`, `service_id`)

- **(b) Implementation Strictness:** 34 checks (e.g., passing explicit `None` for optional fields, string-to-int type coercions, enum synonym casing)

- **(c) Other:** 0 checks


### Counts per Check ID:

- `schema_type:year`: 7

- `schema_type:free_entry`: 6

- `schema_type:good_for_kids`: 6

- `schema_enum:unit`: 6

- `schema_enum:genre`: 2

- `schema_required:service_id`: 2

- `schema_enum:experience_or_education_type`: 1

- `schema_type:start_date`: 1

- `schema_type:end_date`: 1

- `schema_required:number_of_seats`: 1

- `schema_required:ride_type`: 1

- `schema_enum:price_range`: 1

- `schema_required:number_of_adults`: 1

- `schema_enum:show_type`: 1

- `schema_type:unit`: 1

- `schema_enum:ContentItem`: 1

- `schema_type:MetaDescription`: 1

- `schema_type:UrlName`: 1

- `schema_type:MetaTitle`: 1

- `schema_undeclared:roomType`: 1

- `schema_undeclared:additional_services`: 1

---

## E. Configuration Fidelity (Prompt 5)

### Comparison with Baseline Commit (`2cc8af8:server/pipeline/arg_ground.py`)

1. **Original Design in `2cc8af8`:**

   - Fuzzy matching: Used `difflib.SequenceMatcher` windowed ratio over context tokens with threshold `FUZZY = 0.88`.

   - Stemming: Used a lightweight custom suffix-stripping function `_stem` removing common endings (`ing`, `ed`, `es`, `s`, `ly`, etc.).

2. **Current `GroundingConfig` Defaults in `3185b16`:**

   - `fuzzy_threshold = 0.88`

   - `fuzzy_match = True` (calls the identical `_fuzzy_score` difflib implementation)

   - `stemming = True` (calls the identical custom `_stem` implementation)

   - **Do they differ from the baseline? NO.** The current implementation maintains byte-identical logic to the baseline.

3. **Discrepancy with Earlier Report:**

   - The earlier report described fuzzy matching as *"token-sort ratio at 0.82"* and stemming as *"Snowball stemmer"*.

   - **Finding:** Neither token-sort ratio, nor threshold 0.82, nor Snowball stemmer exists anywhere in the repository. The code always used `difflib.SequenceMatcher` with threshold `0.88` and custom `_stem`.

4. **Byte-Identical Regression Test Coverage:**

   - `tests/test_grounding_config.py::test_default_config_reproduces_legacy_behavior_identically` explicitly tests both the stemming path (`connecting` $\rightarrow$ `connect`) and the fuzzy match path (`amazonn` $\rightarrow$ `amazon prime`), verifying identical verdicts and scores to the unconfigured baseline.

---

## F. Ablation Tables for the Other Datasets

Full 18-configuration ablation results from `review/ablation_dev/ABLATION_REPORT.md`:


| Dataset | Configuration | Detection [95% CI] | Diff Detection vs all-on [95% CI] | Hard-Block [95% CI] | Interruption [95% CI] | Diff Interruption vs all-on [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| argground | all-on | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.068 [0.052, 0.085] | 0.000 [0.000, 0.000] |
| argground | all-off | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.147 [0.124, 0.173] | +0.079 [0.062, 0.098] |
| argground | loo_spelled_numbers | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.068 [0.052, 0.085] | 0.000 [0.000, 0.000] |
| argground | loo_numeric_formats | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.113 [0.094, 0.135] | +0.045 [0.032, 0.059] |
| argground | loo_iso_dates | 0.948 [0.931, 0.963] | -0.017 [-0.028, -0.007] | 0.000 [0.000, 0.000] | 0.072 [0.055, 0.090] | +0.003 [0.000, 0.008] |
| argground | loo_spoken_dates_times | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.073 [0.056, 0.091] | +0.004 [0.001, 0.009] |
| argground | loo_currency_equivalence | 0.972 [0.960, 0.983] | +0.007 [0.002, 0.013] | 0.000 [0.000, 0.000] | 0.090 [0.072, 0.111] | +0.022 [0.012, 0.033] |
| argground | loo_stemming | 0.966 [0.953, 0.978] | +0.001 [0.000, 0.004] | 0.000 [0.000, 0.000] | 0.070 [0.054, 0.088] | +0.002 [0.000, 0.006] |
| argground | loo_fuzzy_match | 0.973 [0.961, 0.983] | +0.008 [0.002, 0.015] | 0.000 [0.000, 0.000] | 0.069 [0.054, 0.087] | +0.001 [0.000, 0.003] |
| argground | loo_token_set_containment | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.068 [0.052, 0.085] | 0.000 [0.000, 0.000] |
| argground | aoi_spelled_numbers | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.147 [0.124, 0.173] | +0.079 [0.062, 0.098] |
| argground | aoi_numeric_formats | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.102 [0.084, 0.126] | +0.034 [0.022, 0.048] |
| argground | aoi_iso_dates | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.149 [0.125, 0.173] | +0.080 [0.063, 0.099] |
| argground | aoi_spoken_dates_times | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.147 [0.124, 0.173] | +0.079 [0.062, 0.098] |
| argground | aoi_currency_equivalence | 0.979 [0.968, 0.988] | +0.014 [0.007, 0.022] | 0.000 [0.000, 0.000] | 0.125 [0.104, 0.148] | +0.057 [0.042, 0.072] |
| argground | aoi_stemming | 0.977 [0.967, 0.987] | +0.013 [0.005, 0.022] | 0.000 [0.000, 0.000] | 0.140 [0.117, 0.165] | +0.072 [0.055, 0.089] |
| argground | aoi_fuzzy_match | 0.959 [0.943, 0.972] | -0.006 [-0.019, 0.006] | 0.000 [0.000, 0.000] | 0.143 [0.121, 0.169] | +0.075 [0.058, 0.093] |
| argground | aoi_token_set_containment | 0.979 [0.968, 0.987] | +0.014 [0.006, 0.023] | 0.000 [0.000, 0.000] | 0.142 [0.119, 0.167] | +0.074 [0.056, 0.092] |
| deref_fcrb | all-on | 0.654 [0.605, 0.709] | 0.000 [0.000, 0.000] | 0.127 [0.091, 0.160] | 0.559 [0.508, 0.613] | 0.000 [0.000, 0.000] |
| deref_fcrb | all-off | 0.743 [0.692, 0.791] | +0.089 [0.057, 0.122] | 0.127 [0.091, 0.160] | 0.648 [0.598, 0.698] | +0.089 [0.062, 0.123] |
| deref_fcrb | loo_spelled_numbers | 0.663 [0.611, 0.717] | +0.010 [0.000, 0.022] | 0.127 [0.091, 0.160] | 0.571 [0.521, 0.624] | +0.013 [0.003, 0.026] |
| deref_fcrb | loo_numeric_formats | 0.657 [0.606, 0.713] | +0.003 [0.000, 0.010] | 0.127 [0.091, 0.160] | 0.571 [0.520, 0.625] | +0.013 [0.003, 0.026] |
| deref_fcrb | loo_iso_dates | 0.673 [0.620, 0.726] | +0.019 [0.006, 0.034] | 0.127 [0.091, 0.160] | 0.571 [0.522, 0.627] | +0.013 [-0.006, 0.035] |
| deref_fcrb | loo_spoken_dates_times | 0.676 [0.623, 0.731] | +0.022 [0.007, 0.039] | 0.127 [0.091, 0.160] | 0.584 [0.533, 0.639] | +0.025 [0.009, 0.046] |
| deref_fcrb | loo_currency_equivalence | 0.657 [0.608, 0.711] | +0.003 [0.000, 0.010] | 0.127 [0.091, 0.160] | 0.565 [0.515, 0.617] | +0.006 [0.000, 0.016] |
| deref_fcrb | loo_stemming | 0.654 [0.605, 0.709] | 0.000 [0.000, 0.000] | 0.127 [0.091, 0.160] | 0.559 [0.508, 0.613] | 0.000 [0.000, 0.000] |
| deref_fcrb | loo_fuzzy_match | 0.689 [0.637, 0.741] | +0.035 [0.016, 0.056] | 0.127 [0.091, 0.160] | 0.587 [0.536, 0.639] | +0.029 [0.013, 0.048] |
| deref_fcrb | loo_token_set_containment | 0.654 [0.605, 0.709] | 0.000 [0.000, 0.000] | 0.127 [0.091, 0.160] | 0.559 [0.508, 0.613] | 0.000 [0.000, 0.000] |
| deref_fcrb | aoi_spelled_numbers | 0.737 [0.685, 0.786] | +0.083 [0.052, 0.113] | 0.127 [0.091, 0.160] | 0.641 [0.591, 0.692] | +0.083 [0.055, 0.115] |
| deref_fcrb | aoi_numeric_formats | 0.740 [0.689, 0.788] | +0.086 [0.055, 0.117] | 0.127 [0.091, 0.160] | 0.635 [0.584, 0.686] | +0.076 [0.051, 0.109] |
| deref_fcrb | aoi_iso_dates | 0.743 [0.692, 0.791] | +0.089 [0.057, 0.122] | 0.127 [0.091, 0.160] | 0.651 [0.602, 0.702] | +0.092 [0.064, 0.126] |
| deref_fcrb | aoi_spoken_dates_times | 0.743 [0.692, 0.791] | +0.089 [0.057, 0.122] | 0.127 [0.091, 0.160] | 0.648 [0.598, 0.698] | +0.089 [0.062, 0.123] |
| deref_fcrb | aoi_currency_equivalence | 0.740 [0.691, 0.788] | +0.086 [0.054, 0.117] | 0.127 [0.091, 0.160] | 0.641 [0.592, 0.692] | +0.083 [0.056, 0.115] |
| deref_fcrb | aoi_stemming | 0.717 [0.667, 0.767] | +0.063 [0.036, 0.092] | 0.127 [0.091, 0.160] | 0.635 [0.585, 0.688] | +0.076 [0.051, 0.106] |
| deref_fcrb | aoi_fuzzy_match | 0.695 [0.645, 0.750] | +0.041 [0.021, 0.064] | 0.127 [0.091, 0.160] | 0.613 [0.563, 0.666] | +0.054 [0.027, 0.088] |
| deref_fcrb | aoi_token_set_containment | 0.721 [0.669, 0.771] | +0.067 [0.039, 0.093] | 0.127 [0.091, 0.160] | 0.635 [0.585, 0.688] | +0.076 [0.051, 0.106] |
| deref_cfb | all-on | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | all-off | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | loo_spelled_numbers | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_numeric_formats | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_iso_dates | 0.477 [0.426, 0.531] | -0.003 [-0.009, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.323, 0.467] | 0.000 [-0.016, 0.017] |
| deref_cfb | loo_spoken_dates_times | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.402 [0.329, 0.470] | +0.006 [0.000, 0.018] |
| deref_cfb | loo_currency_equivalence | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_stemming | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_fuzzy_match | 0.697 [0.648, 0.744] | +0.216 [0.174, 0.262] | 0.000 [0.000, 0.000] | 0.402 [0.330, 0.472] | +0.006 [0.000, 0.018] |
| deref_cfb | loo_token_set_containment | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | aoi_spelled_numbers | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_numeric_formats | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_iso_dates | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_spoken_dates_times | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_currency_equivalence | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_stemming | 0.697 [0.648, 0.744] | +0.216 [0.174, 0.262] | 0.000 [0.000, 0.000] | 0.402 [0.330, 0.474] | +0.006 [-0.012, 0.028] |
| deref_cfb | aoi_fuzzy_match | 0.486 [0.435, 0.541] | +0.006 [0.000, 0.015] | 0.000 [0.000, 0.000] | 0.408 [0.333, 0.478] | +0.011 [0.000, 0.030] |
| deref_cfb | aoi_token_set_containment | 0.697 [0.648, 0.744] | +0.216 [0.174, 0.262] | 0.000 [0.000, 0.000] | 0.402 [0.330, 0.474] | +0.006 [-0.012, 0.028] |
| mcpatlas | all-on | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | all-off | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | loo_spelled_numbers | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_numeric_formats | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.670, 0.705] | +0.000 [0.000, 0.001] |
| mcpatlas | loo_iso_dates | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_spoken_dates_times | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_currency_equivalence | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_stemming | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.690 [0.672, 0.707] | +0.002 [0.001, 0.005] |
| mcpatlas | loo_fuzzy_match | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.703 [0.685, 0.720] | +0.015 [0.010, 0.021] |
| mcpatlas | loo_token_set_containment | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | aoi_spelled_numbers | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_numeric_formats | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.053 [0.044, 0.063] |
| mcpatlas | aoi_iso_dates | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_spoken_dates_times | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_currency_equivalence | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_stemming | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.703 [0.686, 0.720] | +0.016 [0.011, 0.021] |
| mcpatlas | aoi_fuzzy_match | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.714 [0.696, 0.730] | +0.027 [0.020, 0.034] |
| mcpatlas | aoi_token_set_containment | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.706 [0.688, 0.723] | +0.018 [0.013, 0.024] |



---

## G. Top False-Block Claims, Measured Mechanically

For the 30 most frequent (argument, value) false-block pairs from Prompt 5, exact case-sensitive mechanical substring checks were executed across all matching case records:


| Rank | Dataset | Argument | Value | Ablation Count | Matched Cases | In User Turn | In Earlier Tool Output | In Schema | Nowhere | No Tool Output Field |
|---|---|---|---|---|---|---|---|---|---|---|

| 1 | `mcpatlas` | `base_id` | `appIF9byLfQwdHqE2` | 201 | 201 | 0 | 0 | 0 | 201 | 201 |

| 2 | `mcpatlas` | `database` | `video_game_store` | 184 | 184 | 0 | 0 | 0 | 184 | 184 |

| 3 | `mcpatlas` | `field_name` | `Date` | 81 | 86 | 0 | 0 | 0 | 86 | 86 |

| 4 | `mcpatlas` | `interval` | `1d` | 59 | 59 | 0 | 0 | 0 | 59 | 59 |

| 5 | `mcpatlas` | `table_name` | `Sales Expenses` | 54 | 65 | 0 | 0 | 0 | 65 | 65 |

| 6 | `mcpatlas` | `path` | `/data` | 48 | 87 | 0 | 0 | 0 | 87 | 87 |

| 7 | `mcpatlas` | `collection` | `Purchase History` | 33 | 33 | 0 | 0 | 0 | 33 | 33 |

| 8 | `mcpatlas` | `languageId` | `python` | 28 | 28 | 0 | 0 | 0 | 28 | 28 |

| 9 | `mcpatlas` | `symbol` | `BTC` | 23 | 30 | 1 | 0 | 0 | 29 | 30 |

| 10 | `mcpatlas` | `command` | `ls` | 22 | 30 | 8 | 0 | 0 | 22 | 30 |

| 11 | `mcpatlas` | `collection` | `Customers` | 22 | 46 | 0 | 0 | 0 | 46 | 46 |

| 12 | `mcpatlas` | `path` | `/data/Top Movies.csv` | 20 | 21 | 1 | 0 | 0 | 20 | 21 |

| 13 | `mcpatlas` | `path` | `/data/repos` | 17 | 18 | 0 | 0 | 0 | 18 | 18 |

| 14 | `argground` | `symbol` | `MSFT` | 15 | 20 | 1 | 0 | 0 | 19 | 20 |

| 15 | `mcpatlas` | `database_id` | `21b97551-844e-8090-b48d-d33c1c2be7f8` | 15 | 15 | 0 | 0 | 0 | 15 | 15 |

| 16 | `mcpatlas` | `table_name` | `Turnover Retention` | 15 | 15 | 0 | 0 | 0 | 15 | 15 |

| 17 | `mcpatlas` | `database_id` | `21b97551-844e-8068-b387-fe7a56b04348` | 15 | 15 | 0 | 0 | 0 | 15 | 15 |

| 18 | `mcpatlas` | `collection` | `Delivery Logistics` | 14 | 14 | 0 | 0 | 0 | 14 | 14 |

| 19 | `mcpatlas` | `max_records` | `10` | 13 | 13 | 0 | 0 | 0 | 13 | 13 |

| 20 | `mcpatlas` | `path` | `/data/Crime_records.csv` | 13 | 13 | 0 | 0 | 0 | 13 | 13 |

| 21 | `mcpatlas` | `command` | `ls /data` | 12 | 12 | 0 | 0 | 0 | 12 | 12 |

| 22 | `mcpatlas` | `source` | `en-EN` | 12 | 12 | 0 | 0 | 0 | 12 | 12 |

| 23 | `deref_cfb` | `sortBy` | `attr_book_score` | 11 | 22 | 0 | 0 | 19 | 3 | 22 |

| 24 | `mcpatlas` | `collection` | `Social Media` | 11 | 16 | 0 | 0 | 0 | 16 | 16 |

| 25 | `mcpatlas` | `channel_id` | `C093FF10B5J` | 10 | 10 | 0 | 0 | 0 | 10 | 10 |

| 26 | `mcpatlas` | `target` | `es-ES` | 10 | 11 | 0 | 0 | 0 | 11 | 11 |

| 27 | `mcpatlas` | `table_name` | `Inventory Levels Turnover` | 10 | 10 | 0 | 0 | 0 | 10 | 10 |

| 28 | `mcpatlas` | `path` | `/data/CoinbaseTradeHistory.csv` | 10 | 10 | 0 | 0 | 0 | 10 | 10 |

| 29 | `deref_cfb` | `pick_up_time` | `08:00` | 9 | 20 | 0 | 0 | 0 | 20 | 20 |

| 30 | `mcpatlas` | `repo_path` | `/data/repos/snake-game` | 9 | 9 | 0 | 0 | 0 | 9 | 9 |


### Mechanical Totals Across All 30 False-Block Pairs:

- **Found in User Turn:** 11

- **Found in Earlier Tool Output:** **0**

- **Found in Tool Schema:** 19

- **Found Nowhere in Case Record:** 1095

- **Case Record Has No Earlier Tool Output Field:** **1125**


**Critical Finding:** The earlier report provided speculative narrative explanations (e.g. *"Dynamic Airtable Base ID generated in Turn 1 output"*, *"Database name enumerated in prior list_databases call"*). In reality, **`benchmarks/data/mcpatlas/cases.json` contains no tool output fields whatsoever**. The values were not found in earlier tool outputs locally because the dataset file does not store them.

---

## H. Statistics & Bootstrap Fidelity

### 1. Youden's J with Cluster-Bootstrap 95% CIs for All Prompt 4 Frontier Rows

```markdown
| Dataset | Policy Variant | Detection (ASK/BLOCK) [95% CI] | Detection (BLOCK-only) [95% CI] | Hard-Block Rate (Clean) [95% CI] | Interruption Rate (Clean) [95% CI] | Youden J [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| argground | legacy_blocking | 0.964 [0.950, 0.975] | 0.964 [0.950, 0.975] | 0.068 [0.054, 0.086] | 0.068 [0.054, 0.086] | 0.896 [0.875, 0.917] |
| argground | ASK-on-coverage | 0.964 [0.950, 0.975] | 0.000 [0.000, 0.005] | 0.000 [0.000, 0.004] | 0.068 [0.054, 0.086] | 0.896 [0.875, 0.917] |
| argground | WARN-on-coverage | 0.000 [0.000, 0.005] | 0.000 [0.000, 0.005] | 0.000 [0.000, 0.004] | 0.000 [0.000, 0.004] | 0.000 [0.000, 0.000] |
| argground | block-on-oracle-only | 0.000 [0.000, 0.005] | 0.000 [0.000, 0.005] | 0.000 [0.000, 0.004] | 0.000 [0.000, 0.004] | 0.000 [0.000, 0.000] |
| deref_fcrb | legacy_blocking | 0.654 [0.600, 0.704] | 0.654 [0.600, 0.704] | 0.559 [0.504, 0.613] | 0.559 [0.504, 0.613] | 0.095 [0.035, 0.159] |
| deref_fcrb | ASK-on-coverage | 0.654 [0.600, 0.704] | 0.156 [0.120, 0.200] | 0.127 [0.095, 0.168] | 0.559 [0.504, 0.613] | 0.095 [0.035, 0.159] |
| deref_fcrb | WARN-on-coverage | 0.156 [0.120, 0.200] | 0.156 [0.120, 0.200] | 0.127 [0.095, 0.168] | 0.127 [0.095, 0.168] | 0.029 [-0.006, 0.063] |
| deref_fcrb | block-on-oracle-only | 0.156 [0.120, 0.200] | 0.156 [0.120, 0.200] | 0.127 [0.095, 0.168] | 0.127 [0.095, 0.168] | 0.029 [-0.006, 0.063] |
| deref_cfb | legacy_blocking | 0.480 [0.427, 0.534] | 0.480 [0.427, 0.534] | 0.397 [0.327, 0.471] | 0.397 [0.327, 0.471] | 0.084 [0.025, 0.141] |
| deref_cfb | ASK-on-coverage | 0.480 [0.427, 0.534] | 0.009 [0.003, 0.026] | 0.000 [0.000, 0.022] | 0.397 [0.327, 0.471] | 0.084 [0.025, 0.141] |
| deref_cfb | WARN-on-coverage | 0.009 [0.003, 0.026] | 0.009 [0.003, 0.026] | 0.000 [0.000, 0.022] | 0.000 [0.000, 0.022] | 0.009 [0.000, 0.020] |
| deref_cfb | block-on-oracle-only | 0.009 [0.003, 0.026] | 0.009 [0.003, 0.026] | 0.000 [0.000, 0.022] | 0.000 [0.000, 0.022] | 0.009 [0.000, 0.020] |
```


### 2. Bootstrap Iteration Count & Runtime Analysis

- **Bootstrap Iterations Used ($B$):** In Prompt 4, $B = 2,000$ was used. In Prompt 5, $B = 1,000$ was used.

- **Regeneration with $B = 10,000$:**

  - A benchmark test of `cluster_bootstrap_ci` on the 2,423 MCP-Atlas rows at $B = 10,000$ completed in **58.53 seconds** for a single metric.

  - Across all 72 ablation combinations (4 datasets $\times$ 18 configs $\times$ paired differences), total execution would require $\approx 70 \text{ minutes}$.

  - Because total runtime exceeds the 10-minute threshold specified in Prompt 5B, full regeneration at $B = 10,000$ was **not done**.

---

## I. Statements from Earlier Report NOT Supported by Verification

1. **Dataset Acronym Expansions:**

   - *Claim:* `fcrb` is "Free Code Reasoning", `cfb` is "Complex Functions", `argground` is "Financial / Arithmetic".

   - *Fact:* No file in the repository contains these descriptions. `DATASET_CARD.md` documents only `MCPEvol-Bench`.

2. **Dev Split Case Counts:**

   - *Claim:* DeRef fcrb dev has "306 cases" and DeRef cfb dev has "307 cases".

   - *Fact:* DeRef fcrb dev has **630 cases** (315 clean, 315 error). DeRef cfb dev has **507 cases** (174 clean, 333 error).

3. **Fuzzy Matching & Stemming Implementation:**

   - *Claim:* Fuzzy match used "token-sort ratio at 0.82" and stemming used "Snowball stemmer".

   - *Fact:* The code never used token-sort ratio or Snowball stemmer. It used `difflib.SequenceMatcher` with threshold `0.88` and a custom suffix-stripping `_stem` function.

4. **Root Cause Attribution on Top 30 False Blocks:**

   - *Claim:* Top false blocks were generated by prior tool turn outputs.

   - *Fact:* While plausible in the live environment, this cannot be demonstrated from the local file: `benchmarks/data/mcpatlas/cases.json` has **zero** earlier tool outputs stored in its records.

5. **MCP-Atlas Split Existence:**

   - *Claim:* Implied an official MCP-Atlas dev split existed.

   - *Fact:* All 2,423 cases in `benchmarks/data/mcpatlas/cases.json` are marked `'dev'`. The repo has no registered held-out split for MCP-Atlas.
