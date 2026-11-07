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
