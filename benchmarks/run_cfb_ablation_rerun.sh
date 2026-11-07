#!/bin/bash
# Re-run of the cfb ablation configurations that crashed in a network outage (Nemotron 4B and 30B, plain and definition).  Same commands and
# parameters as run_cfb_ablation.sh; the judge cache makes each run resume where it stopped.  One worker, so that at most three judge
# processes run at the same time next to the 120B/550B stage.  Usage: bash benchmarks/run_cfb_ablation_rerun.sh
cd "$(dirname "$0")/.."
export PYTHONPATH=.
LOGDIR=${LOGDIR:-benchmarks/logs_cfb_ablation}
mkdir -p "$LOGDIR"
run() {   # provider model tag rpm
  p="$1"; m="$2"; tag="$3"; rpm="$4"
  python -u benchmarks/llm_judge_args.py --provider "$p" --model "$m" --bench benchmarks/data/deref/cases_cfb.json --split dev --limit 100 \
    --max-context-chars 3000 --rpm "$rpm" --out "benchmarks/llm_judge_args_cfb_${tag}_dev_v0.json" > "$LOGDIR/${tag}_plain_rerun.log" 2>&1
  python -u benchmarks/llm_judge_args.py --provider "$p" --model "$m" --bench benchmarks/data/deref/cases_cfb_schema_note.json --split dev --limit 100 \
    --max-context-chars 3000 --rpm "$rpm" --out "benchmarks/llm_judge_args_cfbschema_${tag}_dev_v0.json" > "$LOGDIR/${tag}_schema_rerun.log" 2>&1
}
run nvidia nvidia/nemotron-3.5-bolt-e4b nv4b 20
run nvidia nvidia/nemotron-3.5-lightning-30b-a3b nv30b 20
echo done > "$LOGDIR/rerun.done"
