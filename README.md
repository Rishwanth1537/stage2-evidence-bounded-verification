# Self-Reflective Hallucination Checker via MCP

An MCP server that exposes two tools enabling LLM agents to perform
**pre-execution self-verification** before acting on their own reasoning:

| Tool | Purpose |
|---|---|
| `verify_logic_chain` | Checks whether a proposed reasoning chain is factually consistent with a source context |
| `verify_schema_alignment` | Checks whether planned tool-call arguments match the current tool schema |

---

## Benchmark Performance

All numbers below are preliminary and come from result files in `benchmarks/`; each can be regenerated with the command shown. This is a research prototype.

### Internal: MCPEvol-Bench (60 hand-written cases, 29 consistent / 31 hallucinated)

Fixed thresholds (GED 0.35, entailment 0.40); consistent is the positive class.

| Type | Cases | Accuracy | Precision | Recall |
|---|---|---|---|---|
| schema | 12 | 100% | 1.00 | 1.00 |
| format | 13 | 100% | 1.00 | 1.00 |
| content | 25 | 60% | 0.75 | 0.25 |
| negation | 5 | 60% | 0.50 | 0.50 |
| role_swap | 5 | 40% | 0.33 | 0.50 |
| **Overall** | **60** | **75.0%** | **0.82** | **0.62** |

Schema and format cases are constructed violations caught by the deterministic validator; they show the validator works, not that semantic hallucinations are detected. Reproduce: `make bench`.

### Component ablation (35 text-based cases; fixed thresholds, nothing tuned)

| Variant | Accuracy | Balanced acc. | Precision | Recall |
|---|---|---|---|---|
| NLI only (whole claim) | 80.0% | 0.781 | 1.00 | 0.56 |
| GED only | 54.3% | 0.564 | 0.50 | 0.81 |
| Hybrid (current pipeline) | 57.1% | 0.551 | 0.56 | 0.31 |
| Hybrid + asymmetric GED (experimental) | 62.9% | 0.604 | 0.71 | 0.31 |

NLI-only is better than the current hybrid (exact McNemar p = 0.008). The asymmetric variant's gain over the hybrid is not significant at n = 35 (p = 0.5). Reproduce: `PYTHONPATH=. python benchmarks/ablation_local.py` (about 2 minutes on CPU, writes `benchmarks/ablation_results.json`).

### Redesign: grounded mode (`verify_logic_chain` with `mode="grounded"`)

The ablation showed the graph stage adds no accuracy, so a second mode was added: a claim is consistent iff (1) whole-claim NLI (same windowed DeBERTa, **no** span template) is at least 0.40, (2) every number, date, version or time in the plan also occurs in the premise (`server/pipeline/value_check.py`), and (3) any user-query constraints are preserved. The default `mode="hybrid"` is unchanged. Accuracy on text-based cases, fixed thresholds, nothing tuned:

| Variant | Dev (35 original) | Design set (210, generated) | Held-out (214, generated) |
|---|---|---|---|
| Shipped hybrid (GED + span NLI) | 57.1% | 53.3% | 52.8% |
| NLI whole claim, date template | 80.0% | 76.2% | 76.6% |
| NLI whole claim, raw | 88.6% | 91.9% | 94.4% |
| **Grounded (raw NLI + value check)** | 88.6% | 94.3% | **95.3%** |

The design set's errors motivated the value check (optimistic); the held-out set uses a different seed and was not inspected before the design, but it shares the generator's templates and is synthetic. On held-out cases the value check fixes 2 cases and breaks none (exact McNemar p = 0.5, not significant). The graph distance alone is near chance on the design set (AUROC 0.52 symmetric, 0.53 asymmetric, versus 0.96 for raw NLI), and a symmetric distance penalises a premise with an extra sentence (mean 0.22 to 0.34 on consistent cases). Known limitations: plans phrased as future actions ("The agent will download X as requested") are often judged not entailed by request-style premises, spelled-out numbers and unit conversions are not handled, and localisation is coarser than span-level NLI.

Reproduce: `python benchmarks/make_mcpevol_v2.py` (seeded generator; `--seed 11 --prefix V3 --out benchmarks/mcpevol_v3.json` for the held-out set), `PYTHONPATH=. python benchmarks/ablation_local.py --dataset benchmarks/mcpevol_v3.json --output benchmarks/ablation_results_v3.json --veto-threshold 0.55`, and `PYTHONPATH=. python benchmarks/eval_grounded.py --dataset benchmarks/mcpevol_v3.json`. An LLM-as-judge baseline script is provided (`benchmarks/llm_judge_eval.py`, needs `ANTHROPIC_API_KEY`; sends benchmark text to the API; not yet run).

### Argument-level grounding (`verify_argument_grounding`, proxy `logic_mode="arguments"`)

Instead of judging a whole sentence, each (argument, value) of a planned call is checked against the conversation it should come from, type by type: numbers (digits, separators, percentages, k/m, spelled-out), ISO dates and timestamps against written dates and clock times ("2 pm" = T14:00), ISO-4217 currency codes against currency names, and normalised / stemmed / fuzzy string matching. The call score is the weakest checkable argument (the same `min` aggregation as Ma et al., arXiv 2610.18497, not our invention); a call is blocked iff the score is below tau. Tau can be chosen by a split-conformal quantile of genuine calls (`conformal_threshold`) so that the false-block rate stays within a budget alpha. Booleans and empty values are not checked; there is no world knowledge ("MSFT" for "Microsoft" is reported ungrounded) and no arithmetic.

Evaluated on **ArgGround-Bench** (`benchmarks/make_argground_bench.py`): public, LLM-generated function-calling conversations (Glaive v2); each case is a genuine call or the same call with exactly one argument value replaced by a value absent from the conversation. 93.5% of genuine argument values occur verbatim in the context. Held-out half, 1,751 calls (919 genuine, 832 injected); thresholds and calibration from the other half:

| Method | False-block rate [95% CI] | Detection of injected errors | Balanced acc. |
|---|---|---|---|
| Exact string match (our implementation of the idea) | 14.0% [11.9%, 16.3%] | 96.4% | 0.912 |
| **Type-aware matching** | **7.3%** [5.6%, 9.0%] | 96.5% | 0.946 |
| + ignore ungrounded optional arguments (lower risk tier) | 5.7% | 84.6% | 0.895 |
| Calibrated, false-block budget 5% (tau = 0.62) | 3.7% | 87.5% | - |
| Calibrated, false-block budget 10% (tau = 1.00) | 7.3% | 97.8% | - |

The split-conformal threshold gives a marginal guarantee: if genuine calls are exchangeable with the calibration calls, a new genuine call is blocked with probability at most alpha, averaged over calibration draws. For one fixed calibration set the realised false-block rate is random (Beta-distributed; about half of calibration draws exceed alpha at n of about 900), so the observed 3.7% and 7.3% below budgets of 5% and 10% are partly due to score ties and chance, not evidence of beating the guarantee. A high-probability (calibration-conditional) version needs a more conservative order statistic. The guarantee does not cover detection, precision at low error prevalence, or distribution shift. A 2% budget is infeasible at this stage (about 7% of genuine calls contain values the context never states). Caveats: the injected errors are synthetic substitutions, conversations are LLM-generated, the baseline is our own reimplementation, and the held-out half was run twice (before and after fixing a regex bug found by a unit test). Reproduce: `python benchmarks/make_argground_bench.py --pages 40 --seed 5` then `PYTHONPATH=. python benchmarks/eval_argground.py --split test`.

**Natural (model-made) errors: exploratory, dev half only.** On the public DeRef data (Ma et al., arXiv 2610.18497; `lm2445/DeRef`, Apache-2.0; BFCL-based `fcrb`, ComplexFuncBench-based `cfb`) the call score separates wrong from correct calls at roughly chance level: call-level AUROC 0.48 (fcrb, 630 calls) and 0.56 (cfb, 507 calls); at tau 0.88, 52% / 43% of *correct* calls would be blocked and 44% / 50% of wrong calls (`benchmarks/eval_deref.py`, `benchmarks/explore_deref_dev.py`). Reasons: many wrong values are visible in the context but are the wrong choice (a grounding check cannot see this), and many correct values have no textual source (translation, defaults, inferred), so "unsupported" does not mean "wrong" (only 44% / 62% of unsupported values are wrong, per the dataset's own path labels). The injected-error result above therefore applies only to injected absent-value substitutions. A bug was found and fixed: the number matcher ignored minus signs, so negative values such as longitudes were flagged even when verbatim in the context (19% of cfb "visible" correct arguments); after the fix 0% are flagged, cfb scoring takes 12 s instead of 9 min, and the call-level AUROC is 0.57 (cfb) and 0.48 (fcrb), so the conclusion is unchanged. The ArgGround-Bench test-half numbers above were computed before this fix (dev-half false-block rate 7.0% became 6.8%); they will be recomputed once, and logged, in the final protocol. No LLM judge has been run yet; the closest paper reports plain-input judge argument AUROC of 72.5 to 91.95 on fcrb and 63.4 to 78.9 on cfb.

### External: LLM-AggreFact test split (NLI component only, no GED)

Full test split, 29,320 claims, 77.9% labelled supported (so always answering "supported" scores 77.9% accuracy but 0.50 balanced accuracy). Run on a Kaggle T4 with `kaggle/aggrefact_windowed_eval.ipynb`; summary in `benchmarks/kaggle_full_run_summary.json` (numbers verified against the executed notebook outputs; the notebook's own `aggrefact_windowed_results.json` is the authoritative record).

| Setting | Threshold | Bal. acc. | AUROC | Precision | Recall |
|---|---|---|---|---|---|
| Truncation at 512 tokens (earlier CPU run, templated claims) | 0.40 | 0.585 | 0.675 | 0.892 | 0.294 |
| Truncation at 512 tokens, raw claims, dev-calibrated (Kaggle) | 0.002 | 0.616 | 0.672 | 0.856 | 0.568 |
| Windowed 180/40 words, fixed | 0.40 | 0.636 | 0.745 | 0.925 | 0.380 |
| Windowed 180/40 words, dev-calibrated | 0.005 | 0.673 | 0.745 | 0.886 | 0.633 |

Like-for-like (same model, raw claims, dev-calibrated thresholds), windowed minus truncation: AUROC +0.0725 (paired bootstrap 95% CI 0.068 to 0.077), balanced accuracy +0.057 (95% CI 0.051 to 0.063). AUROC 95% CI for the windowed scorer: 0.738 to 0.751. The dev-calibrated threshold is extreme (0.005), which indicates strongly peaked scores, so AUROC is the more robust figure. Per-source AUROC ranges from 0.92 (Reveal) to 0.59 (ExpertQA); RAGTruth (0.66) is 56% of the test split. A seeded 500-claim laptop sample gives AUROC 0.740 (`PYTHONPATH=. python benchmarks/aggrefact_sample.py --n 500 --seed 42`, about 35 minutes on CPU).

This external run evaluates only the DeBERTa NLI component; it says nothing about the GED stage. **MiniCheck baseline** (flan-t5-large; the full split would take about 8 hours on a T4, and a first attempt at batch 16 ran out of GPU memory, so it was scored on a seeded stratified subset: 3,000 dev claims for thresholds, 5,000 test claims, batch 4). All three systems use exactly the same rows:

| System | Bal. acc. [95% CI] | AUROC [95% CI] | Precision | Recall |
|---|---|---|---|---|
| A: DeBERTa-v3-base, truncation | 0.617 [0.600, 0.633] | 0.674 [0.656, 0.693] | 0.856 | 0.572 |
| B: DeBERTa-v3-base, windowed 180/40 | 0.666 [0.649, 0.682] | 0.744 [0.727, 0.760] | 0.863 | 0.754 |
| C: MiniCheck flan-t5-large | 0.746 [0.731, 0.760] | 0.821 [0.807, 0.836] | 0.914 | 0.734 |

Paired bootstrap on AUROC: B minus A +0.069 (95% CI 0.059 to 0.079); B minus C -0.078 (95% CI -0.095 to -0.059). Windowing closes about half of the gap between truncation and MiniCheck; the rest is clear. Cost on a T4: about 0.40 s per claim for MiniCheck vs 0.028 s for windowed DeBERTa (roughly 14 times slower).

---

### Current research findings (development halves, exploratory)
The deterministic argument checker is a cheap first stage for values that are absent from the context, but on natural tool-call errors LLM judges (Groq gpt-oss, Claude Haiku/Sonnet/Opus) clearly beat it. Detection of natural errors is limited by the information available to the verifier: giving a judge the tool definition raises detection by 16 to 20 points, while model size matters little. Cross-model agreement is a strong but costly signal whose advantage over a schema-aware judge is not statistically established. Full tables, caveats and corrections: `review/EXPERIMENTS_2026-10-30.md`, `review/DEV_PILOT_RESULTS.md`, `review/INFORMATION_ABLATION_FINDINGS.md`, `review/CONSENSUS_FINDINGS.md`. The plan for the next phase is `review/NOVEL_PROJECT_PLAN.md`.

## What Can It Detect?

### Via `verify_logic_chain` (text-based semantic pipeline)

| Hallucination | Example | Detection Signal |
|---|---|---|
| Numeric mutation | `$50 → $500` | GED value-node cost (1.0) + entailment |
| **Negation mismatch** | `did NOT transfer` vs `transferred` | GED negation cost (1.0) |
| **Role swap** | `Alice paid Bob` vs `Bob paid Alice` | GED AGENT/PATIENT edge labels |
| Version drift | `v2.4.0 → v2.4.1` | GED value-node cost + entailment |
| Temporal shift | `Monday → Tuesday` | GED DATE-kind cost + entailment |
| Action mismatch | `delete` vs `read` | GED predicate cost + entailment |
| Entity substitution | `Alice → Bob` | GED + entailment |

### Via `verify_schema_alignment` (deterministic JSON Schema validation)

| Hallucination | Example | Detection Signal |
|---|---|---|
| Missing schema field | absent required arg | SCHEMA mismatch |
| Type violation | `"five"` where `integer` expected | FORMAT mismatch |
| Enum violation | value not in allowed set | FORMAT mismatch |
| Pattern violation | string doesn't match regex | FORMAT mismatch |
| Range violation | number outside min/max | FORMAT mismatch |

> **Note on content-type hallucinations**: The text pipeline (`verify_logic_chain`) works
> best on natural-language fact pairs. For tool-call argument validation, prefer
> `verify_schema_alignment` with explicit `agent_args` and `tool_schema` inputs.

---

## Architecture

```
LLM Agent
   │
   │  verify_logic_chain(hypothesis, premise)
   ▼
FastMCP Server (async STDIO)
   │
   ├── SRL Pipeline      (BERT-NER + spaCy value NER → predicate-arg frames)
   │     note: uses dslim/bert-base-NER + spaCy dep-parse heuristic,
   │           not a full AllenNLP predicate-argument SRL model
   │     └─ lru_cache(512) on extract_frames
   ├── Dep. Parser       (spaCy + AGENT/PATIENT/RECIPIENT semantic role mapping)
   │     └─ lru_cache(512) on extract_dep_triples
   ├── Negation Detector (spaCy neg dep → marks predicates negated=True)
   ├── Graph Builder     (NetworkX DiGraph, lru_cache(512))
   ├── GED Alignment     (scipy linear_sum_assignment O(n³), value-aware cost model)
   │     └─ value kinds (MONEY/DATE/VERSION/…) cost 1.0 on any substitution
   │     └─ post-normalisation value-mismatch bonus (+0.20 per unmatched value node)
   ├── Entailment        (DeBERTa NLI cross-encoder, batched, span-aware templates)
   │     └─ stop-predicate filter removes generic verbs from span checking
   ├── Taxonomy          (schema / format / content typed classification)
   ├── Constraints       (numeric/entity extraction from user_query)
   └── Session Tracker   (LRU-evicting deque, TTL expiry, background cleanup)
   │
   ▼
FactualConsistencyReport { score, mismatched_spans, feedback }
```

### Key design decisions

**Value-node exact-match semantics**: Numeric, currency, version, date, and temporal
spans are typed as `VALUE` kinds in the semantic graph. Substituting `$50` with `$500`
(or `v2.4.0` with `v2.4.1`) incurs the maximum node cost (1.0) and an additional
post-normalisation penalty, preventing large graphs from diluting numeric mutations.

**Negation detection**: Predicate nodes carry a `negated` boolean. GED assigns
cost 1.0 when a negated predicate is compared against a non-negated one with the
same lemma — `did NOT transfer` vs `transferred` is maximally inconsistent.

**Role-swap detection**: Dependency labels are mapped to semantic roles
(nsubj→AGENT, dobj→PATIENT, iobj→RECIPIENT) so `Alice paid Bob` and `Bob paid Alice`
produce topologically different graphs that GED can distinguish.

**Hungarian optimal matching (P5)**: Node assignment uses `scipy.optimize.linear_sum_assignment`
(true O(n³) Hungarian algorithm) instead of greedy sort-based matching, with a greedy
fallback if scipy is unavailable.

**Stop-predicate filter**: Generic function verbs (`call`, `pass`, `use`, `be`, etc.)
are excluded from DeBERTa entailment checking. They appear in almost every sentence
and produce high false-positive rates against short schema-description premises.

---

## Project Layout

```
mcp-hallucination-checker/
├── server/
│   ├── main.py              # FastMCP server + background session cleanup timer
│   ├── config.py            # Loads configs/thresholds.yaml
│   ├── tools/
│   │   ├── verify_logic.py  # verify_logic_chain orchestration
│   │   └── schema.py        # verify_schema_alignment (full JSON Schema subset)
│   ├── pipeline/
│   │   ├── srl.py           # BERT-NER + spaCy value NER → predicate-arg frames
│   │   ├── dep_parser.py    # Dep parsing + AGENT/PATIENT role mapping (lru_cache)
│   │   ├── negation.py      # Negated predicate detection via `neg` dep edges
│   │   ├── graph_builder.py # Semantic graph (negation-tagged, lru_cache)
│   │   ├── ged.py           # GED: scipy Hungarian + value-aware cost model
│   │   ├── entailment.py    # DeBERTa NLI, batched, exact-value hypothesis templates
│   │   ├── constraints.py   # Constraint extraction from user_query
│   │   └── taxonomy.py      # schema | format | content classifier
│   ├── models/
│   │   └── schemas.py       # Pydantic I/O schemas
│   └── session/
│       └── tracker.py       # LRU-evicting session deque (TTL + MAX_SESSIONS)
├── benchmarks/
│   ├── ablation_local.py    # NLI-only / GED-only / hybrid ablation (fixed thresholds)
│   ├── aggrefact_sample.py  # Seeded AggreFact subsample: truncation vs windowed NLI
│   ├── make_argground_bench.py  # ArgGround-Bench builder (public function-calling conversations + injected errors)
│   ├── eval_argground.py    # exact vs type-aware vs conformal-calibrated argument grounding
│   ├── make_mcpevol_v2.py   # Seeded generator for larger template-based tool-call cases (v2/v3)
│   ├── eval_grounded.py     # Evaluates the grounded mode (raw NLI + value check)
│   ├── llm_judge_eval.py    # LLM-as-judge baseline (needs ANTHROPIC_API_KEY; not yet run)
│   ├── mcpevol.json         # 60-case labelled evaluation dataset
│   │                        # content: text-pair cases
│   │                        # format/schema: include agent_args + tool_schema
│   ├── mcpevol_runner.py    # Evaluation harness
│   │                        # routes format+schema → verify_schema_alignment
│   │                        # routes content → verify_logic_chain
│   └── threshold_sweep.py   # GED threshold calibration script
├── tests/
│   ├── test_pipeline.py     # SRL + graph unit tests
│   ├── test_negation.py     # Negation cost, GED integration, role-swap tests
│   ├── test_ged.py          # GED unit tests + value-node cost model tests
│   ├── test_server.py
│   ├── test_constraints.py
│   ├── test_taxonomy.py
│   ├── test_session.py
│   ├── test_schema_alignment.py
│   ├── test_properties.py   # 12 property-based tests (Hypothesis)
│   └── test_integration.py  # End-to-end gold-label tests (real models)
├── configs/
│   └── thresholds.yaml      # GED threshold (0.35), entailment cutoff (0.40)
├── .github/workflows/
│   └── ci.yml               # CI: pytest (3 Python versions) + ruff lint
├── pyproject.toml
├── requirements.txt
├── kaggle/                  # GPU notebooks: windowed AggreFact eval (+MiniCheck), MCPEvol ablation
└── Makefile                  # make test / lint / bench / sweep / clean
```

---

### Research tooling added in October 2026 (not part of the shipped server)
`benchmarks/llm_judge_args.py` (Groq, NVIDIA, Gemini, Anthropic, OpenRouter, custom providers), `agent_judge.py` (judges run as Claude subagents), `run_judge_panel.py`, `contract_tier.py`, `decidability.py`, `ask_policy.py`, `analyze_*.py`, `measure_cost.py`, data builders (`load_deref.py`, `load_bfcl_consensus.py`, `make_ablation_benches.py`, `taubench_state_probe.py`). How to rerun each experiment: `handoff/09_PIPELINES_HOWTO.md`; file map: `handoff/04_FILE_MAP.md`; review documents: `review/README.md`.

## Setup & Quickstart

```bash
# 1. Install (editable + dev extras)
pip install -e ".[dev]"

# 2. Download ML models
make download-models

# 3. Run MCP server
python server/main.py
```

Configure in Claude Desktop or any MCP client:
```json
{
  "mcpServers": {
    "hallucination-checker": {
      "command": "python",
      "args": ["server/main.py"]
    }
  }
}
```

---

## Configuration

Edit `configs/thresholds.yaml`:

```yaml
# GED normalised score above this → reasoning chain flagged as inconsistent
# Lower = more sensitive (more hallucinations caught, higher false-positive risk)
# Run `make sweep` to find the optimal value for your dataset.
ged_threshold: 0.35

# Entailment probability below this → span flagged as mismatched
# Lowered from 0.50 to 0.40 to reduce false positives on borderline spans.
entailment_threshold: 0.40

# Max nodes before switching to fast structural GED approximation
ged_fast_mode_node_limit: 80
```

To find the best GED threshold for your dataset:

```bash
make sweep
# or directly:
python benchmarks/threshold_sweep.py --dataset benchmarks/mcpevol.json
```

---

## Benchmark & Evaluation

The `benchmarks/mcpevol.json` dataset contains 60 labeled cases:

- **content** (25 cases): natural-language fact pairs — tested via `verify_logic_chain`
- **format** (13 cases): type/constraint checks with `agent_args` + `tool_schema` — tested via `verify_schema_alignment`
- **schema** (12 cases): missing-field checks with `agent_args` + `tool_schema` — tested via `verify_schema_alignment`
- **negation** (5 cases): positive/negative meaning changes — tested via `verify_logic_chain`
- **role_swap** (5 cases): reversed semantic roles — tested via `verify_logic_chain`

Schema and format records require explicit typed inputs:

```json
{
  "id":          "T24",
  "hypothesis":  "Calling create_order with product_id=88.",
  "premise":     "Tool schema requires fields: product_id (integer), quantity (integer), address (string).",
  "label":       false,
  "type":        "schema",
  "agent_args":  { "product_id": 88 },
  "tool_schema": {
    "required":   ["product_id", "quantity", "address"],
    "properties": {
      "product_id": { "type": "integer" },
      "quantity":   { "type": "integer" },
      "address":    { "type": "string" }
    }
  }
}
```

Run the evaluation harness:
```bash
make bench
# or with verbose per-case output:
python benchmarks/mcpevol_runner.py \
    --dataset benchmarks/mcpevol.json \
    --verbose
```

  For a manually downloaded LLM-AggreFact shard, avoid another Hub download:
  ```bash
  make bench-external-local
  # or explicitly:
  python benchmarks/external_eval.py \
    --source local \
    --local-dir . \
    --split test \
    --output benchmarks/aggrefact_local_results.json \
    --verbose
  ```

  The local MCPEvol-Bench file is a project-specific smoke-test benchmark. It is
  not an independent measure of generalization. For an independently sourced
  grounded-fact evaluation, install the optional loader and run the public
  LLM-AggreFact test split:

  ```bash
  make install-benchmark
  make bench-external-public
  ```

  The public dataset is `lytang/LLM-AggreFact` (CC-BY-ND-4.0), with `dev` and
  `test` splits containing `doc`, `claim`, and `label` fields. Hugging Face may
  require account approval for access. Use `--limit N --seed 42` for a
  deterministic smoke run; report full test-split results separately from sampled
  development runs. The evaluator records source metadata in its JSON output.

---

## Testing

```bash
# Fast: unit + property-based tests (models mocked, no download needed)
make test

# All including end-to-end (requires downloaded models)
make test-all
```

### Test Suite Summary

| File | Coverage |
|---|---|
| test_pipeline.py | SRL frames, value-span enrichment, graph construction |
| test_negation.py | Negation cost model, GED negation integration, role-swap topology |
| test_ged.py | GED unit tests + value-kind cost model + numeric/version mutation detection |
| test_constraints.py | Constraint extraction and scoring |
| test_taxonomy.py | Hallucination type classification |
| test_schema_alignment.py | Schema drift score, format/schema type classification |
| test_session.py | Rolling mean, drift alert, TTL/window behaviour |
| test_server.py | End-to-end MCP tool call (mocked models) |
| test_properties.py | 12 Hypothesis property-based invariant tests |
| test_integration.py | Real-model end-to-end gold-label tests |

Total: **70 tests** (62 unit/property + 8 integration).

---

## Session Drift Detection

Pass a `session_id` to `verify_logic_chain` to enable drift tracking.
The server maintains a rolling window of factual consistency scores per session.
`drift_alert=true` is returned when the rolling mean drops below the configured
`entailment_threshold` — indicating the agent's reasoning quality is degrading
over the course of a multi-step plan.

**Memory management**: Sessions are evicted via LRU when the pool exceeds
10,000 entries, or via TTL (1 hour of inactivity) during the background
cleanup pass that runs every 5 minutes.

---

## Schema Alignment — Supported Constraints

`verify_schema_alignment` validates against the following JSON Schema constraints:

| Constraint | Example |
|---|---|
| `required` presence | missing field → SCHEMA mismatch |
| `type` | `"five"` for `integer` → FORMAT mismatch |
| `enum` | value not in `["low","medium","high"]` → FORMAT mismatch |
| `pattern` | email doesn't match `^[^@]+@[^@]+$` → FORMAT mismatch |
| `minLength` / `maxLength` | string too short/long → FORMAT mismatch |
| `minimum` / `maximum` | number out of range → FORMAT mismatch |
| Optional field type | optional field present with wrong type → FORMAT mismatch |

---

## Known Limitations

**Content-type false negatives**: The GED threshold (0.35) is calibrated for clear
structural mutations. Paraphrases of consistent facts (T01, T04, T06) score
above the threshold because their graphs are structurally similar — this is
expected behaviour rather than a bug.

**Stop-predicate filter tradeoff**: Filtering generic verbs (`call`, `use`, etc.)
from entailment checking eliminates false positives on schema-description premises
but also reduces sensitivity to action-verb mutations like `delete` vs `read`
(T08). If your domain relies heavily on action-verb detection, remove those verbs
from `_STOP_PREDICATES` in `server/tools/verify_logic.py`.

**SRL approximation**: The "SRL" pipeline uses `dslim/bert-base-NER` (an NER model)
plus spaCy dependency-parse heuristics to assign role labels, rather than a true
predicate-argument SRL model. Named-entity roles (PER, ORG, LOC) and value spans
(MONEY, DATE, CARDINAL) are well-covered; general verb arguments (ARG0, ARG1) are
inferred from dependency structure only.
