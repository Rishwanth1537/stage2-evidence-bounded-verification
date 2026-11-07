#!/bin/bash
# Size ladder on NVIDIA-hosted Nemotron models: fcrb dev (200 seeded cases), without and with the tool definition (rule inside the case text).
# Frozen prompt, temperature 0, one run per configuration.  Logs go to $LOGDIR.  Usage: bash benchmarks/run_nvidia_ladder.sh
cd "$(dirname "$0")/.."
export PYTHONPATH=.
LOGDIR=${LOGDIR:-/tmp/nvidia_ladder}
mkdir -p "$LOGDIR"
run_model() {
  m="$1"; tag=$(echo "$m" | tr '/.' '__' | tr '-' '_')
  python -u benchmarks/llm_judge_args.py --provider nvidia --model "$m" --bench benchmarks/data/deref/cases_fcrb.json \
    --split dev --limit 200 --rpm 20 --out "benchmarks/llm_judge_args_fcrb_nvidia_${tag}_dev_v0.json" > "$LOGDIR/${tag}_plain.log" 2>&1
  python -u benchmarks/llm_judge_args.py --provider nvidia --model "$m" --bench benchmarks/data/deref/cases_fcrb_schema_note.json \
    --split dev --limit 200 --rpm 20 --out "benchmarks/llm_judge_args_fcrbschema_nvidia_${tag}_dev_v0.json" > "$LOGDIR/${tag}_schema.log" 2>&1
}
for m in nvidia/nemotron-3.5-bolt-e4b nvidia/nemotron-3.5-lightning-30b-a3b nvidia/nemotron-3.5-super-vl-120b-a12b nvidia/nemotron-3-ultra-550b-a55b; do
  run_model "$m" &
done
wait
echo done > "$LOGDIR/ladder.done"
