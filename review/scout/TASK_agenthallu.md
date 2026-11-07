# TASK: AgentHallu scout

## Licence (read before building)
- LICENSE file: "This work is licensed under a Creative Commons Attribution 4.0 International License" (CC BY 4.0).
- README "License" section: "This dataset is under CC-BY 4.0 license."
- Result: research use and redistribution of analysis are permitted with attribution. Proceeding. Cite: Liu et al. 2026, arXiv 2601.06818.

## Download
- Cloned liuxuannan/AgentHallu (depth 1) to C:\Users\GOVARDHAN SATYA\agenthallu_raw\repo
- Commit: 9ffe8bc888feaf15d89833f4b0e3c4697f44acc1
- Size: 36 MB on disk including .git (cap 100 MB OK).
- Note: repo contains a `.env` file and a `Lib/` Python folder; neither was opened or executed. Only AgentHallu/*/*.json is read.

## Layout
- AgentHallu/<framework>/NNN.json, 693 trajectories (BFCL 164, Camel 93, Magentic_One 94, Octotools 47, OpenDeepSearch 100, OpenManus 104, SmolAgents 91). README says 5 domains.
- Record keys: model_id, agent_type, question (list of turns for BFCL), true_answer, question_source, question_domain, explanation, history[ {step, role, content, tool_calls[{name, arguments}], tool_responses[]} ], agent_answer, is_hallucination ("true"/"false"), hallucination_step (string; absent on clean records), hallucination_category, hallucination_subcategory, hallucination_reason (human text).
- Labels are trajectory-level plus the FIRST hallucinating step (step granularity, not call granularity).

## Counts
- Hallucinated 103 of 164 in BFCL; clean BFCL 61. Tool-Use categories are ONLY in BFCL: Incorrect Tool Arguments 36, Missing Required Call 32, Unnecessary Tool Call 23, Parallel Call Conflict 12.
- All other frameworks (Camel, Magentic_One, Octotools, OpenDeepSearch, OpenManus, SmolAgents) have zero tool-argument category cases (Planning/Retrieval/Reasoning/Human-Interaction only). Clean trajectories there: Camel 36, Magentic 40, Octotools 17, ODS 42, OpenManus 20, Smol 34.
- Of the 36 Incorrect-Tool-Arguments trajectories: attributed step has exactly 1 tool call in 31; 2-3 calls in 4 (wrong call ambiguous, skipped); 1 attributed step is a text-only step (no call, skipped).
- Clean BFCL: 61 trajectories, 452 calls, 49 with empty arguments (dropped), 403 kept.

## Built
- Builder: U:\txt\mcp-hallucination-checker\benchmarks\load_agenthallu.py (usage: python -I benchmarks/load_agenthallu.py <clone> [--all-frameworks]). JSON read only.
- Output: U:\txt\mcp-hallucination-checker\benchmarks\data\agenthallu\cases.json (git-ignored): 434 cases = 31 label False (Incorrect Tool Arguments) + 403 label True (clean, BFCL only). All split "dev". Premise = task + preceding assistant text/calls/results, last 6000 chars (no case reached the 6000 cap).
- Extra fields: framework, human_reason (positives only), top-level "skipped".

## Caveats / surprises
- human_reason LEAKS the label and explanation; never feed it to a checker. Drop it when evaluating.
- Positive count is small (31), class imbalance 31:403; subsample clean for balanced eval.
- Attribution is first-hallucination step. Earlier calls in hallucinated trajectories are not labelled clean (e.g. BFCL/000 has a typo'd key "sofdeurce" at step 1 yet attribution is elsewhere), so I used only fully clean trajectories for label True.
- Positives are mostly "semantic overreach" (extra content/wrong field placement), not schema errors. Argument strings contain doubled-escaped "\n".
- Clean trajectories still contain calls that returned tool errors; label True means "no human-attributed hallucination", not "call succeeded".
- Repo includes .env and Lib/ (not opened/executed).

## Examples (trimmed)
1. agenthallu:BFCL/002:s6 label False: echo {file_name: "TeamNotes.txt", content: "TeamNotes.txt\n\nPurpose: ... Simona: Collaboration leads to success ... [Start adding your ideas here]"}. Human: whole template inserted instead of only the requested line.
2. agenthallu:BFCL/021:s9 label False: create_ticket {priority 3, title "emergency", description "Servers are down unexpectedly. Initial project plan details."}. Human: invented phrase added to description.
3. agenthallu:BFCL/001:s6:c0 label True: grep {file_name: "log.txt", pattern: "Error"} after cd archive, in a clean trajectory.
