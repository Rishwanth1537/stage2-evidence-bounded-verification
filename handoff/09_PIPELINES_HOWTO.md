# 09 How to rerun every experiment (current as of 2026-10-31)

All commands run from the repo root `U:\txt\mcp-hallucination-checker` (Git Bash). `PYTHONPATH=.` is required. Use the default `python` unless a command says `.venv`. **Write scripts with the Write/Edit tools, never with `python - <<EOF` heredocs when the code contains `\n` or backslashes** (the shell turns them into real characters; this broke code four times). Use `python -I` for throw-away scripts so the scratchpad cannot shadow standard-library modules.

## A. Keys and models
```bash
python benchmarks/keys.py                                   # which keys are visible (names only); file: C:\Users\GOVARDHAN SATYA\.mcp_checker_keys.env
python benchmarks/llm_judge_args.py --list-models --provider groq|nvidia|gemini|anthropic|openrouter
```
NVIDIA lists many models the account cannot call (HTTP 404 "Function not found"). Callable on 2026-10-31: `nvidia/nemotron-3.5-bolt-e4b`, `nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/nemotron-3.5-super-vl-120b-a12b`, `nvidia/nemotron-3-ultra-550b-a55b`, `nvidia/ising-calibration-1.5-31b`, `poolside/laguna-xs-2.1`, `deepseek-ai/deepseek-v4.1-flash`, `z-ai/glm-5.3-flash`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`. Groq: `openai/gpt-oss-20b`, `openai/gpt-oss-120b` (free tier 8,000 tokens per minute and 200,000 tokens per day per model). Gemini free tier: 20 requests per day, not usable.
Reasoning models need token headroom: `llm_judge_args.chat` raises `max_tokens` for gpt-oss (1,500, `reasoning_effort=low`), Gemini, and names containing `nemotron-3`, `deepseek-v4`, `glm-5`, `reasoning` (2,500).

## B. Datasets and where they come from
| Data | Command / source | Notes |
|---|---|---|
| DeRef fcrb, cfb (cases with dev/test split by query id, seed 11) | `python benchmarks/load_deref.py` -> `benchmarks/data/deref/cases_{fcrb,cfb}.json` | Apache-2.0; test halves untouched except the ledger entries |
| tau-bench (MIT) | clone at `C:\Users\GOVARDHAN SATYA\taubench_raw\repo`; cases in `benchmarks/data/taubench/cases.json` via `benchmarks/taubench_state_probe.py` | 1,980 recorded runs, 737 suspect write calls |
| BFCL 30 models x 200 single-turn cases | `python benchmarks/load_bfcl_consensus.py fetch` then `build` -> `benchmarks/data/bfcl/consensus_cases.json` | source `AgentSuite/BFCL_V4-trajectories`, **no declared licence**; about 950 MB transferred, 24 MB kept; raw slices in `C:\Users\GOVARDHAN SATYA\bfcl_raw\filtered`; `HuanzhiMao/BFCL-Result` is NOT reachable |
| Injected absent-value set (ArgGround-Bench) | `python benchmarks/make_argground_bench.py ...` -> `benchmarks/argground_bench.json` | LLM-generated Glaive v2 conversations; scoped claims only |
| Schema-augmented benches | `python benchmarks/make_ablation_benches.py` (fcrb + BFCL 5-model sets with definitions), `... note` (rule sentence inside the case text for API judges), `... bfcl200` (924-call control set) | all git-ignored under `benchmarks/data/` |

## C. Judges
- **API judge (temperature 0, frozen prompt hash `9b59ae0a3fa5384a`)**: `python benchmarks/llm_judge_args.py --provider P --model M --bench <cases.json> --split dev --limit 200 --rpm 20 --out <file>`; `--max-context-chars N` for long contexts (cfb: 3000); `--split test` needs `--allow-test` and writes the ledger. Panel runner: `python benchmarks/run_judge_panel.py --list` (config `benchmarks/judge_panel.json`). NVIDIA size ladder: `bash benchmarks/run_nvidia_ladder.sh` (logs in `/tmp/nvidia_ladder`).
- **Claude subagent judge (agent mode)**: `python benchmarks/agent_judge.py make --tag T --bench B --limit N [--schema-note] --out DIR` builds unlabelled batch files (25 items each) under DIR/T; launch one agent per about 10 batches with the instructions used in the session (read batch_k.txt, write DIR/T/results/NAME/batch_k.json; open nothing else; at most three agents at once; an interrupted agent is resumed with SendMessage); then `python benchmarks/agent_judge.py ingest --tag T --name NAME --out DIR --bench B --limit N` and score with `llm_judge_args.py --provider custom --base-url http://127.0.0.1:9/v1 --key-env AGENT_JUDGE_KEY --model agent-NAME ...` (set `AGENT_JUDGE_KEY=x`; everything is a cache hit, no network). Use the same `--limit`/`--seed`/`--bench` as `make`.

## D. Analyses
| Question | Command |
|---|---|
| judge vs checker, paired test | printed by `llm_judge_args.py` |
| per-derivation-path flags | `python benchmarks/analyze_study.py paths --cases benchmarks/data/deref/cases_fcrb.json --split dev --judge <rows.json> ...` |
| cascade sweep | `python benchmarks/analyze_cascade.py --dataset fcrb|cfb|injected --judge <rows.json> ...` |
| cost and speed | `python benchmarks/measure_cost.py` |
| contract tier / complement | `python benchmarks/contract_tier.py`, `python benchmarks/contract_complement.py` |
| information ablation | `python benchmarks/analyze_schema_ablation.py` |
| consensus, judge control | `python benchmarks/analyze_consensus.py --out ...`, `python benchmarks/compare_consensus_judge.py --judge <rows.json>` |
| ask-policy, conformal rules, 1,000 re-splits | `python benchmarks/ask_policy.py` |
| decidability labels + blind audit sample | `python benchmarks/decidability.py --audit` -> `review/audit/` |
| state lookup on tau-bench | `python benchmarks/taubench_state_probe.py` |
| NLI role-contrast | `.venv` python: `benchmarks/explore_role_contrast.py` |

## E. Rules that keep the study honest
Dev first; look; fix; then each frozen configuration once on test with `--allow-test`; every look at a test half is logged in `benchmarks/test_run_ledger.jsonl`. New hypotheses or prompt variants go into `review/PREREGISTRATION.md` (Deviations log) before the test run. Do not edit `benchmarks/judge_prompts.py`.

## F. Added 2026-11-01
| Task | Command |
|---|---|
| decidability labels (current counts) | `PYTHONPATH=. python benchmarks/decidability.py` -> `benchmarks/decidability_dev.json` |
| fresh audit sample (already built; rebuild only if the rules change) | `PYTHONPATH=. python benchmarks/decidability.py --audit2` -> `review/audit2/` (**overwrites it**; do not run after the user started filling the CSV) |
| compare annotator answers with our classes | `PYTHONPATH=. python benchmarks/compare_audit.py --csv review/audit2/audit_sample_blind.csv --key review/audit2/audit_key_DO_NOT_OPEN.csv` (LLM answers: `--json-glob "<dir>/answers_*.json"`) |
| BFCL on strong errors | `ask_policy.py --strong --out ...`, `compare_consensus_judge.py --strong --judge <rows.json>` |
| size ladder table | `PYTHONPATH=. python benchmarks/analyze_ladder.py` |
| AgentHallu slice: rebuild evaluation file, run, analyse | `python -I benchmarks/load_agenthallu.py <clone>`; `python benchmarks/build_agenthallu_eval.py`; judges as in section C with `--bench benchmarks/data/agenthallu/cases_eval.json --limit 124`; `python benchmarks/analyze_agenthallu.py` |
| agent-mode judges on a new bench | `agent_judge.py make --tag T --bench B --limit N --out DIR`, launch agents on the batch files, `agent_judge.py ingest --tag T --name NAME ...`, then score with `--provider custom --base-url http://127.0.0.1:9/v1 --key-env AGENT_JUDGE_KEY --model agent-NAME` (set `AGENT_JUDGE_KEY=x`) |
| AgentDojo value planting | `PYTHONPATH=. python benchmarks/analyze_agentdojo.py` (clean runs have `attack_type` null, not the string "none") |
Pitfalls added today: `llm_judge_args.py` now reads case files as UTF-8 (files with non-ASCII text crashed the default Windows encoding); null/empty cached replies must both be purged; NVIDIA reasoning models need up to 12,000 tokens and a 240 s timeout; run at most two NVIDIA jobs at a time.

