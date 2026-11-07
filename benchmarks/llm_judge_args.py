"""
LLM-as-judge baseline for ARGUMENT GROUNDING on ArgGround-Bench, using any OpenAI-compatible chat endpoint
(Groq and NVIDIA's hosted API are preconfigured).  No third-party packages are needed.

  export GROQ_API_KEY=...      (or NVIDIA_API_KEY=...)
  python benchmarks/llm_judge_args.py --list-models --provider groq
  python benchmarks/llm_judge_args.py --provider groq --model <id from the list> --split dev  --limit 200 --dry-run
  python benchmarks/llm_judge_args.py --provider groq --model <id> --split test --limit 600

Design notes
  * Prompts are frozen in benchmarks/judge_prompts.py (variant 0 = main; 1 to 4 = paraphrases for the prompt-sensitivity study).
  * Temperature 0.  Every response is cached in a JSONL file, so re-runs cost nothing and a crash resumes.
  * Rate limits: --rpm spaces requests; HTTP 429 and 5xx are retried with backoff (Retry-After honoured).
  * Unparseable replies are counted separately and scored as a miss (never silently as "supported").
  * Metrics: false-block rate (genuine calls blocked), detection (injected errors blocked), balanced accuracy, bootstrap 95% CIs,
    exact McNemar versus the deterministic checker on the same cases, per-call latency and token usage.
  * PRIVACY: benchmark text is sent to the provider you choose.
  * Model ids and rate limits change; take the id from --list-models.  Free tiers may cap requests and tokens per day; use --limit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from judge_prompts import PROMPT_HASH, build_messages  # noqa: E402
from keys import get_key, KEY_FILE  # noqa: E402

PROVIDERS = {
    "groq": {"base": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY"},
    "nvidia": {"base": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY"},
    "gemini": {"base": "https://generativelanguage.googleapis.com/v1beta/openai", "key_env": "GEMINI_API_KEY"},
    "openrouter": {"base": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY"},
    # Claude models through Anthropic's native Messages API (model id from --list-models, e.g. a Haiku, Sonnet or Opus id)
    "anthropic": {"base": "https://api.anthropic.com/v1", "key_env": "ANTHROPIC_API_KEY", "style": "anthropic"},
    # any other OpenAI-compatible endpoint: --provider custom --base-url https://host/v1 --key-env MY_KEY_NAME
    "custom": {"base": None, "key_env": "CUSTOM_API_KEY"},
}


# ----------------------------------------------------------------------------- HTTP
def http_json(url, key, payload=None, timeout=90, style="openai"):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "mcp-hallucination-checker/1.0"}
    if style == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def anthropic_payload(model, messages, max_tokens, temperature=0):
    """Anthropic Messages API: system text is a top-level field, the rest are user/assistant turns."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
    payload = {"model": model, "messages": turns, "max_tokens": max_tokens, "temperature": temperature}
    if system:
        payload["system"] = system
    return payload


def anthropic_normalise(out):
    """Return the OpenAI-shaped dict the rest of the script reads."""
    text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    u = out.get("usage", {})
    return {"choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": u.get("input_tokens"), "completion_tokens": u.get("output_tokens")}}


REASONING_HINTS = ("nemotron-3", "deepseek-v4", "glm-5", "reasoning")      # models that spend tokens on hidden reasoning (observed empty replies)


def chat(provider, key, model, messages, max_tokens=120, retries=6, sleep=time.sleep, temperature=0):
    style = PROVIDERS[provider].get("style", "openai")
    if style == "anthropic":
        url = PROVIDERS[provider]["base"] + "/messages"
        payload = anthropic_payload(model, messages, max_tokens, temperature)
    else:
        url = PROVIDERS[provider]["base"] + "/chat/completions"
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if "gpt-oss" in model or provider == "gemini":
            # reasoning models spend the token budget on hidden reasoning; without headroom the visible reply is empty
            payload["max_tokens"] = max(max_tokens, 1500)
            payload["reasoning_effort"] = "low"
        elif any(t in model for t in REASONING_HINTS):
            payload["max_tokens"] = max(max_tokens, 12000)      # same reason; no reasoning_effort knob assumed (2,500 and 6,000 were too small for nemotron-3.5-lightning: 33% and 6-18% null replies)
    last = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            out = http_json(url, key, payload, timeout=240 if any(t in model for t in REASONING_HINTS) else 90, style=style)
            if style == "anthropic":
                out = anthropic_normalise(out)
            return out, time.time() - t0
        except urllib.error.HTTPError as e:
            body = e.read()
            last = f"HTTP {e.code}: {body[:200]!r}"
            if e.code == 400 and b"temperature" in body.lower() and "temperature" in payload:
                payload.pop("temperature")  # some newer models fix the sampling temperature themselves; record it in the data card
                continue
            if e.code in (429, 500, 502, 503, 504) or (e.code == 404 and not body.strip()):   # empty-body 404 = gateway hiccup under load (NVIDIA)
                ra = e.headers.get("Retry-After")
                sleep(float(ra) if ra and ra.replace('.', '', 1).isdigit() else min(60, 2 ** attempt * 2))
                continue
            raise RuntimeError(last)
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            sleep(min(60, 2 ** attempt * 2))
    raise RuntimeError(f"giving up after {retries} attempts: {last}")


# ----------------------------------------------------------------------------- parsing
def parse_verdict(text: str):
    """Return (supported: bool, unsupported: list) or None if the reply cannot be parsed."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    sup = obj.get("supported")
    if isinstance(sup, str):
        sup = {"true": True, "false": False}.get(sup.strip().lower())
    if not isinstance(sup, bool):
        return None
    un = obj.get("unsupported_arguments", [])
    return sup, [str(x) for x in un] if isinstance(un, list) else []


# ----------------------------------------------------------------------------- cache
class Cache:
    def __init__(self, path):
        self.path, self.data = Path(path), {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line); self.data[r["key"]] = r
                except Exception:
                    pass

    def get(self, key):
        return self.data.get(key)

    def put(self, key, rec):
        rec = {"key": key, **rec}
        self.data[key] = rec
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")


def cache_key(provider, model, variant, messages):
    return hashlib.sha256(json.dumps([provider, model, variant, PROMPT_HASH, messages], sort_keys=True).encode()).hexdigest()


# ----------------------------------------------------------------------------- metrics
def rates(labels, blocked):
    y = np.asarray(labels, bool); b = np.asarray(blocked, bool)
    fbr = float(b[y].mean()) if y.any() else float("nan")
    det = float(b[~y].mean()) if (~y).any() else float("nan")
    return {"false_block_rate": fbr, "detection_rate": det, "balanced_accuracy": (1 - fbr + det) / 2, "n": int(len(y)),
            "n_genuine": int(y.sum()), "n_injected": int((~y).sum())}


def boot_ci(labels, blocked, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    y = np.asarray(labels, bool); b = np.asarray(blocked, bool)
    f, d = [], []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].all() or (~y[i]).all():
            continue
        f.append(b[i][y[i]].mean()); d.append(b[i][~y[i]].mean())
    q = lambda a: [round(float(np.percentile(a, 2.5)), 4), round(float(np.percentile(a, 97.5)), 4)]
    return {"false_block_rate_95ci": q(f), "detection_rate_95ci": q(d)}


def mcnemar_exact(correct_a, correct_b):
    a, b = np.asarray(correct_a, bool), np.asarray(correct_b, bool)
    x, y = int((a & ~b).sum()), int((~a & b).sum())
    n = x + y
    if n == 0:
        return {"only_a_correct": x, "only_b_correct": y, "p": 1.0}
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(min(x, y) + 1)) / 2 ** n)
    return {"only_a_correct": x, "only_b_correct": y, "p": round(p, 4)}


# ----------------------------------------------------------------------------- main run
def trim_context(text, max_chars):
    """Keep the most recent max_chars of the context (a truncation policy is a stated limitation, report it)."""
    if not max_chars or len(text) <= max_chars:
        return text
    return "[earlier context truncated]\n" + text[-max_chars:]


def run(cases, provider, model, variant, cache, key, rpm, dry=False, chat_fn=chat, sleep=time.sleep, log=print, max_context_chars=None):
    gap = 60.0 / rpm if rpm else 0.0
    rows, last_call = [], 0.0
    for i, c in enumerate(cases):
        msgs = build_messages(variant, trim_context(c["premise"], max_context_chars), c.get("calls") or c["call"])
        if dry:
            if i < 2:
                log(json.dumps(msgs, indent=1)[:1500])
            continue
        k = cache_key(provider, model, variant, msgs)
        hit = cache.get(k)
        if hit is None:
            wait = gap - (time.time() - last_call)
            if wait > 0:
                sleep(wait)
            last_call = time.time()
            out, lat = chat_fn(provider, key, model, msgs)
            text = (out.get("choices") or [{}])[0].get("message", {}).get("content") or ""    # content can be null when the token budget ran out
            usage = out.get("usage", {})
            hit = {"text": text, "latency_s": round(lat, 3), "prompt_tokens": usage.get("prompt_tokens"),
                   "completion_tokens": usage.get("completion_tokens")}
            cache.put(k, hit)
        v = parse_verdict(hit["text"])
        rows.append({"id": c["id"], "query_id": c.get("query_id"), "label": bool(c["label"]), "parsed": v is not None,
                     "supported": None if v is None else v[0], "unsupported_arguments": None if v is None else v[1],
                     "latency_s": hit["latency_s"], "prompt_tokens": hit.get("prompt_tokens"), "completion_tokens": hit.get("completion_tokens")})
        if (i + 1) % 25 == 0:
            log(f"  {i + 1}/{len(cases)}")
    return rows


def summarise(rows):
    labels = [r["label"] for r in rows]
    # an unparseable reply is scored as a miss: genuine calls -> blocked (counted as a false block), injected -> allowed
    blocked = [(not r["supported"]) if r["parsed"] else bool(r["label"]) for r in rows]
    s = rates(labels, blocked); s.update(boot_ci(labels, blocked))
    s["n_unparseable"] = int(sum(not r["parsed"] for r in rows))
    lat = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    s["latency_s_mean"] = round(float(np.mean(lat)), 3) if lat else None
    s["latency_s_p95"] = round(float(np.percentile(lat, 95)), 3) if lat else None
    toks = [(r["prompt_tokens"] or 0) + (r["completion_tokens"] or 0) for r in rows]
    s["tokens_mean"] = round(float(np.mean(toks)), 1) if toks else None
    return s, blocked


def self_test():
    assert parse_verdict('{"supported": true, "unsupported_arguments": []}') == (True, [])
    assert parse_verdict('Sure! {"supported": "false", "unsupported_arguments": ["amount"]}') == (False, ["amount"])
    assert parse_verdict("no json") is None and parse_verdict('{"supported": 3}') is None
    cases = [{"id": f"c{i}", "label": i % 2 == 0, "premise": "User: pay 5", "call": {"name": "f", "arguments": {"a": 5 if i % 2 == 0 else 6}}} for i in range(8)]

    def fake(provider, key, model, messages, **kw):
        txt = messages[-1]["content"]
        ok = "(" in txt and '"a": 5' in txt
        return {"choices": [{"message": {"content": json.dumps({"supported": ok, "unsupported_arguments": [] if ok else ["a"]})}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10}}, 0.01
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        cache = Cache(Path(d) / "c.jsonl")
        rows = run(cases, "groq", "m", 0, cache, "k", 0, chat_fn=fake, sleep=lambda s: None, log=lambda *a: None)
        s, blocked = summarise(rows)
        assert s["false_block_rate"] == 0.0 and s["detection_rate"] == 1.0 and s["n_unparseable"] == 0
        calls = {"n": 0}
        def counting(*a, **k):
            calls["n"] += 1; return fake(*a, **k)
        run(cases, "groq", "m", 0, Cache(Path(d) / "c.jsonl"), "k", 0, chat_fn=counting, sleep=lambda s: None, log=lambda *a: None)
        assert calls["n"] == 0, "cache not used"
    assert mcnemar_exact([1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [0] * 10)["p"] == round(2 / 1024, 4)
    t = trim_context("x" * 100 + "END", 10)
    assert t.endswith("END") and len(t) < 60 and trim_context("short", 10) == "short" and trim_context("abc", None) == "abc"
    multi = build_messages(0, "User: hi", [{"name": "f", "arguments": {"a": 1}}, {"name": "g", "arguments": {"b": 2}}])
    assert "Planned tool calls" in multi[-1]["content"] and "g(" in multi[-1]["content"]
    bad = [{"id": "x", "label": True, "parsed": False, "supported": None, "unsupported_arguments": None, "latency_s": 0.1, "prompt_tokens": 1, "completion_tokens": 1},
           {"id": "y", "label": False, "parsed": False, "supported": None, "unsupported_arguments": None, "latency_s": 0.1, "prompt_tokens": 1, "completion_tokens": 1}]
    s2, b2 = summarise(bad)
    assert b2 == [True, False] and s2["n_unparseable"] == 2   # unparseable = miss on both classes
    print("self-test passed; prompt hash", PROMPT_HASH)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), default="groq")
    ap.add_argument("--model")
    ap.add_argument("--base-url", default=None, help="with --provider custom: OpenAI-compatible base URL, e.g. https://host/v1")
    ap.add_argument("--key-env", default=None, help="with --provider custom: name of the key in the environment or key file")
    ap.add_argument("--bench", default=str(ROOT / "benchmarks" / "argground_bench.json"),
                    help="argground_bench.json or benchmarks/data/deref/cases_fcrb.json | cases_cfb.json")
    ap.add_argument("--max-context-chars", type=int, default=None, help="keep only the most recent N characters of context (cfb is long)")
    ap.add_argument("--allow-test", action="store_true", help="required for --split test (pre-registration guard; logged)")
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--variant", type=int, default=0, choices=range(5))
    ap.add_argument("--rpm", type=float, default=20.0, help="max requests per minute (0 = unthrottled)")
    ap.add_argument("--cache", default=str(ROOT / "benchmarks" / "llm_judge_args_cache.jsonl"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.provider == "custom":
        if not a.base_url or not a.key_env:
            sys.exit("--provider custom needs --base-url and --key-env")
        PROVIDERS["custom"] = {"base": a.base_url.rstrip("/"), "key_env": a.key_env}
    key = get_key(PROVIDERS[a.provider]["key_env"])
    if a.list_models:
        if not key:
            sys.exit(f"set {PROVIDERS[a.provider]['key_env']} as an environment variable or in {KEY_FILE} first")
        for m in http_json(PROVIDERS[a.provider]["base"] + "/models", key, style=PROVIDERS[a.provider].get("style", "openai")).get("data", []):
            print(m["id"])
        return
    if not a.model:
        sys.exit("--model is required (see --list-models)")
    if not key and not a.dry_run:
        sys.exit(f"no key found: set {PROVIDERS[a.provider]['key_env']} as an environment variable, or put it in {KEY_FILE} (outside the repo)")
    if a.split == "test" and not a.dry_run:
        if not a.allow_test:
            sys.exit("test half requested without --allow-test (pre-registration guard)")
        import datetime
        with (ROOT / "benchmarks" / "test_run_ledger.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"when": datetime.datetime.now().isoformat(timespec="seconds"), "script": "llm_judge_args.py",
                                "bench": Path(a.bench).name, "provider": a.provider, "model": a.model, "variant": a.variant,
                                "limit": a.limit, "seed": a.seed, "prompt_hash": PROMPT_HASH}) + "\n")
    cases = json.loads(Path(a.bench).read_text(encoding="utf-8"))["cases"]
    if cases and "split" in cases[0]:
        pool = [c for c in cases if c["split"] == a.split]
    else:
        from eval_argground import split_cases
        dev, test = split_cases(cases)
        pool = {"dev": dev, "test": test}[a.split]
    rng = np.random.default_rng(a.seed)
    idx = rng.permutation(len(pool))[: a.limit]
    sample = [pool[i] for i in sorted(idx)]
    print(f"{a.provider}/{a.model} split={a.split} n={len(sample)} variant={a.variant} prompt_hash={PROMPT_HASH}")
    rows = run(sample, a.provider, a.model, a.variant, Cache(a.cache), key, a.rpm, dry=a.dry_run, max_context_chars=a.max_context_chars)
    if a.dry_run:
        return
    s, blocked = summarise(rows)
    from server.pipeline.arg_ground import call_is_grounded
    byid = {c["id"]: c for c in sample}

    def ours_block(c):
        if "args_meta" in c:                       # DeRef cases: score only the dataset's in_analysis arguments
            from eval_deref import score_case
            return score_case(c)[0] < 0.88
        return not call_is_grounded(c["call"]["arguments"], c["premise"])
    ours_blocked = [ours_block(byid[r["id"]]) for r in rows]
    labels = [r["label"] for r in rows]
    correct_judge = [(not b) == l for b, l in zip(blocked, labels)]
    correct_ours = [(not b) == l for b, l in zip(ours_blocked, labels)]
    result = {"provider": a.provider, "model": a.model, "split": a.split, "variant": a.variant, "prompt_hash": PROMPT_HASH, "seed": a.seed,
              "judge": s, "deterministic_checker_same_cases": {**rates(labels, ours_blocked), **boot_ci(labels, ours_blocked)},
              "mcnemar_exact_judge_vs_checker": mcnemar_exact(correct_judge, correct_ours), "rows": rows}
    bench_tag = Path(a.bench).stem.replace("argground_bench", "glaive").replace("cases_", "")
    out = Path(a.out) if a.out else ROOT / "benchmarks" / f"llm_judge_args_{bench_tag}_{a.provider}_{re.sub(r'[^A-Za-z0-9]+', '_', a.model)}_{a.split}_v{a.variant}.json"
    out.write_text(json.dumps(result, indent=1))
    print(json.dumps({k: result[k] for k in ("judge", "deterministic_checker_same_cases", "mcnemar_exact_judge_vs_checker")}, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
