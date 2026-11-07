> **Status 2026-11-01:** items 1-4 approved by the user and downloaded (AgentHallu CC BY 4.0 verified; AgentDojo checkout is 434 MB on disk although the download was 37 MB; MCP-Atlas 15.6 MB; tau2-bench data 11 MB of the 25 MB, big task and PDF files skipped). ToolSandbox not downloaded. Reports: `review/scout/TASK_agenthallu.md`, `TASK_mcpatlas_tau2.md`, `TASK_agentdojo.md`.

# Download request (needs the user's yes; nothing has been downloaded) - 2026-10-31

Sizes are those reported by the GitHub and Hugging Face APIs on 2026-10-31. Everything would go outside the repository under `C:\Users\GOVARDHAN SATYA\` (new, empty folders) and be read as data only (no downloaded code is executed). Total of the recommended items: about 90 MB.

| # | Dataset | Source | Size | Licence (as reported) | Purpose | Recommend |
|---|---|---|---|---|---|---|
| 1 | AgentHallu (human-attributed hallucinations in agent trajectories; includes tool-argument errors) | GitHub `liuxuannan/AgentHallu` | 7 MB | API shows NOASSERTION; earlier scout read CC-BY-4.0 in the README - **I will read the README/licence file first and stop if it forbids research use** | human-labelled gold for the audit and a confirmatory slice | yes |
| 2 | tau2-bench task definitions and databases | Hugging Face `HuggingFaceH4/tau2-bench-data` | 25 MB | MIT | untouched stateful benchmark for the locked test (tasks, no trajectories) | yes (the GitHub repo is 453 MB; not needed) |
| 3 | MCP-Atlas (real MCP servers, tasks) | Hugging Face `ScaleAI/MCP-Atlas` (parquet) | 16 MB | CC-BY-4.0 | MCP-native slice; checks that findings are not BFCL-only | yes |
| 4 | AgentDojo (injection runs, MIT) | GitHub `ethz-spylab/agentdojo` | 38 MB | MIT | robustness slice (value planting) | yes, later |
| 5 | ToolSandbox | GitHub `apple/ToolSandbox` | 0.1 MB | NOASSERTION (read the licence first) | stateful tool use with milestones | only after reading its licence |
| 6 | Full BFCL leaderboard outputs | `HuanzhiMao/BFCL-Result` | - | - | not reachable (HTTP 401) | user can check in a browser |

Not requested: the 453 MB tau2-bench repository, the 3 GB BFCL result repository, anything gated.

Reply with "approve 1-4" (or a different list) and I will download, check the licences, build the cases and decidability labels, and report. Item 1 depends on its licence text.
