> **Strong-error update (2026-11-01).** 63% of the BFCL 'wrong' arguments behind these numbers are weak labels (format variants of gold or optional arguments gold leaves blank). On strong errors only: Opus with the tool definition detects 65.1% at 8.0% false blocks, consensus 74.4% at the same rate, union 88.4%, difference CI -0.19 to +0.40 (43 wrong calls; not significant); consensus call-level AUROC stays 0.89. See `PAPER_PLAN_V2.md` section 12.

> **Superseded headline (2026-10-30, later).** The numbers below come from the first 56 cases. On all 200 single-turn cases (30 models, 19,443 argument instances, 790 wrong) cross-model disagreement has AUROC 0.93 (bootstrap CI 0.86 to 0.98) and detects 35% / 71% / 92% of wrong arguments at 1% / 5% / 10% false blocks (plurality vote 36%; 613 of 790 wrong arguments are systematic; mean pairwise error phi 0.73). The judge control on 924 calls (5 models, 109 wrong) gives: Opus with the tool definition 8.0% false blocks / 45.9% detection, consensus at the same false-block rate 56.0%, union 67.0% at 14.1%; the difference (consensus minus judge) has a 95% CI of -0.14 to +0.31, so it is not significant, and the 56-case control (73% vs 52%) overstated the gap. See `EXPERIMENTS_2026-10-30.md`.

# Cross-model consensus as an argument verifier: first result (exploratory, 2026-10-30)

Script `benchmarks/analyze_consensus.py` (no fitted parameters, so no split); data `benchmarks/data/bfcl/consensus_cases.json` built by `benchmarks/load_bfcl_consensus.py` (report: `review/scout/TASK_bfcl_consensus_data.md`). Source: public Hugging Face dataset `AgentSuite/BFCL_V4-trajectories` (declares **no licence**; research use only, not redistributed) with prompts and gold answers from the Apache-2.0 gorilla repo. The dataset named in earlier notes, `HuanzhiMao/BFCL-Result`, returns HTTP 401 and could not be used; earlier notes that called it "verified" were wrong.

## Data
30 models from six families (OpenAI, Anthropic, Google, DeepSeek, Qwen, Kimi, including thinking on/off variants of the same model), one identical prompt format, 56 single-turn BFCL cases (6 categories), 5,800 argument instances in 1,499 usable calls (181 malformed outputs excluded), 217 wrong arguments (3.75%). Score for an argument instance = 1 minus the share of the other 29 models that gave the same value.

## Result
| Quantity | Value |
|---|---|
| AUROC of disagreement, all wrong arguments | 0.845 (cluster bootstrap 95% CI 0.66 to 0.99, 56 test cases) |
| Detection at 1% / 5% / 10% false-block rate (all wrong) | 26.7% / 62.2% / 75.1% |
| Plurality vote (block if value differs from most common) | false blocks 1.1%, detection 33.6% |
| Error correlation (mean pairwise phi), within / across families | 0.80 / 0.84 |
| Lone errors (wrong while fewer than half the others are wrong), n = 40 | AUROC 0.995, **circular, do not quote** |
| Systematic errors (at least half the others wrong too), n = 177 | AUROC 0.81, plurality detection 18.6% |

## How to read it
1. **The 0.995 for lone errors is by construction.** A lone error is defined by the other models being mostly correct, which forces them to agree with each other and disagree with the lone model. Only the all-wrong figures are meaningful.
2. **82% of the wrong arguments are systematic** (177 of 217): at least half of the other models are also marked wrong there. Many of these are gold-versus-consensus mismatches (a date phrased differently, a percentage written 4 against a gold of 0.04), not model hallucinations. The consensus signal therefore partly measures format disagreement, and "wrong" in BFCL's strict sense is not the same as wrong in the sense of our other experiments.
3. **Errors are strongly shared across models** (phi about 0.8 even across families). Errors are mostly a property of the slot, not of the model. That supports the "information ceiling" idea: most of this error mass is invisible to any single model's introspection or to a plurality vote (detection 33.6%).
4. **Not comparable with the fcrb judge results.** Different dataset, different error mix, different label rule, 56 test cases, strict gold. The 62% detection at 5% false blocks must not be set beside the judges' 53 to 59% on fcrb.
5. **Cost.** The score needs 29 other model calls per check. It is an analysis of information content, not a deployable gate; a deployable analogue is k samples from the agent itself, which this dataset cannot test.

## What would make it a result
Run the same frozen judge on the same BFCL calls and compare at matched false-block rate (control experiment, not yet run); enlarge to all 200 single-turn cases and all prompt formats if the data stay reachable; recompute with gold-artifact slots removed (human or rule adjudication) so "wrong" means wrong; test self-consistency with k samples from open models.

## Addendum: judge control on the same BFCL calls (dev, agent mode, 2026-10-30)
491 calls from 10 models (one per family/size band) on the 56 cases, 67 wrong calls (13.6%); judges Sonnet and Opus (agent mode, batches of 25), with the request only ("without") and with the tool definition plus the one-sentence rule ("with", prompt variant S). Consensus call score = maximum over arguments of the disagreement with all other models; its threshold is set to match each judge's false-block rate (`benchmarks/compare_consensus_judge.py`, cluster bootstrap over 56 test cases).

| System | False blocks | Detection | Consensus at the same false-block rate |
|---|---|---|---|
| Sonnet, request only | 15.1% | 20.9% | 14.4% / 85.1% |
| Sonnet, with tool definition | 13.0% | 40.3% | 12.0% / 73.1% |
| Opus, request only | 12.7% | 37.3% | 12.0% / 73.1% |
| Opus, with tool definition | 13.0% | 52.2% | 12.0% / 73.1% |
Consensus AUROC 0.866. Judge OR consensus: 74.6% (Sonnet with definition) to 86.6% (Opus) detection at 23.6 to 23.8% false blocks.

Reading:
1. The tool definition again raises judge detection (Sonnet +19.4, Opus +14.9 points), and consensus still detects more at the same false-block rate (73 to 85% against 21 to 52%).
2. **The differences are not significant**: bootstrap 95% intervals for consensus minus judge detection include zero for both schema-condition judges (Sonnet -0.06 to 0.68; Opus -0.26 to 0.57), because there are only 67 wrong calls from 56 test cases.
3. **What consensus measures here is partly format convention.** A model that writes a value differently from the other 29 models is flagged, and in BFCL the majority convention often coincides with the gold convention. That is useful for a benchmark but is not the same as detecting a wrong choice. Consensus also needs 29 extra model calls per check (or k samples of the agent), so it is an information bound and not a cheap gate.
4. The union of a judge and consensus reaches 75 to 87% detection, which shows the two signals are partly complementary.

Not done: all 200 single-turn cases and all prompt formats, a gold-artifact-free relabel, k-sample self-consistency with open models, a human audit, any test half.
