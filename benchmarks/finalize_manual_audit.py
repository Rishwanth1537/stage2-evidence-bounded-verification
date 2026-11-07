"""
Turn review/audit2/claude_manual_labels.json (one Claude session's own hand labels for the 98 blind items; NOT a human audit) into the
answers file for compare_audit.py and a filled copy of the blind CSV, and report agreement with the six-annotator AI consensus.

  python -I benchmarks/finalize_manual_audit.py
"""
import csv
import json
from collections import Counter
from pathlib import Path

A2 = Path(__file__).resolve().parents[1] / "review" / "audit2"


def main():
    lab = {a: (q1, q2, n) for a, q1, q2, n in json.loads((A2 / "claude_manual_labels.json").read_text(encoding="utf-8"))}
    assert len(lab) == 98
    Path(A2 / "claude_manual_answers.json").write_text(json.dumps([{"audit_id": a, "q1": q1, "q2": q2, "notes": n} for a, (q1, q2, n) in lab.items()], indent=1), encoding="utf-8")
    rows = list(csv.DictReader(open(A2 / "audit_sample_blind.csv", encoding="utf-8-sig")))
    q1k = [k for k in rows[0] if k.startswith("Q1")][0]; q2k = [k for k in rows[0] if k.startswith("Q2")][0]
    for r in rows:
        r[q1k], r[q2k], r["notes"] = lab[r["audit_id"]][0], lab[r["audit_id"]][1], "Claude manual label (not human): " + lab[r["audit_id"]][2]
    with open(A2 / "audit_sample_claude_manual.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    cons = {r["audit_id"]: r for r in json.loads((A2 / "ai_consensus_final_answers.json").read_text(encoding="utf-8"))}
    same = sum(lab[a][0] == cons[a]["q1"] for a in lab)
    yes_both = [a for a in lab if lab[a][0] == "yes" and cons[a]["q1"] == "yes"]
    q2same = sum(lab[a][1] == cons[a]["q2"] for a in yes_both)
    print("manual counts:", dict(Counter(v[0] for v in lab.values())))
    print("Q1 agreement with AI final consensus: %d/98" % same)
    print("Q2 agreement where both say yes: %d/%d" % (q2same, len(yes_both)))
    diff = [(a, lab[a][0], cons[a]["q1"]) for a in sorted(lab) if lab[a][0] != cons[a]["q1"]]
    print("differences (id, manual, AI final):")
    for d in diff:
        print("  ", d)


if __name__ == "__main__":
    main()
