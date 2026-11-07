"""
Combine several AI annotators' answers on the blind audit sample into one consensus, and measure how much they agree.

  python benchmarks/aggregate_ai_audit.py --dir <folder with answers_<model>_<run>.json> --csv review/audit2/audit_sample_blind.csv \
      --out-json review/audit2/ai_consensus_answers.json --out-csv review/audit2/audit_sample_ai_consensus.csv

Consensus Q1 = plurality over annotators; a tie between the top answers is recorded as "cannot tell".  Consensus Q2 = plurality of Q2 among
the annotators who answered Q1 = yes (only when the consensus Q1 is yes).  Also reports unanimity, test-retest agreement per model (run 1 vs
run 2) and agreement between models.  These are AI labels: they never replace the human audit.
"""
import argparse
import csv
import glob
import json
import os
from collections import Counter
from itertools import combinations
from pathlib import Path

Q1_OK = {"yes", "no", "acceptable alternative", "cannot tell"}
Q2_OK = {"conversation", "tool definition", "system state", "other models agreeing", "only the user", "cannot tell", ""}


def plurality(vals, tie="cannot tell"):
    c = Counter(vals).most_common()
    if not c:
        return tie
    if len(c) > 1 and c[0][1] == c[1][1]:
        return tie
    return c[0][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-csv", required=True)
    a = ap.parse_args()
    ann = {}
    for f in sorted(glob.glob(os.path.join(a.dir, "answers_*_[0-9].json"))):
        name = Path(f).stem.replace("answers_", "")
        rows = json.loads(Path(f).read_text(encoding="utf-8"))
        d = {}
        for r in rows:
            q1 = r.get("q1", "").strip().lower(); q2 = (r.get("q2") or "").strip().lower()
            assert q1 in Q1_OK, (name, r)
            if q1 != "yes":
                q2 = ""
            assert q2 in Q2_OK, (name, r)
            d[r["audit_id"]] = (q1, q2, r.get("notes", ""))
        ann[name] = d
    ids = sorted(next(iter(ann.values())))
    assert all(sorted(d) == ids for d in ann.values()), "annotators cover different items"
    print("annotators:", list(ann), "items:", len(ids))
    cons = {}
    for i in ids:
        q1s = [d[i][0] for d in ann.values()]
        q1 = plurality(q1s)
        q2s = [d[i][1] for d in ann.values() if d[i][0] == "yes"]
        q2 = plurality(q2s) if q1 == "yes" else ""
        notes = next((d[i][2] for d in ann.values() if d[i][0] == q1 and d[i][2]), "")
        votes = Counter(q1s)
        cons[i] = {"audit_id": i, "q1": q1, "q2": q2, "notes": f"AI consensus {dict(votes)}; {notes}"[:400], "votes_q1": dict(votes), "votes_q2": dict(Counter(q2s))}
    stats = {"n_annotators": len(ann), "unanimous_q1_items": sum(len(set(d[i][0] for d in ann.values())) == 1 for i in ids),
             "majority_ge_2_3_items": sum(max(Counter(d[i][0] for d in ann.values()).values()) >= 2 * len(ann) / 3 for i in ids),
             "consensus_q1_counts": dict(Counter(c["q1"] for c in cons.values())), "pairwise_q1_agreement": {}, "test_retest_q1": {}}
    for x, y in combinations(ann, 2):
        stats["pairwise_q1_agreement"][f"{x} vs {y}"] = round(sum(ann[x][i][0] == ann[y][i][0] for i in ids) / len(ids), 3)
    for m in sorted({n.rsplit("_", 1)[0] for n in ann}):
        r1, r2 = f"{m}_1", f"{m}_2"
        if r1 in ann and r2 in ann:
            stats["test_retest_q1"][m] = round(sum(ann[r1][i][0] == ann[r2][i][0] for i in ids) / len(ids), 3)
    yes_ids = [i for i in ids if cons[i]["q1"] == "yes"]
    stats["q2_unanimous_among_consensus_yes"] = sum(len(set(v for v in [d[i][1] for d in ann.values() if d[i][0] == "yes"])) == 1 for i in yes_ids)
    stats["n_consensus_yes"] = len(yes_ids)
    Path(a.out_json).write_text(json.dumps([{k: c[k] for k in ("audit_id", "q1", "q2", "notes")} for c in cons.values()], indent=1), encoding="utf-8")
    Path(a.out_json.replace(".json", "_stats.json")).write_text(json.dumps({"stats": stats, "per_item": cons}, indent=1), encoding="utf-8")
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
    q1k = [k for k in rows[0] if k.startswith("Q1")][0]; q2k = [k for k in rows[0] if k.startswith("Q2")][0]
    for r in rows:
        c = cons[r["audit_id"]]
        r[q1k], r[q2k], r["notes"] = c["q1"], c["q2"], c["notes"]
    with open(a.out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
