> **SUPERSEDED 2026-11-01 for the human audit:** use `review/audit2/` (fresh sample B001-B098, revised rules, disjoint from this one). This folder (A001-A100) was used for the Opus pre-audit and for revising the rules (items A001-A050), so it is no longer an independent test. Do not fill it in.

# Audit instructions (about 45 to 60 minutes, 100 items)

**File to fill in:** `audit_sample_blind.csv` (open in Excel or Google Sheets; UTF-8). **Do not open** `audit_key_DO_NOT_OPEN.csv` until you have finished; it holds our own labels and would bias your answers.

**What each row is.** An AI agent was about to call a tool. The row shows what the user asked (`conversation_or_context`), the tool, what the agent did (`what_the_agent_did`), the tool's own description of that argument when we have it (`definition_of_argument`), and what the benchmark says (`benchmark_reference`: its accepted values or its label). For the tau-bench rows the agent run failed the task and this write call is not one of the task's gold actions.

**Answer two questions per row (use the exact words so we can count them):**

1. `Q1_is_the_agents_value_actually_wrong`: type one of
   - `yes`: the value is wrong for what the user asked,
   - `no`: the value is fine (the benchmark label is wrong),
   - `acceptable alternative`: a different but reasonable way to write the right answer (for example another date format or "NYC" for "New York"),
   - `cannot tell`.
2. `Q2_what_is_enough_to_decide`: if the value is wrong, which is the lowest-numbered source that is enough to tell it is wrong?
   - `conversation`: the user's words alone show it,
   - `tool definition`: the conversation is not enough, but the tool's definition (allowed values, type, documented format) shows it,
   - `system state`: only looking something up in the system's data could show it,
   - `other models agreeing`: nothing above settles it, but you would trust a majority of other AI models,
   - `only the user`: it is a plausible, valid value and only the user could say whether it is what they wanted,
   - `cannot tell`.
   For rows where Q1 is `no` or `acceptable alternative` leave Q2 empty.

Use `notes` for anything odd (for example "the benchmark expects an ISO date but the user said next Friday"). Work from your own judgement; do not look anything up. Skim a row for at most a minute. If something is truly ambiguous write `cannot tell`.

**When done:** save the file and tell me the path. I will then compute (a) how often the benchmark's "wrong" label is actually wrong (label precision), (b) how often your Q2 answer matches our rule-based class, per dataset and class, and (c) which rules need fixing before anything is reported.
