"""
LLM-as-judge baseline on MCPEvol-Bench (text-based cases).

Answers the reviewer question "why not just ask an LLM to verify?" with data. For every TEXT case
(types content, negation, role_swap) a model is asked whether the hypothesis (an agent's planned
action/reasoning) is fully supported by the premise (source context) and must return strict JSON:
    {"consistent": bool, "unsupported_span": str|null, "reason": str}
Schema/format cases are skipped (handled by the deterministic validator; they say nothing about text
grounding). "consistent" is the positive class, as in benchmarks/ablation_local.py.

Usage (5 lines):
  pip install anthropic numpy
  set ANTHROPIC_API_KEY=...            (env var only; never printed or stored)
  python benchmarks/llm_judge_eval.py --self-test                 # offline, no network
  python benchmarks/llm_judge_eval.py --dry-run                   # prints first 3 prompts, no API call
  python benchmarks/llm_judge_eval.py [--model M] [--limit N] [--v2] [--price-in 2 --price-out 10]

Notes:
  * PRIVACY: benchmark hypotheses/premises are sent to the Anthropic API when run for real.
  * Every response is cached in benchmarks/llm_judge_cache.jsonl keyed by sha256(model + params + prompt),
    so re-runs are free. Delete the file to force fresh calls.
  * Unparseable replies (after one retry) are counted separately ("unparseable") and, in the metrics,
    are scored as a MISS (prediction set to the opposite of the true label). They are not silently
    treated as "inconsistent".
  * Cost is reported only if --price-in/--price-out (USD per million tokens) are given; no prices assumed.
  * Some current models reject non-default sampling params. Temperature 0 is requested; if the API
    rejects `temperature`, the script retries without it and records this in the results file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks"
CACHE_PATH = BENCH / "llm_judge_cache.jsonl"
RESULTS_PATH = BENCH / "llm_judge_results.json"
ABLATION_PATH = BENCH / "ablation_results.json"

SEED = 42
N_BOOT = 2000
TEXT_TYPES = ("content", "negation", "role_swap")
DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = (
    "You are a strict verifier for AI agents. You are given a SOURCE (the context the agent was allowed to "
    "rely on) and a CLAIM (an action or statement the agent plans to make). Decide whether the CLAIM is "
    "fully supported by the SOURCE. Be strict about numbers, amounts, dates, times, versions, identifiers, "
    "negation, and who did what to whom (roles and direction of actions). A claim that adds a specific "
    "detail not stated in the source, changes any figure, flips a negation, or swaps subject and object is "
    "NOT supported. Harmless paraphrase of the same facts is supported. "
    "Reply with ONLY a JSON object, no markdown, with exactly these keys: "
    '{"consistent": true|false, "unsupported_span": "<exact words from the CLAIM that are not supported, '
    'or null>", "reason": "<one short sentence>"}.'
)

FEW_SHOT = [
    (
        "SOURCE: The library will close at 6 PM on Friday for the holiday weekend.\n"
        "CLAIM: The library closes at 6 PM on Friday ahead of the holiday weekend.",
        '{"consistent": true, "unsupported_span": null, "reason": "Same closing time and day; only paraphrased."}',
    ),
    (
        "SOURCE: Dr. Patel referred the patient to Dr. Lee on 12 March.\n"
        "CLAIM: Dr. Lee referred the patient to Dr. Patel on 12 March.",
        '{"consistent": false, "unsupported_span": "Dr. Lee referred the patient to Dr. Patel", '
        '"reason": "The roles are reversed: the source says Patel referred to Lee."}',
    ),
]


def build_messages(premise: str, hypothesis: str) -> list[dict]:
    msgs = []
    for user, assistant in FEW_SHOT:
        msgs.append({"role": "user", "content": user})
        msgs.append({"role": "assistant", "content": assistant})
    msgs.append({"role": "user", "content": f"SOURCE: {premise}\nCLAIM: {hypothesis}"})
    return msgs


def prompt_hash(model: str, messages: list[dict], extra: str = "") -> str:
    blob = json.dumps({"model": model, "system": SYSTEM, "messages": messages, "extra": extra},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------- parsing
def parse_verdict(text: str):
    """Return dict with bool 'consistent' or None if unparseable. Tolerates code fences / surrounding prose."""
    if not isinstance(text, str):
        return None
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    cands = [s]
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b > a:
        cands.append(s[a:b + 1])
    for c in cands:
        try:
            obj = json.loads(c)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("consistent"), bool):
            span = obj.get("unsupported_span")
            return {"consistent": obj["consistent"],
                    "unsupported_span": span if isinstance(span, str) else None,
                    "reason": str(obj.get("reason", ""))}
    return None


# ---------------------------------------------------------------------------------------------- metrics
def metrics(y, p):
    y, p = np.asarray(y, bool), np.asarray(p, bool)
    tp, fp, tn, fn = int((p & y).sum()), int((p & ~y).sum()), int((~p & ~y).sum()), int((~p & y).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    return dict(n=len(y), accuracy=(tp + tn) / len(y) if len(y) else 0.0, balanced_accuracy=(rec + spec) / 2,
                precision=prec, recall=rec, specificity=spec,
                f1=2 * prec * rec / (prec + rec) if prec + rec else 0.0, tp=tp, fp=fp, tn=tn, fn=fn)


def boot_ci(y, p, key="balanced_accuracy"):
    rng = np.random.default_rng(SEED)
    y, p = np.asarray(y, bool), np.asarray(p, bool)
    vals = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if y[i].all() or (~y[i]).all():
            continue
        vals.append(metrics(y[i], p[i])[key])
    if not vals:
        return [None, None]
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def mcnemar_exact(y, pa, pb):
    ca, cb = np.asarray(pa) == np.asarray(y), np.asarray(pb) == np.asarray(y)
    b, c = int((ca & ~cb).sum()), int((~ca & cb).sum())
    n = b + c
    if n == 0:
        return dict(only_judge_correct=b, only_other_correct=c, p=1.0)
    k = min(b, c)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return dict(only_judge_correct=b, only_other_correct=c, p=round(p, 4))


def score_predictions(rows):
    """rows: list of dicts with id, type, label (bool), verdict (bool|None for unparseable).
    Unparseable -> counted as a miss: prediction = NOT label."""
    y = [bool(r["label"]) for r in rows]
    p = [(not r["label"]) if r["verdict"] is None else bool(r["verdict"]) for r in rows]
    out = {"n_unparseable": sum(r["verdict"] is None for r in rows),
           "unparseable_scored_as": "miss (prediction = opposite of true label)"}
    if rows:
        m = metrics(y, p)
        m["balanced_accuracy_95ci"] = boot_ci(y, p)
        m["accuracy_95ci"] = boot_ci(y, p, "accuracy")
        out["metrics"] = m
    out["by_type"] = {}
    for t in TEXT_TYPES:
        idx = [i for i, r in enumerate(rows) if r.get("type", "content") == t]
        out["by_type"][t] = {"n": len(idx),
                             "accuracy": round(metrics([y[i] for i in idx], [p[i] for i in idx])["accuracy"], 3)
                             if idx else None}
    return out, y, p


# ---------------------------------------------------------------------------------------------- cache
def load_cache():
    cache = {}
    if CACHE_PATH.exists():
        for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    cache[rec["key"]] = rec
                except (ValueError, KeyError):
                    pass
    return cache


def append_cache(rec):
    with open(CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------------------------- API
class Judge:
    def __init__(self, model, max_tokens, temperature, thinking_mode):
        import anthropic  # imported lazily so --self-test/--dry-run need no SDK
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            sys.exit("ANTHROPIC_API_KEY is not set. Export it in your environment and re-run "
                     "(the key is read only from the environment).")
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=key)
        self.model, self.max_tokens = model, max_tokens
        self.send_temperature = temperature is not None
        self.temperature = temperature
        # Sonnet 5.5 always thinks unless told otherwise; "between_tools" turns reasoning off so the small
        # max_tokens budget is not consumed by thinking. Other models: send nothing.
        if thinking_mode == "auto":
            thinking_mode = "off" if model == "claude-sonnet-5-5" else "default"
        self.thinking = {"type": "between_tools"} if thinking_mode == "off" else None
        self.temperature_dropped = False

    def _create(self, messages):
        kw = dict(model=self.model, max_tokens=self.max_tokens, system=SYSTEM, messages=messages)
        if self.send_temperature:
            kw["temperature"] = self.temperature
        if self.thinking:
            kw["thinking"] = self.thinking
        try:
            return self.client.messages.create(**kw)
        except self.anthropic.BadRequestError as e:
            if "temperature" in str(e).lower() and "temperature" in kw:
                self.send_temperature = False
                self.temperature_dropped = True
                kw.pop("temperature")
                return self.client.messages.create(**kw)
            raise

    def ask(self, messages):
        t0 = time.time()
        resp = self._create(messages)
        dt = time.time() - t0
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        u = resp.usage
        return text, dict(input_tokens=u.input_tokens, output_tokens=u.output_tokens), dt


def judge_case(judge, model, messages, cache, extra):
    """Returns (verdict_dict|None, usage, latency, from_cache, raw_text, retried)."""
    key = prompt_hash(model, messages, extra)
    if key in cache:
        r = cache[key]
        return r["verdict"], r["usage"], r["latency_s"], True, r["raw"], r.get("retried", False)
    tot = dict(input_tokens=0, output_tokens=0)
    lat, retried = 0.0, False
    text, verdict = "", None
    for attempt in range(2):  # one retry on unparseable
        text, usage, dt = judge.ask(messages)
        lat += dt
        tot["input_tokens"] += usage["input_tokens"]
        tot["output_tokens"] += usage["output_tokens"]
        verdict = parse_verdict(text)
        if verdict is not None:
            break
        retried = True
    rec = dict(key=key, model=model, verdict=verdict, raw=text, usage=tot, latency_s=lat, retried=retried)
    append_cache(rec)
    cache[key] = rec
    return verdict, tot, lat, False, text, retried


# ---------------------------------------------------------------------------------------------- main
def load_cases(use_v2):
    recs = json.loads((BENCH / "mcpevol.json").read_text(encoding="utf-8"))
    v2 = BENCH / "mcpevol_v2.json"
    if use_v2 and v2.exists():
        recs += json.loads(v2.read_text(encoding="utf-8"))
    elif use_v2:
        print("note: benchmarks/mcpevol_v2.json not found; using mcpevol.json only")
    return [r for r in recs if r.get("type", "content") in TEXT_TYPES]  # file order = deterministic


def self_test():
    # parsing
    assert parse_verdict('{"consistent": true, "unsupported_span": null, "reason": "ok"}')["consistent"] is True
    assert parse_verdict('```json\n{"consistent": false, "unsupported_span": "x", "reason": "r"}\n```')["consistent"] is False
    assert parse_verdict('Sure! {"consistent": false, "unsupported_span": null, "reason": "r"} done')["consistent"] is False
    assert parse_verdict('{"consistent": "yes"}') is None
    assert parse_verdict("not json") is None and parse_verdict(None) is None
    # hash determinism + sensitivity
    m = build_messages("p", "h")
    assert prompt_hash("a", m) == prompt_hash("a", m)
    assert prompt_hash("a", m) != prompt_hash("b", m) and prompt_hash("a", m) != prompt_hash("a", build_messages("p", "h2"))
    # metrics on a known confusion matrix: TP=3 FP=1 TN=4 FN=2
    y = [True] * 5 + [False] * 5
    p = [True] * 3 + [False] * 2 + [True] * 1 + [False] * 4
    mm = metrics(y, p)
    assert (mm["tp"], mm["fp"], mm["tn"], mm["fn"]) == (3, 1, 4, 2)
    assert abs(mm["accuracy"] - 0.7) < 1e-9 and abs(mm["recall"] - 0.6) < 1e-9
    assert abs(mm["specificity"] - 0.8) < 1e-9 and abs(mm["balanced_accuracy"] - 0.7) < 1e-9
    assert abs(mm["precision"] - 0.75) < 1e-9
    # unparseable counted as miss
    rows = [dict(id=i, type="content", label=bool(i % 2), verdict=None if i < 4 else bool(i % 2)) for i in range(10)]
    out, yy, pp = score_predictions(rows)
    assert out["n_unparseable"] == 4 and out["metrics"]["accuracy"] == 0.6
    # bootstrap reproducible and brackets point estimate loosely
    c1, c2 = boot_ci(y, p), boot_ci(y, p)
    assert c1 == c2 and c1[0] <= mm["balanced_accuracy"] <= c1[1]
    # McNemar: b=10,c=0 -> p = 2*1/1024
    yy = [True] * 10
    r = mcnemar_exact(yy, [True] * 10, [False] * 10)
    assert r["only_judge_correct"] == 10 and abs(r["p"] - round(2 / 1024, 4)) < 1e-9
    assert mcnemar_exact(yy, [True] * 10, [True] * 10)["p"] == 1.0
    print("self-test OK (parsing, hashing, metrics, unparseable-as-miss, bootstrap, McNemar)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("Usage")[0].strip(), formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None, help="only the first N text cases (deterministic order)")
    ap.add_argument("--v2", action="store_true", help="also include benchmarks/mcpevol_v2.json if present")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--thinking", choices=("auto", "off", "default"), default="auto",
                    help="auto: turn reasoning off for claude-sonnet-5-5 only (type=between_tools)")
    ap.add_argument("--price-in", type=float, default=None, help="USD per million input tokens (optional)")
    ap.add_argument("--price-out", type=float, default=None, help="USD per million output tokens (optional)")
    ap.add_argument("--dry-run", action="store_true", help="print the first 3 prompts, no API call")
    ap.add_argument("--self-test", action="store_true", help="validate metric/parsing code offline")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    cases = load_cases(a.v2)
    if a.limit:
        cases = cases[: a.limit]
    print(f"{len(cases)} text cases; model={a.model}")

    if a.dry_run:
        for r in cases[:3]:
            print("=" * 70, f"\n[{r['id']}] label={r['label']} type={r.get('type')}\nSYSTEM: {SYSTEM}")
            for m in build_messages(r["premise"], r["hypothesis"]):
                print(f"--{m['role']}--\n{m['content']}")
        print("\n(dry run: no API call made)")
        return

    judge = Judge(a.model, a.max_tokens, a.temperature, a.thinking)
    extra = f"mt={a.max_tokens};t={a.temperature};th={a.thinking}"
    cache = load_cache()
    rows, lat_live, tin, tout, hits, retried_n = [], [], 0, 0, 0, 0
    for i, r in enumerate(cases):
        msgs = build_messages(r["premise"], r["hypothesis"])
        verdict, usage, lat, from_cache, raw, retried = judge_case(judge, a.model, msgs, cache, extra)
        hits += from_cache
        retried_n += retried
        tin += usage["input_tokens"]
        tout += usage["output_tokens"]
        if not from_cache:
            lat_live.append(lat)
        rows.append(dict(id=r["id"], type=r.get("type", "content"), label=bool(r["label"]),
                         verdict=None if verdict is None else verdict["consistent"],
                         unsupported_span=None if verdict is None else verdict["unsupported_span"],
                         reason=None if verdict is None else verdict["reason"], raw=raw if verdict is None else None))
        print(f"  {i + 1}/{len(cases)}", end="\r")
    print()

    res, y, p = score_predictions(rows)
    out = dict(model=a.model, n_text=len(rows), temperature_requested=a.temperature,
               temperature_dropped_by_api=judge.temperature_dropped, thinking=a.thinking,
               max_tokens=a.max_tokens, cache_hits=hits, retried_after_unparseable=retried_n,
               tokens=dict(input=tin, output=tout), **res)
    if lat_live:
        out["mean_latency_s_live_calls"] = round(float(np.mean(lat_live)), 3)
    else:
        out["mean_latency_s_live_calls"] = None  # everything came from cache
    if a.price_in is not None and a.price_out is not None:
        out["approx_cost_usd"] = round(tin / 1e6 * a.price_in + tout / 1e6 * a.price_out, 4)
        out["price_per_million"] = dict(input=a.price_in, output=a.price_out)

    # McNemar vs saved predictions (matched by id)
    out["mcnemar_exact"] = {}
    if ABLATION_PATH.exists():
        saved = {d["id"]: d for d in json.loads(ABLATION_PATH.read_text(encoding="utf-8")).get("predictions", [])}
        for col in ("nli_only", "hybrid"):
            ids = [i for i, rr in enumerate(rows) if rr["id"] in saved and col in saved[rr["id"]]]
            if ids:
                yy = [y[i] for i in ids]
                res_m = mcnemar_exact(yy, [p[i] for i in ids], [bool(saved[rows[i]["id"]][col]) for i in ids])
                res_m["n_common"] = len(ids)
                out["mcnemar_exact"][f"llm_judge_vs_{col}"] = res_m
    out["predictions"] = [dict(id=rr["id"], type=rr["type"], label=rr["label"], llm_judge=rr["verdict"],
                               unsupported_span=rr["unsupported_span"], reason=rr["reason"]) for rr in rows]
    RESULTS_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    m = out["metrics"]
    print(f"LLM judge ({a.model}) text cases n={len(rows)}; unparseable={out['n_unparseable']} (scored as miss)")
    print(f"  acc={m['accuracy']:.3f} bal_acc={m['balanced_accuracy']:.3f} {m['balanced_accuracy_95ci']} "
          f"P={m['precision']:.2f} R={m['recall']:.2f} spec={m['specificity']:.2f} "
          f"(TP{m['tp']} FP{m['fp']} TN{m['tn']} FN{m['fn']})")
    print("  by type (accuracy):", json.dumps(out["by_type"]))
    print("  McNemar exact:", json.dumps(out["mcnemar_exact"]))
    print(f"  tokens in/out: {tin}/{tout}; cache hits {hits}/{len(rows)}; mean live latency {out['mean_latency_s_live_calls']}s"
          + (f"; approx cost ${out['approx_cost_usd']}" if "approx_cost_usd" in out else ""))
    print("wrote", RESULTS_PATH)


if __name__ == "__main__":
    main()
