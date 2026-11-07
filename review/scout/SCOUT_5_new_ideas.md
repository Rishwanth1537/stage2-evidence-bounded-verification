# SCOUT 5: novelty check of five new ideas (as of 2026-10-30)

Method: arXiv export API (sorted by submission date, 2026 papers read at abstract level, all listed ids below were fetched through the API) plus WebSearch for venues. "Abstract-level" means I did not read full texts; where a verdict depends on full-text details I say so. Prior scouts SCOUT_1..4 in this folder already cover other papers; this file only adds what bears on ideas A-E.

## Verdict table

| Idea | Verdict | Confidence | Main reason |
|---|---|---|---|
| A cross-model consensus on tool-call args (BFCL, 100+ models) + error-correlation | OPEN (adjacent work exists) | medium (about 70%) | Cross-model disagreement exists for free text (2604.17112) and UQ for function calling is single-model (2604.22985); no one uses many-model agreement on argument values or studies error correlation on BFCL |
| B evidence-ablation, judge plateau, decidability taxonomy | PARTLY DONE | medium-high | 2610.18497 already shows judges follow the reference and that a derived reference lifts AUROC; the size-plateau claim, schema/live-state ablation and the taxonomy by weakest evidence are not found |
| C contrastive candidate grounding (negative twins from context) | OPEN | medium (about 65%) | Nearest: likelihood competition in 2610.03894, entity binding in 2606.30531, role provenance in 2605.11039; no twin-swapping plus NLI |
| D MCP annotations for read-only verification probes | OPEN | medium-high (about 75%) | No paper found using readOnlyHint/idempotentHint for verification; EffectWorld (2610.35981) uses effect declarations for trace safety, not argument checking |
| E end-to-end certified cascade (deterministic tiers + LLM, LTT/conformal) | PARTLY DONE | medium | Conformal/LTT gates for tool calls exist (2607.22868, 2607.24343, 2610.19811); a tiered deterministic+LLM cascade with one joint false-block guarantee on argument correctness is not found |

No 2026 paper found makes the whole plan obsolete (see section at end).

## A. Cross-model consensus as verifier

Closest papers:
1. 2604.17112 (2026-04-18) Complementing Self-Consistency with Cross-Model Disagreement for UQ. Uses disagreement of a small scale-matched ensemble as epistemic uncertainty, flags confident failures. Stops at: free-text long-form answers, 7-9B models, five models; no structured tool-call arguments, no error-correlation study across 100+ models.
2. 2604.22985 (2026-04-24) Uncertainty Quantification for LLM Function-Calling. First UQ benchmark for function calling (BFCL-based per search snippet); multi-sample semantic entropy gives no clear edge over single-sample methods; AST-based clustering of outputs helps. Stops at: samples from one model; no cross-model signal; no per-argument-value agreement.
3. 2610.03894 (2026-10-02) Proxy Confidence. Notes frontier models are repetitive so resampling fails, and uses a different open-weight surrogate's log-probs to score tool calls (per-argument teacher forcing). Stops at: one surrogate, likelihood not agreement of produced values; no multi-model vote, no correlation analysis. This is the strongest support for the premise that same-model resampling is weak, and the closest competitor in spirit.
4. 2608.27750 (2026-08-27) Probe-based detection of tool-calling errors, 18 tool-calling LLMs on BFCL. Stops at: white-box per-model linear probes, not cross-model agreement.
5. 2610.07570 (2026-10-06) Unanimously Wrong. Shows agreement can be unanimously wrong (medical QA). Stops at: not tool calls; but it is a warning that the correlation structure is the crux for idea A.
Not found: any paper that takes leaderboard outputs from many models for the same prompt and measures argument-level agreement or error correlation. Caveat: BFCL per-model raw outputs are published by the leaderboard maintainers (not verified here by me; check the BFCL repo/result folders before committing to this plan). Risk: correlated errors (all models misread the same ambiguous prompt) may make A weak exactly where it matters; that is also what makes the correlation study the publishable part.

## B. Evidence ablation ("information, not scale") and decidability taxonomy

Closest papers:
1. 2610.18497 (2026-10-13) Judges Follow the Reference: The Derivation Gap in Verifying Tool-Call Arguments (Ma, Wang, Qian, Cao, Gutierrez Basulto; 28 pp). Seven judges accept correct values less when no reference text exists (defaults, inferred, truncated); judges favor a visible wrong value over a correct one with hidden source; DeRef (a separate model writes a reference without seeing the candidate) lifts AUROC on three benchmarks, to 98-99.6 on the controlled test. Stops at: no judge-size scaling plateau shown in the abstract, no schema/live-state evidence ablation, no taxonomy by weakest evidence source. NOTE: your repo already references this id (README, STATUS, MASTER_PLAN, SCOUT_1/2/4), so you know it; it is the single biggest overlap with B and with the existing "reference derivation" work, and its name "DeRef" collides with benchmarks/eval_deref.py. Treat it as prior art, cite it, and differentiate.
2. 2609.19425 (2026-09-16) Closed-World Resolution Against Tool Hallucination. Taxonomy H1-H5 and M1-M5 (MCP); model scale does not help (675B equals 7-8B) for fabricated tools/arguments. Stops at: hallucinated tool names and undeclared arguments, not wrong-but-valid values; no judge evidence ablation.
3. 2607.22868 (2026-07-24) What Can Be Enforced? Theory of certified runtime safety: guarantees depend on what the judge observes. Stops at: theory of observability for policy enforcement; no empirical argument-correctness decidability classes.
4. 2606.30531 (2026-06-29) Entity Binding Failures: taxonomy of wrong-entity failures, entity-resolution preconditions; 60 tasks, five backends. Stops at: taxonomy by failure type, not by the evidence needed to decide.
5. 2608.27750 (2026-08-27): says model size matters for probe success; contrary signal to "plateau" claims, but for probes not judges.
Verdict reasoning: the "judges need reference, not size" half is substantially covered by 2610.18497 (scale half unverified at abstract level; read the full paper's judge list and sizes before claiming a plateau). The decidability taxonomy (conversation / tool contract / environment state / none) and the live-state evidence rung appear open. Frame B as extending 2610.18497 along the evidence axis, not as a competitor to it.

## C. Contrastive candidate grounding (negative twins)

Closest papers:
1. 2610.03894 (2026-10-02) Proxy Confidence: "tool-choice competition" (function vs sibling functions) and request-PMI per argument value. Stops at: competes tools, not alternative values of the same slot built from context; no NLI.
2. 2606.30531 (2026-06-29) Entity Binding Failures: wrong entity among visible candidates, mitigations are resolution preconditions and clarification. Stops at: no automatic twin construction or NLI scoring.
3. 2605.11039 (2026-05-11) PACT: argument-level provenance and semantic roles for authority-bearing arguments. Stops at: security trust contract, not correctness among several type-compatible context values.
4. 2610.18497: shows the "visible incorrect value" failure (judges favor it) which motivates C, but its fix is a derived reference, not twins.
5. 2607.24343 (2026-07-27) role-stratified conformal control: per-role, not contrastive.
Not found: building negative twins by swapping type-compatible context values and judging original vs twins. Caveat: weak search recall for this phrasing (several strict queries returned nothing); medium confidence.

## D. MCP-native verification probes using annotations

Closest papers/sources:
1. 2610.35981 (2026-10-26) Small agents should know what their tools do (EffectWorld). Tools declare effect, idempotence, read/write resources; a replay verifier judges effect-safety of traces without judges; evaluated on BFCL. Stops at: effect safety/efficiency of whole traces and training signal; not pre-execution verification of a pending call's id/name/enum arguments against live read-only state; not MCP readOnlyHint.
2. 2601.08012 (2026-01-12) Towards Verifiably Safe Tool Use: capability-enhanced MCP with labels for capabilities, confidentiality, trust. Stops at: information-flow/safety specs, not argument verification.
3. 2610.33108 (2026-10-22) ToolContractGate: deterministic evaluator on OpenAPI-derived contracts. Stops at: contract/drift checks, no live state probing.
4. 2602.19218 (2026-02-22) Gecko: simulated environment with stateful feedback for refining tool calls. Stops at: simulator, not the live server's read-only tools.
5. 2609.19425 and 2606.06387 (WebMCP): MCP registry hallucination and poisoning of tool surface; WebMCP paper mentions readOnlyHint only in an attack context. Spec facts (not research): MCP annotations are hints, destructiveHint defaults true, idempotentHint default false, and are not verified against behavior (https://www.mcpbundles.com/guides/tool-annotations, https://sunpeak.ai/docs/mcp-apps/server/tool-annotations).
No paper found using annotations to discover probe tools. Design risk to address: annotations are untrusted self-declarations (a malicious or sloppy server can mislabel a write tool as read-only, which is a tool-poisoning vector), so a probe should be allowlisted or sandboxed; the secret is that this risk makes a "trust but check" contribution. Medium-high confidence open; recall limit: arXiv search for "readOnlyHint" returned one unrelated paper, and GitHub/blog coverage was only partially searched.

## E. End-to-end certified cascade

Closest papers:
1. 2607.22868 (2026-07-24) What Can Be Enforced?: Neyman-Pearson false-block/miss frontier, conformal marginal certificate (possibly via block-all), deterministic gate theory, closed-loop caveat. Stops at: theory plus diagnostics; no tiered deterministic+LLM cascade on real argument errors.
2. 2607.24343 (2026-07-27) Role-Stratified Conformal Risk Control for LLM Tool Calls: per-argument-role thresholds and finite-sample guarantees, wraps any per-field detector, AgentDojo and InjecAgent, six models. Stops at: guarantee for a single detector's scores (injection/untrusted-source risk), not argument correctness through a cascade of tiers. This is the main competitor for the "stated guarantee" claim at argument granularity.
3. 2610.19811 (2026-10-14) Calibration and Risk-Budgeted Decisions with System One Models: Learn-Then-Test for allow/block with conservative fallback; naive thresholds exceed risk about half the time versus 7.8% for LTT. Stops at: single scorer, moderation/safety/reranking data, not tool arguments or tiers.
4. 2609.22048 (2026-09-18) Available Guardrails: certified precision per reporting unit (e.g., a tool) with exact-binomial inversion; shows finite data may not allow certification. Stops at: general selective prediction; relevant to per-tool certificates.
5. 2610.36570 (2026-10-27) CASEL: finite-sample threshold plus routing among execute/verify/sandbox/abstain, simulation only (assumed intervention effectiveness). 2604.09155 CORA (conformal risk-controlled GUI agents) and 2610.05563 G-CARB (conformal stopping for compositional harm) are other certified action gates.
Verdict: the generic ingredient (LTT/conformal on tool-call gating) is done; the specific combination (deterministic tiers that never block wrongly + an LLM fallback, with the false-block rate certified end-to-end on a real benchmark of argument errors) is not found. See SCOUT_3 for the earlier conformal/cascade survey. Caveat: exchangeability across tools/domains is the usual weak point and 2607.22868 and 2607.24343 both flag drift.

## Other 2026 papers worth citing or watching
- 2610.11030 NOMOS (2026-10-08): compiles written policies into statically verified tool-call gates (policy, not argument correctness).
- 2609.40027 / 2605.09168 CIVeX and its red team: causal identification verifiers with confidence bounds.
- 2605.24462 No Certificate, No Execution (position paper on certified traces).
- 2604.16706 Auditing Automated Evaluation, Error Propagation, and Runtime Mitigation in Tool-Using Agents (not read; check for judge-reliability overlap).
- 2607.04034 The "I Don't Know" Filter in function calling (not read; possible overlap with abstention).

## (1) Venues and benchmarks (verify every date on the official page)

Deadlines I could actually verify via search snippets:
1. ICLR 2027 workshops (iclr.cc/Conferences/2027/WorkshopGuidelines): proposals closed 2026-10-09, workshop acceptances 2026-11-29; suggested contributed-paper deadline 2027-02-01, mandatory paper notification 2027-02-26. Individual workshop deadlines vary; no agent-safety/tool-use ICLR 2027 workshop list is published yet. Precedent: "Agents in the Wild: Safety, Security, and Beyond" ran at ICLR 2026 and a second edition at ICML 2026 (https://icml.cc/virtual/2026/workshop/54082), so a third edition is plausible but unverified.
2. ACL 2027 (Kyoto, Aug 17-22, 2027; https://2027.aclweb.org/): ARR deadline reported inconsistently (Jan 4, Feb 15 or Feb 16, 2027) and officially TBA at the time of search; unverified, check ARR.
3. PAgE workshop at POPL 2027 (Mexico City, Jan 10-16, 2027; https://popl27.sigplan.org/home/page-2027): safe agentic engineering, topics include type-safe tool interfaces and verification of agentic plans, 6-page SIGPLAN format, non-archival. Submission deadline not found; likely too close to meet if not already open, check the page. Good fit for idea D/E framing (formal-methods audience).
4. NAACL 2027: ARR deadline 2026-10-12 (passed) per search snippet; EACL 2027 ARR 2026-08-03 (passed).
5. Not verified (no search result found): ICML 2027 workshops, COLM 2027, AAAI-27 deadlines, NeurIPS 2027 workshops. Recommend the plan treat ICLR 2027 workshops (Feb 2027) and ACL 2027 via ARR (Feb 2027) as the realistic first targets, and look for NeurIPS 2026 workshop leftovers only if still open.
Benchmarks where such work is judged: BFCL v4 (2608.06370 reports 14 models on v4), tau2-bench (used in 2610.24346), AgentDojo and InjecAgent (used by 2607.24343, 2605.11039), ToolFailBench (2607.04686), Hallucinated-Tools Benchmark HTB (2609.19425), plus ToolHACE (2610.17125, response-level hallucination, not arguments). I did not verify leaderboard hosting or submission mechanics for any of them.

## (2) Does any 2026 paper make the whole plan obsolete?
No. Nothing found combines pre-execution argument verification, MCP-native probing and a certified cascade. The highest-threat items, in order: 2610.18497 (takes the "judges need a derived reference" result; already known to you), 2607.24343 plus 2607.22868 (take the generic "certified guarantee on tool-call arguments" claim, so E must differentiate on argument correctness and tiering), and 2610.03894 (a cross-model surrogate signal for argument values, overlapping A/C). Re-run the arXiv query for these topics weekly; this field posts several relevant papers a week.

## Limits of this scout
Abstract-level reading only; full-text details (judge sizes in 2610.18497, datasets in 2604.22985) not checked. Strict boolean arXiv queries often returned nothing, so absence of hits for A, C and D is moderate evidence, not proof. GitHub repos, blogs and leaderboards were barely covered (WebSearch returned only spec documentation for MCP annotations).
