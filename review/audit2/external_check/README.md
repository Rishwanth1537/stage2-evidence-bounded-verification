# External check: how to use this folder

Files: `audit_sample_blind.csv` (the 98 unlabelled rows), `RULES_AND_PROMPT.md` (the final rules, including the decisions made on 2026-11-04, and the prompt).

1. Give another model the prompt in `RULES_AND_PROMPT.md` and `audit_sample_blind.csv`, nothing else. Save its answer as JSON, for example `other_model_answers.json`, in the format given at the end of the rules file. (If the model answers in CSV or text, convert it to that JSON list.)
2. Compare with Claude's labels (kept separately in `review/audit2/claude_manual_answers.json`, which the other model must not see):
```bash
python -I benchmarks/compare_two_audits.py review/audit2/claude_manual_answers.json other_model_answers.json
```
It prints Q1 agreement, Cohen's kappa, the Q2 agreement, a confusion table and every disagreement with the other model's note, so each can be settled one at a time.
3. To test the decidability classes and label precision with the other model's answers, use the project key as before (analyst only):
```bash
python -I benchmarks/compare_audit.py --json-glob other_model_answers.json --key review/audit2/audit_key_DO_NOT_OPEN.csv --lo B001 --hi B098
```
Notes: these are AI labels. The rules were written after the Claude labelling and include decisions the project owner made on the doubtful items, so agreement partly measures how well the rules transmit the decisions; the first pass of Claude labels did not use them. A second external run with the rows in reverse order (reverse the CSV rows) gives a test-retest figure.
