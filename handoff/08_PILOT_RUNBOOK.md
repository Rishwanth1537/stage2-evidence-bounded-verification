> **Status 2026-10-31:** the dev pilot described here has been run (Groq gpt-oss 20B/120B; results in `review/DEV_PILOT_RESULTS.md`). For current commands and the agent-mode and NVIDIA procedures use `handoff/09_PIPELINES_HOWTO.md`. The text below is kept for the original protocol.

# 08 Pilot runbook (for when the provider keys exist)

Goal: first answer to the professor's question on the **dev half only**: how do LLM judges compare with the deterministic checker on natural errors, at a matched false-block rate. Nothing in this runbook touches a test half.

## 0. Put the keys somewhere safe (do NOT paste them into any chat or file in the repo)
Choose one:
- **Environment variable, current PowerShell session:** `$env:GROQ_API_KEY = "..."` and/or `$env:NVIDIA_API_KEY = "..."` (then start the commands below from the same window; if Claude Code runs the commands for you, set the variable before launching it).
- **Private key file outside the repo (works for every session):** create `C:\Users\GOVARDHAN SATYA\.mcp_checker_keys.env` in an editor with lines
  ```
  GROQ_API_KEY=your-key
  NVIDIA_API_KEY=your-key
  ```
  Check that the keys are found (names only are printed): `python benchmarks/keys.py`.

Also note on each provider's dashboard the **free-tier limits** (requests per minute, tokens per day). The sample sizes below assume roughly 20 requests per minute and a few hundred thousand tokens per day; change `--limit` and `--rpm` accordingly.

## 1. Look at the models and the prompts first (no judging yet)
```bash
cd /u/txt/mcp-hallucination-checker
python benchmarks/keys.py
python benchmarks/llm_judge_args.py --list-models --provider groq          # choose one small (~8B) and one large (~70B or larger) id
python benchmarks/llm_judge_args.py --list-models --provider nvidia
python benchmarks/load_deref.py                                             # already built; rebuilds cases_fcrb.json / cases_cfb.json
python benchmarks/llm_judge_args.py --provider groq --model <id> --bench benchmarks/data/deref/cases_fcrb.json --split dev --limit 3 --dry-run
```
fcrb contexts are tiny (median 90 characters). **cfb contexts are long (median 9 KB, p90 36 KB):** for the pilot use `--max-context-chars 12000` and state this truncation whenever cfb results are reported; start with fcrb only.

## 2. Pilot: dev half, two judges, fcrb
```bash
python benchmarks/llm_judge_args.py --provider groq --model <small-id> --bench benchmarks/data/deref/cases_fcrb.json --split dev --limit 200 --rpm 20
python benchmarks/llm_judge_args.py --provider groq --model <large-id> --bench benchmarks/data/deref/cases_fcrb.json --split dev --limit 200 --rpm 20
```
Each run prints judge false-block rate, detection and latency/tokens, the deterministic checker on the same cases, and an exact McNemar test. Results are cached in `benchmarks/llm_judge_args_cache.jsonl`, so re-running costs nothing and a rate-limit crash resumes.

Look at: `n_unparseable` (if above about 2% the prompt/model pairing is a problem; **do not edit** `judge_prompts.py` after any test run; during the dev pilot a change must be logged in `review/PREREGISTRATION.md` and the prompt hash updated).

## 3. Derivation-path view (hypothesis H7) on the dev half
```bash
PYTHONPATH=. python benchmarks/analyze_study.py paths --cases benchmarks/data/deref/cases_fcrb.json --split dev \
    --judge benchmarks/llm_judge_args_fcrb_groq_<small>_dev_v0.json --judge benchmarks/llm_judge_args_fcrb_groq_<large>_dev_v0.json
```
This prints, per derivation path and label, the share of arguments flagged by exact match, our checker and each judge (only cases that all systems cover).

## 4. Gate G1 (decide how to continue)
Compare, on dev: (a) judge detection at its own false-block rate against our checker at the same rate (the `h1` analysis needs both a dev and a test judge file; for the pilot read the numbers printed by the judge script), (b) the cascade view with `analyze_study.py cascade` on a dev judge file, which reports escalation share and **leakage** (wrong calls the first stage lets through that the judge would have blocked). If a large judge is far ahead and leakage is high, switch to the evaluation-study framing now (see `review/MASTER_PLAN.md` sections 4 and 9).

## 5. Test halves (only after the dev pilot and the frozen choices)
Use `--split test --allow-test` once per final configuration. Every use is appended to `benchmarks/test_run_ledger.jsonl`; additional runs must be reported. The `h1` analysis needs one dev judge file and one test judge file from the same model/prompt:
```bash
PYTHONPATH=. python benchmarks/analyze_study.py h1 --cases benchmarks/data/deref/cases_fcrb.json \
    --judge-dev <dev judge json> --judge-test <test judge json> --allow-test --note "pre-registered H1"
```

## Privacy and cost
Benchmark text is sent to the provider you choose. No dollar cost is computed; the judge script prints tokens per case so you can price runs with your provider's current rates.

## 7. Judge panel (added 2026-10-24): Claude models and any other provider
`benchmarks/llm_judge_args.py` now supports `--provider anthropic` (native Messages API, key `ANTHROPIC_API_KEY`), `openrouter` (`OPENROUTER_API_KEY`), `gemini`, and `custom` (`--base-url https://host/v1 --key-env NAME`, any OpenAI-compatible endpoint). Claude calls send the same frozen prompt (hash `9b59ae0a3fa5384a`) with temperature 0; if a model rejects `temperature`, the call is retried without it, so record that in the data card.

One command for the dev halves: `python benchmarks/run_judge_panel.py --list` (shows which keys exist), then `python benchmarks/run_judge_panel.py` (or `--only claude-opus`). It reads `benchmarks/judge_panel.json`, skips judges without a key or without a model id, skips finished result files, and prints a summary table. Confirm model ids first with `python benchmarks/llm_judge_args.py --list-models --provider anthropic`. Anthropic and OpenRouter entries are billed: at about 520 tokens per call, 500 dev calls per model is roughly 0.26 million input-plus-output tokens, so check the price first. Test halves are not run by the panel script; use `--split test --allow-test` once per frozen configuration.
