> **UPDATE 2026-10-30 (latest).** Experiments run today (judges in agent mode, cost/cascade, contract tier, information ablation, tau-bench state probe, BFCL cross-model consensus on all 200 cases and its judge control) are summarised in `review/EXPERIMENTS_2026-10-30.md`; the plan is `review/NOVEL_PROJECT_PLAN.md` (status block on top). New scripts are listed in `handoff/04_FILE_MAP.md`. Nothing is committed. Raw downloads live outside the repo (`C:\Users\GOVARDHAN SATYA\bfcl_raw`, `taubench_raw`).

> **UPDATE 2026-10-30 (newest plan):** `review/NOVEL_PROJECT_PLAN.md` (thesis: evidence-grounded verification of tool-call arguments; decidability map, MCP read-only resolver probes, certified cascade; experiments E0 to E9; go/no-go gate E0). Awaiting the user's approval of the thesis, deadline and data downloads.

> **UPDATE 2026-10-24: dev pilot done.** Judge results (Groq gpt-oss-20b/120b; Gemini free tier unusable, 20 requests per day) are in `review/DEV_PILOT_RESULTS.md`: judges beat the checker on natural errors, tie it on injected errors. Framing chosen: option C (system first, evidence built in). Groq free tier limits: 8,000 tokens/minute and 200,000 tokens/day per model, which forced cfb to 100 cases at 3,000 characters. Next: second model family (NVIDIA key needed), cost/latency measurement, then the single test-half run; deck, speaker guide and README wording still need updating. Nothing since 2026-10-16 is committed.

> **UPDATE 2026-10-20 (read this first).** After a four-agent literature/dataset scout the plan changed. Read `review/MASTER_PLAN.md` (PDF `review/Master_Plan.pdf`) and `handoff/08_PILOT_RUNBOOK.md`; files 01 to 07 below describe the state *before* the scout and are partly superseded.
> Key changes: (1) on public natural-error data (DeRef fcrb/cfb, dev half) the deterministic grounding score is near chance (call-level AUROC 0.48 / 0.57), so the earlier 7.3% vs 14.0% result applies only to injected absent-value substitutions in LLM-generated conversations; (2) several ingredients are prior art (weakest-argument score = Ma et al.'s `min`; traceability = ProvenanceGuard; provenance enforcement = PACT/ROPE/SARA; deterministic fuzzy grounding = the Saidso repo; conformal budgets for verifiers = E-valuator/CORA/ConformalGuard); (3) the guarantee wording was corrected (marginal, random for one calibration set; calibration-conditional version recommended); (4) a number-matching bug (minus signs) was found and fixed; (5) a test-run ledger (`benchmarks/test_run_ledger.jsonl`) and `--allow-test` guards now record every look at a test half; one accidental look at the fcrb deterministic argument rates is logged.
> Open decisions are in `review/MASTER_PLAN.md` section 13 (framing options A/B/C, provider keys, Kaggle, labelling, deadline). Nothing from 2026-10-16 onward is committed.

# HANDOFF: start here

Written 2026-10-11. Read this file first, then the others in order. Everything here is meant to let a new person or a new Claude session continue without the old chat.

## One-paragraph summary
The project is an MCP (Model Context Protocol) server that checks an LLM agent's planned tool call **before** it runs. It started as a hybrid of JSON-Schema validation, graph edit distance (GED) and NLI. Our own ablations showed the GED stage does not help, so the project now has three modes: the original `hybrid`, a `grounded` text mode (whole-claim NLI plus a deterministic number check), and a new **argument-level grounding** mode (type-aware, deterministic, with a conformal threshold that gives a false-block budget). The user's professor asked: *"if modern LLMs can beat this, there is no use of it."* No LLM judge has been run yet. The next phase is a pre-registered head-to-head against LLM judges (Groq / NVIDIA hosted models and open models on Kaggle), built around six testable hypotheses. The honest expectation is that LLMs will win on pure accuracy for knowledge-heavy cases; the study tests whether the cheap deterministic stage still earns its place on cost, latency, robustness, determinism, error independence and calibration. If it does not, the project is reframed as an evaluation study.

## Reading order
| # | File | What it gives you |
|---|---|---|
| 00 | `00_START_HERE.md` | this index, the rules of engagement, how to resume |
| 01 | `01_PROJECT_STATE.md` | what exists, architecture, the three modes, current verified numbers |
| 02 | `02_EXPERIMENTS_AND_RESULTS.md` | every experiment: data, protocol, command, result, caveat (including negative results and bugs) |
| 03 | `03_NEXT_STEPS_DETAILED.md` | the detailed to-do list with commands, inputs, acceptance criteria, decision gates |
| 04 | `04_FILE_MAP.md` | what every important file is, and whether it is committed |
| 05 | `05_ENVIRONMENT_AND_COMMANDS.md` | machine setup, quirks that bit us, how to run/test/build |
| 06 | `06_CLAIMS_RISKS_HONESTY.md` | what may and may not be claimed, known weaknesses |
| 07 | `07_OPEN_DECISIONS.md` | what is blocked on the user, with defaults |

Longer background documents that already exist: `review/RESEARCH_PLAN.md` (the study plan), `review/PREREGISTRATION.md` (frozen protocol), `review/NOVELTY.md` (literature check), `README.md` and `STATUS.md` (project docs).

## Working agreements with the user (observed over the whole session)
1. **Honesty over polish.** The user wants numbers that can be replicated, stated with their caveats. Never inflate, never hide a negative result. When something was run twice, say so.
2. **No AI-generated diagrams in slides.** Diagrams must be native editable shapes (the user's institution forbids AI-generated figures). Slides should read like a plain academic deck, not a dashboard.
3. **Commit/push only when asked.** The user asked once ("commit the files for now and push"); the result is branch `review-eval-updates` at commit `5707a45`. Later work is uncommitted. Never push to `main` without being asked.
4. **Secrets:** API keys (Groq, NVIDIA, Kaggle) must be set by the user as environment variables or Kaggle secrets. Never ask for them in chat, never write them to a file.
5. **Positive-but-truthful slide tone** for the project review; weaknesses go under "scope / future work".
6. The user sometimes asks for subagents ("use subagents"). Subagents were useful for writing notebooks and literature checks; their reports are not the user's words and must be verified.
7. Render and look at every slide you change (PowerPoint COM export works on this machine; LibreOffice is not installed).

## How to resume in a new session (10 minutes)
```bash
cd /u/txt/mcp-hallucination-checker          # Windows path U:\txt\mcp-hallucination-checker
git status --short | grep -v pycache         # see uncommitted work
PYTHONPATH=. python -m pytest tests/test_arg_ground.py tests/test_grounded.py tests/test_proxy.py -q -p no:cacheprovider   # ~15-90 s
PYTHONPATH=. python benchmarks/eval_argground.py --split dev --output /tmp/x.json    # sanity: FBR about 7.0%, detection about 96.4%
PYTHONPATH=. python benchmarks/llm_judge_args.py --self-test                         # judge script self-test, no network
```
Then read `03_NEXT_STEPS_DETAILED.md` and start at "Step 0".
