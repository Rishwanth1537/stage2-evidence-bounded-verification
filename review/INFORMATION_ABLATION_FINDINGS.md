# Information ablation and contract tier: first result (dev half, exploratory, 2026-10-30)

Scripts: `benchmarks/contract_tier.py` (deterministic checks of an argument against the tool's own definition), `benchmarks/contract_complement.py`, `benchmarks/make_ablation_benches.py`, `benchmarks/analyze_schema_ablation.py`; judges run in agent mode (`benchmarks/agent_judge.py`). Tool definitions come from the Apache-2.0 BFCL data in the gorilla repository, joined to DeRef fcrb cases by function name; when a name has several definitions the variant whose parameter NAMES cover the call is used (names only, never values or labels). Results: `benchmarks/contract_tier_dev.json`, `contract_complement_dev.json`, `schema_ablation_dev.json`.

## 1. Contract tier alone (fcrb dev)
Type (with two leniencies the tool descriptions document: "True"/"False" strings for boolean parameters and "dontcare" where the description allows it), enum membership, documented formats (City, State; YYYY-MM-DD; HH:MM) and undeclared argument names. Call-level on the 168 judge-sample calls that have a definition: false blocks 15.9%, detection 25.6% (all 630 dev calls: 16.2% / 22.5%; context grounding S2 alone 51.4% / 44.1%). Most precise check: `fmt_city_state` (precision 0.68 earlier version); enum and type violations are rarer than expected on this data. A first version that took the first definition of a function name flagged 25% of correct calls; the variant fix cut that to 16%.

## 2. Information ablation (same 168 cases, same judges, with and without the tool definition)
Condition "with": the tool definition is appended to the conversation and one sentence is added to the task text (a value that violates the definition is not supported). This is a new prompt variant; the frozen prompt hash covers the original text only.

| Judge | without: FBR / detection | with: FBR / detection | paired p (with vs without) | judge OR contract (without) | with OR contract |
|---|---|---|---|---|---|
| Haiku | 32.9% / 50.0% | 24.4% / 66.3% | 0.0011 (30 vs 9) | 43.9% / 66.3% | 31.7% / 75.6% |
| Sonnet | 11.0% / 51.2% | 18.3% / 70.9% | 0.12 (26 vs 15) | 26.8% / 69.8% | 24.4% / 74.4% |
| Opus | 19.5% / 53.5% | 14.6% / 72.1% | 0.0045 (33 vs 13) | 31.7% / 70.9% | 20.7% / 75.6% |
Contract tier alone: 15.9% / 25.6%.

Reading:
1. **Information moves detection, model size barely does.** Across the three Claude models detection spans 50.0 to 53.5% without the definition (3.5 points) and 66.3 to 72.1% with it (5.8 points), while adding the definition raises each judge by 16 to 20 points. The effect of model size inside a condition is small and not tested for significance here; the information effect is the same size for all three.
2. **The deterministic contract tier recovers a large part of the gain without any model**: judge-without OR contract reaches 66 to 71%, close to judge-with (66 to 72%). The trade is more false blocks for the weaker judges (Haiku 32.9% to 43.9%).
3. Combining both (judge with definition OR contract tier) gives 74 to 76% detection at 21 to 32% false blocks.

## 3. Caveats that matter
- **Many of these errors would be caught by the server anyway.** A value outside an enum, a wrong type or a wrongly formatted date is usually rejected by the tool's own validation; it fails loudly and is cheap to recover from. The gate then saves a round trip rather than preventing a silent mistake. The dangerous errors are the ones nothing downstream rejects (valid but wrong item, wrong role); this experiment says little about those.
- **Benchmark circularity.** BFCL's gold answers enforce the schema, so "wrong" partly means "violates the definition". Real tool use has no such labels.
- **Label noise.** fcrb labels come from the dataset; no human audit yet.
- **Sample size.** 168 calls (82 correct, 86 wrong), intervals wide; the Sonnet difference alone is not significant. Dev half only; nothing here is a confirmatory result.
- **Agent mode.** Batches of 25 per task, no temperature control, the added rule is part of the prompt.
- **The definition leaks little but not nothing.** Variant choice used argument names; "unknown argument" is therefore rarer than it would be in deployment.

## 4. Size ladder with open models at temperature 0 (dev, 2026-11-01; `benchmarks/analyze_ladder.py`, `run_nvidia_ladder.sh`)
Same 168 fcrb dev calls that carry a tool definition, frozen prompt, temperature 0, NVIDIA-hosted Nemotron models, with and without the tool definition (the rule sentence sits inside the case text, `cases_fcrb_schema_note.json`; the frozen prompt hash is unchanged). J = detection minus false-block rate (Youden), because binary judges cannot be matched at a false-block rate and detection alone rewards judges that block a lot.

| Judge | Mode | FBR / detection without | FBR / detection with | Gain in detection | J without -> with | Paired p |
|---|---|---|---|---|---|---|
| Claude Haiku | agent | 32.9 / 50.0 | 24.4 / 66.3 | +16.3 | 17.1 -> 41.9 | 0.0011 |
| Claude Sonnet | agent | 11.0 / 51.2 | 18.3 / 70.9 | +19.8 | 40.2 -> 52.6 | 0.12 |
| Claude Opus | agent | 19.5 / 53.5 | 14.6 / 72.1 | +18.6 | 34.0 -> 57.5 | 0.0045 |
| Nemotron 4B (bolt-e4b) | API t=0 | 19.5 / 54.7 | 24.4 / 64.0 | +9.3 | 35.1 -> 39.6 | 0.68 |
| Nemotron 30B-A3B (lightning) | API t=0 | 47.6 / 65.1 | 52.4 / 70.9 | +5.8 | 17.6 -> 18.5 | 1.0 |
| Nemotron 120B-A12B (super-vl) | API t=0 | 35.4 / 57.0 | 40.2 / 75.6 | +18.6 | 21.6 -> 35.3 | 0.088 |
| Nemotron 550B-A55B (ultra) | API t=0 | 29.3 / 57.0 | 32.9 / 77.9 | +20.9 | 27.7 -> 45.0 | 0.044 |

The 120B cells needed several reruns after NVIDIA server errors (HTTP 500 and read timeouts) and finished with 0 unparseable replies. Unparseable replies: all runs 0 or 1 of 168 except the 30B model (1 of 168 without, 5 of 168 with the definition: about 3%, slightly above the 2% limit; it is the only judge above it and is flagged).

Reading:
1. **Information helps every judge that can use it.** Detection rises by 16 to 21 points for the three Claude models and the 550B model; Youden's J rises by 12 to 25 points. The two small or weak open models gain little (4B: +4.4 J, not significant; 30B-A3B: +0.9 J, not significant) - the 30B model blocks about half of all correct calls with or without the definition.
2. **Without new information detection is flat in size** (Claude spread 3.5 points; Nemotron 4B to 550B 2.3 points between the extremes, 10.5 points counting the 30B model, which buys detection with false blocks). Size shows up in *false-block calibration* (J), not in detection.
3. **So the supported statement is an interaction, not "size does not matter":** extra evidence raises the ceiling, and a judge needs enough capability to exploit it. This is a finding about these judges and this benchmark, with n = 168 and wide intervals.
4. **With the definition, the gain grows with the model's active size**: detection gain +5.8 (30B-A3B, 3B active), +9.3 (4B), +18.6 (120B-A12B, 12B active), +20.9 (550B-A55B, 55B active); detection with the definition 64.0 / 70.9 / 75.6 / 77.9 for 4B / 30B / 120B / 550B (monotone in total size), while detection without the definition does not order by size (54.7 / 65.1 / 57.0 / 57.0, the 30B model's higher figure is bought with 47.6% false blocks). This is the cleanest sign of the interaction, from four open models of one family; it is not a scaling law (four points, one family, wide intervals, only the 550B gain is individually significant at 0.05).

Caveats: agent-mode Claude judges and temperature-0 API judges are different conditions and are never pooled; the NVIDIA judges are one model family; benchmark gold partly enforces schemas (circularity), and the LLM pre-audit says many fcrb/BFCL "wrong" labels may be acceptable alternatives (see `PAPER_PLAN_V2.md` section 11).

