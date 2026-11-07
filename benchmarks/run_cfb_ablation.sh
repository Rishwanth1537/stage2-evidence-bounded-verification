#!/bin/bash
# Information ablation on cfb dev (Deviation 20): the same 100 seeded cases, judged without and with the tool definition, API judges at
# temperature 0, frozen prompt (hash 9b59ae0a3fa5384a), context cut to the most recent 3000 characters (the definition is appended at the end).
# Logs go to $LOGDIR.  NVIDIA models run two at a time; Groq models run afterwards (8k tokens/min, 200k tokens/day per model; the judge cache
# makes every run resumable).  Usage: bash benchmarks/run_cfb_ablation.sh
cd "$(dirname "$0")/.."
export PYTHONPATH=.
LOGDIR=${LOGDIR:-benchmarks/logs_cfb_ablation}
mkdir -p "$LOGDIR"
run() {   # provider model tag rpm
  p="$1"; m="$2"; tag="$3"; rpm="$4"
  python -u benchmarks/llm_judge_args.py --provider "$p" --model "$m" --bench benchmarks/data/deref/cases_cfb.json --split dev --limit 100 \
    --max-context-chars 3000 --rpm "$rpm" --out "benchmarks/llm_judge_args_cfb_${tag}_dev_v0.json" > "$LOGDIR/${tag}_plain.log" 2>&1
  python -u benchmarks/llm_judge_args.py --provider "$p" --model "$m" --bench benchmarks/data/deref/cases_cfb_schema_note.json --split dev --limit 100 \
    --max-context-chars 3000 --rpm "$rpm" --out "benchmarks/llm_judge_args_cfbschema_${tag}_dev_v0.json" > "$LOGDIR/${tag}_schema.log" 2>&1
}
( run nvidia nvidia/nemotron-3.5-bolt-e4b nv4b 20 ) &
( run nvidia nvidia/nemotron-3.5-lightning-30b-a3b nv30b 20 ) &
wait
( run nvidia nvidia/nemotron-3.5-super-vl-120b-a12b nv120b 20 ) &
( run nvidia nvidia/nemotron-3-ultra-550b-a55b nv550b 8 ) &
wait
# Groq: the plain cfb runs already exist for these two models (limit 100, 3000 chars); only the definition variants are new.
python -u benchmarks/llm_judge_args.py --provider groq --model openai/gpt-oss-120b --bench benchmarks/data/deref/cases_cfb_schema_note.json --split dev --limit 100 \
  --max-context-chars 3000 --rpm 4 --out benchmarks/llm_judge_args_cfbschema_groq_openai_gpt_oss_120b_dev_v0.json > "$LOGDIR/groq120_schema.log" 2>&1
python -u benchmarks/llm_judge_args.py --provider groq --model openai/gpt-oss-20b --bench benchmarks/data/deref/cases_cfb_schema_note.json --split dev --limit 100 \
  --max-context-chars 3000 --rpm 4 --out benchmarks/llm_judge_args_cfbschema_groq_openai_gpt_oss_20b_dev_v0.json > "$LOGDIR/groq20_schema.log" 2>&1
echo done > "$LOGDIR/ablation.done"
