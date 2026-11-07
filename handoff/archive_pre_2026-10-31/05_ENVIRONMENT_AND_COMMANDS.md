# 05 Environment, quirks and commands

Machine: Windows 11, i5-13420H CPU, no NVIDIA GPU, 16 GB RAM. Shells: Git Bash (preferred for scripts) and PowerShell. Disk is tight: `U:` about 2 GB free, `C:` about 18 GB.

## Python environments (important: there are two)
| Env | Path | Has | Use for |
|---|---|---|---|
| `U:\txt\.venv` | `/u/txt/.venv/Scripts/python.exe` | torch 2.14 (CPU), transformers 5.18, spaCy 3.8, models cached; **no pytest, no nbformat, no python-pptx** | anything that loads NLI/NER models (ablation, grounded evaluation, AggreFact sample) |
| default `python` | `C:\Users\GOVARDHAN SATYA\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe` (Python 3.11.9) | pytest 9.1.1, python-pptx 1.0.2 (installed in this session), markdown, numpy, pandas, torch (tests import it) | pytest, building decks/PDFs, the judge script and `eval_argground.py` (no model needed) |
Always run with `PYTHONPATH=.` from the repo root.

spaCy: `en_core_web_trf` is **not** installed; the code silently falls back to `en_core_web_sm`, and result files do not record which was used (known gap).

## Commands that work
```bash
# tests (fast, models mocked)
PYTHONPATH=. python -m pytest tests/test_arg_ground.py tests/test_grounded.py tests/test_proxy.py tests/test_server.py tests/test_schema_alignment.py tests/test_session.py tests/test_constraints.py tests/test_taxonomy.py -q -p no:cacheprovider

# argument-grounding benchmark (network for the build; no model for the evaluation)
python benchmarks/make_argground_bench.py --pages 40 --seed 5          # writes benchmarks/argground_bench.json (git-ignored)
PYTHONPATH=. python benchmarks/eval_argground.py --split dev  --output benchmarks/argground_dev_results.json
PYTHONPATH=. python benchmarks/eval_argground.py --split test --output benchmarks/argground_test_results.json   # evaluate test sparingly; see PREREGISTRATION

# text-level generated sets, ablation, grounded mode (models; use the .venv python; ~2 min per 35 cases, ~13 min per 210)
python benchmarks/make_mcpevol_v2.py                                             # v2 (seed 7)
python benchmarks/make_mcpevol_v2.py --seed 11 --prefix V3 --out benchmarks/mcpevol_v3.json
PYTHONPATH=. /u/txt/.venv/Scripts/python.exe benchmarks/ablation_local.py --dataset benchmarks/mcpevol_v3.json --output benchmarks/ablation_results_v3.json --veto-threshold 0.55
PYTHONPATH=. /u/txt/.venv/Scripts/python.exe benchmarks/eval_grounded.py --dataset benchmarks/mcpevol_v3.json

# AggreFact laptop sample (about 35 min CPU)
PYTHONPATH=. /u/txt/.venv/Scripts/python.exe benchmarks/aggrefact_sample.py --n 500 --seed 42

# LLM judges (needs a key in the environment; PowerShell: $env:GROQ_API_KEY="...")
python benchmarks/llm_judge_args.py --self-test
python benchmarks/llm_judge_args.py --list-models --provider groq
python benchmarks/llm_judge_args.py --provider groq --model <id> --split dev --limit 200 --dry-run
python benchmarks/llm_judge_args.py --provider groq --model <id> --split dev --limit 200 --rpm 20
```

## Quirks that cost time (read before touching anything)
1. **Bash heredocs mangle backslashes and some quoting.** A Python script inserted through `python - <<'EOF'` once turned `\b` into raw backspace characters (`\x08`) inside a regex, silently breaking clock-time matching in `arg_ground.py` (found by a unit test; fixed by byte replacement). Rule: for any script containing regexes, backslashes or nested quotes, create the file with the editor/Write tool and run it; do not pipe it through a heredoc. If you must patch regexes, check with `repr()`.
2. **Edge headless PDF generation is flaky:** `msedge.exe --headless --disable-gpu --no-pdf-header-footer --print-to-pdf=<path> file:///<html>` sometimes silently writes nothing; retry (up to 3 times) and check the file timestamp. Markdown to HTML uses the `markdown` package with `tables`, `sane_lists`, `nl2br` and a blank line inserted before bullet lists.
3. **Deck rendering:** PowerPoint COM works for exporting slides to PNG (`Presentations.Open(path, ReadOnly, ...)`, `Slide.Export`); LibreOffice is not installed. A deck that is open in PowerPoint is locked; save under a new name (this is why there are v1 to v9).
4. **Decks v7 to v9 were produced by editing the previous deck with python-pptx** (clone a slide, rebuild shapes, renumber footers). Footer numbers are static text boxes at x=9.0 in, y=5.3 in; renumber after inserting slides. The pptxgenjs sources for v3 to v6 are gone.
5. **Scratchpad is wiped between days.** Do not leave the only copy of a script there.
6. **Web tools:** `WebSearch`/`WebFetch` failed with a model error in this environment; `curl` works for arXiv (`https://arxiv.org/abs/<id>` pages, PDFs), GitHub raw files, Hugging Face (`https://huggingface.co/api/datasets/<id>`, datasets-server `https://datasets-server.huggingface.co/rows?...`). The arXiv listing API (`export.arxiv.org/api/query`) returned empty; use the abs pages.
7. **Windows + Hugging Face cache** prints a symlink warning; harmless.
8. **Kaggle connector** was unauthenticated and later timed out; Kaggle runs so far were done by the user in the browser. Notebooks need Internet On (phone-verified account) and the T4 GPU.
9. **LLM-AggreFact** is gated (the user had access); never redistribute it (CC-BY-ND-4.0).
10. **Git:** `git add -A` would stage caches and obsolete decks; stage explicit paths. LF to CRLF warnings are harmless.
11. **Benchmark builds can differ slightly between runs** (page fetch failures change the case count); dev/test split is by premise with a fixed seed, so a rebuilt benchmark gives a different split membership. Treat a rebuilt benchmark as a new benchmark, record the case count and a hash, and prefer committing the generated JSON for the final runs.

## Standing procedure for any new result
Write the script first; run on **dev**; look; fix bugs (unit-test them); run on **test once**; record numbers and caveats in `handoff/02_EXPERIMENTS_AND_RESULTS.md` and `STATUS.md`; if the test half was seen before a change, say so.
