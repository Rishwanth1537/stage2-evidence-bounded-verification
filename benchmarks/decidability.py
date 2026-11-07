"""
Decidability labels: for every WRONG argument (or wrong call), the weakest evidence source that decides it is wrong.  Development data only.

Classes (rungs of the evidence ladder, lowest first):
  E1_conversation   the conversation itself states or determines the right value, so a careful reader sees the call's value is wrong
  E2_contract       not E1, but the tool definition (type, enum, documented format, undeclared argument) shows the value is wrong
  E3_state          not E1/E2, but the environment's state decides it (tau-bench: a lookup rejects the id or status)
  E4_peers          not E1-E3, but other models agree on a different value that matches a gold alternative
  CHOICE_user       the value is supported and valid, and none of the above decides: a wrong choice that only the user can settle
  U_silent          the value is not supported by the conversation and nothing else decides (invented, translated, or needs world knowledge)

Rules per dataset (documented so they can be audited; they never use a verifier's verdict):
  BFCL (gold alternatives known):  E1 if some scalar gold alternative is grounded in the request by the type-aware matcher; else E2 if the model's
      value violates the tool definition; else E4 if the plurality of the other models (share >= 0.5) equals a gold alternative; else CHOICE_user if
      the model's value is grounded in the request, else U_silent.
  DeRef fcrb dev (no reference value; path = how the PLANNED value relates to the context): contract violation -> E2; else path visible/format/
      history_only -> E1 (a value present in the conversation but the wrong choice: the conversation determines the right one); path default -> E2;
      path no_source/placeholder -> U_silent.
  tau-bench suspect write calls: environment error with a lookup flag -> E3; every other suspect call (item, payment, free text, unwanted extra action,
      valid id of the same user) -> CHOICE_user.
The labels are analysis labels (they use gold and the tool definition, which a verifier does not have).  The 100-case human audit checks them.

  Since Deviation 19 (2026-11-04) U_silent is merged into E1_conversation and E4_peers is dropped (--legacy-classes reproduces the old labels).
  PYTHONPATH=. python benchmarks/decidability.py [--audit]       (writes benchmarks/decidability_dev.json; with --audit also review/audit/*)
"""
import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from analyze_consensus import canon  # noqa: E402
from contract_tier import load_schemas, pick, violations  # noqa: E402
from server.pipeline.arg_ground import check_value  # noqa: E402

HARD = ("type", "enum", "fmt_city_state", "fmt_date", "fmt_time", "unknown_arg")


def scalar(v):
    return isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip() != ""


def grounded(name, v, text):
    if isinstance(v, list):
        items = [x for x in v if scalar(x)]
        return bool(items) and all(check_value(name, x, text).verdict == "GROUNDED" for x in items)
    return scalar(v) and check_value(name, v, text).verdict == "GROUNDED"


def contract_bad(spec, v, in_props=True):
    if not in_props:
        return True
    return any(k in violations(spec, v, relaxed=True) for k in HARD)


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_DT = re.compile(r"^\s*(?:(\d{4})-(\d{1,2})-(\d{1,2}))?(?:[ T]*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap]m)?)?\s*$", re.I)


def _norm(x):
    return " ".join(_PUNCT.sub(" ", str(x).lower()).split())


def _dt(x):
    m = _DT.match(str(x))
    if not m or not any(m.groups()):
        return None
    y, mo, d, hh, mi, ss, ap = m.groups()
    h = int(hh) if hh is not None else None
    if h is not None and ap:
        h = h % 12 + (12 if ap.lower() == "pm" else 0)
    return (int(y) if y else None, int(mo) if mo else None, int(d) if d else None, h, int(mi) if mi else None, int(ss or 0) if hh is not None else None)


def relaxed_equal(value, gold_alts, default=None):
    """True when the value is a format variant of a gold alternative (case, punctuation, one string containing the other when at least 3
    characters, equal numbers, equal dates/times written in different forms) or equals the tool's default.  Added after the LLM pre-audit found
    that many benchmark 'wrong' labels are acceptable alternatives; tuned on audit items A001-A050 only."""
    cands = [g for g in gold_alts if not (isinstance(g, str) and g == "")]
    if default is not None and _norm(value) == _norm(default):
        return True
    for g in cands:
        if isinstance(value, bool) or isinstance(g, bool):
            continue
        if isinstance(value, (int, float)) and isinstance(g, (int, float)):
            if float(value) == float(g):
                return True
            continue
        if isinstance(value, str) and isinstance(g, str):
            a, b = _norm(value), _norm(g)
            if a and (a == b or (min(len(a), len(b)) >= 3 and (a in b or b in a))):
                return True
            da, db = _dt(value), _dt(g)
            if da is not None and db is not None and da == db:
                return True
    return False


# ------------------------------------------------------------------ BFCL
def schema_for(call_fn, schemas):
    for s in schemas:
        if s["name"] == call_fn or s["name"].replace(".", "_") == call_fn.replace(".", "_"):
            return s
    return None


CONSOLIDATE = True    # Deviation 19: three AI audit passes + user decisions gave 17/40 class agreement (< 60%): U_silent -> E1_conversation, E4_peers dropped


def label_bfcl(consolidate=None):
    consolidate = CONSOLIDATE if consolidate is None else consolidate
    d = json.loads((ROOT / "benchmarks/data/bfcl/consensus_cases.json").read_text(encoding="utf-8"))
    idx = {s: {m: canon(x["value"]) for m, x in pm.items()} for s, pm in d["consensus_index"].items()}
    out = []
    for r in d["records"]:
        for call in r["calls"]:
            sch = schema_for(call["function"], r["function_schemas"])
            props = (sch or {}).get("parameters", {}).get("properties", {})
            for arg, lab in call["arg_labels"].items():
                v = call["arguments"].get(arg)
                base = {"dataset": "bfcl", "item": f"{r['test_id']}|{r['model']}|{call['gold_call_index']}|{arg}", "test": r["test_id"],
                        "model": r["model"], "arg": arg, "value": v, "request": r["request"], "tool": call["function"],
                        "spec": props.get(arg), "gold": call["gold_arguments"].get(arg), "correct": lab["label"] == "correct"}
                if base["correct"]:
                    base["class"] = None
                    out.append(base)
                    continue
                gold = [g for g in (call["gold_arguments"].get(arg) or [])]
                gold_scalars = [g for g in gold if scalar(g) or (isinstance(g, list) and any(scalar(x) for x in g))]
                spec = props.get(arg, {})
                if relaxed_equal(v, gold, spec.get("default")):
                    cls = "WEAK_format_variant"            # acceptable alternative of a gold value (or the tool default)
                elif any(isinstance(g, str) and g == "" for g in gold):
                    cls = "WEAK_optional_unrequested"      # optional argument that gold leaves blank; many such 'errors' are acceptable
                else:
                    g_in = any(grounded(arg, g, r["request"]) for g in gold_scalars)
                    m_in = grounded(arg, v, r["request"])
                    cbad = contract_bad(spec, v, arg in props)
                    if g_in and not m_in:
                        cls = "E1_conversation"            # the conversation states the right value and does not support the agent's
                    elif cbad:
                        cls = "E2_contract"                # the conversation supports the value (or is silent) but the tool definition rules it out
                    else:
                        slot = idx.get(f"{r['test_id']}|{call['gold_call_index']}|{arg}", {})
                        others = [canon_v for m, canon_v in slot.items() if m != r["model"]]
                        cls = None
                        if others and not consolidate:
                            top, cnt = Counter(others).most_common(1)[0]
                            if cnt / len(others) >= 0.5 and any(canon(g) == top for g in gold):
                                cls = "E4_peers"
                        if cls is None:
                            cls = "CHOICE_user" if m_in else ("E1_conversation" if consolidate else "U_silent")
                base["class"] = cls
                out.append(base)
    return out


# ------------------------------------------------------------------ DeRef fcrb dev
def label_fcrb(consolidate=None):
    consolidate = CONSOLIDATE if consolidate is None else consolidate
    schemas = load_schemas()
    cases = [c for c in json.loads((ROOT / "benchmarks/data/deref/cases_fcrb.json").read_text(encoding="utf-8"))["cases"] if c["split"] == "dev"]
    out = []
    for c in cases:
        calls = c.get("calls") or [c["call"]]
        for a in c["args_meta"]:
            if not a["in_analysis"]:
                continue
            ci = a.get("call_index", 0)
            call = calls[ci] if ci < len(calls) else calls[0]
            sch = pick(schemas, call)
            props = (sch or {}).get("parameters", {}).get("properties", {})
            base = {"dataset": "fcrb", "item": f"{c['id']}|{a['name']}", "arg": a["name"], "value": a["value"], "request": c["premise"],
                    "tool": call["name"], "spec": props.get(a["name"]), "path": a["path"], "correct": a["label"] == "correct"}
            if base["correct"]:
                base["class"] = None
            else:
                bad = sch is not None and contract_bad(props.get(a["name"], {}), a["value"], a["name"] in props)
                numeric_unsupported = isinstance(a["value"], (int, float)) and not isinstance(a["value"], bool) and bool(re.search(r"\d", c["premise"]))
                if bad:
                    cls = "E2_contract"
                elif a["path"] in ("visible", "format", "history_only", "default"):
                    cls = "E1_conversation"                # 'default' wrong = the agent ignored a value the conversation states (dontcare/default used)
                elif numeric_unsupported:
                    cls = "E1_conversation"                # a number the conversation does not contain while it contains another number
                else:
                    cls = "E1_conversation" if consolidate else "U_silent"
                base["class"] = cls
            out.append(base)
    return out


# ------------------------------------------------------------------ tau-bench
def label_tau():
    cs = json.loads((ROOT / "benchmarks/data/taubench/cases.json").read_text(encoding="utf-8"))
    cs = cs["cases"] if isinstance(cs, dict) else cs
    out = []
    for i, c in enumerate(cs):
        if c["label"] != "suspect":
            continue
        flagged = str(c.get("flags")) not in ("[]", "", "None") and str(c.get("env_error")) == "True"
        out.append({"dataset": "taubench", "item": f"tau|{i}|{c['src']}|{c['task_id']}", "tool": c["tool"], "kwargs": c["kwargs"],
                    "diff_class": c["diff_class"], "env_response": c["env_response"], "context": c["context"],
                    "class": "E3_state" if flagged else "CHOICE_user", "correct": False})
    return out


def bfcl_call_status():
    """id 'test|model' -> 'strong' (at least one argument error that is not a weak label), 'weak_only', or 'correct'."""
    st = {}
    for r in label_bfcl():
        cid = r["test"] + "|" + r["model"]
        cur = st.get(cid, "correct")
        if not r["correct"]:
            if not str(r["class"]).startswith("WEAK_"):
                cur = "strong"
            elif cur != "strong":
                cur = "weak_only"
        st[cid] = cur
    return st


def summarise(rows, name):
    wrong = [r for r in rows if not r["correct"]]
    cnt = Counter(r["class"] for r in wrong)
    n = len(wrong)
    print(f"{name}: {n} wrong")
    for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
        print(f"   {k:18s} {v:5d}  {100 * v / n:5.1f}%")
    return {"n_wrong": n, "counts": dict(cnt)}


def text(x, n=1100):
    x = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return x if len(x) <= n else "[...] " + x[-n:]


def build_audit(bf, fc, tau, seed=7):
    rng = random.Random(seed)

    def take(rows, cls, k):
        pool = [r for r in rows if not r["correct"] and r["class"] == cls]
        rng.shuffle(pool)
        return pool[:k]
    sample = []
    for cls in ("E1_conversation", "E2_contract", "E4_peers", "CHOICE_user"):
        sample += take(bf, cls, 10)
    for cls, k in (("E1_conversation", 10), ("E2_contract", 10), ("U_silent", 10)):
        sample += take(fc, cls, k)
    ts = [r for r in tau if r["class"] == "E3_state"]; rng.shuffle(ts)
    tc = [r for r in tau if r["class"] == "CHOICE_user" and r["diff_class"] != "extra_call_tool_not_in_gold"]; rng.shuffle(tc)
    te = [r for r in tau if r["diff_class"] == "extra_call_tool_not_in_gold"]; rng.shuffle(te)
    sample += ts[:4] + tc[:7] + te[:4]
    cb = [r for r in bf if r["correct"]]; rng.shuffle(cb)
    cf = [r for r in fc if r["correct"]]; rng.shuffle(cf)
    sample += cb[:8] + cf[:7]
    rng.shuffle(sample)
    return sample


def relabel_audit(bf, fc, tau):
    """Re-label the SAME 100 audit items under the revised rules (the original key stays untouched) -> review/audit/audit_key_v2.csv."""
    cls = {r["item"]: (r["class"] or "CORRECT_CONTROL") for r in bf + fc + tau}
    src = ROOT / "review" / "audit" / "audit_key_DO_NOT_OPEN.csv"
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    for r in rows:
        r["our_class_v1"] = r["our_class"]
        r["our_class"] = cls.get(r["item"], "MISSING")
    with (ROOT / "review" / "audit" / "audit_key_v2.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("wrote audit_key_v2.csv;", Counter(r["our_class"] for r in rows).most_common())


def build_audit2(bf, fc, tau, exclude, seed=13):
    """Fresh validation sample (100 items) under the REVISED rules, disjoint from the first audit sample.  Mixes random draws (for population-valid
    label precision) with class-stratified draws (to validate the rules) and random 'correct' controls.  At most two BFCL items per test case."""
    rng = random.Random(seed)
    used, sample, per_test = set(exclude), [], Counter()

    def draw(pool, k, kind):
        pool = [r for r in pool if r["item"] not in used]
        rng.shuffle(pool)
        got = 0
        for r in pool:
            if got >= k:
                break
            if r["dataset"] == "bfcl" and per_test[r["test"]] >= 2:
                continue
            used.add(r["item"]); got += 1
            if r["dataset"] == "bfcl":
                per_test[r["test"]] += 1
            sample.append(dict(r, _draw=kind))
    bf_wrong = [r for r in bf if not r["correct"]]
    fc_wrong = [r for r in fc if not r["correct"]]
    draw(bf_wrong, 20, "random")
    for cls in ("E1_conversation", "E2_contract", "E4_peers", "CHOICE_user", "U_silent"):
        draw([r for r in bf_wrong if r["class"] == cls], 4, "stratified")
    draw(fc_wrong, 10, "random")
    for cls, k in (("E1_conversation", 7), ("E2_contract", 7), ("U_silent", 6)):
        draw([r for r in fc_wrong if r["class"] == cls], k, "stratified")
    draw([r for r in tau if r["class"] == "E3_state"], 5, "stratified")
    draw([r for r in tau if r["class"] == "CHOICE_user" and r["diff_class"] != "extra_call_tool_not_in_gold"], 3, "stratified")
    draw([r for r in tau if r["diff_class"] == "extra_call_tool_not_in_gold"], 2, "stratified")
    draw([r for r in bf if r["correct"]], 10, "control")
    draw([r for r in fc if r["correct"]], 10, "control")
    rng.shuffle(sample)
    return sample


def write_audit(sample, out, prefix):
    out.mkdir(exist_ok=True)
    blind, key = [], []
    for n, r in enumerate(sample, 1):
        aid = f"{prefix}{n:03d}"
        if r["dataset"] == "taubench":
            shown = {"conversation_or_context": text(r["context"]), "tool": r["tool"], "what_the_agent_did": text(r["kwargs"]),
                     "system_response": text(r["env_response"], 300), "definition_of_argument": "",
                     "benchmark_reference": "(agent run failed the task; this write call is not among the task's gold actions)"}
        else:
            shown = {"conversation_or_context": text(r["request"]), "tool": r["tool"], "what_the_agent_did": f"{r['arg']} = {json.dumps(r['value'], ensure_ascii=False)}",
                     "system_response": "", "definition_of_argument": text(r.get("spec") or "(not available)", 500),
                     "benchmark_reference": ("accepted values: " + json.dumps(r["gold"], ensure_ascii=False)) if r["dataset"] == "bfcl" else
                     ("benchmark label: " + ("correct" if r["correct"] else "wrong"))}
        if r["dataset"] == "bfcl":
            shown["benchmark_reference"] += "  (benchmark label: " + ("correct" if r["correct"] else "wrong") + ")"
        blind.append({"audit_id": aid, "source": r["dataset"], **shown,
                      "Q1_is_the_agents_value_actually_wrong (yes / no / acceptable alternative / cannot tell)": "",
                      "Q2_what_is_enough_to_decide (conversation / tool definition / system state / other models agreeing / only the user / cannot tell)": "", "notes": ""})
        key.append({"audit_id": aid, "item": r["item"], "dataset": r["dataset"], "our_class": r["class"] or "CORRECT_CONTROL", "draw": r["_draw"]})
    with (out / "audit_sample_blind.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(blind[0].keys())); w.writeheader(); w.writerows(blind)
    with (out / "audit_key_DO_NOT_OPEN.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(key[0].keys())); w.writeheader(); w.writerows(key)
    print("audit sample:", len(blind), "items ->", out, Counter((k["dataset"], k["draw"]) for k in key))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit2", action="store_true", help="build the fresh validation sample in review/audit2 (revised rules, disjoint from audit 1)")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--relabel-audit", action="store_true")
    ap.add_argument("--legacy-classes", action="store_true", help="reproduce the pre-Deviation-19 classes (U_silent and E4_peers kept); used for the audit samples")
    a = ap.parse_args()
    legacy = a.legacy_classes or a.audit or a.audit2 or a.relabel_audit
    bf, fc, tau = label_bfcl(not legacy), label_fcrb(not legacy), label_tau()
    if a.relabel_audit:
        relabel_audit(bf, fc, tau)
    if a.audit2:
        old = {r["item"] for r in csv.DictReader(open(ROOT / "review" / "audit" / "audit_key_DO_NOT_OPEN.csv", encoding="utf-8-sig"))}
        write_audit(build_audit2(bf, fc, tau, old), ROOT / "review" / "audit2", "B")
        return
    res = {"bfcl": summarise(bf, "BFCL (30 models, 200 cases)"), "fcrb_dev": summarise(fc, "DeRef fcrb dev"), "taubench": summarise(tau, "tau-bench suspect calls")}
    (ROOT / "benchmarks" / "decidability_dev.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    if a.audit:
        out = ROOT / "review" / "audit"
        out.mkdir(exist_ok=True)
        sample = build_audit(bf, fc, tau)
        blind, key = [], []
        for n, r in enumerate(sample, 1):
            aid = f"A{n:03d}"
            if r["dataset"] == "taubench":
                shown = {"conversation_or_context": text(r["context"]), "tool": r["tool"], "what_the_agent_did": text(r["kwargs"]),
                         "system_response": text(r["env_response"], 300), "definition_of_argument": "", "benchmark_reference": "(agent run failed the task; this write call is not among the task's gold actions)"}
            else:
                shown = {"conversation_or_context": text(r["request"]), "tool": r["tool"], "what_the_agent_did": f"{r['arg']} = {json.dumps(r['value'], ensure_ascii=False)}",
                         "system_response": "", "definition_of_argument": text(r.get("spec") or "(not available)", 500),
                         "benchmark_reference": ("accepted values: " + json.dumps(r["gold"], ensure_ascii=False)) if r["dataset"] == "bfcl" else
                         ("benchmark label: " + ("correct" if r["correct"] else "wrong"))}
            if r["dataset"] == "bfcl":
                shown["benchmark_reference"] += "  (benchmark label: " + ("correct" if r["correct"] else "wrong") + ")"
            blind.append({"audit_id": aid, "source": r["dataset"], **shown, "Q1_is_the_agents_value_actually_wrong (yes / no / acceptable alternative / cannot tell)": "",
                          "Q2_what_is_enough_to_decide (conversation / tool definition / system state / other models agreeing / only the user / cannot tell)": "", "notes": ""})
            key.append({"audit_id": aid, "item": r["item"], "dataset": r["dataset"], "our_class": r["class"] or "CORRECT_CONTROL"})
        with (out / "audit_sample_blind.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(blind[0].keys())); w.writeheader(); w.writerows(blind)
        with (out / "audit_key_DO_NOT_OPEN.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(key[0].keys())); w.writeheader(); w.writerows(key)
        print("audit sample:", len(blind), "items ->", out)


if __name__ == "__main__":
    main()
