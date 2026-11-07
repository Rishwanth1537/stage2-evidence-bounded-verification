# Novelty Check: MCP Hallucination Checker

Date of check: 2026-10-01. Scope: read-only review; no other project file was edited.

**Bottom line.** No single component is novel. Every ingredient has a clear antecedent: AMR/semantic-graph factuality (2022-23), graph + NLI localisation (GraphEval, 2024), NLI grounding checkers (SummaC, AlignScore, MiniCheck), pre-execution tool-call firewalls with JSON-Schema validation (many OSS repos, AEGIS 2026), tool-hallucination taxonomies and benchmarks with schema validators (arXiv 2609.19425, SAAG 2607.18245), and asymmetric hypothesis-in-premise dependency-graph matching with negation and numeric-mismatch checks (Haghighi, Ng, Manning, 2005). The defensible contribution is a **system-level integration plus an honest evaluation**, and only if the evidence in section 4 is produced. The current evidence (60 self-written cases; LLM-AggreFact balanced accuracy 58.5%, recall 29.4% in the pre-windowing full run) does not support any "state-of-the-art" or "novel method" claim.

## How this was researched (tool caveat)

WebSearch and WebFetch failed in this session (model error: "gemini-2.5-flash-lite[1m] ... may not exist"). I fetched primary sources directly with curl instead: arXiv API and PDFs (converted with pdftotext), the ACL Anthology PDF, the GitHub REST search API, and raw GitHub READMEs. Coverage is limited to what arXiv-API and GitHub-API keyword queries surfaced; Semantic Scholar was rate-limited. This is NOT an exhaustive survey; absence of a prior work below is not proof that none exists. Section 5 lists exactly what was read vs. only seen as snippets.

---

## 1. Related-work table

### 1a. Graph / semantic-structure factual consistency

| Work | Year / venue | What it actually does (verified) | Overlap with this project | How this project differs |
|---|---|---|---|---|
| Robust Textual Inference via Graph Matching (Haghighi, Ng, Manning) https://aclanthology.org/H05-1049/ | 2005, HLT/EMNLP | Dependency graphs for text T and hypothesis H. Entailment = low cost of matching **H's graph into T's graph**. Vertex cost (lexical, WordNet incl. an asymmetric hypernym feature) plus relation cost; learned weights. Has an explicit **negation check**, factive check, superlative check, and a **numeric-mismatch** note. RTE-1 accuracy about 56.8%. Notes subgraph matching is hard and approximated. | Asymmetric hypothesis-in-premise graph matching, negation, numeric mismatch, relation preservation: essentially your "future contribution" and your negation/value rules. | Modern parser/NER, DeBERTa NLI stacked on top, applied to agent reasoning. The technique is 20 years old. |
| Recognizing Textual Entailment with Tree Edit Distance (Kouylekov and Magnini) | 2005-06 (title/year seen only in a Semantic Scholar listing; abstract NOT read) | Tree edit distance over dependency trees for RTE. | Edit distance over syntactic structure for entailment. | Yours is graph-based and value-aware; same family. |
| FactGraph (Ribeiro et al.) https://arxiv.org/abs/2204.06508 | NAACL 2022 | Parses document and summary to AMR graphs; graph encoder with structure-aware adapters plus text encoder; learned classifier; edge-level (FactGraph-E) error localisation; uses Smatch(AMR) overlap as a baseline metric. | Semantic graph of source vs. claim for factual consistency; localisation of unsupported parts. | Learned model vs. your training-free heuristic GED. Summarization benchmarks, not agent/tool setting. |
| AMRFact (Qiu et al.) https://arxiv.org/abs/2311.09521 | NAACL 2024 (per arXiv comment) | Uses AMR graphs to **generate** perturbed inconsistent summaries as training negatives; NegFilter via NLI + BARTScore; trains a classifier; evaluated on AggreFact-SOTA. | AMR graph manipulation to model error types. | Graphs used for data generation, not runtime matching. |
| Dependency-level entailment, DAE (Goyal and Durrett) https://arxiv.org/abs/2010.05478 | 2020 (abstract read; venue not verified) | Decomposes entailment to dependency arcs to **localise** non-factual parts of a generation. | Arc/span-level localisation with entailment. | You use span-level NLI templates; DAE trains an arc-level classifier. |
| GraphEval (Sansford et al.) https://arxiv.org/abs/2407.10793 | 2024 (arXiv; venue not verified) | LLM extracts a KG of triples from the response; each triple checked by an off-the-shelf NLI model against the context; flags specific hallucinated triples; balanced-accuracy gain over raw NLI; GraphCorrect for repair. | **Closest** prior work to "structure + NLI to localise unsupported spans". | LLM-extracted triples, no graph distance, no value-strict cost, no schema or tool-call gate. Yours: parser graphs + GED score + NLI. |
| AMREx https://arxiv.org/abs/2411.01343 | 2024 | Smatch-based AMR comparison of claim vs. evidence plus rules/explanations for FEVER and AVeriTeC. | Graph-overlap scoring for verification. | Different task (claim verification vs. retrieved evidence). |
| "When Does Meaning Backfire?" AMRs in NLI https://arxiv.org/abs/2506.14613 | 2025 | AMR in fine-tuning hurts generalisation; prompting gives slight gains from amplifying surface differences, which can mislead toward non-entailment. | Cautionary evidence relevant to your paraphrase false positives (T01, T04, T06). | n/a |

### 1b. NLI / grounding checkers

| Work | Year / venue | What it does | Overlap | Difference |
|---|---|---|---|---|
| SummaC https://arxiv.org/abs/2111.09525 | TACL 2022 | Sentence-level NLI score matrices aggregated for summary inconsistency. | NLI grounding; segmenting documents. | You score spans/windows, no matrix aggregation. |
| AlignScore https://arxiv.org/abs/2305.16739 | ACL 2023 | Unified alignment model trained on many tasks; chunked context. | Learned grounding score. | Strong baseline you have not run. |
| MiniCheck https://arxiv.org/abs/2404.10774 | EMNLP 2024 | Small checkers trained on GPT-4-generated synthetic data; claim vs. multi-sentence documents; introduces **LLM-AggreFact**. | Your external eval uses LLM-AggreFact; MiniCheck is the natural baseline. | You use DeBERTa-v3-base NLI (STATUS.md says not MiniCheck-large). Your full-test pre-windowing result (acc 42.3%, balanced acc 58.5%, precision 89%, recall 29%) is weak relative to a purpose-built checker (I did not retrieve MiniCheck leaderboard numbers). |

### 1c. Tool-call / agent hallucination and pre-execution gates

| Work | Year / venue | What it does | Overlap | Difference |
|---|---|---|---|---|
| Internal Representations as Indicators of Hallucinations in Agent Tool Selection (Healy et al.) https://arxiv.org/abs/2601.05214 | arXiv Jan 2026 | Lightweight classifier on last-layer hidden states at function-name / argument / end tokens in the same forward pass; Glaive-derived dataset; Llama-3.1-8B, Qwen-7B; up to 86.4% accuracy; baselines are multi-sample consistency (NCP, semantic similarity); gates execution. | Real-time pre-execution tool-call hallucination detection. | White-box and learned; yours is black-box, model-agnostic. Not comparable without a shared dataset. |
| AgentHallu https://arxiv.org/abs/2601.06818 | arXiv Jan 2026 | 693 trajectories, 5 categories / 14 sub-categories (Tool-Use: missing tool, incorrect argument, parallel conflict, irrelevant tool); task is attributing the responsible step; best model 41.1% step localisation, tool-use 11.6%. | Benchmark with a tool-use hallucination category. | Post-hoc attribution, not pre-execution gating. Good external test set candidate. |
| Closed-World Resolution Against Tool Hallucination (Iyer) https://arxiv.org/abs/2609.19425 | arXiv Sep 2026 | Taxonomy H1-H5 (nonexistent tool, undeclared/missing args, type/enum/range violation, off-frontier tool, borrowed signature). Training-free registry + signature type-check resolver placed before any gate. Ten-model live study (322 hallucinations). **MCP extension (M1-M5)**. Releases Hallucinated-Tools Benchmark (HTB) with a JSON-schema-validator baseline. States the check is "intentionally trivial ... we do not claim the check is novel". | Deterministic schema/type/enum/range check before execution, at the MCP layer, with a released benchmark. | **Directly undercuts novelty of verify_schema_alignment and of a tool-call benchmark claim.** Has no content/reasoning grounding (no GED/NLI). |
| SAAG https://arxiv.org/abs/2607.18245 | arXiv 2026 | Cascade: registry conformance, structural completeness (schema), **argument value grounding** (exact match of argument values against the user query, flags numeric hallucination); structured feedback for repair; Glaive-derived benchmark; sub-4B models. | Staged schema check followed by value grounding; value-strict flavour. | Exact-match grounding, no graph/NLI; an evaluation/repair framework, not an MCP gate. |
| AEGIS https://arxiv.org/abs/2603.12621 | arXiv Mar 2026 | Pre-execution firewall: argument string extraction, content risk scanning, policy validation, human approval, signed audit trail; 14 frameworks; 48 attacks, 500 benign calls, 8.3 ms median overhead. | Pre-execution interception with risk handling. | Security-focused, not factual grounding. |
| AgentGuardian https://arxiv.org/abs/2601.10440 | arXiv Jan 2026 | Learns access-control policies from traces to govern tool calls. | Policy gate on tool calls. | Access control, not hallucination checking. |
| SimpleToolHalluBench 2510.22977; Verifier Tax 2603.19328; AgentProp-Bench 2604.16706 | 2025-26 | Abstracts only: tool hallucination benchmark; safety vs. success trade-off of runtime enforcement; a runtime interceptor reduces fabricated tool-claims. | Supporting context. | Abstract-level knowledge only. |

### 1d. Existing MCP guardrail / verification servers and gateways (READMEs fetched)

| Project | What it does (from README) | Overlap | Difference |
|---|---|---|---|
| fredyee/hallucc-mcp https://github.com/fredyee/hallucc-mcp | MCP server (hosted backend, API key), 5 tools: `verify_text` (claim-by-claim hallucination check with sources), `verify_agent` (final-output check plus 6-dimension trajectory eval incl. tool-claim consistency), `check_cua_actions` (L0-L3 rule-based risk gating of computer-use actions, takeover, task-scope escalation, multi-agent chain taint), `check_cua_code_audit`, `check_safety` (injection/jailbreak guard). In the official MCP registry. | MCP-packaged hallucination verification **and** risk-tier gating of actions. | Backend closed/hosted; no published method or benchmark; no JSON-Schema argument validation described; no graph distance. Shows "MCP server + hallucination check + risk tiers" is already occupied. |
| reaatech/tool-use-firewall https://github.com/reaatech/tool-use-firewall | MCP proxy pipeline: rate limit, cost, secret scan, argument validator, **JSON Schema validation of `tools/call` args against upstream `inputSchema`**, policy engine, read-only mode, anomaly detector, approval workflow, audit. | Proxy at MCP boundary + schema validation + approval for destructive ops. | No content/reasoning grounding. |
| Harshit-J004/toolguard https://github.com/Harshit-J004/toolguard | 7-layer MCP interceptor: policy, `risk_tier` (Tier 2 needs human approval), semantic validation (DROP TABLE, traversal), schema drift enforcement, fuzz tests. | Risk tiers + schema checks on MCP calls. | Security/robustness; no factual grounding. |
| QWED-AI/qwed-verification https://github.com/QWED-AI/qwed-verification | Deterministic verification of LLM outputs, tool calls, code, schemas before execution; Schema, Math, Logic, SQL, Fact (TF-IDF) and Graph engines; ADMIT/BLOCKED admission. | Pre-execution verification of tool calls with schema and fact engines. | Mostly symbolic; Fact engine is TF-IDF; no NLI+GED combination. |
| Fish121380/csc-agent-guard-v1 https://github.com/Fish121380/csc-agent-guard-v1 | Deterministic pre-execution gate verifying tool calls against host-maintained verified world state and policy; accept/reject/ask/conflict. | Pre-execution verification of tool calls against evidence. | Evidence is structured state, not text. |
| Doberman-Core, cordum, pipelock, IBM ContextForge, hyprmcp gateway, mcp-guardian, mcpcustoms, aki83reo gateway | MCP proxies/gateways: PASS/AUTH/BLOCK, policy-as-code, approval, DLP/injection scanning, audit (ContextForge also JSON-schema extraction/plugins). Mostly head of README plus grep only. | Interception and tiered verdicts are commonplace. | Security / access-control focus. |

I did NOT find, in sources I could reach, a prior system combining (i) JSON-Schema argument validation, (ii) a value-aware graph distance between agent reasoning and source context, and (iii) span-level NLI localisation inside a risk-tiered MCP gate. This is a negative search result with limited coverage, not proof.

---

## 2. Claim-by-claim verdict

| # | Candidate claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Verification system at the MCP boundary (tools and/or proxy) so agents verify before acting | **Not novel** as a concept (engineering contribution only) | hallucc-mcp, tool-use-firewall, ToolGuard, Doberman, QWED, AEGIS (2603.12621), Iyer 2609.19425 (MCP-layer resolver, M1-M5). |
| 2 | Hybrid: deterministic schema + GED + NLI in one gate | **Partially novel (combination only)** | Each part exists (schema: many; NLI: many; graph+NLI: GraphEval 2024; schema then value grounding: SAAG 2026). No prior system found with exactly this triple, but combination novelty needs an ablation showing the whole beats the parts; none exists yet (STATUS.md: baselines not run). |
| 3 | Value-strict GED (numbers, dates, versions, negation, role swaps) | **Not novel as an idea; partially novel as a tuned implementation** | Haghighi 2005 already has negation checks and a numeric-mismatch rule inside graph-matching entailment; SAAG flags numeric value hallucination by exact match; AMRFact models predicate/entity/negation errors. Typed value kinds at cost 1.0 plus a post-normalisation bonus is an engineering choice; no evidence yet that it beats NLI-only or a regex numeric-consistency check. |
| 4 | Risk-tier gating (LOW none / MEDIUM schema / HIGH schema + logic) | **Not novel** | hallucc-mcp L0-L3, ToolGuard risk_tier, Doberman PASS/AUTH/BLOCK, AEGIS human approval. Code note: in server/proxy/interceptor.py the HIGH-tier logic check runs only if both reasoning_context and source_context are supplied; otherwise a HIGH call effectively gets schema-only. A design gap to fix or document. |
| 5 | Tool-call hallucination benchmark (MCPEvol-Bench) | **Not novel; weak as written** | HTB (2609.19425, released, H1-H5/M1-M5), AgentHallu (693 human-annotated trajectories), SimpleToolHalluBench, Glaive-derived sets (2601.05214, SAAG). MCPEvol-Bench is 60 self-written cases (29/31), of which 25 are schema/format cases a plain JSON-Schema validator solves (README: 100%). Call it a smoke test. |
| 6 | Asymmetric hypothesis-in-premise subgraph matching instead of symmetric GED | **Not novel as a technique; well-motivated as a fix** | Haghighi, Ng, Manning 2005 define entailment as the cost of matching the hypothesis graph into the text graph. Current ged.py normalises by |V_hyp|+|V_prem|+|E_hyp|+|E_prem| and the value bonus uses symmetric_difference, so extra true premise content counts as an error; this plausibly explains the long-document recall collapse (hypothesis, not tested). Publishing "symmetric vs asymmetric" as an ablation is valuable; do not call it a new method. |
| 7 | Localising unsupported spans via NLI over graph-derived spans | **Partially novel / incremental** | GraphEval (triples+NLI), DAE (arc-level), FactGraph-E (edge-level). Yours differs only in implementation (parser-derived frames, templates). |
| 8 | Pre-execution self-verification exposed as an MCP tool the agent calls on itself | **Partially novel (framing)** | Most deployed systems enforce externally via proxies; self-verification tool APIs exist (hallucc-mcp verify_text/verify_agent). Unproven that agents call it reliably (tests/test_agent_loop.py is a test, not an agent-in-the-loop study). |

---

## 3. Wording recommendations

**Safe to claim (given current evidence):**
- "A research prototype MCP server and proxy that combines deterministic JSON-Schema argument validation with graph-based and NLI-based grounding checks before tool execution."
- "Builds on semantic-graph factuality (FactGraph, GraphEval), NLI grounding (SummaC, MiniCheck) and tool-call firewalls, integrated into one risk-tiered gate."
- "Value-sensitive structural comparison that penalises numeric, date, version, negation and role changes."
- "MCPEvol-Bench is a small hand-written smoke-test set (60 cases), not an independent measure of generalisation." (matches STATUS.md)
- Report honestly: external LLM-AggreFact run had high precision (89%) and low recall (29%), balanced accuracy 58.5%.

**Avoid:**
- "First", "novel method", "state of the art", "outperforms", "solves hallucination", "production-ready", "general hallucination detection".
- "Novel benchmark" for MCPEvol-Bench.
- Using 83.3% overall or 100% format/schema as capability evidence (deterministic validator on self-written cases).
- Claiming asymmetric subgraph matching as new; cite Haghighi et al. 2005.
- Calling it "SRL"; keep "SRL-style frames" (README already says it is NER + dependency heuristics).

**Suggested positioning sentence:**
"We present an open-source MCP verification gate that, before a tool call executes, validates its arguments against the tool's JSON Schema and, for high-risk calls, checks that the agent's stated reasoning is grounded in its source context using a value-sensitive semantic-graph comparison and span-level NLI; we compare it against schema-only, NLI-only and graph-only ablations and against MiniCheck/AlignScore on LLM-AggreFact, and report where it fails." Use this only after the ablations exist; until then say "prototype" and drop the evaluation clause.

If a research claim is wanted, frame it empirically: "does adding value-sensitive structural checks to NLI improve detection of numeric/negation/role errors in agent reasoning at tool-call time, and at what latency and false-positive cost?" rather than "a new method".

---

## 4. Missing evidence needed (ranked)

1. **Component ablations on a shared test set**: schema-only, NLI-only, GED-only, GED+NLI, schema+GED+NLI, and symmetric vs. asymmetric matching. STATUS.md lists these as not done; without them claim 2 has no support.
2. **Strong external baselines on the same data**: MiniCheck (FT5 and DeBERTa-large), AlignScore, windowed plain DeBERTa-NLI, and a trivial regex numeric/negation consistency check. Use LLM-AggreFact with dev-set threshold tuning (threshold 0.40 is currently uncalibrated per STATUS.md) and confidence intervals. The full windowed run is still pending.
3. **Independent, larger tool-call benchmarks**: evaluate on HTB (2609.19425) and AgentHallu (693 human-annotated trajectories) and/or a Glaive/BFCL-derived set, reporting per-category results. Expect a plain schema validator to win on schema-detectable classes; show whether GED/NLI adds anything beyond it.
4. **Content-error tool-call dataset**: schema-valid but ungrounded arguments (wrong amounts, borrowed or stale values), i.e. the H5 residue in 2609.19425. This is the only place the GED/NLI layer could add value over schema checks; compare to an LLM-judge baseline and a SAAG-style exact-match grounding baseline.
5. **Human validation**: independent annotators, inter-annotator agreement (e.g. Cohen's kappa), and confirmation that labels were not written after seeing system outputs; the threshold sweep uses the same 60 cases it is evaluated on.
6. **Benchmark size and balance**: hundreds to thousands of cases with a held-out test never used for tuning. At n=60, 50 correct gives a 95% Wilson interval of roughly 72% to 91%.
7. **End-to-end gate evaluation with a real agent**: blocked-hallucination rate, false-block rate on benign calls, task-success impact (cf. Verifier Tax 2603.19328), and per-tier latency (AEGIS reports 8.3 ms median; BERT-NER + spaCy + DeBERTa on CPU will be far larger).
8. **Error analysis of the long-document recall collapse**: test whether symmetric normalisation and the 0.35 GED threshold cause it and whether asymmetric matching plus windowing fixes it.
9. **Robustness tests**: paraphrase and adversarial cases (README admits T01/T04/T06 paraphrase false positives; 2506.14613 warns structure can amplify surface differences).
10. **Reproducibility**: pinned model/package versions, released data, license check (LLM-AggreFact is CC-BY-ND-4.0), seeds, hardware.

---

## 5. Sources: read vs. snippet-only

**Actually read (via curl; PDFs through pdftotext; abstract plus selected method sections unless noted):**
- https://arxiv.org/abs/2601.05214 (Internal Representations ... Tool Selection)
- https://arxiv.org/abs/2204.06508 (FactGraph; method and Smatch baseline)
- https://arxiv.org/abs/2311.09521 (AMRFact; abstract level; venue from arXiv comment)
- https://arxiv.org/abs/2404.10774 (MiniCheck; abstract plus keyword-targeted reading of intro/method; venue from arXiv comment)
- https://arxiv.org/abs/2609.19425 (Closed-World Resolution; abstract, intro, taxonomy, algorithm)
- https://arxiv.org/abs/2607.18245 (SAAG; abstract, intro, stage definitions)
- https://arxiv.org/abs/2601.06818 (AgentHallu; abstract and taxonomy table)
- https://arxiv.org/abs/2407.10793 (GraphEval; abstract and method overview)
- https://arxiv.org/abs/2411.01343 (AMREx; abstract and partial intro)
- https://aclanthology.org/H05-1049/ and its PDF (Haghighi et al. 2005; method, checks, numeric mismatch)
- https://raw.githubusercontent.com/fredyee/hallucc-mcp/main/README.md (full)
- Raw READMEs, read in part (head plus targeted grep), for reaatech/tool-use-firewall, Harshit-J004/toolguard, QWED-AI/qwed-verification, Fish121380/csc-agent-guard-v1, davccavalcante/mcpcustoms, luckyPipewrench/pipelock, cordum-io/cordum, IBM/mcp-context-forge, hyprmcp/mcp-gateway, eqtylab/mcp-guardian, DobermanCore/Doberman-Core, aki83reo/secure-agent-mcp-gateway (all at https://github.com/OWNER/REPO).
- Local: README.md, STATUS.md, server/proxy/interceptor.py, server/pipeline/ged.py.

**Abstract only (arXiv API abstract/metadata):**
- AlignScore https://arxiv.org/abs/2305.16739 (ACL 2023), SummaC https://arxiv.org/abs/2111.09525 (TACL), DAE https://arxiv.org/abs/2010.05478
- AEGIS https://arxiv.org/abs/2603.12621, AgentGuardian https://arxiv.org/abs/2601.10440
- https://arxiv.org/abs/2506.14613, https://arxiv.org/abs/2405.01259
- https://arxiv.org/abs/2510.22977, https://arxiv.org/abs/2603.19328, https://arxiv.org/abs/2604.16706, https://arxiv.org/abs/2602.01129, https://arxiv.org/abs/2512.08290

**Snippet / listing only (NOT read; unverified):**
- Kouylekov and Magnini tree-edit-distance RTE papers (2005-06): title/year from a Semantic Scholar list.
- "Reliability Alignment" (Xu et al., 2025) and ToolBeHonest (Zhang et al., 2024): known only because SAAG cites them.
- GitHub repos known only from search-API descriptions: hol-guard, AegisFlow, Kuadrant mcp-gateway, MCPGuard, mcpcurl, argwitness, rashomon, ai-validator, ThinkWatch, agent-security-scanner-mcp, radius, others. Features not verified.
- Venue and year for GraphEval and DAE are not verified beyond arXiv listing.

**Not done:** I ran no baselines; I did not retrieve MiniCheck/AlignScore leaderboard numbers; arXiv searches for numeric-sensitive graph factuality and for graph matching textual entailment returned nothing (not evidence of absence).
