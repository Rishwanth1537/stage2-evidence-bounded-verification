> **SUPERSEDED** by `review/MASTER_PLAN.md` sections 9 and 14 (phases P0 to P8) and `handoff/08_PILOT_RUNBOOK.md`. The step list below pre-dates the scout; keep it only for the engineering backlog and the dataset recipes (which are now detailed in `review/scout/SCOUT_4_datasets_and_natural_errors.md`).

# 03 Next steps, in detail

Goal of this phase: answer the professor's question with measurements. Hypotheses H1 to H6, systems S0 to S10, datasets D1 to D4 and N1, N2, N3 are defined in `review/RESEARCH_PLAN.md` (sections 3 to 5); the frozen protocol is `review/PREREGISTRATION.md`. This file turns them into ordered work.

Legend: **[U]** needs the user; **[C]** can be done by Claude/engineer now; **[K]** needs Kaggle; **[API]** needs a provider key.

## Step 0: unblock inputs and tidy the repo (1 day)
| # | Task | Who | Detail / commands | Done when |
|---|---|---|---|---|
| 0.1 | Commit the current work | [U] decides, [C] does | Everything since `5707a45` is uncommitted. Stage by explicit path, **not** `git add -A`. Include: `server/pipeline/{arg_ground,value_check}.py`, `server/tools/{verify_arguments,verify_grounded}.py`, changes to `server/{main.py,models/schemas.py,pipeline/entailment.py,proxy/interceptor.py}`, `tests/{test_arg_ground,test_grounded}.py`, `benchmarks/*.py` (new scripts), `benchmarks/kaggle_full_run_summary.json`, `benchmarks/mcpevol_v2.json` and `mcpevol_v3.json` (generated, small), `kaggle/*.ipynb`, `README.md`, `STATUS.md`, `.gitignore`, `review/{RESEARCH_PLAN,PREREGISTRATION,SPEAKER_GUIDE}.md`, `review/{Research_Plan,Speaker_Guide}.pdf`, `review/MCP_Hallucination_Checker_Review_v9.pptx`, `handoff/`. **Skip:** old decks v1 to v8, `*.zip`, caches, large result JSONs (already git-ignored), `egg-info`. Branch `review-eval-updates` (push there; never to `main` without being asked). | `git log` shows the commit; `git status` clean except ignored files |
| 0.2 | Provider keys | [U] | Set `GROQ_API_KEY` and/or `NVIDIA_API_KEY` as environment variables (PowerShell: `$env:GROQ_API_KEY="..."` for the session). Never paste keys in chat or files. Also report each dashboard's free-tier limits (requests/minute, tokens/day). | `python benchmarks/llm_judge_args.py --list-models --provider groq` prints model ids |
| 0.3 | Kaggle access | [U] | The Kaggle connector earlier returned *Unauthenticated* and later *CONNECT_TIMEOUT* (disconnected). Re-authorise in claude.ai connector settings, or work manually: upload notebooks yourself. User's Kaggle username: `govardhansatya`; existing private datasets used so far: `llm-aggrefact` (the two parquet shards) and `deberta-nli` (model files); notebook `notebook841f5404bb` (windowed AggreFact eval). Needs Internet On (phone-verified). | quota visible; notebook runs |
| 0.4 | Decisions | [U] | See `07_OPEN_DECISIONS.md` (deadline, which LLM counts as "modern", labelling option). | answered |
| 0.5 | Free disk | [U] | `U:` has about 2 GB free, `C:` about 18 GB. Delete obsolete decks/logs if more space is needed; the Hugging Face cache is on `C:`. | >= 3 GB free on U: |

## Step 1: pilot the judges on the dev half only (1 to 2 days) [API]
Purpose: find out quickly whether the professor's concern is going to bite.
1. `python benchmarks/llm_judge_args.py --provider groq --model <small ~8B id> --split dev --limit 200 --dry-run` (check prompts), then without `--dry-run`. Repeat for a ~70B-class model and for the NVIDIA equivalents. `--rpm` defaults to 20; lower it if 429s appear. Responses are cached in `benchmarks/llm_judge_args_cache.jsonl` (git-ignored).
2. Read the printed JSON: judge FBR/detection with CIs, `n_unparseable`, latency, tokens, and the McNemar line against our checker on the same cases. If `n_unparseable` > 2%, **do not edit** `judge_prompts.py` after any test run; during the pilot (dev only) wording changes are allowed but must be recorded in `PREREGISTRATION.md` "Deviations log" and the prompt hash updated before any test-half run.
3. **Decision gate G1 (pilot):** compare on dev at matched FBR (use `conformal_threshold` on dev scores to pick our tau so our FBR matches the judge's within 1 point; script for this is part of Step 5). Interpretation table is in `RESEARCH_PLAN.md` section 8. If the big judge beats us by far more than 2 points detection even at matched FBR and the cascade cannot close it, plan the "evaluation study" framing now; do not wait for the full study.
Acceptance: pilot table for >= 2 judges x 200 dev cases saved as JSON in `benchmarks/`; a short paragraph added to `STATUS.md` ("pilot, dev half only").

## Step 2: build the other benchmarks (3 to 4 days) [C]
Datasets (all verified reachable 2026-10-09; **schemas not inspected yet**, print them first):
- D2 `NousResearch/hermes-function-calling-v1` (Apache-2.0; configs `func_calling_singleturn`, `func_calling`, `glaive_func_calling`, `json_mode_agentic`, ...). HF datasets-server `rows` endpoint works.
- D3 `Team-ACE/ToolACE` (Apache-2.0).
- D4 BFCL: GitHub `ShishirPatil/gorilla` folder `berkeley-function-call-leaderboard/bfcl_eval/data` (files like `BFCL_v4_multi_turn_base.json`, `BFCL_v4_live_simple.json`); ground-truth answers are in a separate `possible_answer` folder (check); human-curated; best for multi-turn context.
- Optional: xLAM 60k (gated, auto-approval), tau-bench (GitHub, licence not checked).
Work: for each dataset write `make_argground_<name>.py` (copy the recipe in `benchmarks/make_argground_bench.py`: parse calls + preceding context, one-argument injected mutation whose new value is absent from the context, split by conversation, seed recorded, data card), keep builders deterministic and **commit the builders before running any judge on them**. Target >= 1,500 cases each.
Acceptance: `benchmarks/argground_{hermes,toolace,bfcl}.json` built; for each, run `eval_argground.py`-style evaluation of exact vs type-aware (needs a `--bench` path argument; the script already has `--bench`); numbers recorded in `02_EXPERIMENTS_AND_RESULTS.md`.

## Step 3: natural-error set N1 (3 to 4 days) [K or API]
1. Choose agent models: 3 to 4 open instruct models on Kaggle GPU in 4-bit (for example Qwen2.5 3B/7B, Llama 3.x 3B/8B; check licences and gated access) and/or Groq/NVIDIA hosted models. Prompt = function schema + conversation up to the call; ask for the call as JSON. Sample at temperature 0.7 to 1.0 to get diverse errors; one to three samples per prompt.
2. Auto-label (no human judgement): a call is **genuine** iff every argument matches gold after normalisation (case, whitespace, number formatting, ISO date/time vs written, currency code vs name; reuse `server/pipeline/arg_ground.py` helpers carefully so the checker is not grading itself: write a separate comparison function `equivalent(pred, gold)` and unit-test it); **error** iff some value differs. Drop calls with wrong function name or invalid JSON into a separate "malformed" bucket (they are caught by the schema validator, not by grounding).
3. Audit (decision [U] on labelling): sample <= 100 automatic "errors", have one person mark acceptable alternatives ("NYC" vs "New York City"); report label precision; repeat 50 after a week for self-consistency. No inter-rater claim.
Acceptance: `benchmarks/natural_errors.json` (>= 1,000 candidate errors, >= 1,000 genuine calls from the same prompts), data card describing models/temperatures/prompts, audit result.

## Step 4: run all systems on all sets (3 to 4 days)
- S3 DeBERTa whole-call NLI and S4 MiniCheck on D1 to D4 + N1 [K GPU]: adapt `kaggle/minicheck_in_pipeline.ipynb` / `aggrefact_windowed_eval.ipynb` patterns; hypothesis text for NLI: "The assistant calls {name} with {arg} = {value}" per argument (fix before running).
- S5/S6 open judges on Kaggle [K]: new notebook using 4-bit models with the **same frozen prompt**; also record token probabilities of the "supported" decision so the judge can be conformalised.
- S7/S8 hosted judges [API]: `llm_judge_args.py` on the **test** half, once per configuration, with identical seeded samples across providers. Use `--variant 0` for main results and `--variant 1..4` only for the H4 study.
- S10 self-consistency: run variant 0 three times at temperature 0 is pointless; use temperature 0.7 for the three votes (add a `--temperature` option to the script first; it is currently fixed at 0).
Rule: nothing tuned on the test half; each final configuration evaluated once; record every extra run.

## Step 5: analyses for H1 to H6 (4 to 6 days) [C]
Scripts to write (none exist yet):
| Hypothesis | Script / notebook | Inputs | Output |
|---|---|---|---|
| H1 matched-FBR comparison | `benchmarks/analyze_h1.py` | per-case scores/verdicts of S2 and each judge | detection gap at matched FBR with one-sided CI and non-inferiority test (margin 2 points) |
| H2 cascade and cost | `benchmarks/analyze_cascade.py` | S2 scores, judge verdicts, measured latency/tokens | escalation fraction, cascade accuracy vs judge-only, latency and token savings (no dollar figures unless the user supplies prices) |
| H3 injection | `benchmarks/make_injection_set.py` + run judges | 500 D1-test cases, 5 instruction-injection families (approve-instruction, role-play, delimiter spoofing, multilingual, fake system message) | detection drop per family and per system |
| H4 determinism | `benchmarks/analyze_variance.py` | repeated runs, 5 prompt paraphrases | flip rate, Fleiss kappa |
| H5 independence | `benchmarks/analyze_independence.py` | N1 with each agent model and the judges | phi coefficient between agent error and judge miss, McNemar, OR-combination curve |
| H6 shift | `benchmarks/analyze_conformal_shift.py` | S2 scores on D1..D4 | FBR vs budget per dataset after calibrating on D1 only; coverage table |
All use bootstrap over conversations (>= 1,000 resamples), exact McNemar for pairs, Holm correction across H1 to H6, effect sizes with CIs. Put results in `benchmarks/*_results.json` (git-ignored pattern) plus a summary JSON committed like `kaggle_full_run_summary.json`.

## Step 6: decide and write up (4 to 5 days)
1. Apply the decision table in `RESEARCH_PLAN.md` section 8 **as written**; do not change criteria after seeing results (if a criterion must change, log it in the Deviations log).
2. Update `README.md`, `STATUS.md`, the deck (new slides for judge comparison, robustness, cascade; keep the plain style; render and check each slide), `review/SPEAKER_GUIDE.md` and its PDF.
3. Rewrite the project's one-sentence claim to whatever the data supports, using the safe wording in `06_CLAIMS_RISKS_HONESTY.md`.

## Minimum viable path (about 2 weeks, if the deadline is tight)
Step 0 (all) then Step 1 (two judges on dev), Step 2 for D1 only (reuse), a **100-case natural-error set built by hand or with one open model**, Step 4 for S1, S2, one open judge and one hosted judge on D1-test only, Step 5 for H1 and H2 only, Step 6. State clearly what was not tested (H3 to H6, cross-dataset).

## Engineering backlog (small, any time)
- Add `--temperature` and `--max-tokens` options to `benchmarks/llm_judge_args.py`; add a `--bench` override test.
- Per-argument judge output (currently call-level) for localisation comparison with `verify_argument_grounding`.
- `make reproduce` target that regenerates every table from saved JSON.
- Ablate each normaliser in `arg_ground.py` (numbers, spelled-out, ISO dates, currency, stemming, fuzzy) on the D1 dev half.
- Consider a boolean check from cue words; consider a lightweight alias table (ticker/company, country/currency) but report it as world knowledge added by hand.
- CI currently runs pytest on Python 3.10 to 3.12 and ruff; new files should pass `ruff check`.
