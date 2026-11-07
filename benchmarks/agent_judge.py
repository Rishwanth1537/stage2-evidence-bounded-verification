"""
Run the SAME judge task with Claude subagents instead of an API key ("agent-mode judges").

  make    build unlabelled batch files for the same seeded sample the API judges saw
  ingest  turn the subagents' answer files into response-cache entries, so that
          llm_judge_args.py (provider custom, model agent-<name>) computes the usual metrics and the McNemar test offline

Differences from the API judges (state them whenever agent-mode numbers are reported):
  * the model sees a batch of cases in one task and a harness system prompt; answers are not at temperature 0;
  * a subagent has file tools, so the batch files hold no labels and live outside the repo, and the agent is told to open nothing else;
  * latency and token figures are not available.
The task text and the two few-shot examples are the frozen ones (judge_prompts.PROMPT_HASH).

  python benchmarks/agent_judge.py make   --tag fcrb --bench benchmarks/data/deref/cases_fcrb.json --limit 200 --out DIR
  python benchmarks/agent_judge.py ingest --tag fcrb --name claude-haiku --out DIR --bench ... --limit 200 [--max-context-chars N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
from judge_prompts import FEW_SHOT, PROMPT_HASH, TASK_V0, build_messages, render_user  # noqa: E402
from llm_judge_args import Cache, cache_key, trim_context  # noqa: E402


SCHEMA_NOTE = ("Extra rule for this file: after some conversations a \"Tool definition\" is shown. A value that violates the tool definition "
               "(wrong type, not one of the allowed enum values, or not in the format the description asks for) is NOT supported, in addition "
               "to the rules above.\n")


def sample_cases(bench, split, limit, seed):
    cases = json.loads(Path(bench).read_text(encoding="utf-8"))["cases"]
    if cases and "split" in cases[0]:
        pool = [c for c in cases if c["split"] == split]
    else:
        from eval_argground import split_cases
        dev, test = split_cases(cases)
        pool = {"dev": dev, "test": test}[split]
    idx = np.random.default_rng(seed).permutation(len(pool))[:limit]
    return [pool[i] for i in sorted(idx)]


def header(schema_note=False):
    shots = "\n\n".join(f"Example\n{render_user(e['conversation'], e['call'])}\nAnswer: {json.dumps(e['answer'])}" for e in FEW_SHOT)
    return (f"{TASK_V0}\n\n{shots}\n\nHow to answer this file: judge EVERY item below independently, as its own task, using only the "
            "conversation shown in that item. Do not use outside knowledge about whether the call is a sensible action; only whether each "
            "argument value is supported by the conversation. Write ONE JSON array to the output path you were given, one object per "
            'item, exactly: {"item": "<item id>", "supported": true or false, "unsupported_arguments": ["argument name", ...]}. '
            "Do not read any other file, run any code, or look for labels.\n" + (SCHEMA_NOTE if schema_note else ""))


def cmd_make(a):
    out = Path(a.out) / a.tag
    out.mkdir(parents=True, exist_ok=True)
    sample = sample_cases(a.bench, a.split, a.limit, a.seed)
    items = []
    for i, c in enumerate(sample):
        b, j = divmod(i, a.batch)
        items.append({"item": f"b{b + 1}-{j + 1:02d}", "case_id": c["id"], "batch": b + 1,
                      "text": render_user(trim_context(c["premise"], a.max_context_chars), c.get("calls") or c["call"])})
    nb = max(it["batch"] for it in items)
    for b in range(1, nb + 1):
        body = "\n\n".join(f"### ITEM {it['item']}\n{it['text']}" for it in items if it["batch"] == b)
        (out / f"batch_{b}.txt").write_text(header(a.schema_note) + "\n" + body + "\n", encoding="utf-8")
    (out / "map.json").write_text(json.dumps({"tag": a.tag, "prompt_hash": PROMPT_HASH, "n": len(items),
                                              "items": [{k: it[k] for k in ("item", "case_id", "batch")} for it in items]}, indent=1),
                                  encoding="utf-8")
    print(f"{a.tag}: {len(items)} items in {nb} batch files under {out}")


def cmd_ingest(a):
    out = Path(a.out) / a.tag
    mp = json.loads((out / "map.json").read_text(encoding="utf-8"))
    sample = sample_cases(a.bench, a.split, a.limit, a.seed)
    if len(sample) != mp["n"] or [c["id"] for c in sample] != [it["case_id"] for it in mp["items"]]:
        sys.exit("sample no longer matches map.json (different bench/limit/seed)")
    answers = {}
    for f in sorted((out / "results" / a.name).glob("batch_*.json")):
        try:
            for r in json.loads(f.read_text(encoding="utf-8")):
                answers[str(r.get("item"))] = r
        except Exception as e:  # a malformed file means its items count as unparseable
            print(f"  unreadable {f.name}: {e}")
    cache, model = Cache(a.cache), f"agent-{a.name}"
    missing = 0
    for c, it in zip(sample, mp["items"]):
        msgs = build_messages(0, trim_context(c["premise"], a.max_context_chars), c.get("calls") or c["call"])
        r = answers.get(it["item"])
        if r is None or not isinstance(r.get("supported"), bool):
            text, missing = "", missing + 1
        else:
            text = json.dumps({"supported": r["supported"], "unsupported_arguments": [str(x) for x in r.get("unsupported_arguments", [])]})
        cache.put(cache_key("custom", model, 0, msgs), {"text": text, "latency_s": None, "prompt_tokens": None, "completion_tokens": None})
    print(f"{a.tag}/{model}: {len(sample) - missing}/{len(sample)} answers ingested, {missing} missing (counted as unparseable)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "ingest"])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--bench", default=str(ROOT / "benchmarks" / "argground_bench.json"))
    ap.add_argument("--split", default="dev", choices=["dev"])  # test halves are never prepared here
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--max-context-chars", type=int, default=None)
    ap.add_argument("--schema-note", action="store_true", help="append the tool-definition rule to the task text (information ablation)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--cache", default=str(ROOT / "benchmarks" / "llm_judge_args_cache.jsonl"))
    a = ap.parse_args()
    if a.cmd == "ingest" and not a.name:
        sys.exit("--name is required for ingest")
    {"make": cmd_make, "ingest": cmd_ingest}[a.cmd](a)


if __name__ == "__main__":
    main()
