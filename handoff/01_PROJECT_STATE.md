# 01 Project state (rewritten 2026-10-31)

## What the system is
An MCP server (`server/main.py`, FastMCP) exposing tools an agent can call before acting, plus a proxy that can enforce them. Research prototype; not production-validated.

### Tools (MCP)
| Tool | Module | What it does |
|---|---|---|
| `verify_logic_chain` (mode `hybrid`, default) | `server/tools/verify_logic.py` | NER + dependency "SRL-style" frames, semantic graph, value-aware GED, span-level NLI, taxonomy, constraints, session drift. **Performs poorly** (see below) |
| `verify_logic_chain` with `mode="grounded"` | `server/tools/verify_grounded.py` | consistent iff whole-claim windowed NLI >= 0.40 AND every number-like token occurs in the source AND query constraints are preserved |
| `verify_schema_alignment` | `server/tools/schema.py` | deterministic JSON-Schema subset validation (required, type, enum, pattern, range, length) |
| `verify_argument_grounding` | `server/tools/verify_arguments.py`, `server/pipeline/arg_ground.py` | per-argument, type-aware matching of each value against the conversation; call score = weakest argument; block iff score < tau (conformal threshold) |

### Proxy (`server/proxy/interceptor.py`)
`InterceptingToolProxy(tool_fn, tool_schema, risk_level, logic_mode, arg_tau, ...)`. Tiers LOW (no checks), MEDIUM (schema), HIGH (schema, then logic). `logic_mode` is `hybrid` (default), `grounded` or `arguments`. The HIGH-tier logic check only runs when source context is supplied, otherwise only the schema check applies (**fails open**). `@guarded` enforces nothing unless calls go through `proxy.call()`.

### Research tooling added since 2026-10-16 (not part of the shipped server)
Judge harness (`benchmarks/llm_judge_args.py`, `judge_prompts.py`, `agent_judge.py`, `run_judge_panel.py`), analyses (`analyze_study.py`, `analyze_cascade.py`, `analyze_consensus.py`, `compare_consensus_judge.py`, `analyze_schema_ablation.py`, `ask_policy.py`, `decidability.py`, `measure_cost.py`), data builders (`load_deref.py`, `load_bfcl_consensus.py`, `make_ablation_benches.py`, `taubench_state_probe.py`), the contract tier (`contract_tier.py`, `contract_complement.py`). Full list: `handoff/04_FILE_MAP.md`.

## Where each verification idea stands
| Idea | Status | Evidence |
|---|---|---|
| Hybrid (GED + span NLI) | default only for backward compatibility; **near chance** | 52.8% on 214 held-out generated cases; the `origin/Case1` variant is statistically identical (53.7%) |
| Grounded text mode | implemented, preliminary | 95.3% on held-out generated cases (94.4% for raw NLI alone) |
| Argument-level grounding | implemented | injected absent-value errors: 7.3% false blocks vs 14.0% exact match at 96.5% detection (test half, computed before the minus-sign fix; to be recomputed once); on natural errors near chance |
| Contract tier | new, research tool | 16% false blocks, 22-26% detection on fcrb; complements judges |

## Verified numbers (development halves unless marked; protocols in `handoff/02`, summary in `review/EXPERIMENTS_2026-10-30.md`)
| Result | Value |
|---|---|
| Natural errors (DeRef fcrb dev, 200 seeded cases): checker | 56.4% false blocks, 43.4% detection |
| Same, judges (false blocks / detection) | Groq gpt-oss-20b 37.2 / 54.7; gpt-oss-120b 31.9 / 59.4; Claude Haiku 28.7 / 52.8; Sonnet 9.6 / 53.8; Opus 17.0 / 54.7 |
| Injected errors (200 cases): checker vs judges | 6.9 / 98.0 vs 2.0-11.9 / 97.0-100: tie |
| Cost and speed | checker 0.3-0.9 ms and no tokens; hosted judge about 1.1 s and 520 tokens per call |
| Information ablation (168 fcrb calls with a definition) | detection 50.0 / 51.2 / 53.5% -> 66.3 / 70.9 / 72.1% (Haiku / Sonnet / Opus) |
| Cross-model consensus (BFCL, 30 models, 200 cases) | AUROC 0.93; vs Opus+definition on 924 calls 56.0% vs 45.9% detection at about 8% false blocks, CI -0.14 to +0.31 |
| Ask-policy (5,427 BFCL calls, 1,000 re-splits) | plain conformal within budget in 57-62% of splits; cluster bootstrap >99% but detection 14/33/61% at budgets 5/10/20% |
| tau-bench state lookup | 0 of 538 environment-accepted errors caught |
| LLM-AggreFact full test split NLI only: truncation vs windowed AUROC | 0.672 vs 0.745 (paired +0.0725, CI 0.068 to 0.077) |
"FBR" = false-block rate (correct calls wrongly blocked); "detection" = share of wrong calls blocked.

## What is NOT done
No test-half result for any new experiment; no human label audit; API judges only from Groq and NVIDIA (no Anthropic API, OpenRouter, Gemini usable); judges in agent mode are batched; no live-MCP or deployed evidence; no real agent self-consistency; guarantee not written up or tested under shift; deck/speaker guide/README claims partly outdated; nothing committed since 2026-10-16.

## Deliverables for the user's project review (older)
Deck `review/MCP_Hallucination_Checker_Review_v9.pptx` and `review/SPEAKER_GUIDE.md/.pdf` match the **old** claims; do not present them as current without updating (the user asked to leave them for now).
