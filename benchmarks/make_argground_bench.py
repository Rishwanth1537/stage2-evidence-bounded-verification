"""
Build ArgGround-Bench from PUBLIC function-calling conversations (glaiveai/glaive-function-calling-v2, fetched through the
Hugging Face datasets-server API; the dataset's licence applies to the source text). These conversations are LLM-generated,
not logs from real deployments.

Each case = one planned tool call plus the conversation that preceded it.
  premise    : everything said before the call (user turns, assistant turns, earlier function responses)
  call       : {"name": ..., "arguments": {...}}
  label      : True  = the original gold call (assumed consistent with its context)
               False = the gold call with exactly ONE argument value replaced by a value that does NOT occur in the premise
  mutation   : which kind of change (number_scale, number_shift, string_swap, bool_flip) - None for gold calls

Realism notes (state them): labels for gold calls are assumptions, not human judgements; some gold arguments are legitimately
not stated in the context (model-chosen defaults), which is exactly what a grounding checker has to cope with, so the
share of gold values found verbatim in the premise is reported.  Injected errors are synthetic substitutions, not errors
made by a real model.

Usage:  python benchmarks/make_argground_bench.py --pages 40 --seed 5
Output: benchmarks/argground_bench.json   (git-ignored; regenerate from the seed)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://datasets-server.huggingface.co/rows"
DATASET = "glaiveai/glaive-function-calling-v2"
CALL_RE = re.compile(r"<functioncall>\s*(\{.*?\})\s*<\|endoftext\|>", re.S)
ARGS_RE = re.compile(r'"name":\s*"([^"]+)",\s*"arguments":\s*\'(.*)\'\s*\}\s*$', re.S)
ROLE_RE = re.compile(r"(USER|ASSISTANT|FUNCTION RESPONSE):", re.S)


def fetch(offset: int, length: int = 100):
    url = API + "?" + urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": "train", "offset": offset, "length": length})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return [x["row"] for x in json.load(r)["rows"]]
        except Exception:
            time.sleep(2 * (attempt + 1))
    return []


def parse_call(text: str):
    m = CALL_RE.search(text)
    if not m:
        return None
    body = m.group(1)
    mm = ARGS_RE.search(body)
    if not mm:
        return None
    try:
        parsed = json.loads(mm.group(2))
    except Exception:
        return None
    return {"name": mm.group(1), "arguments": parsed} if isinstance(parsed, dict) else None


def parse_schemas(system: str):
    """Return {function name: {"required": [...], "optional": [...]}} parsed from the JSON blocks in the system prompt."""
    dec, out, i = json.JSONDecoder(), {}, 0
    while True:
        i = system.find("{", i)
        if i < 0:
            return out
        try:
            obj, end = dec.raw_decode(system[i:])
        except Exception:
            i += 1
            continue
        i += end
        if isinstance(obj, dict) and "name" in obj and isinstance(obj.get("parameters"), dict):
            props = list((obj["parameters"].get("properties") or {}).keys())
            req = [r for r in (obj["parameters"].get("required") or []) if isinstance(r, str)]
            out[obj["name"]] = {"required": req, "optional": [p for p in props if p not in req]}


def calls_with_context(chat: str):
    """Yield (call, premise_text_before_call) for every function call in a conversation."""
    parts = ROLE_RE.split(chat)
    # parts: [prefix, role1, text1, role2, text2, ...]
    history = []
    for i in range(1, len(parts) - 1, 2):
        role, text = parts[i], parts[i + 1].replace("<|endoftext|>", "").strip()
        if role == "ASSISTANT" and "<functioncall>" in parts[i + 1]:
            call = parse_call(parts[i + 1])
            if call and call["arguments"]:
                yield call, "\n".join(history)
            history.append("Assistant: (called a function)")
        else:
            label = {"USER": "User", "ASSISTANT": "Assistant", "FUNCTION RESPONSE": "Function response"}[role]
            history.append(f"{label}: {text}")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).lower()).strip()


def appears(value, premise: str) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        v = f"{value:g}" if isinstance(value, float) else str(value)
        return re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", premise.replace(",", "")) is not None
    return norm(value) in norm(premise)


def mutate(rng: random.Random, call, premise, pool):
    args = call["arguments"]
    keys = [k for k, v in args.items() if isinstance(v, (int, float, str, bool)) and not (isinstance(v, str) and not v.strip())]
    rng.shuffle(keys)
    for k in keys:
        v = args[k]
        new, kind = None, None
        if isinstance(v, bool):
            new, kind = (not v), "bool_flip"
        elif isinstance(v, (int, float)):
            cands = [v * 10, v + rng.choice([5, 10, 50, 100]), max(0, v - rng.choice([1, 5, 10])), v * 2]
            rng.shuffle(cands)
            for c in cands:
                c = int(c) if isinstance(v, int) else round(float(c), 2)
                if c != v and not appears(c, premise):
                    new, kind = c, ("number_scale" if c in (v * 10, v * 2) else "number_shift")
                    break
        else:
            options = [x for x in pool.get((call["name"], k), []) + pool.get(("*", k), []) if norm(x) != norm(v) and not appears(x, premise)]
            if options:
                new, kind = rng.choice(options), "string_swap"
        if new is not None:
            mutated = {"name": call["name"], "arguments": {**args, k: new}, "schema": call.get("schema")}
            return mutated, {"argument": k, "gold": v, "mutated": new}, kind
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=40, help="number of random 100-row pages to fetch")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--max-premise-chars", type=int, default=2500)
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "argground_bench.json"))
    args = ap.parse_args()
    rng = random.Random(args.seed)

    offsets = sorted(rng.sample(range(0, 112000, 100), args.pages))
    gold = []
    for off in offsets:
        for row in fetch(off):
            schemas = parse_schemas(row.get("system", ""))
            for call, premise in calls_with_context(row["chat"]):
                if len(premise) > args.max_premise_chars or not premise.strip():
                    continue
                call["schema"] = schemas.get(call["name"])
                gold.append((call, premise))
    print(f"fetched {len(gold)} gold calls from {args.pages} pages")

    pool = defaultdict(list)
    for call, _ in gold:
        for k, v in call["arguments"].items():
            if isinstance(v, str) and 0 < len(v) < 60:
                pool[(call["name"], k)].append(v)
                pool[("*", k)].append(v)

    cases, stats = [], Counter()
    seen = set()
    for call, premise in gold:
        key = (json.dumps({"name": call["name"], "arguments": call["arguments"]}, sort_keys=True), premise)
        if key in seen:
            continue
        seen.add(key)
        # groundedness of gold values
        for k, v in call["arguments"].items():
            if isinstance(v, (int, float, str)) and not isinstance(v, bool):
                stats["gold_value_total"] += 1
                stats["gold_value_in_premise"] += appears(v, premise)
        cases.append({"premise": premise, "call": call, "label": True, "mutation": None, "change": None})
        mut, change, kind = mutate(rng, call, premise, pool)
        if mut is not None:
            cases.append({"premise": premise, "call": mut, "label": False, "mutation": kind, "change": change})
    rng.shuffle(cases)
    for i, c in enumerate(cases, 1):
        c["id"] = f"AG-{i:05d}"
    meta = {"source": DATASET, "seed": args.seed, "pages": args.pages, "n_cases": len(cases),
            "n_consistent": sum(c["label"] for c in cases), "mutations": Counter(c["mutation"] for c in cases if not c["label"]),
            "gold_value_in_premise_rate": round(stats["gold_value_in_premise"] / max(1, stats["gold_value_total"]), 3)}
    Path(args.out).write_text(json.dumps({"meta": meta, "cases": cases}, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
