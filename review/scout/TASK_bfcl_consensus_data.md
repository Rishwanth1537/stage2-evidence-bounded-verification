# BFCL cross-model consensus data: scout report

Status: DONE. Dataset built at `benchmarks/data/bfcl/consensus_cases.json` (git-ignored, 4.0 MB).
Loader: `benchmarks/load_bfcl_consensus.py` (`fetch` then `build`; stdlib only; reads JSON only; nothing imported from `server/pipeline`).

## 1. Source discovery
- `https://huggingface.co/api/datasets/HuanzhiMao/BFCL-Result` -> HTTP 401 "Invalid username or password" with curl. Same for `/tree/main`, `resolve/main/README.md`, and ~10 spelling variants. HF answers 401 for nonexistent or private repos, and `HuanzhiMao` has no public datasets (API author listing shows 2 models and 1 space). So that repo is not publicly reachable; do not cite it.
- Gorilla GitHub repo: `result/` and `score/` folders never existed in history (commits API for both paths is empty); only prompts and gold live under `berkeley-function-call-leaderboard/bfcl_eval/data`.
- Found the substitute: **`https://huggingface.co/datasets/AgentSuite/BFCL_V4-trajectories`** (public, ungated, third party, not the official leaderboard). 30 models, 5,865 tasks each, one `{model}.jsonl` per model (38-62 MB each, ~1.45 GB total, so downloaded with HTTP Range requests only; file sizes from `https://huggingface.co/api/datasets/AgentSuite/BFCL_V4-trajectories/tree/main`).
- **Licence actually seen**: the AgentSuite dataset card declares none (tags only: agent, function-calling, tool-use, llm-trajectories). Prompts/gold come from the gorilla repo, Apache-2.0 (`https://raw.githubusercontent.com/ShishirPatil/gorilla/main/LICENSE`). Treat model outputs as research-use, do not redistribute.
- Prompts, schemas, gold: `https://raw.githubusercontent.com/ShishirPatil/gorilla/main/berkeley-function-call-leaderboard/bfcl_eval/data/BFCL_v4_{simple_python,parallel,multiple,parallel_multiple,live_simple,live_multiple}.json`, gold in `.../data/possible_answer/BFCL_v4_<same>.json`, case list `.../data/BFCL_v4_format_sensitivity.json`.

## 2. What the dataset really contains (surprising)
- The AgentSuite files contain only three blocks: web_search (multi-turn), memory_* and `format_sensitivity`. The stand-alone simple/multiple/parallel result files are NOT there.
- `format_sensitivity` = 200 official single-turn test cases x 26 prompt-format configurations (5,200 lines per model; case composition: simple_python 30, parallel 15, multiple 15, parallel_multiple 15, live_simple 24, live_multiple 86, live_parallel 6, live_parallel_multiple 9). Within a model file, cases are sorted by numeric id; the 26 configs of a case are adjacent (not in a fixed order).
- To make all models see the identical prompt I keep ONE config: `ret_fmt=python&tool_call_tag=False&func_doc_fmt=python&prompt_fmt=plaintext&style=classic`.
- So this is 56 cases (first N by file order per category: simple_python 12, parallel 8, multiple 8, parallel_multiple 8, live_simple 10, live_multiple 10), not the full categories. More cases can be fetched by raising `PER_CAT` (cost about 0.15 MB of transfer per case per model).
- The 30 "models" include variants of the same model (thinking on/off for Claude 4, 4.5, Gemini flash, DeepSeek V3.2; Kimi K2 x2; Qwen3 x4), so errors are correlated; independent families: OpenAI, Anthropic, Google, DeepSeek, Qwen, Moonshot (Kimi). No sub-7B open models; smallest are gpt-4.1-nano, gpt-5-nano, gpt-oss-20b, gpt-4o-mini.
- Fetch method: binary search with 24 KB range probes to locate each category block, then a streamed range read from there; only lines of the chosen config are written to disk (`C:\Users\GOVARDHAN SATYA\bfcl_raw\filtered\<model>.jsonl`, 56 lines each). Transfer total about 250 MB (cap 400 MB), fetch took about 13 min with 8 threads.

## 3. Numbers
- Models: 30. Categories: 6 (above). Test ids: 56. (test_id, model) pairs fetched: 1,680.
- Usable records (calls): **1,499**; malformed: **181** (function name/count mismatch 97, no bracketed call list/prose 29, non-literal value such as `data['sales']` 28, syntax error 17, API 503 inference error 7, other 3). Malformed per category: parallel_multiple 52, live_multiple 45, parallel 45, simple_python 17, live_simple 16, multiple 6.
- Arguments labelled: **5,800**; wrong **222** (3.8%). All wrong are `value_mismatch`; match levels of the correct ones: exact 5,525, loose (punctuation/spacing) 36, normalised (case/whitespace) 17. 3 required arguments omitted in total.
- Consensus index: 235 distinct (test, gold-call, argument) slots; 24 slots have at least one wrong model.
- IMPORTANT caveat for the verifier experiment: 182 of the 222 wrong labels sit in slots where at least half of the models are "wrong", i.e. most gold-wrong arguments are gold-vs-consensus disagreements (e.g. gold wants "5 pm" while everyone writes "5:00 pm", gold 0.04 while everyone writes 4, gold expects the literal "next Friday"). Only about 40 labels are "lone-model" errors where the other models agree with gold. A consensus verifier will flag the lone errors but will treat the "everyone wrong" slots as correct; report both subsets separately.
- Disk: raw `C:\Users\GOVARDHAN SATYA\bfcl_raw\` = 13 MB (gorilla data ~5 MB, filtered 30 files, one probe dir); output JSON 4.0 MB.

### Argument-level wrong rate per model (config above)
| model | calls | args | wrong args | wrong rate | malformed |
|---|---|---|---|---|---|
| DeepSeek-R1-0528 | 50 | 198 | 7 | 3.5% | 6 |
| DeepSeek-V3-0324 | 47 | 176 | 6 | 3.4% | 9 |
| DeepSeek-V3.2-Exp-thinking-off | 44 | 168 | 3 | 1.8% | 12 |
| DeepSeek-V3.2-Exp-thinking-on | 50 | 187 | 7 | 3.7% | 6 |
| Kimi-K2-Instruct | 53 | 208 | 7 | 3.4% | 3 |
| Kimi-K2-Instruct-0905 | 53 | 208 | 8 | 3.8% | 3 |
| Qwen3-235B-A22B-FP8 | 51 | 198 | 6 | 3.0% | 5 |
| Qwen3-235B-A22B-Instruct-2507-FP8 | 54 | 213 | 9 | 4.2% | 2 |
| Qwen3-235B-A22B-Thinking-2507-FP8 | 53 | 205 | 7 | 3.4% | 3 |
| Qwen3-Coder-480B-A35B-Instruct-FP8 | 40 | 104 | 5 | 4.8% | 16 |
| claude-4-opus-thinking-off | 53 | 206 | 9 | 4.4% | 3 |
| claude-4-opus-thinking-on-10k | 53 | 204 | 6 | 2.9% | 3 |
| claude-4-sonnet-thinking-off | 52 | 202 | 7 | 3.5% | 4 |
| claude-4-sonnet-thinking-on-10k | 51 | 194 | 7 | 3.6% | 5 |
| claude-4.5-sonnet-thinking-off | 52 | 204 | 7 | 3.4% | 4 |
| claude-4.5-sonnet-thinking-on-10k | 51 | 200 | 6 | 3.0% | 5 |
| gemini-2.5-flash-thinking-off | 53 | 204 | 8 | 3.9% | 3 |
| gemini-2.5-flash-thinking-on | 47 | 192 | 5 | 2.6% | 9 |
| gemini-2.5-pro-thinking-on | 51 | 206 | 9 | 4.4% | 5 |
| gpt-4.1 | 53 | 207 | 10 | 4.8% | 3 |
| gpt-4.1-mini | 51 | 194 | 6 | 3.1% | 5 |
| gpt-4.1-nano | 51 | 208 | 7 | 3.4% | 5 |
| gpt-4o-20240806 | 51 | 196 | 7 | 3.6% | 5 |
| gpt-4o-mini | 50 | 190 | 10 | 5.3% | 6 |
| gpt-5 | 49 | 196 | 9 | 4.6% | 7 |
| gpt-5-nano | 52 | 206 | 12 | 5.8% | 4 |
| gpt-oss-120b | 51 | 188 | 7 | 3.7% | 5 |
| gpt-oss-20b | 29 | 130 | 7 | 5.4% | 27 |
| o3-high | 53 | 207 | 10 | 4.8% | 3 |
| o4-mini-high | 51 | 201 | 8 | 4.0% | 5 |

(Malformed rows are excluded from the call/arg counts; gpt-oss-20b, Qwen3-Coder and DeepSeek-V3.2-off lose the most to unparsable or wrong-function output.)

### Five example wrong arguments, with the other models' values
1. `simple_python_58`, `specific_function`: gemini-2.5-pro wrote `false`; the other 25 models wrote `true`.
2. `parallel_multiple_14`, call 2, `country`: gpt-oss-20b wrote `"Nepa"`; all other 28 wrote `"Nepal"` (a typo, the clean consensus case).
3. `parallel_multiple_43`, call 0, `sculpture_size`: gpt-4o-mini wrote `[48, 48]`; all other 27 wrote `[4, 4]` (unit confusion).
4. `live_simple_13-3-9`, `location`: Qwen3-Coder wrote `"上海, 中国"` (Chinese); 27 others wrote `"Shanghai, China"`, one `"Shanghai, CN"`.
5. `parallel_multiple_91`, call 0, `joules_per_mol`: o3-high wrote `2800000.0`; others `2800.0` (13) or `2800` (4).
Gold-vs-consensus example (not a lone error): `parallel_44`, `date`: 23 of 25 others wrote `"next Friday"`, gpt-5-nano wrote `"2025-10-17"`; here the lone model is actually the one marked wrong, but also `live_multiple_3-2-0` `loc`: gpt-4.1 `"Ha Noi"` vs 17 x `"Ha Noi, Vietnam"` and 8 x `"Hanoi, Vietnam"` (the latter are labelled wrong against gold too).

## 4. Output schema (`consensus_cases.json`)
- `meta`: sources, licences, config, models, counts, comparison description.
- `records[]` (one per usable test_id x model): `test_id, model, category, request, function_schemas, raw_output, lenient_parse, bfcl_meta_valid, calls[]`; each call has `gold_call_index, function, arguments, gold_arguments (list of acceptable values per arg; "" = may be omitted), arg_labels{arg: {label: correct|wrong, match_level, reason}}, missing_required`.
- `malformed[]`: `test_id, model, category, reason, raw_output` (plus pred/gold function lists for name mismatches).
- `consensus_index`: key `"<test_id>|<gold_call_index>|<arg>"` -> `{model: {value, label}}`, ready for cross-model agreement features.
- Comparison rules (independent implementation): NFKC + casefold + whitespace collapse; loose string match ignoring punctuation `, . / \ - _ * ^ ' " backtick`; numeric tolerance (int vs float); numeric string coercion counted correct but tagged level `coerced` (none occurred); ordered list equality; dict equality with key normalisation and per-key alternative lists; any of the gold alternatives; call alignment to gold is order-free (best-score permutation); extra args not in gold are wrong. Lenient parsing accepts bare calls, comma/newline-separated calls and prose around a bracketed list (`lenient_parse: true`).

## 5. Reproduce
`python benchmarks/load_bfcl_consensus.py fetch` (about 13 min, about 250 MB transfer, resumes by skipping non-empty filtered files) then `python benchmarks/load_bfcl_consensus.py build`. Raw dir overridable with env `BFCL_RAW_DIR`.
