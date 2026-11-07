# Scout: MCP-Atlas and tau2-bench-data

Downloaded (user-approved) as untrusted data; parquet/JSON read only, nothing executed, nothing installed.
Locations: `C:\Users\GOVARDHAN SATYA\mcpatlas_raw\` (15 MB), `C:\Users\GOVARDHAN SATYA\tau2data_raw\` (11 MB). Total 26 MB, under the 60 MB cap.

## Licences and cards (verbatim facts)
- ScaleAI/MCP-Atlas: YAML `license: cc-by-4.0`; README says "released under the CC-BY-4.0". Public subset of 500 tasks of the MCP Atlas benchmark; "36 real MCP servers and 220 tools"; "3-6 tool calls per task". README: "TRAJECTORY data can be used for post-eval diagnostics. (Note: diagnostics results and processes are not included in the public release)". Paper arXiv 2602.00933.
- HuggingFaceH4/tau2-bench-data: YAML `license: mit`, task_categories text-generation, English. README: "domain data from the tau2-bench repository for agentic evaluation". Nothing else.

## MCP-Atlas
File: MCP-Atlas.parquet, 15,638,757 bytes, 500 rows x 5 string columns.
- TASK: 24-char id. ENABLED_TOOLS: JSON list of 10-25 tools (mostly names; 71 entries are dicts `{name, optionalParams, requiredParams}`); 220 distinct tools across 40 name prefixes (servers).
- PROMPT: single-turn natural-language request. GTFA_CLAIMS: list of verifiable claims for the final answer.
- TRAJECTORY: JSON list of OpenAI-style chat messages (assistant `tool_calls[].function.{name,arguments(JSON string)}`, `tool` messages with `content[].{text,isError}`).
- Counts: 500 trajectories, 2,423 tool calls (106 distinct tool names), all `arguments` parse as JSON. Messages per trajectory 6-34. 4 calls name a tool not in that task's ENABLED_TOOLS list.
- Incorrect or failed trajectories: NONE. It is one reference trajectory per task; every tool result has `isError: false` (0 of 2,423). No model-generated failing runs, no labelled-wrong calls. Some regex hits for "error" in tool text are ordinary content, not failures.
- Caveat: the trajectory is a reference run that includes exploratory calls (for example a repository search before the lookup), so "gold" means "accepted reference call", not a minimal call list.
- Usability for natural tool-call argument errors: none (no negatives). Usable as a clean positives set for false-positive rate (label True), and as a base for synthetic mutation. Real tools with real recorded outputs, so grounding against earlier tool outputs in the same trajectory is possible (not built).

Built: `benchmarks/load_mcpatlas.py` (Write tool, pandas/pyarrow only). Output `benchmarks/data/mcpatlas/cases.json` (git-ignored via `benchmarks/data/`): 2,423 cases, source "mcpatlas", split "dev", label True, premise = task PROMPT, call = {name, arguments}. id = `mcpatlas-<TASK>-<k>`. Note premise does not include earlier tool outputs, so later calls that depend on earlier results (ids, dates) cannot be grounded from the premise alone.

Examples (premise trimmed):
1. `mcpatlas-689f4d693e212e8ef3390731-0` premise "...year difference between the creation of the repository of the shooter game assaultcube and the domain registration date..." call `github_search_repositories {"query":"assaultcube"}`.
2. `mcpatlas-68a398aa2f58036e8d45edcf-2` premise "How many sports games were sold online in the cloud nosql video game store ... Giannis ..." call `mongodb_list-collections {"database":"video_game_store"}`.
3. `mcpatlas-68a398aa2f58036e8d45ee13-4` premise "closing price of microsoft ... nasdaq ... relative strength index" call `twelvedata_GetTimeSeries {"params":{"symbol":"MSFT","date":"2024-02-29","interval":"1day","exchange":"NASDAQ"}}`.

## tau2-bench-data
Repo tree: `domains/{airline,retail,mock,telecom}`, `user_simulator/`. Downloaded all except `telecom/tasks_full.json` (14 MB), telecom workflow `.pdf/.png/.dot/.py` and tech_support_* docs (not needed; skipped to stay lean; `.py` is code and was not fetched).

| Domain | tasks.json | tasks with gold actions / total gold actions | DB |
|---|---|---|---|
| airline | 50 tasks (149 KB) | 43 / 148 | db.json 7.0 MB: 300 flights, 500 users, 2000 reservations |
| retail | 114 tasks (328 KB) | 112 / 553 | db.json 2.8 MB: 50 products, 500 users, 1000 orders |
| telecom | 114 tasks (659 KB); tasks_small 20 tasks | 114 / 516; small 20 / 27 | db.toml 9.6 KB, user_db.toml 0.9 KB |
| mock | 9 tasks | 7 / 7 | db.json 281 B |

Each domain also has policy markdown (airline 7.7 KB, retail 6.7 KB, telecom main_policy 5.7 KB). Task fields: id, description, user_scenario (reason_for_call, known_info, task_instructions), initial_state, evaluation_criteria {actions, communicate_info, nl_assertions}. Gold actions: `{action_id, name, arguments, info}`; common ones: get_reservation_details, update_reservation_flights, cancel_reservation, get_order_details, find_user_id_by_name_zip, return_delivered_order_items, set_network_mode_preference, toggle_airplane_mode.
- Recorded agent trajectories / errors: NONE. Only task specs, gold actions, policies, databases, user-simulator guidelines.
- Legitimate uses with gold actions only: (a) positives (label True) with premise = user scenario + policy; (b) deterministic checks of arguments against the database (does user_id / order_id / reservation id exist, do ids match the user in the scenario); (c) constructed negatives by mutating a gold call (swap id, wrong user, wrong enum or value, drop a required arg), clearly labelled SYNTHETIC mutation, not natural errors; (d) policy-violating calls are NOT derivable from gold alone. Mutated negatives must not be reported as natural error data; any rate measured on them measures sensitivity to the mutation recipe.
- No cases.json was built for tau2 (not requested).

## Verdicts
- MCP-Atlas: clean positives only, no natural errors. Useful for false-positive checks and as mutation base.
- tau2-bench-data: no trajectories, no natural errors. Useful for DB-grounded synthetic negatives only, labelled as such.
