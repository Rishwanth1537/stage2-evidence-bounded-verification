"""
Contract tier: deterministic checks of an argument value against the TOOL'S OWN DEFINITION (type, enum, documented format).
Exploratory, DEV half only.  The schema is joined to DeRef fcrb cases by function name from the BFCL data files in
C:\\Users\\GOVARDHAN SATYA\\bfcl_raw\\gorilla_data (Apache-2.0, fetched by the BFCL consensus task).

  PYTHONPATH=. python benchmarks/contract_tier.py [--limit-sample] [--out benchmarks/contract_tier_dev.json]

Checks (each reported separately):
  type          integer/float/string/boolean/array/dict declared by the schema vs the value actually passed
  enum          value not among the schema's enum values (exact, case-sensitive)
  enum_ci       as above but case-insensitive (to show how much of `enum` is only casing)
  fmt_city_state  description asks for 'City, State' and the value is not "<city>, <2-letter state>"
  fmt_date      description names YYYY-MM-DD and the value is not an ISO date
  fmt_time      description names HH:MM and the value is not hh:mm
  unknown_arg   argument name not declared by the schema
Reports detection of wrong arguments and false blocks on correct ones, by derivation path, and call-level numbers for contract alone,
context grounding alone (S2, tau 0.88) and their union, on all 630 dev calls and on the 200-call seeded judge sample.
"""
import argparse
import glob
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

GORILLA = Path(r"C:\Users\GOVARDHAN SATYA\bfcl_raw\gorilla_data")
DONTCARE = {"dontcare", "don't care", ""}


def load_schemas():
    """name -> list of distinct definitions (BFCL repeats a function name across files with different parameter sets)."""
    fns = {}
    for f in sorted(glob.glob(str(GORILLA / "BFCL_v4_*.json"))):
        for line in open(f, encoding="utf-8"):
            try:
                o = json.loads(line)
            except Exception:
                continue
            for fn in o.get("function", []) or []:
                lst = fns.setdefault(fn["name"], [])
                if fn not in lst:
                    lst.append(fn)
    return fns


def pick(schemas, call):
    """Variant whose parameter names cover the call's arguments; ties and misses fall back to the largest overlap, then file order.
    The rule uses argument NAMES only (never values or labels), so it cannot leak correctness; it does make `unknown_arg` rare."""
    variants = schemas.get(call["name"])
    if not variants:
        return None
    names = set(call["arguments"])

    def key(v):
        props = set(v.get("parameters", {}).get("properties", {}))
        return (names <= props, len(names & props), -len(props))
    return max(variants, key=key)


def type_ok(declared, v):
    d = (declared or "").lower()
    if d in ("", "any"):
        return True
    if d == "string":
        return isinstance(v, str)
    if d == "integer":
        return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v == int(v))
    if d in ("float", "number"):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if d == "boolean":
        return isinstance(v, bool)
    if d in ("array", "tuple"):
        return isinstance(v, (list, tuple))
    if d in ("dict", "object"):
        return isinstance(v, dict)
    return True


CITY_HINT = re.compile(r"City, State|city and state|e\.g\.,? '?[A-Z][a-z]+, [A-Z]{2}")
CITY_OK = re.compile(r"^[^,]+,\s*[A-Z]{2}$")


DATE_RELAXED = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{1,2}:\d{2}(:\d{2})?)?\s*([AaPp][Mm])?$")
TIME_RELAXED = re.compile(r"^(\d{4}-\d{2}-\d{2}[ T])?\d{1,2}:\d{2}(:\d{2})?\s*([AaPp][Mm])?$")


def violations(spec, value, relaxed=False):
    """relaxed=True (used by decidability.py, tuned on audit items A001-A050 only): accept a time of day after an ISO date, 12-hour times with
    AM/PM, and check enum membership of array items.  The default (False) reproduces the first version used in earlier results."""
    out = []
    if value is None:
        return out
    if relaxed and isinstance(value, list) and isinstance(spec.get("items"), dict) and spec["items"].get("enum"):
        if any(x not in spec["items"]["enum"] for x in value):
            out.append("enum")
    desc0 = spec.get("description", "") or ""
    lenient = (isinstance(value, str) and value.lower() in ("true", "false") and (spec.get("type") or "").lower() == "boolean") or \
              (isinstance(value, str) and value.lower() == "dontcare" and "dontcare" in desc0.lower())
    if not lenient and not type_ok(spec.get("type"), value):
        out.append("type")
    en = spec.get("enum")
    if en is not None and not isinstance(value, (list, dict)):
        if value not in en and str(value) not in [str(x) for x in en]:
            out.append("enum")
            if str(value).lower() not in [str(x).lower() for x in en]:
                out.append("enum_ci")
    desc = spec.get("description", "") or ""
    if isinstance(value, str) and str(value).lower() not in DONTCARE:
        if CITY_HINT.search(desc) and not CITY_OK.match(value):
            out.append("fmt_city_state")
        date_re = DATE_RELAXED if relaxed else re.compile(r"^\d{4}-\d{2}-\d{2}$")
        time_re = TIME_RELAXED if relaxed else re.compile(r"^\d{1,2}:\d{2}$")
        if "YYYY-MM-DD" in desc and not date_re.match(value):
            out.append("fmt_date")
        if re.search(r"HH:MM|HH:mm", desc) and not time_re.match(value):
            out.append("fmt_time")
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return [float("nan")] * 2
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 3), round(c + h, 3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "contract_tier_dev.json"))
    a = ap.parse_args()
    from agent_judge import sample_cases
    from eval_deref import score_case
    schemas = load_schemas()
    bench = str(ROOT / "benchmarks/data/deref/cases_fcrb.json")
    cases = [c for c in json.loads(Path(bench).read_text(encoding="utf-8"))["cases"] if c["split"] == "dev"]
    sample_ids = {c["id"] for c in sample_cases(bench, "dev", 200, 0)}
    res = {"n_cases": len(cases)}
    per_arg = defaultdict(lambda: Counter())
    call_rows = []
    for c in cases:
        calls = c.get("calls") or [c["call"]]
        flagged_call = False
        have_schema = True
        for a_ in c["args_meta"]:
            if not a_["in_analysis"]:
                continue
            ci = a_.get("call_index", 0)
            call = calls[ci] if ci < len(calls) else calls[0]
            fn = pick(schemas, call)
            if fn is None:
                have_schema = False
                continue
            props = fn.get("parameters", {}).get("properties", {})
            lab = a_["label"]
            per_arg[("all", lab)]["n"] += 1
            per_arg[(a_["path"], lab)]["n"] += 1
            if a_["name"] not in props:
                v = ["unknown_arg"]
            else:
                v = violations(props[a_["name"]], a_["value"])
            for key in set(v):
                per_arg[("all", lab)][key] += 1
                per_arg[(a_["path"], lab)][key] += 1
            if any(k in v for k in ("type", "enum", "fmt_city_state", "fmt_date", "fmt_time", "unknown_arg")):
                per_arg[("all", lab)]["any"] += 1
                per_arg[(a_["path"], lab)]["any"] += 1
                flagged_call = True
        s2 = score_case(c)[0]
        call_rows.append({"id": c["id"], "wrong": c["label"] is False or c["label"] == 0, "contract": flagged_call, "ctx": s2 < 0.88,
                          "schema": have_schema, "sample": c["id"] in sample_ids})
    # in this dataset c["label"] True = correct call; wrong = not label
    for r, c in zip(call_rows, cases):
        r["wrong"] = not bool(c["label"])
    keys = ["any", "type", "enum", "enum_ci", "fmt_city_state", "fmt_date", "fmt_time", "unknown_arg"]
    res["argument_level"] = {}
    for (path, lab), cnt in sorted(per_arg.items()):
        n = cnt["n"]
        res["argument_level"][f"{path}|{lab}"] = {"n": n, **{k: cnt[k] for k in keys if cnt[k]}, "any_rate": round(cnt["any"] / n, 3) if n else None,
                                                  "any_ci": wilson(cnt["any"], n)}
    def table(rows, name):
        w = np.array([r["wrong"] for r in rows]); out = {}
        for sysname, f in (("contract", lambda r: r["contract"]), ("context_S2", lambda r: r["ctx"]), ("union", lambda r: r["contract"] or r["ctx"])):
            b = np.array([f(r) for r in rows])
            out[sysname] = {"fbr": round(float(b[~w].mean()), 3), "det": round(float(b[w].mean()), 3)}
        out["n"] = len(rows); out["n_with_schema"] = int(sum(r["schema"] for r in rows))
        return out
    res["call_level_all_dev"] = table(call_rows, "all")
    res["call_level_judge_sample_with_schema"] = table([r for r in call_rows if r["sample"] and r["schema"]], "sample")
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
