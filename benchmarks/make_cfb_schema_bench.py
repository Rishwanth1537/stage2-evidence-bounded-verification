"""
Build cases_cfb_schema_note.json: the cfb cases in the SAME order as cases_cfb.json, with the tool definition (name, description, parameters,
which for cfb also says where an identifier comes from) appended to the premise, plus the rule sentence inside the case text so the frozen
judge prompt (hash 9b59ae0a3fa5384a) is unchanged.  Same construction as make_ablation_benches.schema_note_bench for fcrb.  The tool
definitions come from the `functions` field of the raw DeRef cfb.jsonl (Apache-2.0).  The definition is appended at the END so that
--max-context-chars (which keeps the most recent characters) never cuts it.

  python -I benchmarks/make_cfb_schema_bench.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEAD = ("\n\nTool definition (a value that violates it, meaning wrong type, not one of the allowed enum values, or not in the format the "
        "description asks for, is NOT supported):\n")


def main():
    funcs = {}
    for ln in open(ROOT / "benchmarks/data/deref/cfb.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        funcs[r["item_id"]] = r["functions"]
    src = json.loads((ROOT / "benchmarks/data/deref/cases_cfb.json").read_text(encoding="utf-8"))
    n = 0
    for c in src["cases"]:
        fs = funcs.get(c["id"].split(":", 1)[1])
        calls = c.get("calls") or [c["call"]]
        if isinstance(calls, str):
            import ast
            calls = ast.literal_eval(calls)
        defs = []
        for call in calls:
            call = call if isinstance(call, dict) else ast.literal_eval(call)
            d = (fs or {}).get(call.get("name"))
            if d and d not in defs:
                defs.append(d)
        if defs:
            c["premise"] = c["premise"] + HEAD + "\n".join(json.dumps(d, ensure_ascii=False) for d in defs)
            n += 1
    out = ROOT / "benchmarks/data/deref/cases_cfb_schema_note.json"
    out.write_text(json.dumps(src), encoding="utf-8")
    print("cfb schema-note bench:", n, "of", len(src["cases"]), "cases carry a tool definition ->", out.name)


if __name__ == "__main__":
    main()
