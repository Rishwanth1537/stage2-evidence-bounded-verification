# MCP-Atlas Re-Ingestion & Fast Cluster Bootstrap Report (Prompt 5C)

**Date:** 2026-11-07  
**Branch:** `stage2-evidence-bounded-verification`  
**Author:** Pair Programming Agent  

---

## 1. Process & Commit Verification

- **Prompt 5B Push Status:** Commit `5caf669` (`P5B: result verification report`) was subjected to Rule 2 pre-commit safety audit and pushed cleanly to `origin/stage2-evidence-bounded-verification`.
- **Working Tree Cleanliness:** All benchmark data under `benchmarks/data/` (including `benchmarks/data/mcpatlas/raw/`) is strictly gitignored. No test splits or confirmatory evaluation slices were modified.
- **Server Code Invariance:** Zero lines under `server/` were modified.

---

## 2. Rationale & Data Discrepancy Analysis

In Prompt 5B, verification revealed that `benchmarks/data/mcpatlas/cases.json` only contained the fields:
`id`, `source`, `split`, `premise`, `call`, and `label`.
It contained **zero earlier tool output fields**, despite MCP-Atlas trajectories consisting of multi-turn interactions. Consequently, when earlier reports speculated that clean tool calls were failing due to dynamic IDs generated in earlier turns, that hypothesis could not be substantiated from local files.

The upstream release `ScaleAI/MCP-Atlas` on Hugging Face provides full multi-turn conversational trajectories including tool call outputs. Re-ingesting the full dataset while retaining earlier tool outputs allows direct, mechanical verification of where call arguments originate.

---

## 3. Loader Audit (`benchmarks/load_mcpatlas.py`)

An audit of `benchmarks/load_mcpatlas.py` established:
1. **Source & Extraction:** Reads directly from the Hugging Face `ScaleAI/MCP-Atlas` parquet.
2. **Dropped Fields:** Line 23 explicitly contained:
   ```python
   if msg.get("role") != "assistant":
       continue
   ```
   This dropped all `role == "tool"` messages, entirely discarding all tool output bodies. Furthermore, `premise` was set to `row["PROMPT"]` for every turn, completely stripping multi-turn execution context.
3. **Task & Call Aggregation:** 
   - 500 tasks yield exactly 2,423 reference tool calls (mean 4.85 calls/task, min 3, median 5, max 17).
   - Higher call counts (up to 17) correspond to legitimate iterative agent exploration loops (e.g. paginated Airtable queries across 12 monthly slices).
4. **Tool Server Count Clarification:**
   - The project dossier claimed "106 real MCP servers".
   - In reality, the dataset contains **36 distinct MCP server namespaces** (e.g., `github_`, `slack_`, `airtable_`, `postgres_`) offering **106 distinct tools**. The dossier mistakenly conflated tool count with server count; the research paper's figure of 36 servers is the one supported by the data.

---

## 4. Download Provenance & Licensing

- **Source URL:** `https://huggingface.co/datasets/ScaleAI/MCP-Atlas/resolve/main/MCP-Atlas.parquet`
- **File Size:** **15,638,757 bytes** (14.91 MB)
- **License:** `license: cc-by-4.0` (*Creative Commons Attribution 4.0 International*)
- **Local Storage:** `benchmarks/data/mcpatlas/raw/MCP-Atlas.parquet` (*gitignored*)

---

## 5. Re-Ingestion & Regression Parity (`cases_v2.json`)

`benchmarks/load_mcpatlas.py` was extended to generate `benchmarks/data/mcpatlas/cases_v2.json` while maintaining backward compatibility with `cases.json`.

Each record in `cases_v2.json` preserves:
- `id`: `mcpatlas-<TASK>-<k>`
- `task_id` (`cluster_id`): `mcpatlas-<TASK>`
- `step_index`: 1-based index within the trajectory (1, 2, ..., 17)
- `call`: `{"name": ..., "arguments": ...}`
- `user_prompt` & `premise`: Initial user task instruction
- `tool_schema`: `None` (no schemas in dataset)
- `earlier_tool_outputs`: Full text of all prior tool turn outputs in the trajectory

### Truncation Transparency
- **Truncation threshold:** None (`max_output_chars=None`).
- **Truncated outputs:** **0**. 100% of tool output text is preserved verbatim across all 2,423 calls (maximum single output length: 4,110,141 characters).

### Regression Check
Grounding against `premise` only (user prompt) on `cases_v2.json` confirms exact numeric parity with Prompt 5:
- **Case Count & ID Parity:** Exactly 2,423 cases; 0 ID, call, or premise mismatches.
- **Strict Interruption Rate (`all-on`):** **68.758% (1,666 / 2,423)** (matches the 68.8% registered figure).
- **Strict Interruption Rate (`all-off`):** **74.123% (1,796 / 2,423)** (matches the 74.1% baseline).

### Inventory Report

| Metric | Value | Proportion |
| :--- | :--- | :--- |
| **Total Calls** | 2,423 | 100.0% |
| **Calls with $\ge 1$ Earlier Tool Output** | 1,923 | **79.4%** |
| **Calls at Step 1 (no earlier outputs)** | 500 | **20.6%** |
| **Median Earlier Output Length (chars)** | 4,516.0 | — |
| **Maximum Earlier Output Length (chars)** | 4,113,724 | — |

**Step Index Distribution across 2,423 Calls:**
- Step 1: 500
- Step 2: 500
- Step 3: 500
- Step 4: 416
- Step 5: 275
- Step 6: 125
- Step 7: 50
- Step 8: 20
- Step 9: 9
- Step 10: 6
- Step 11: 5
- Step 12: 4
- Step 13: 3
- Step 14: 3
- Step 15: 3
- Step 16: 3
- Step 17: 1

---

## 6. Mechanical Origin Check (Top 30 False-Blocked Pairs)

For the 30 most frequent false-blocked `(argument, value)` pairs from Prompt 5, exact case-sensitive mechanical substring checks were performed across all matching cases against:
1. User prompt
2. Earlier tool outputs in the trajectory
3. Tool schema defaults / enums
4. Nowhere

### Detailed Breakdown

| Rank | Dataset | Argument | Value | Matched Calls | In User Prompt | In Earlier Tool Output | In Schema | Nowhere |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `mcpatlas` | `base_id` | `appIF9byLfQwdHqE2` | 201 | 0 | **201** | 0 | 0 |
| 2 | `mcpatlas` | `database` | `video_game_store` | 184 | 0 | **182** | 0 | 2 |
| 3 | `mcpatlas` | `field_name` | `Date` | 86 | 0 | **86** | 0 | 0 |
| 4 | `mcpatlas` | `interval` | `1d` | 59 | 0 | **22** | 0 | 37 |
| 5 | `mcpatlas` | `table_name` | `Sales Expenses` | 65 | 0 | **65** | 0 | 0 |
| 6 | `mcpatlas` | `path` | `/data` | 87 | 0 | **82** | 0 | 5 |
| 7 | `mcpatlas` | `collection` | `Purchase History` | 33 | 0 | **33** | 0 | 0 |
| 8 | `mcpatlas` | `languageId` | `python` | 28 | 0 | 0 | 0 | 28 |
| 9 | `mcpatlas` | `symbol` | `BTC` | 30 | 1 | **9** | 0 | 20 |
| 10 | `mcpatlas` | `command` | `ls` | 30 | 8 | **20** | 0 | 2 |
| 11 | `mcpatlas` | `collection` | `Customers` | 46 | 0 | **46** | 0 | 0 |
| 12 | `mcpatlas` | `path` | `/data/Top Movies.csv` | 21 | 1 | 0 | 0 | 20 |
| 13 | `mcpatlas` | `path` | `/data/repos` | 18 | 0 | 0 | 0 | 18 |
| 14 | `argground` | `symbol` | `MSFT` | 20 | 1 | 0 | 0 | 19 |
| 15 | `mcpatlas` | `database_id` | `21b97551-844e-8090-b48d-d33c1c2be7f8` | 15 | 0 | **15** | 0 | 0 |
| 16 | `mcpatlas` | `table_name` | `Turnover Retention` | 15 | 0 | **15** | 0 | 0 |
| 17 | `mcpatlas` | `database_id` | `21b97551-844e-8068-b387-fe7a56b04348` | 15 | 0 | **15** | 0 | 0 |
| 18 | `mcpatlas` | `collection` | `Delivery Logistics` | 14 | 0 | **14** | 0 | 0 |
| 19 | `mcpatlas` | `max_records` | `10` | 13 | 0 | **13** | 0 | 0 |
| 20 | `mcpatlas` | `path` | `/data/Crime_records.csv` | 13 | 0 | 0 | 0 | 13 |
| 21 | `mcpatlas` | `command` | `ls /data` | 12 | 0 | 0 | 0 | 12 |
| 22 | `mcpatlas` | `source` | `en-EN` | 12 | 0 | 0 | 0 | 12 |
| 23 | `deref_cfb` | `sortBy` | `attr_book_score` | 22 | 0 | 0 | **22** | 0 |
| 24 | `mcpatlas` | `collection` | `Social Media` | 16 | 0 | **16** | 0 | 0 |
| 25 | `mcpatlas` | `channel_id` | `C093FF10B5J` | 10 | 0 | **10** | 0 | 0 |
| 26 | `mcpatlas` | `target` | `es-ES` | 11 | 0 | **9** | 0 | 2 |
| 27 | `mcpatlas` | `table_name` | `Inventory Levels Turnover` | 10 | 0 | **10** | 0 | 0 |
| 28 | `mcpatlas` | `path` | `/data/CoinbaseTradeHistory.csv` | 10 | 0 | 0 | 0 | 10 |
| 29 | `deref_cfb` | `pick_up_time` | `08:00` | 20 | 0 | 0 | 0 | 20 |
| 30 | `mcpatlas` | `repo_path` | `/data/repos/snake-game` | 9 | 0 | 0 | 0 | 9 |

### Mechanical Summary

- **Total Matched Calls:** 1,125
- **Appears in User Prompt:** 11 (1.0%)
- **Appears in Earlier Tool Output:** **863 (76.7%)**
- **Appears in Tool Schema:** 22 (2.0%)
- **Appears Nowhere in Record:** 229 (20.4%)

**Measurement Finding:** While the Prompt 5B audit showed 0 tool output matches because `cases.json` dropped all tool messages, `cases_v2.json` demonstrates that **76.7%** of the most frequent false-blocked values originate directly from prior tool outputs in the conversation.

---

## 7. AgentHallu Feasibility Audit

An inspection of `benchmarks/load_agenthallu.py` and `benchmarks/build_agenthallu_eval.py` established:
1. **Source of Local Data:** Extracted from the public AgentHallu repository (`github.com/bihan1/AgentHallu`).
2. **Framework Filtering:** The full dataset contains 693 trajectories across 7 frameworks (`BFCL`, `ToolBench`, `RestGPT`, `Seal-Tools`, `TravelPlanner`, `AgentBench`, `WebArena`). `load_agenthallu.py` line 62 explicitly filters:
   ```python
   if fw != "BFCL" and not all_frameworks:
       continue
   ```
   This discarded the other 6 frameworks, leaving 92 trajectories.
3. **Trajectory Usability:** All 434 local cases in `cases.json` represent the tool calls from those 92 BFCL trajectories. `build_agenthallu_eval.py` selected all 31 positive trajectories and 93 clean calls round-robin across all 92 trajectories.
4. **Recipe for Trajectory-Disjoint Dev Split:**
   - Clone the full AgentHallu repository.
   - Run `load_agenthallu.py <repo_dir> --all-frameworks`.
   - Filter to the remaining 601 trajectories (the non-BFCL frameworks).
   - This produces a dev split with 0% trajectory overlap with the current evaluation set.

---

## 8. Fast Cluster Bootstrap ($B=10,000$)

### Implementation & Verification
1. **Vectorized Count Resampling (`benchmarks/stats.py`):**
   - Implemented `fast_cluster_bootstrap_ratio`, `fast_cluster_bootstrap_youden`, and `fast_paired_cluster_bootstrap_ratio_diff`.
   - Aggregates cases per cluster into count arrays: $(tp_k, p_k, fp_k, n_k)$.
   - Replaced row-iteration loops with vectorized index resampling: `np.sum(counts[sampled_indices], axis=1)`.
   - The reference slow path was retained. Verification in `tests/test_stats.py` (`test_fast_vs_slow_cluster_bootstrap_agreement`) confirms exact float parity between the fast and slow implementations.
   - Test suite status: **10 passed in 40.57s** (`pytest tests/test_stats.py`).

2. **Frontier Gate Regeneration ($B=10,000$):**
   - Re-evaluated all 3 dev datasets across all 6 gate policy variants at $B=10,000$.
   - **Total Runtime:** **96.71 seconds** for full case re-extraction, policy evaluation, and 18 bootstrap runs at $B=10,000$.
   - Output saved to `review/frontier_dev/FRONTIER_REPORT.md`.

3. **Normalizer Ablation Regeneration ($B=10,000$):**
   - Regenerated all 18 configurations across all 4 datasets (ArgGround dev, DeRef fcrb dev, DeRef cfb dev, MCP-Atlas dev) at $B=10,000$.
   - **Total Runtime:** **440.46 seconds** (7.34 minutes) including full nearest-context span extraction and 72 paired cluster-bootstrap differences at $B=10,000$.
   - Output saved to `review/ablation_dev/ABLATION_REPORT.md`.

