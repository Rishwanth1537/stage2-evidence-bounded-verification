"""
Compare two sets of audit answers item by item (for example Claude's labels and another model's labels).

  python -I benchmarks/compare_two_audits.py review/audit2/claude_manual_answers.json other_model_answers.json

Each file is a JSON list of {"audit_id", "q1", "q2", "notes"}.  Prints Q1 agreement, Cohen's kappa on Q1, Q2 agreement where both say yes,
a confusion table, and the list of disagreements (id, A, B, B's note) so each can be decided one by one.
"""
import json
import sys
from collections import Counter
from pathlib import Path


def load(p):
    return {r["audit_id"]: (r["q1"].strip().lower(), (r.get("q2") or "").strip().lower(), r.get("notes", "")) for r in json.loads(Path(p).read_text(encoding="utf-8"))}


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    ids = sorted(set(a) & set(b))
    print("items compared:", len(ids), "(missing in B: %d)" % len(set(a) - set(b)))
    agree = sum(a[i][0] == b[i][0] for i in ids)
    pa = Counter(a[i][0] for i in ids); pb = Counter(b[i][0] for i in ids)
    pe = sum(pa[k] * pb[k] for k in pa) / (len(ids) ** 2)
    kappa = (agree / len(ids) - pe) / (1 - pe) if pe < 1 else float("nan")
    print("Q1 agreement: %d/%d = %.1f%%   Cohen kappa %.2f" % (agree, len(ids), 100 * agree / len(ids), kappa))
    both = [i for i in ids if a[i][0] == "yes" and b[i][0] == "yes"]
    print("Q2 agreement where both say yes: %d/%d" % (sum(a[i][1] == b[i][1] for i in both), len(both)))
    cats = ["yes", "no", "acceptable alternative", "cannot tell"]
    print("\nrows = A, columns = B")
    print("%-24s" % "" + "".join("%-24s" % c for c in cats))
    for ca in cats:
        print("%-24s" % ca + "".join("%-24d" % sum(a[i][0] == ca and b[i][0] == cb for i in ids) for cb in cats))
    print("\nDisagreements (id | A | B | B's note):")
    for i in ids:
        if a[i][0] != b[i][0]:
            print(" %s | %s | %s | %s" % (i, a[i][0], b[i][0], b[i][2][:140]))


if __name__ == "__main__":
    main()
