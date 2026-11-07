"""Build a cross-model consensus dataset of natural tool-call argument errors from BFCL.

Two stages (run with the stdlib only; downloaded files are read as JSON, never executed):

  python load_bfcl_consensus.py fetch   # range-download needed slices from Hugging Face / GitHub
  python load_bfcl_consensus.py build   # parse, label, write data/bfcl/consensus_cases.json

Sources
  * Model outputs: Hugging Face dataset AgentSuite/BFCL_V4-trajectories (one jsonl per model,
    30 models).  Only the `format_sensitivity` task block is single-turn; each test case appears
    there once per prompt-format configuration.  We keep ONE configuration (the plain python
    format) so every model saw the identical prompt.  Files are huge (40-60 MB), so `fetch`
    uses HTTP Range requests to jump to a few contiguous case blocks and keeps only the lines
    of the chosen configuration (a few hundred KB per model on disk).
  * Prompts, function schemas, gold answers: ShishirPatil/gorilla,
    berkeley-function-call-leaderboard/bfcl_eval/data (raw.githubusercontent.com), Apache-2.0.

The argument comparison in this file is deliberately independent of server/pipeline.
"""
import ast
import json
import math
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("BFCL_RAW_DIR", r"C:\Users\GOVARDHAN SATYA\bfcl_raw")
GOR = os.path.join(RAW, "gorilla_data")
FILT = os.path.join(RAW, "filtered")
OUT_DIR = os.path.join(HERE, "data", "bfcl")
OUT = os.path.join(OUT_DIR, "consensus_cases.json")

HF_REPO = "AgentSuite/BFCL_V4-trajectories"
HF_TREE = "https://huggingface.co/api/datasets/%s/tree/main" % HF_REPO
HF_FILE = "https://huggingface.co/datasets/%s/resolve/main/" % HF_REPO
GH_DATA = ("https://raw.githubusercontent.com/ShishirPatil/gorilla/main/"
           "berkeley-function-call-leaderboard/bfcl_eval/data/")

# the one prompt configuration kept for every model
CFG = "ret_fmt=python&tool_call_tag=False&func_doc_fmt=python&prompt_fmt=plaintext&style=classic"
# how many cases (first n in the official list order) to take from each category
PER_CAT = {"simple_python": 30, "parallel": 15, "multiple": 15, "parallel_multiple": 15,
           "live_simple": 24, "live_multiple": 86, "live_parallel": 6, "live_parallel_multiple": 9}  # all 200 single-turn cases (was 56)
TASK_RANK = {"BFCL_v4_web_search_no_snippet": 0, "BFCL_v4_web_search_base": 1,
             "BFCL_v4_memory_kv": 2, "BFCL_v4_memory_rec_sum": 3,
             "BFCL_v4_memory_vector": 4, "format_sensitivity": 5}
BYTE_CAP = 1500 * 1024 * 1024  # abort the fetch if more than this has been transferred
_bytes = [0]
_lock = threading.Lock()


def _count(n):
    with _lock:
        _bytes[0] += n
        if _bytes[0] > BYTE_CAP:
            raise RuntimeError("transfer cap exceeded")


def http(url, rng=None, timeout=90, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Range": rng} if rng else {})
            data = urllib.request.urlopen(req, timeout=timeout).read()
            _count(len(data))
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + i)
    raise last


# ---------------------------------------------------------------- fetch
def case_order():
    ids = json.load(open(os.path.join(GOR, "BFCL_v4_format_sensitivity.json"), encoding="utf8"))
    flat, wanted_by_cat = [], {}
    for cat, lst in ids.items():
        start = len(flat)
        # the trajectory files list cases sorted by their numeric id parts, not in the json list order
        flat.extend(sorted(lst, key=lambda s: [int(x) for x in re.findall(r"\d+", s)]))
        if cat in PER_CAT:
            wanted_by_cat[cat] = (start, start + PER_CAT[cat])
    return flat, {c: i for i, c in enumerate(flat)}, wanted_by_cat


def key_of_ids(ids, pos):
    """Smallest (task_rank, case_index) among meta ids found in a window."""
    best = None
    for i in ids:
        if i.startswith("format_sensitivity_"):
            c = i.rsplit(":", 1)[-1]
            if c not in pos:
                continue
            k = (5, pos[c])
        else:
            k = None
            for t, r in TASK_RANK.items():
                if i.startswith(t.replace("BFCL_v4_", "") + "_"):
                    k = (r, 0)
            if k is None:
                continue
        if best is None or k < best:
            best = k
    return best


META_ID = re.compile(r'"meta": \{"id": "([^"]+)"')


def probe_key(model, size, off, pos):
    for width in (24000, 330000):  # long web_search lines need a wide window to reach their meta tail
        b = http(HF_FILE + model + ".jsonl", "bytes=%d-%d" % (off, min(size - 1, off + width))).decode("utf8", "ignore")
        k = key_of_ids(META_ID.findall(b), pos)
        if k is not None:
            return k
    return None


def find_offset(model, size, target, pos, lo=0):
    """Largest offset whose window key is < target (binary search, ~12 probes of 24 KB)."""
    hi = size - 1
    while hi - lo > 20000:
        mid = (lo + hi) // 2
        k = probe_key(model, size, mid, pos)
        if k is not None and k >= target:
            hi = mid
        else:
            lo = mid
    return max(0, lo - 20000)


def read_segment(model, size, start_off, first, last, pos, out):
    """Stream from start_off, keep CFG lines for cases with index in [first, last)."""
    req = urllib.request.Request(HF_FILE + model + ".jsonl", headers={"Range": "bytes=%d-" % start_off})
    resp = urllib.request.urlopen(req, timeout=120)
    buf = b""
    first_line = True
    got = set()
    try:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            _count(len(chunk))
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                if first_line:  # partial line at the seek point
                    first_line = False
                    continue
                m = META_ID.search(ln[-600:].decode("utf8", "ignore"))
                if not m:
                    continue
                i = m.group(1)
                c = i.rsplit(":", 1)[-1]
                if c not in pos:
                    continue
                if pos[c] >= last:
                    return got
                if pos[c] >= first and (":" + CFG + ":") in i:
                    out.write(ln.decode("utf8") + "\n")
                    got.add(c)
    finally:
        resp.close()
    return got


def fetch_model(model, size, pos, wanted_by_cat):
    os.makedirs(FILT, exist_ok=True)
    path = os.path.join(FILT, model + ".jsonl")
    before = _bytes[0]
    n = 0
    with open(path, "w", encoding="utf8") as out:
        off = 0
        for cat, (a, b) in wanted_by_cat.items():
            off = find_offset(model, size, (5, a), pos, lo=off)
            got = read_segment(model, size, off, a, b, pos, out)
            n += len(got)
    return model, n


def fetch():
    os.makedirs(GOR, exist_ok=True)
    flat, pos, wanted = case_order()
    for cat in list(PER_CAT):
        for sub in ("", "possible_answer/"):
            p = os.path.join(GOR, sub + "BFCL_v4_%s.json" % cat)
            if os.path.exists(p) and os.path.getsize(p) > 0:
                continue
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(http(GH_DATA + sub + "BFCL_v4_%s.json" % cat))
    tree = json.loads(http(HF_TREE))
    models = {t["path"][:-6]: t["size"] for t in tree if t["path"].endswith(".jsonl")}
    only = sys.argv[2:]
    todo = [m for m in sorted(models) if not only or m in only]
    todo = [m for m in todo if only or not (os.path.exists(os.path.join(FILT, m + ".jsonl"))
                                            and os.path.getsize(os.path.join(FILT, m + ".jsonl")) > 0)]
    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(fetch_model, m, models[m], pos, wanted) for m in todo]
        for f in futs:
            m, n = f.result()
            print("%-40s cases_kept=%d transferred_total_MB=%.1f" % (m, n, _bytes[0] / 1e6), flush=True)


# ---------------------------------------------------------------- argument comparison
import unicodedata  # noqa: E402
from itertools import permutations  # noqa: E402

LEVEL_RANK = {"exact": 0, "numeric": 1, "normalised": 2, "loose": 3, "coerced": 4}


def _worst(a, b):
    return a if LEVEL_RANK[a] >= LEVEL_RANK[b] else b


def norm_str(s):
    s = unicodedata.normalize("NFKC", s).casefold().strip()
    return re.sub(r"\s+", " ", s)


def loose_str(s):
    return re.sub(r"[\s,./\\\-_*^'\"`]", "", norm_str(s))


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _parse_numeric_string(s):
    t = s.strip().replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None


def match(p, g):
    """Return the weakest match level at which pred value p equals gold value g, else None."""
    if isinstance(g, bool) or isinstance(p, bool):
        if isinstance(g, bool) and isinstance(p, bool):
            return "exact" if p == g else None
        if isinstance(g, bool) and isinstance(p, str) and norm_str(p) in ("true", "false"):
            return "coerced" if (norm_str(p) == "true") == g else None
        return None
    if p is None or g is None:
        if p is None and g is None:
            return "exact"
        other = g if p is None else p
        return "normalised" if other == "" else None
    if _num(p) and _num(g):
        if p == g:
            return "exact"
        return "numeric" if math.isclose(p, g, rel_tol=1e-9, abs_tol=1e-12) else None
    if isinstance(p, str) and isinstance(g, str):
        if p == g:
            return "exact"
        if norm_str(p) == norm_str(g):
            return "normalised"
        return "loose" if loose_str(p) == loose_str(g) else None
    if isinstance(p, str) and _num(g):
        v = _parse_numeric_string(p)
        return "coerced" if v is not None and math.isclose(v, g, rel_tol=1e-9, abs_tol=1e-12) else None
    if _num(p) and isinstance(g, str):
        v = _parse_numeric_string(g)
        return "coerced" if v is not None and math.isclose(v, p, rel_tol=1e-9, abs_tol=1e-12) else None
    if isinstance(p, (list, tuple)) and isinstance(g, (list, tuple)):
        if len(p) != len(g):
            return None
        lvl = "exact"
        for a, b in zip(p, g):
            m = match(a, b)
            if m is None:
                return None
            lvl = _worst(lvl, m)
        return lvl
    if isinstance(p, dict) and isinstance(g, dict):
        pk = {norm_str(str(k)): v for k, v in p.items()}
        gk = {norm_str(str(k)): v for k, v in g.items()}
        if set(pk) != set(gk):
            return None
        lvl = "exact"
        for k in gk:
            # BFCL gold dicts hold a LIST of acceptable values per key
            m = match_any(pk[k], gk[k] if isinstance(gk[k], list) else [gk[k]])
            if m is None:
                return None
            lvl = _worst(lvl, m)
        return lvl
    return None


def match_any(p, alts):
    """Best (lowest-rank) level over the acceptable gold alternatives; '' alternative = omittable."""
    best = None
    for g in alts:
        m = match(p, g)
        if m is not None and (best is None or LEVEL_RANK[m] < LEVEL_RANK[best]):
            best = m
    return best


# ---------------------------------------------------------------- parsing model output
def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return None if base is None else base + "." + node.attr
    return None


def _calls_from_elts(elts):
    calls = []
    for el in elts:
        if isinstance(el, ast.Expr):
            el = el.value
        if not isinstance(el, ast.Call):
            return None, "element_not_call"
        name = _dotted(el.func)
        if name is None or el.args:
            return None, "positional_or_unnamed"
        args = {}
        for kw in el.keywords:
            if kw.arg is None:
                return None, "star_kwargs"
            try:
                args[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, SyntaxError):
                return None, "non_literal_value"
        calls.append((name, args))
    if not calls:
        return None, "no_call"
    return calls, None


def parse_calls(text):
    """Parse a python-style call list. Returns (calls, error, lenient).
    calls = [(name, {arg: value})]; lenient=True when the output was not a bracketed list
    (bare call, comma- or newline-separated calls) and was recovered anyway."""
    if not isinstance(text, str) or not text.strip():
        return None, "empty_output", False
    t = text.strip()
    if t.startswith("Error during inference"):
        return None, "inference_error", False
    t = t.replace("<<function>>", "")
    t = re.sub(r"^```(?:python|py)?\s*|\s*```$", "", t).strip()
    if t.startswith("[") and t.endswith("]"):
        try:
            body = ast.parse(t, mode="eval").body
        except SyntaxError:
            body = None
        if isinstance(body, ast.List):
            c, e = _calls_from_elts(body.elts)
            return c, e, False
    for wrapped in ("[" + t + "]",):
        try:
            body = ast.parse(wrapped, mode="eval").body
            if isinstance(body, ast.List) and all(isinstance(x, ast.Call) for x in body.elts):
                c, e = _calls_from_elts(body.elts)
                return c, e, True
        except SyntaxError:
            pass
    try:
        mod = ast.parse(t, mode="exec")
        if mod.body and all(isinstance(x, ast.Expr) and isinstance(x.value, ast.Call) for x in mod.body):
            c, e = _calls_from_elts(mod.body)
            return c, e, True
    except SyntaxError:
        pass
    i, j = t.find("["), t.rfind("]")
    if i < 0 or j < i:
        return None, "no_call_list", False
    try:  # prose around a bracketed list
        body = ast.parse(t[i:j + 1], mode="eval").body
    except SyntaxError:
        return None, "syntax_error", False
    if not isinstance(body, ast.List):
        return None, "not_a_list", False
    c, e = _calls_from_elts(body.elts)
    return c, e, True


def fname(n):
    return n.replace(".", "_").strip().casefold()


def label_call(pred_args, gold_args, schema_props):
    labels, correct = {}, 0
    for a, v in pred_args.items():
        if a not in gold_args:
            reason = "not_in_schema" if a not in schema_props else "unexpected_arg"
            labels[a] = {"label": "wrong", "match_level": None, "reason": reason}
            continue
        lvl = match_any(v, gold_args[a])
        if lvl is None:
            labels[a] = {"label": "wrong", "match_level": None, "reason": "value_mismatch"}
        else:
            labels[a] = {"label": "correct", "match_level": lvl, "reason": None}
            correct += 1
    return labels, correct


def align(pred_calls, gold_calls, props_of):
    """Match predicted calls to gold calls (order-free). Returns list of (gold_index, pred_index)."""
    gn = [fname(next(iter(g))) for g in gold_calls]
    pn = [fname(n) for n, _ in pred_calls]
    if sorted(gn) != sorted(pn):
        return None
    pairs = []
    for name in set(gn):
        gi = [i for i, n in enumerate(gn) if n == name]
        pi = [i for i, n in enumerate(pn) if n == name]
        best, best_s = None, -1
        perms = permutations(pi) if len(pi) <= 6 else [tuple(pi)]
        for perm in perms:
            s = 0
            for g_i, p_i in zip(gi, perm):
                gfn = next(iter(gold_calls[g_i]))
                _, c = label_call(pred_calls[p_i][1], gold_calls[g_i][gfn], props_of(name))
                s += c
            if s > best_s:
                best, best_s = list(zip(gi, perm)), s
        pairs.extend(best)
    return sorted(pairs)


# ---------------------------------------------------------------- build
def load_gorilla():
    data = {}
    for cat in PER_CAT:
        q = {}
        for ln in open(os.path.join(GOR, "BFCL_v4_%s.json" % cat), encoding="utf8"):
            if ln.strip():
                d = json.loads(ln)
                q[d["id"]] = d
        for ln in open(os.path.join(GOR, "possible_answer", "BFCL_v4_%s.json" % cat), encoding="utf8"):
            if ln.strip():
                d = json.loads(ln)
                if d["id"] in q:
                    q[d["id"]]["ground_truth"] = d["ground_truth"]
        data.update(q)
    return data


def build():
    gor = load_gorilla()
    flat, pos, wanted = case_order()
    cat_of = {}
    for cat, (a, b) in wanted.items():
        for c in flat[a:b]:
            cat_of[c] = cat
    records, malformed, consensus = [], [], {}
    models = []
    for fn in sorted(os.listdir(FILT)):
        if not fn.endswith(".jsonl"):
            continue
        model = fn[:-6]
        models.append(model)
        seen = set()
        for ln in open(os.path.join(FILT, fn), encoding="utf8"):
            r = json.loads(ln)
            cid = r["meta"]["id"].rsplit(":", 1)[-1]
            if cid not in gor or cid in seen or (":" + CFG + ":") not in r["meta"]["id"]:
                continue
            seen.add(cid)
            case = gor[cid]
            asst = [m for m in r["messages"] if m.get("role") == "assistant"]
            raw = asst[-1].get("content") if asst else None
            if raw is None and asst and asst[-1].get("tool_calls"):
                raw = json.dumps(asst[-1]["tool_calls"])
            base = {"test_id": cid, "model": model, "category": cat_of.get(cid, "?")}
            calls, err, lenient = parse_calls(raw)
            if err:
                malformed.append(dict(base, reason=err, raw_output=(raw or "")[:500]))
                continue
            gold = case["ground_truth"]
            schemas = case["function"]
            props = {fname(s["name"]): set(s.get("parameters", {}).get("properties", {})) for s in schemas}
            pairs = align(calls, gold, lambda n: props.get(n, set()))
            if pairs is None:
                malformed.append(dict(base, reason="function_name_or_count_mismatch",
                                      raw_output=(raw or "")[:500],
                                      pred_functions=[n for n, _ in calls],
                                      gold_functions=[next(iter(g)) for g in gold]))
                continue
            out_calls = []
            for g_i, p_i in pairs:
                gfn = next(iter(gold[g_i]))
                gargs = gold[g_i][gfn]
                pname, pargs = calls[p_i]
                labels, _ = label_call(pargs, gargs, props.get(fname(pname), set()))
                missing = [a for a, alts in gargs.items() if a not in pargs and "" not in alts]
                out_calls.append({"gold_call_index": g_i, "function": pname, "arguments": pargs,
                                  "gold_arguments": gargs, "arg_labels": labels,
                                  "missing_required": missing})
                for a, v in pargs.items():
                    consensus.setdefault("%s|%d|%s" % (cid, g_i, a), {})[model] = {
                        "value": v, "label": labels[a]["label"]}
            records.append(dict(base, request=case["question"][0][0]["content"],
                                function_schemas=schemas, calls=out_calls,
                                raw_output=raw, lenient_parse=lenient,
                                bfcl_meta_valid=r["meta"].get("valid")))
    os.makedirs(OUT_DIR, exist_ok=True)
    meta = {
        "model_output_source": HF_FILE + "<model>.jsonl (AgentSuite/BFCL_V4-trajectories, format_sensitivity block)",
        "model_output_licence": "none declared on dataset card",
        "prompt_gold_source": GH_DATA,
        "prompt_gold_licence": "Apache-2.0 (gorilla repo LICENSE)",
        "prompt_config": CFG,
        "cases_per_category": PER_CAT,
        "models": models,
        "n_records": len(records),
        "n_malformed": len(malformed),
        "n_args": sum(len(c["arguments"]) for r in records for c in r["calls"]),
        "n_wrong_args": sum(1 for r in records for c in r["calls"] for v in c["arg_labels"].values()
                            if v["label"] == "wrong"),
        "comparison": "case/NFKC/whitespace normalisation, numeric tolerance, loose punctuation-stripped string "
                      "match, numeric-string coercion (level 'coerced'), ordered list and dict equality, any of the "
                      "gold alternatives; '' alternative = parameter may be omitted",
    }
    json.dump({"meta": meta, "records": records, "malformed": malformed, "consensus_index": consensus},
              open(OUT, "w", encoding="utf8"), ensure_ascii=False)
    print(json.dumps(meta, indent=1))
    summarise(records, malformed, consensus)


def summarise(records, malformed, consensus):
    per = {}
    for r in records:
        s = per.setdefault(r["model"], [0, 0, 0, 0])
        s[0] += 1
        for c in r["calls"]:
            for v in c["arg_labels"].values():
                s[1] += 1
                s[2] += v["label"] == "wrong"
    for mm in malformed:
        per.setdefault(mm["model"], [0, 0, 0, 0])[3] += 1
    print("\n| model | calls | args | wrong args | wrong rate | malformed |\n|---|---|---|---|---|---|")
    for m, (n, a, w, mal) in sorted(per.items()):
        print("| %s | %d | %d | %d | %.1f%% | %d |" % (m, n, a, w, 100.0 * w / max(a, 1), mal))
    # examples: wrong args where >=60% of other models agree on a different value
    ex = []
    for k, d in consensus.items():
        for m, x in d.items():
            if x["label"] != "wrong":
                continue
            others = [json.dumps(o["value"], sort_keys=True) for mm, o in d.items() if mm != m]
            if len(others) < 10:
                continue
            top = max(set(others), key=others.count)
            if json.dumps(x["value"], sort_keys=True) != top and others.count(top) >= 0.6 * len(others):
                ex.append((k, m, x["value"], others.count(top), len(others), top))
    print("\nexamples (wrong value; modal value of other models):")
    seen = set()
    for k, m, v, c, n, top in ex:
        if k in seen:
            continue
        seen.add(k)
        print("-", k, "| model:", m, "| wrong:", json.dumps(v)[:80], "| others modal:", top[:80], "(%d/%d)" % (c, n))
        if len(seen) >= 8:
            break
    print("\nargs where at least one model is wrong:", sum(1 for d in consensus.values()
          if any(x["label"] == "wrong" for x in d.values())), "of", len(consensus))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "fetch":
        fetch()
    elif cmd == "build":
        build()
    else:
        sys.exit("usage: load_bfcl_consensus.py fetch|build")
