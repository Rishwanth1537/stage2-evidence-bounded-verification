"""
Merge the round-2 AI annotations (sharpened rubric, disputed items only) into the round-1 consensus.

  python -I benchmarks/merge_audit_round2.py --r2-dir review/audit2/ai_annotator_answers_r2

Settled items (>= 4 of 6 round-1 votes) keep the round-1 consensus; disputed items take the plurality of the six round-2 answers (a tie is
"cannot tell").  Writes review/audit2/ai_consensus_final_answers.json (for compare_audit.py), ai_consensus_final_stats.json and the filled
review/audit2/audit_sample_ai_consensus_final.csv.  AI labels only; the human audit remains the gate.
"""
import argparse
import csv
import glob
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A2 = ROOT / "review" / "audit2"


def plurality(vals):
    c = Counter(vals).most_common()
    if not c or (len(c) > 1 and c[0][1] == c[1][1]):
        return "cannot tell"
    return c[0][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r2-dir", default=str(A2 / "ai_annotator_answers_r2"))
    a = ap.parse_args()
    r1 = json.loads((A2 / "ai_consensus_answers_stats.json").read_text(encoding="utf-8"))["per_item"]
    ids2 = json.loads(Path(a.r2_dir, "round2_ids.json").read_text(encoding="utf-8"))
    r2 = {}
    for f in sorted(glob.glob(os.path.join(a.r2_dir, "r2_*_[0-9].json"))):
        r2[Path(f).stem] = {r["audit_id"]: (r["q1"].strip().lower(), (r.get("q2") or "").strip().lower(), r.get("notes", "")) for r in json.loads(Path(f).read_text(encoding="utf-8"))}
        assert sorted(r2[Path(f).stem]) == sorted(ids2), f
    final, detail = {}, {}
    for i, v in r1.items():
        if i in ids2:
            q1s = [d[i][0] for d in r2.values()]
            q1 = plurality(q1s)
            q2s = [d[i][1] for d in r2.values() if d[i][0] == "yes"]
            q2 = plurality(q2s) if q1 == "yes" else ""
            note = next((d[i][2] for d in r2.values() if d[i][0] == q1 and d[i][2]), "")
            final[i] = {"audit_id": i, "q1": q1, "q2": q2, "notes": f"round2 {dict(Counter(q1s))}; round1 {v['votes_q1']}; {note}"[:400]}
            detail[i] = {"round1_votes": v["votes_q1"], "round2_votes": dict(Counter(q1s)), "round2_q2_votes": dict(Counter(q2s)), "round1_consensus": v["q1"], "final": q1}
        else:
            final[i] = {"audit_id": i, "q1": v["q1"], "q2": v["q2"], "notes": v["notes"]}
    stats = {"disputed_items": len(ids2), "round2_runs": list(r2), "final_q1_counts": dict(Counter(x["q1"] for x in final.values())),
             "round2_unanimous": sum(len(set(d[i][0] for d in r2.values())) == 1 for i in ids2),
             "round2_ge4_of_6": sum(max(Counter(d[i][0] for d in r2.values()).values()) >= 4 for i in ids2),
             "round2_pairwise_agreement_mean": round(sum(sum(x[i][0] == y[i][0] for i in ids2) / len(ids2) for xi, x in enumerate(r2.values()) for yi, y in enumerate(r2.values()) if xi < yi) / (len(r2) * (len(r2) - 1) / 2), 3),
             "changed_vs_round1": sum(detail[i]["final"] != detail[i]["round1_consensus"] for i in detail)}
    (A2 / "ai_consensus_final_answers.json").write_text(json.dumps(list(final.values()), indent=1), encoding="utf-8")
    (A2 / "ai_consensus_final_stats.json").write_text(json.dumps({"stats": stats, "disputed_detail": detail}, indent=1), encoding="utf-8")
    rows = list(csv.DictReader(open(A2 / "audit_sample_blind.csv", encoding="utf-8-sig")))
    q1k = [k for k in rows[0] if k.startswith("Q1")][0]; q2k = [k for k in rows[0] if k.startswith("Q2")][0]
    for r in rows:
        c = final[r["audit_id"]]
        r[q1k], r[q2k], r["notes"] = c["q1"], c["q2"], c["notes"]
    with open(A2 / "audit_sample_ai_consensus_final.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(json.dumps(stats, indent=1))
    for i in sorted(detail):
        print(i, detail[i])


if __name__ == "__main__":
    main()
