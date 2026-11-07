> **UPDATE 2026-10-30:** still open: framing confirmation (information-bound study vs system-first), deadline and weekly hours, the 100-case label audit, keys for NVIDIA and other API judges, a check in a browser of `HuanzhiMao/BFCL-Result` and the Jev/CLM model links (not reachable by the tools), whether to run a test half, and a commit. Subagent usage limits: at most three agents at once; resume an interrupted agent with SendMessage.

> **UPDATE 2026-10-20:** the current list of decisions is `review/MASTER_PLAN.md` section 13 (framing A/B/C, keys, Kaggle, labelling, deadline, which "modern LLM", permission to run the Saidso baseline). Keys: set them as environment variables or in `C:\Users\GOVARDHAN SATYA\.mcp_checker_keys.env` (outside the repo); never in chat.

# 07 Open decisions and inputs (blocked on the user)

Each item has a default so work can proceed if the user does not answer. The defaults are marked.

| # | Decision / input | Why it matters | Default if unanswered |
|---|---|---|---|
| 1 | **Deadline and weekly hours** | chooses the 2-week minimum path vs the 4 to 6 week full study (file 03) | assume the minimum path |
| 2 | **Provider keys** (`GROQ_API_KEY`, `NVIDIA_API_KEY`) set by the user as environment variables or Kaggle secrets; never pasted in chat | nothing involving LLM judges can run without them | build everything else; judge runs wait |
| 3 | **Free-tier limits** on each dashboard (requests/minute, tokens/day) | sets the seeded sample sizes (`--limit`) in advance | `--limit 200` dev pilot, 600 test, `--rpm 20` |
| 4 | **Which "modern LLM"** the professor means | the strong-judge baseline should match their expectation | largest model listed by each provider; plus an optional 40 to 60 case manual spot-check pasted into a separate chat with a frontier model (manual, not used for statistics) |
| 5 | **Labelling** (user was unsure): (a) none, (b) user audits about 100 cases (about 45 to 60 min), (c) user plus one volunteer on 50 shared cases | the natural-error labels are automatic; the audit only measures their noise | (b); if (a), state "labels not human-checked" in every result |
| 6 | **Kaggle:** re-authorise the connector (it returned Unauthenticated, later CONNECT_TIMEOUT), confirm Internet On, report weekly GPU hours | lets Claude run/upload notebooks; otherwise the user uploads | notebooks delivered as files; user runs them |
| 7 | **Commit scope** | uncommitted work is large | commit to `review-eval-updates` using the path list in file 03 step 0.1 |
| 8 | **Default mode in the server** | `hybrid` is weak but is the default for backward compatibility | keep until the judge study finishes |
| 9 | **Whether to download `aggrefact_windowed_results.json`** from the Kaggle notebook output | enables error analysis on the full test set | skip; use the 500-claim sample analysis |
| 10 | **Hugging Face access** for gated sets (xLAM optional; Llama models need licence acceptance) | optional datasets/models | use ungated sets and Qwen-family models |
| 11 | **Presentation timing**: when is the project review? which deck is shown? | v9 has 27 slides; the guide assumes about 15 minutes for slides 1 to 25 | present v9 as is; add judge results as they arrive |

## Questions the professor may ask (prepared answers are in `review/SPEAKER_GUIDE.md`)
- "Why not just ask an LLM?": today there is no measured answer; Step 1 of file 03 produces one within a few days of getting keys. Until then the honest answer is the list of untested hypotheses H1 to H6.
- "Is the dataset real?": no, LLM-generated public data plus synthetic injected errors; natural-error set N1 and BFCL are the planned fix.
- "Is the guarantee real?": split-conformal, under exchangeability, verified on one held-out split; cross-dataset test is H6.
