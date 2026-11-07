# Audit instructions: use THIS folder (audit2), not `review/audit/` (about 45 to 60 minutes, 98 items)

**Why a second sample.** The first sample (`review/audit/`, ids A001-A100) was stratified by my first set of rules and its first half was used to revise those rules, so it can no longer test them independently. **Please audit only `audit_sample_blind.csv` in this folder (ids B001-B098) and skip the old file.** This sample was built under the revised rules, excludes every item of the old sample, and mixes random draws (these give an honest estimate of how often the benchmarks' "wrong" labels are really wrong) with class-stratified draws (these test the rules) and random "correct" controls.

**Do not open** `audit_key_DO_NOT_OPEN.csv` until you have finished; it holds our own labels and would bias your answers.

**What each row is.** An AI agent was about to call a tool. The row shows what the user asked (`conversation_or_context`), the tool, what the agent did (`what_the_agent_did`), the tool's own description of that argument when we have it (`definition_of_argument`), and what the benchmark says (`benchmark_reference`: its accepted values and/or its label). For the tau-bench rows the agent run failed the task and this write call is not one of the task's gold actions.

**Answer two questions per row (use the exact words so we can count them):**

1. `Q1_is_the_agents_value_actually_wrong`: type one of
   - `yes`: the value is wrong for what the user asked,
   - `no`: the value is fine (the benchmark label is wrong),
   - `acceptable alternative`: a different but reasonable way to write the right answer (another date format, "NYC" for "New York", an optional field filled with a sensible value),
   - `cannot tell`.
2. `Q2_what_is_enough_to_decide` (only if Q1 is `yes`): the lowest-numbered source that is enough to tell it is wrong:
   - `conversation`: the user's words alone show it (including: the user named a value and the agent used a different one, or used `dontcare`/a default instead),
   - `tool definition`: the conversation is not enough, but the tool's definition (allowed values, type, documented format) shows it,
   - `system state`: only looking something up in the system's data could show it,
   - `other models agreeing`: nothing above settles it, but you would trust a majority of other AI models,
   - `only the user`: it is a plausible, valid value and only the user could say whether it is what they wanted,
   - `cannot tell`.
   Leave Q2 empty when Q1 is not `yes`.

Use `notes` for anything odd. Work from your own judgement; do not look anything up. At most about a minute per row; if truly ambiguous write `cannot tell`.

**When done:** save the file and tell me the path. I will compute (a) how often the benchmarks' "wrong" label is really wrong, overall (random draws) and per class (stratified draws), (b) the miss rate on the "correct" controls, (c) agreement between your Q2 answers and the revised decidability classes, and report all of it, including a comparison with the Opus pre-audit.
