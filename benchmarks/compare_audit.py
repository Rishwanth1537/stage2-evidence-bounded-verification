"""
Compare annotator answers with our decidability labels.  Works for the human audit (a CSV with the Q1/Q2 columns filled in) or for the Claude
pre-audit (JSON answer files).  Reports: label precision per source (share of benchmark-"wrong" items the annotator also calls wrong), the
miss rate on benchmark-"correct" controls, and the confusion matrix between the annotator's Q2 answer and our class.

  python benchmarks/compare_audit.py --json-glob "<dir>/answers_*_*.json"       (pre-audit)
  python benchmarks/compare_audit.py --csv review/audit/audit_sample_blind.csv  (human audit, after the user filled it in)
"""
import argparse
import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = {"conversation": "E1_conversation", "tool definition": "E2_contract", "system state": "E3_state",
       "other models agreeing": "E4_peers", "only the user": "CHOICE_user", "cannot tell": "cannot tell", "": "(none)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-glob", default=None)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--key", default=str(ROOT / "review" / "audit" / "audit_key_DO_NOT_OPEN.csv"))
    ap.add_argument("--lo", default="A001", help="first audit id included")
    ap.add_argument("--hi", default="A100", help="last audit id included")
    a = ap.parse_args()
    ans = {}
    if a.json_glob:
        for f in sorted(glob.glob(a.json_glob)):
            for r in json.loads(Path(f).read_text(encoding="utf-8")):
                ans[r["audit_id"]] = (r.get("q1", "").strip().lower(), r.get("q2", "").strip().lower())
    else:
        for r in csv.DictReader(open(a.csv, encoding="utf-8-sig")):
            q1 = [v for k, v in r.items() if k.startswith("Q1")][0]; q2 = [v for k, v in r.items() if k.startswith("Q2")][0]
            ans[r["audit_id"]] = (q1.strip().lower(), q2.strip().lower())
    key = {r["audit_id"]: r for r in csv.DictReader(open(a.key, encoding="utf-8-sig"))}
    # label precision per dataset on benchmark-wrong items
    ans = {k: v for k, v in ans.items() if a.lo <= k <= a.hi}
    prec = defaultdict(Counter)
    weak = defaultdict(Counter)
    ctrl = defaultdict(Counter)
    conf = defaultdict(Counter)
    rand_all, rand_strong = defaultdict(Counter), defaultdict(Counter)
    for aid, (q1, q2) in ans.items():
        k = key[aid]
        ds, cls = k["dataset"], k["our_class"]
        if cls.startswith("WEAK_"):
            weak[cls][q1] += 1
        if cls == "CORRECT_CONTROL":
            ctrl[ds][q1] += 1
        else:
            prec[ds][q1] += 1
            if k.get("draw") == "random":                      # random draws give population-valid label precision (audit2 only)
                rand_all[ds][q1] += 1
                if not cls.startswith("WEAK_"):
                    rand_strong[ds][q1] += 1
            if q1 == "yes" and not cls.startswith("WEAK_"):
                conf[cls][MAP.get(q2, q2)] += 1
    print("Q1 on benchmark-WRONG items (label precision = share 'yes'):")
    for ds, c in prec.items():
        n = sum(c.values())
        print(f"  {ds:9s} n={n:3d}  " + "  ".join(f"{k}={v}" for k, v in c.most_common()) + f"   precision={c['yes'] / n:.2f}")
    if rand_all:
        import math

        def wil(k, n, z=1.96):
            p = k / n
            c = (p + z * z / (2 * n)) / (1 + z * z / n)
            h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
            return c - h, c + h
        print("RANDOM-draw items only (population label precision, Wilson 95%): all benchmark-wrong / after removing WEAK-tier items")
        for ds in rand_all:
            na, ya = sum(rand_all[ds].values()), rand_all[ds]["yes"]
            ns, ys = sum(rand_strong[ds].values()), rand_strong[ds]["yes"]
            la, ha = wil(ya, na)
            ls, hs = wil(ys, ns) if ns else (float("nan"), float("nan"))
            print(f"  {ds:9s} all: {ya}/{na} = {ya / na:.2f} [{la:.2f},{ha:.2f}]   strong: {ys}/{ns}" + (f" = {ys / ns:.2f} [{ls:.2f},{hs:.2f}]" if ns else ""))
    if weak:
        print("Items our rules call WEAK labels (annotator 'yes' = rule too aggressive):")
        for cls, c in weak.items():
            n = sum(c.values())
            print(f"  {cls:28s} n={n:3d}  " + "  ".join(f"{k}={v}" for k, v in c.most_common()) + f"   annotator-says-wrong={c['yes'] / n:.2f}")
    print("Q1 on benchmark-CORRECT controls (a 'yes' here is a missed error):")
    for ds, c in ctrl.items():
        n = sum(c.values())
        print(f"  {ds:9s} n={n:3d}  " + "  ".join(f"{k}={v}" for k, v in c.most_common()) + f"   missed-error rate={c['yes'] / n:.2f}")
    print("Our class (rows) vs annotator Q2 (columns), items with Q1 = yes:")
    cols = sorted({c for r in conf.values() for c in r})
    print("  %-18s" % "our class" + "".join("%-18s" % c[:17] for c in cols))
    for cls, r in sorted(conf.items()):
        print("  %-18s" % cls + "".join("%-18d" % r.get(c, 0) for c in cols) + "  total=%d" % sum(r.values()))
    agree = sum(r.get(cls, 0) for cls, r in conf.items())
    tot = sum(sum(r.values()) for r in conf.values())
    print(f"exact class agreement among Q1=yes items: {agree}/{tot}")


if __name__ == "__main__":
    main()
