# Review of branch `origin/update1` (checked 2026-11-02, not merged, nothing from it is trusted yet)

Branch `update1` (two commits, b5f1c10 and 75eea80, author Rishwanth, built on our commit 07b9ce0) claims to finish Stage 2: audit analysis, self-consistency, shift study, a "locked test", and a report `review/REAL_EMPIRICAL_REPORT.md`. I read the report, the new scripts, the result JSONs and the diff of existing files. **One new result is real; most of the headline claims are not supported by what is in the branch.**

## What is genuinely new and usable
| Item | Verdict |
|---|---|
| `benchmarks/real_run.py` + `real_run_report.json` + `groq_judge_cache.jsonl` | A sixth AgentHallu judge, Groq `openai/gpt-oss-20b`, temperature 0, 124 cases. Judge 7/31 detected at 9/93 false blocks. Plausible and consistent with our five judges (32-48 %). **Keep as an extra row**, but note it was run after the confirmatory protocol was closed, so it is exploratory. It also has the checker at 9/93 false blocks (9.7 %), while our confirmatory run has 12.9 % (12/93): the two runs use a different checker configuration or code path. Must be reconciled before either is quoted. |
| `degraded` / `spacy_model` fields in `schemas.py`, `srl.py`, `verify_logic.py` | Implements the engineering backlog item. Small, looks fine; needs a test and a check that `tests/` still pass. |
| `contract_tier.py --relaxed` flag | Fine, matches our backlog. |
| `ablate_normalisers.py`, `mcpatlas_false_block.py`, `guarantee_calibration_plot.py`, `selfconsistency_bfcl.py` | Scripts only. **No result files for any of them are in the branch** (`selfconsistency_results.json`, `shift_study_results.json`, `guarantee_calibration_results.json` do not exist). Usable as starting code after review. |

## Claims that do not hold
1. **"Completed 98-item blind human/expert audit" (report section 4, Deviation 16).** The filled `audit_sample_blind.csv` answer columns carry the wording and format of our *Opus pre-audit* ("Would settle it: The tool definition ..."), not human answers, and the **unblinding key `audit_key_DO_NOT_OPEN.csv` was committed in the same branch**. The audit is therefore AI-labelled, not a human audit, and was not blind. Do not report precision numbers (BFCL 15.4 %, fcrb 30 %, class agreement 33 %) as human results. Our own audit still needs a human to fill it.
2. **"Locked test run" (`locked_test_evaluation.py`, ledger entry 2026-11-02).** No test half was run: the branch's own note says fcrb/cfb/ArgGround-Bench raw data were absent. The script re-reads *dev* results and `agenthallu_confirmatory.json`, and **hard-codes p-values**: `ha1_pval = 0.001`, `ha3_pval = 0.001`, `hi1_pval = 0.001` ("conservative"), then applies Holm. The "Holm p = 0.008" figures are artefacts of those constants. The ledger entry is mislabelled as a locked test; it must not be treated as one.
3. **H-A1 "80.5 % vs 8.2 %, strongly supported" and "self-consistency k = 4".** Those two numbers are already in our `ask_policy_strong_dev.json` (0.805 and 0.082): peer agreement of 29 models, on BFCL dev, on labels where 63 % of "wrong" calls are weak and the Opus pre-audit gave 30 % precision. `selfconsistency_results.json` does not exist, so self-consistency was never run. The report relabels dev peer-consensus numbers as a confirmed self-consistency result, and by its own audit claim BFCL is "diagnostic only", which contradicts using it for a "strongly supported" headline.
4. **H-A3 "6 of 6 conditions violated, repair gives 92-99 %".** `shift_study.py` contains `generate_synthetic_target_scores` with Beta-distribution scores and uses it when cached case scores are missing (lines 155, 157). No result file is committed, so these numbers cannot be verified and may come from simulated data. Treat as unverified.
5. **Theorem 1** (`Det <= Pr(decidable) + eps(alpha)`) is stated without a proof in the report. `THEORY_APPENDIX.md` was added; read it before relying on it (not reviewed in detail).
6. **Prose in the report** ("exceptionally sensitive", "completely restored", "beats a state-of-the-art 20B model", "several minutes of GPU time" on a hosted API) is stronger than the data; the McNemar result it cites is p = 0.061, not significant.
7. **Decidability change (Deviation 16)** flips `consolidate=True` as the default in `decidability.py`, merging `U_silent` into `E1_conversation` and dropping `E4_peers`, and rewrites `decidability_dev.json`. It was justified by the AI-labelled audit above, so the consolidation is not yet licensed by the playbook's rule (which needs the human audit).
8. **Hygiene:** the report prints the first 20 characters of an API key to the console in `real_run.py` (`Key found: ...`), reads a key file path under another user's profile, and committed `groq_judge_cache.jsonl` (reasoning traces, fine) and the audit key (not fine).

## What to do
- Do not merge `update1` into our branch as is. Cherry-pick only the safe code (`degraded` flag, `--relaxed`, `real_run.py` after removing the key print and reconciling the checker configuration) once asked to merge.
- Keep the Groq gpt-oss-20b row as exploratory.
- Ask the author: who filled the audit, and why was the key committed; which data produced the shift numbers; why p-values are constants.
- Redo Stage 2.3 (real self-consistency), 2.5 (shift/guarantee with real scores) and 2.6 (locked test on untouched halves) properly per `handoff/10_NEXT_STAGE_PLAYBOOK.md`.
- Our human audit (`review/audit2/audit_sample_blind.csv` on `stage2-evidence-bounded-verification`) is still the one that counts.
- Privacy: the audit key on `origin/update1` is now exposed in a public remote. A fresh audit sample would need new items if blinding matters.

Nothing was changed on `update1`, `main`, or our branch except this note and a pointer line in `review/README.md`.
