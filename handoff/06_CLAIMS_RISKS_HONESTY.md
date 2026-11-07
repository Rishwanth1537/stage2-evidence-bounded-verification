# 06 Claims, risks and honesty (rewritten 2026-10-31)

## Claims that may be made today (each with its status)
| Claim | Status |
|---|---|
| On natural tool-call errors (DeRef fcrb) LLM judges of several sizes and providers beat a deterministic context checker; on errors we injected themselves they tie it | dev, exploratory; 200 seeded cases, paired tests |
| Judge detection of natural errors sits at about 50-55% for Claude Haiku/Sonnet/Opus and Groq gpt-oss and rises to 66-72% when the tool's own definition is shown | dev, agent-mode Claude judges, n = 168; Groq/NVIDIA ladder pending |
| The checker is about three to four orders of magnitude faster than a hosted judge call and uses no tokens | measured, with the caveat that it compares a local function with a network call |
| As a first stage the checker saves most judge calls only when errors are values absent from the context | injected set only |
| State lookups caught none of the natural errors the environment accepted on tau-bench (two strong agents, old task set) | measured |
| On the human-attributed AgentHallu BFCL slice (31 positives, registered before running) the deterministic context checker detects 58.1% at 12.9% false blocks and none of five judges (Claude Opus/Sonnet/Haiku, Nemotron 550B/4B: 32-48%) beats it; low power, so "competitive", not "better" | confirmatory, `review/PAPER_PLAN_V2.md` section 14 |
| Cross-model agreement separates wrong arguments well on BFCL (AUROC 0.93) | exploratory; partly measures format convention; costs 29 extra model calls |

## Claims that must NOT be made
- That the deterministic checker detects hallucinated tool calls as well as, or better than, LLM judges.
- That weakest-argument scoring, traceability to context, provenance checking or conformal budgets for verifiers are ours (prior art: Ma et al. 2610.18497, ProvenanceGuard 2607.01236, PACT/ROPE/SARA, Saidso, E-valuator/CORA/ConformalGuard).
- "Novel", "first", "state of the art", "validated", "production-ready", "immune to prompt injection".
- That cross-model consensus beats a schema-aware judge (difference not significant).
- That the guarantee "held": it is marginal; per-split it is exceeded in 38-43% of draws with the plain rule; the cluster-aware rule costs about half the detection.
- That any number is confirmatory: no test half of the new experiments has been read.
- Any BFCL-based number computed on unfiltered labels (63% of BFCL 'wrong' arguments are format variants or optional arguments; use the strong-error versions, `review/PAPER_PLAN_V2.md` section 12).
- Anything that rests on `HuanzhiMao/BFCL-Result` (not reachable) or on `origin/Case1` results.

## Known weaknesses
1. Dev data inspected repeatedly (forking paths); locked test pending; BFCL fully explored so it cannot be the test.
2. Labels come from benchmark gold; BFCL gold partly enforces schemas and formats (circularity for contract-tier gains); no human audit yet.
3. Agent-mode judges: batches of 25, no temperature control, a one-sentence rule added in the with-definition condition (prompt variant S, Deviation 11), the Opus cfb run compared sibling items.
4. Small samples (judge-vs-consensus: 109 wrong calls; information ablation: 168 calls) with wide intervals.
5. Our injected errors are our own design and flatter the checker.
6. Model and API behaviour drifts; free-tier limits shaped sample sizes (cfb: 100 cases, 3,000-character contexts).
7. AgentSuite BFCL outputs have no declared licence.
8. Silent fallbacks in the code base (spaCy trf to sm; other branches' offline fallbacks) can hide degradation.

## Pre-registration discipline
`review/PREREGISTRATION.md` holds the frozen protocol and the deviations log (12 entries plus amendment 12b). Every prompt variant, new hypothesis, or look at a test half is recorded before use; `benchmarks/test_run_ledger.jsonl` lists every test-half access (one accidental look at fcrb deterministic argument rates is logged).

## Safe wording for the project
> A pre-execution gate for MCP tool calls, and a measurement study of what evidence decides whether a tool-call argument is wrong: judges are limited by the information they are given more than by their size, a cheap deterministic stage is useful for values absent from the context, and the errors that no available evidence decides call for asking the user, with a calibrated budget on interruptions. Results are preliminary development-set findings.
