# 10 Next-stage playbook (written 2026-11-01 so work can continue without the original chat)

Audience: a new person or a new Claude session. Read `review/PROJECT_BRIEF.md` first (what is established), then this file (what to do next, in order, with commands, acceptance criteria and decision rules). Commands run from `U:\txt\mcp-hallucination-checker` in Git Bash with `PYTHONPATH=.`; see `handoff/09_PIPELINES_HOWTO.md` for how each pipeline works and `handoff/05_ENVIRONMENT_AND_COMMANDS.md` for pitfalls. **Rules that always apply:** do not edit `benchmarks/judge_prompts.py`; write code with the Write/Edit tools (never python heredocs containing `\n` or backslashes); any new hypothesis or prompt variant goes into `review/PREREGISTRATION.md` before it is run; every look at a test half is logged in `benchmarks/test_run_ledger.jsonl`; never commit unless the user asks, and then with no attribution lines and explicit paths.

## Stage 2.0 - state check (5 minutes)
```bash
git -C /u/txt status --short | grep -v pycache | head -100      # should show only audit keys, egg-info, zip; everything else is committed
python benchmarks/keys.py                                        # which keys are visible (names only)
ls /tmp/nvidia_ladder /tmp/ah_*.log 2>/dev/null                   # temporary logs may be gone: results are in benchmarks/*.json
PYTHONPATH=. python -m pytest tests/test_arg_ground.py tests/test_grounded.py tests/test_judge_providers.py -q -p no:cacheprovider
```
`benchmarks/agenthallu_confirmatory.json` should contain six rows (checker plus five judges); if not, rerun the missing judge (command in 2.2).

## Stage 2.1 - the human audit (blocks every claim built on labels)
Owner: the user. File: `review/audit2/audit_sample_blind.csv` (98 items B001-B098, 45-60 min, instructions in `review/audit2/AUDIT_INSTRUCTIONS.md`; **not** the old `review/audit/`). The key `review/audit2/audit_key_DO_NOT_OPEN.csv` must stay unopened until the CSV is filled.
When the filled CSV comes back:
```bash
PYTHONPATH=. python benchmarks/compare_audit.py --csv review/audit2/audit_sample_blind.csv --key review/audit2/audit_key_DO_NOT_OPEN.csv
```
(the script reads the key's `our_class`; the random-draw vs stratified-draw split is in the key's `draw` column: compute label precision from `draw == random` rows only, per dataset, with Wilson intervals; extend the script for that if it does not already group by `draw`).
**Decision rules**
- BFCL strong-error label precision (random draws, after removing WEAK_ classes) below 50%: BFCL cannot support headline claims; keep it as a diagnostic and rebuild the error set from AgentHallu plus audited items only.
- fcrb label precision below 60%: report fcrb results as "benchmark-label" results with the audit-measured precision stated in the table caption.
- Class agreement (Q1 = yes items) below 60%: collapse the classes (merge `U_silent` into `E1_conversation`, drop `E4_peers` from audited claims) in `benchmarks/decidability.py`, regenerate `decidability_dev.json`, log Deviation 15.
- Missed-error rate on controls above 10%: the "correct" labels are unreliable; say so in the limitations.
- Compare with the Opus pre-audit (`review/PAPER_PLAN_V2.md` section 11) and report where they differ.
Record results in `review/EXPERIMENTS_2026-10-30.md` (new row), `review/PAPER_PLAN_V2.md` (section 15) and `handoff/02_EXPERIMENTS_AND_RESULTS.md`.

## Stage 2.2 - confirmatory AgentHallu analysis (DONE 2026-11-01: all five judges run; H-J1 not supported, H-J2 supported; see `review/PAPER_PLAN_V2.md` section 14; keep this section for reproduction)
Registered in `review/PREREGISTRATION.md` Deviation 14 (cases file hash `c0b3ef1d76baf28a`). Each judge once. Status: complete (Claude Opus, Sonnet, Haiku and Nemotron 550B, 4B).
```bash
PYTHONPATH=. python -u benchmarks/llm_judge_args.py --provider nvidia --model nvidia/nemotron-3-ultra-550b-a55b --bench benchmarks/data/agenthallu/cases_eval.json --split dev --limit 124 --rpm 8 --out benchmarks/llm_judge_args_ah_nvidia_nemotron_3_ultra_550b_a55b_dev_v0.json    # resumes from cache
PYTHONPATH=. python benchmarks/analyze_agenthallu.py          # writes benchmarks/agenthallu_confirmatory.json and prints H-J1/H-J2 per judge
```
Then add the final five-judge table to `review/PAPER_PLAN_V2.md` section 14 and `review/EXPERIMENTS_2026-10-30.md` (row 16). Exploratory only (label it so): overlap/union with the checker (`scratchpad/ah_overlap.py` pattern: 2x2 of checker vs judge on the 31 errors).

## Stage 2.3 - real self-consistency as the ask trigger (the missing piece of C3)
Write `benchmarks/selfconsistency_bfcl.py` (specification):
1. Tests: the 200 BFCL single-turn cases (request and function schemas from `benchmarks/data/bfcl/consensus_cases.json`, gold from `load_bfcl_consensus.load_gorilla()`).
2. Model: `nvidia/nemotron-3.5-bolt-e4b` (fast, 4B) first; a second, stronger model if quota allows. Prompt: system "You are a function-calling assistant. Reply ONLY with the call(s) in python syntax, a list like [func(arg=value)]"; user = JSON function definitions + request. One greedy sample (temperature 0) = the *primary call*; four samples at temperature 0.8 = the *k samples* (use `llm_judge_args.chat(..., temperature=0.8, max_tokens=400)`; cache every reply in a JSONL).
3. Parse with `load_bfcl_consensus.parse_calls`, align and label with `align` and `label_call`; apply the weak-label tiers from `decidability.relaxed_equal` so the evaluation is on strong errors (drop weak-only calls).
4. Score: for each argument of the primary call, disagreement = share of the four samples whose value for that argument differs (missing counts as different); call score = maximum over arguments. Also the peer score of the same value against the 30-model slot (`consensus_index`).
5. Report AUROC and detection at interruption budgets 5/10/20% for: self-consistency, peer disagreement, their union, and (where available) the Opus-with-definition verdict; conformal thresholds from `ask_policy.pac_tau/cluster_tau/boot_tau` with 1,000 re-splits by test case.
Acceptance: a table in `review/PAPER_PLAN_V2.md` (section 16) and `EXPERIMENTS` row; H-A1 evaluated (ask-policy using disagreement beats contract-only by >= 15 points at a 10% budget). If self-consistency AUROC is below 0.70 while peers are above 0.85, the practical objection (cost) stands and C3 is reported as an information bound, not a deployable policy.

## Stage 2.4 - breadth of judges and data
- API judges at temperature 0 for the fcrb ladder and the AgentHallu slice: Groq gpt-oss-20B/120B (`--provider groq`, mind 8k tokens/min and 200k tokens/day per model), NVIDIA models listed in `handoff/09`, and, if the user provides keys, Anthropic API and OpenRouter (`benchmarks/judge_panel.json`, `run_judge_panel.py`).
- Repeat the information ablation (with vs without tool definition) on **cfb** (3,000-character contexts) and on the AgentHallu multi-turn slice (needs the BFCL multi-turn function docs from the gorilla repo: `berkeley-function-call-leaderboard/bfcl_eval/data/multi_turn_func_doc/`; download after stating size).
- MCP-Atlas: false-block rate of the checker on the 2,423 clean real MCP calls (`benchmarks/data/mcpatlas/cases.json`; premise = prompt only, so report separately for calls whose arguments are derivable from the prompt; it cannot measure detection).
- AgentDojo: process the other 27 pipelines only if needed (`python -I benchmarks/load_agentdojo.py <repo> <model1,model2>`); to make a robustness claim the checker needs source typing (trusted vs tool-derived text); a prototype may use tool-name allow-lists of data-fetching tools. Claim C4 stays "negative/limited" unless that prototype is evaluated against a manually audited sample of 100 injected calls.

## Stage 2.5 - shift study and guarantee
Calibrate `ask_policy` thresholds on BFCL strong errors and test on AgentHallu and fcrb (calls, not arguments); repair options: recalibrate on 100/200/500 target calls, weighted conformal, pooled calibration (H-A3). Plot detection vs guarantee strength as a function of the number of calibration test cases (subsample 25, 50, 100, 200 cases). State the guarantees precisely in the paper: (i) marginal split conformal, (ii) calibration-conditional Clopper-Pearson (call-level, optimistic when calls are clustered), (iii) cluster-bootstrap and cluster-Hoeffding (test case as unit). Proof obligations for the appendix: the evidence bound (a verifier reading only evidence E_k has detection at false-block rate alpha at most the share of E_k-decidable errors plus alpha, for errors independent of E_k-features otherwise) and the split-conformal ask-budget statement.

## Stage 2.6 - freeze and locked test (once)
1. Write the frozen configurations (system, prompt hash, thresholds, data hashes, seeds) as a Deviation entry in `review/PREREGISTRATION.md`.
2. Untouched test halves: DeRef fcrb and cfb test halves (`--split test --allow-test`, logs to the ledger), plus any new untouched slice (AgentHallu is already used confirmatorily).
3. Run each frozen configuration once; recompute the ArgGround-Bench test numbers once after the minus-sign fix (`benchmarks/eval_argground.py --split test`, log it).
4. Holm-correct the primary comparisons (H-I1, H-A1, H-J1); report non-significant results as inconclusive.
Kill rules (from the plan): if H-I1 fails on the locked test the paper becomes a negative-results note; if H-A1 fails drop the ask-policy headline.

## Stage 2.7 - write-up and housekeeping
- Paper outline: 1 introduction (the professor's challenge, what we claim); 2 related work (table in `review/NOVEL_PROJECT_PLAN.md` section 2 and the scouts in `review/scout/`); 3 evidence ladder and decidability (definitions, bound); 4 data and labels (audit, weak tiers); 5 experiments (information ablation and ladder, judge vs checker by error type, AgentHallu confirmatory, consensus and ask-policy, guarantee, injection); 6 limitations (dev inspection, label noise, agent-mode judges, licences); 7 conclusion. Figures (native, no AI-generated art): detection vs evidence level per judge; ladder vs active parameters; ask-rate vs errors-caught curves; guarantee vs number of calibration cases.
- Update after the results are frozen: `README.md`, `STATUS.md`, `review/SPEAKER_GUIDE.md` and the deck (`review/MCP_Hallucination_Checker_Review_v9.pptx` still states the old claim; the user asked to leave it for now).
- Engineering: explicit `degraded` flag instead of silent model fallbacks; record the spaCy model used; `make reproduce`.

## Commit plan (only when the user says "commit")
First commit done 2026-11-01 on branch `stage2-evidence-bounded-verification` (pushed to origin; three commits c019c62, 058fd19, 77a789c on top of 886c98c; review-eval-updates is unchanged at 886c98c). For later commits continue on that branch (or a new feature branch). Stage explicit paths, no `git add -A`: `server/`, `tests/`, `benchmarks/*.py`, `benchmarks/*.sh`, `benchmarks/judge_panel.json`, `review/*.md`, `review/audit/*.md`, `review/audit2/audit_sample_blind.csv`, `review/audit2/AUDIT_INSTRUCTIONS.md`, `review/scout/`, `handoff/`, `README.md`, `STATUS.md`, `.gitignore`. Exclude: `*.zip`, `__pycache__`, `*.egg-info`, `benchmarks/data/`, `benchmarks/llm_judge_args_cache.jsonl`, large result JSONs, `review/audit*/audit_key*` until the audit is finished, old decks v1-v8. Commit messages: plain descriptions, **no Co-Authored-By and no "Generated with" lines** (the user has asked for this repeatedly).


## Stage 3 - main-track extension (added 2026-11-04; full table with hypotheses and kill rules in `review/PAPER_PLAN_V2.md` section 22)
Goal: aim at the main track, so add one method and one end-to-end result to the measurement core. Candidates E1 provenance-aware grounding (MCP-Atlas `TRAJECTORY` has tool results), E2 class-conditional conformal ask-rule, E3 end-to-end gate on tau-bench and AgentHallu trajectories, E4 cost-accuracy Pareto, E5 audited benchmark release, E6 judge breadth (needs the user's OpenRouter key and cost approval), E7 theory. Start with E1 and E2 (new Deviations first), decide at Gate 1. Do not start E3-E7 before Gate 1 unless the user says so. Freeze configurations at Gate 2; one locked test; final main-vs-workshop decision at Gate 3. No dates are set: the user decides the timing.
