# 07 Open decisions and inputs (rewritten 2026-10-31)

Defaults apply if the user does not answer; the work proceeds on the defaults.

| # | Decision / input | Why it matters | Default |
|---|---|---|---|
| 1 | **Venue and first-draft date** | picks the minimum path (workshop-ready by mid-January) vs a main-track extension; earliest verified deadline: ICLR 2027 workshop papers 1 Feb 2027 | aim at a workshop-ready draft by mid-January, extend if the locked test holds |
| 2 | **Blind audit** (98 items, 45-60 min, **`review/audit2/`**, not the old `review/audit/`) | label precision and the check of the decidability rules; nothing from the labels is a result without it | not started until the user returns the CSV |
| 3 | **Rotate the keys** pasted in chat (Groq, Gemini, NVIDIA) and put new ones only in the private key file | security | user action |
| 4 | **More API keys**: Anthropic API and/or OpenRouter (billed), Hugging Face token | judge panel breadth for a fair main-track table | Groq + NVIDIA + Claude subagents only |
| 5 | **Downloads** (list with sizes and licences in `review/DATA_DOWNLOAD_REQUEST.md`, about 90 MB) | confirmatory and robustness data from untouched sources | none until approved |
| 6 | **Browser checks the tools cannot do**: `https://huggingface.co/datasets/HuanzhiMao/BFCL-Result` (401 for us), Jev model and blog links, CLM release | possible extra data and baselines | skip; cite published numbers as reported, not replicated |
| 7 | **Further commits / merge** | first commit pushed to `stage2-evidence-bounded-verification` on 2026-11-01 | open a pull request into `main` or `review-eval-updates` only when the user asks; keep no attribution lines |
| 8 | **Case1 branch**: cherry-pick the three test files and docs (authorship preserved)? | small engineering value; code changes did not help (`review/CASE1_ASSESSMENT.md`) | leave alone |
| 9 | **Deck and speaker guide**: update to the new claims | currently describe the old, disproved claim | not updated until the user asks |
| 10 | **Which "modern LLM"** the professor means | baseline choice | Claude Opus/Sonnet/Haiku plus Groq gpt-oss and NVIDIA Nemotron |
| 11 | **Default mode in the server** (`hybrid` is weak) | backward compatibility vs honesty | keep until the paper's results are frozen |

## Questions a reviewer or the professor will ask (answers in `review/PROJECT_BRIEF.md` sections 3-6)
"Why not just ask an LLM?" -> we measured: judges win on natural errors; the interesting finding is that they are information-limited. "Is the guarantee real?" -> marginal; per-split it is not; the cluster-aware version costs power. "Is it novel?" -> the ingredients are prior art; the measurement and the ask-policy with an interruption budget are the candidate contributions. "Do the results hold?" -> dev only, until the locked test.
