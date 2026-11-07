# 03 Next steps (rewritten 2026-11-01; the step-by-step instructions are in `handoff/10_NEXT_STAGE_PLAYBOOK.md`)

Legend: **[U]** needs the user; **[C]** Claude can do it; **[K]** needs a key or quota; **[D]** needs permission to download. Goal: a main-track-capable study of evidence-bounded verification of tool-call arguments and of asking the user instead of blocking, with a calibrated interruption budget (`review/PAPER_PLAN_V2.md`). Older lists: `handoff/archive_pre_2026-10-31/03_NEXT_STEPS_DETAILED.md` (superseded).

## Done since 2026-10-30 (details: `review/EXPERIMENTS_2026-10-30.md`, `review/PROJECT_BRIEF.md` section 4)
Judge panel in agent mode and via APIs; cost and cascade; tool-definition tier and information ablation; Nemotron size ladder (4B, 30B, 120B, 550B) with and without the definition; tau-bench state probe; role-contrast; BFCL consensus (30 models x 200 cases) and its judge control; ask-policy with conformal rules; decidability labels, Opus pre-audit, rule revision, strong-error recomputation; fresh audit sample; downloads and slices (AgentHallu, MCP-Atlas, tau2 data, AgentDojo); AgentHallu confirmatory protocol registered and run (all five judges done: H-J1 not supported, H-J2 supported); AgentDojo value-planting analysis.

## To do, in order (each item has commands and acceptance criteria in the playbook)
| # | Task | Who | Playbook section |
|---|---|---|---|
| 1 | Fill `review/audit2/audit_sample_blind.csv` (98 items, 45-60 min); then run `compare_audit.py` and apply the decision rules | [U] then [C] | 2.1 |
| 2 | ~~Finish the confirmatory AgentHallu analysis~~ DONE (plan section 14) | [C] | 2.2 |
| 3 | Write and run `benchmarks/selfconsistency_bfcl.py` (k samples of one model as the ask trigger vs 29-model peer agreement) | [C][K] | 2.3 |
| 4 | Judge breadth: API judges at temperature 0 (Groq, NVIDIA; Anthropic API and OpenRouter if keys appear); information ablation on cfb and on AgentHallu multi-turn (needs BFCL multi-turn function docs: state size first) | [C][K][D] | 2.4 |
| 5 | Shift study (calibrate on BFCL, test on AgentHallu and fcrb), guarantee vs number of calibration cases, theory statements for the appendix | [C] | 2.5 |
| 6 | Freeze configurations in a Deviation entry; one locked test run per configuration on untouched halves; recompute ArgGround-Bench test numbers once | [C] | 2.6 |
| 7 | Paper draft, figures (native), update README/STATUS/speaker guide/deck, engineering backlog | [C][U] | 2.7 |
| 8 | Commit further work on `stage2-evidence-bounded-verification` (explicit paths, no attribution lines) when the user says so; first commit done 2026-11-01 | [U] decides | commit plan |

## Inputs still needed from the user (also in `handoff/07_OPEN_DECISIONS.md`)
The audit; venue and first-draft date (proposal: `review/PAPER_PLAN_V2.md` section 10); rotate the Groq, Gemini and NVIDIA keys (pasted in chat); optional Anthropic API/OpenRouter keys; browser checks (HuggingFace `HuanzhiMao/BFCL-Result`, Jev, CLM); permission for the BFCL multi-turn function-doc download; when to update the deck; when to commit.

## Engineering backlog (any time)
Explicit `degraded` flag instead of silent model fallbacks and record the spaCy model in result files; `make reproduce` regenerating every table from saved outputs; ablate each normaliser in `arg_ground.py`; re-run the contract-tier numbers with `relaxed=True` and refresh `INFORMATION_ABLATION_FINDINGS.md` if they change; optional cherry-pick of the three Case1 test files and docs with authorship preserved (`review/CASE1_ASSESSMENT.md`).


## Update 2026-11-02 (evening): what changed and what is still open
Done today (uncommitted until the user asks): review of branch `origin/update1` (`review/UPDATE1_BRANCH_REVIEW.md`: most of its headline claims are unsupported); **2.3 real self-consistency run** with Nemotron-4B (`PAPER_PLAN_V2.md` section 15, Deviation 15: self-consistency AUROC 0.667 vs peers 0.883, only 13 strong errors, cost objection stands); **AI re-audit** of the 98-item sample by 3 Claude models x 2 runs (section 16; BFCL strong precision 43%, fcrb 40-90% unresolved, class agreement 38%); **2.5 shift and guarantee study on real scores** (section 17, Deviation 16: shift breaks the budget only when the source is cleaner than the target).
Still open, in this order:
1. **Human audit** (user, 45-60 min): `review/audit2/audit_sample_blind.csv`. The AI consensus is in `audit_sample_ai_consensus.csv`; compare the two with `benchmarks/compare_audit.py`. Needed most for fcrb (40% vs 90% disagreement among AI annotators).
2. ~~Self-consistency, stronger evidence~~ DONE 2026-11-02 (sections 15 and 18 of the plan: pooled AUROC 0.741, peers 0.873). Optional: a still larger model (Nemotron 550B, Groq gpt-oss-120b) to see whether the gap closes; original text: command `python -I benchmarks/selfconsistency_bfcl.py --model <name> --k 8 --out benchmarks/selfconsistency_<tag>.json`; goal: more than 13 strong errors (add models, not cases) and see whether self-consistency AUROC passes 0.70.
3. **Reconcile the checker numbers:** 12.9% false blocks (confirmatory run) vs 9.7% (`update1` `real_run.py`): rerun both on `cases_eval.json` with the same code revision and record the commit hash and spaCy model.
4. **MCP-Atlas false-block rate** of the checker (about 2,400 clean calls): partly covered in section 17 (70% of calls have non-zero non-conformity); report the strict block rate with `call_is_grounded`.
5. **Ask score for the shift study:** the disagreement score exists only on BFCL; either run self-consistency on fcrb/AgentHallu prompts (needs the tool definitions; AgentHallu multi-turn definitions need the BFCL multi-turn function-doc download, state size first) or state the limitation.
6. **Judge breadth (2.4):** API judges at temperature 0 on cfb and the information ablation on cfb; keys for Anthropic/OpenRouter would allow a proper main-track table.
7. **Locked test (2.6):** write a Deviation that freezes configurations, then ONE run on untouched fcrb/cfb test halves and ArgGround-Bench test; log in `benchmarks/test_run_ledger.jsonl`. The `update1` "locked test" is not one.
8. **Theory:** a proper statement of the evidence bound with measured decidable shares (the `update1` appendix assumes the conclusion); conformal part is standard.
9. **Write-up, figures, deck/README/speaker guide** (only when the user says), venue and date decision, key rotation, merge decision for `update1`.


### Update 2026-11-04
Done: checker false-block reconciliation (`PAPER_PLAN_V2.md` section 19: 12/93 vs 9/93 is a different negative sample, not code; population rate 11.9% [9.1, 15.4]); manual labelling of all 98 audit items by the Claude session (section 20, `audit_sample_claude_manual.csv`). The human audit is still open; start with the least-sure items listed in section 20. Next on the list: MCP-Atlas strict false-block rate, API judges at temperature 0 on cfb, locked-test freeze.

### Main-track extension (2026-11-04)
The user wants the main track. New candidate experiments E1-E7 with pre-set hypotheses, kill rules and a gate schedule are in `review/PAPER_PLAN_V2.md` section 22 and `handoff/10_NEXT_STAGE_PLAYBOOK.md` Stage 3. Nothing from it has been run. The user said to experiment first and decide by the results.
