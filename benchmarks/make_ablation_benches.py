"""
Build the two benchmark files for the information-ablation and consensus-control experiments (both git-ignored, DEV data only).

  schema : cases_fcrb_schema.json  - the fcrb cases in the SAME order, with the tool definition appended to the premise for calls whose
           function has a schema in the BFCL data (cases without a schema are unchanged), so a seeded sample picks the same ids as
           the no-schema runs.
  bfcl   : cases_bfcl_consensus.json - calls from 10 models (one per family/size band) on the 56 BFCL cases; label True = every
           argument matches gold; premise = the user request; used to compare a judge with cross-model consensus at matched false-block rate.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from contract_tier import load_schemas, pick  # noqa: E402

MODELS = ["claude-4.5-sonnet-thinking-off", "claude-4-opus-thinking-off", "gpt-5", "gpt-4.1-mini", "gpt-4o-mini", "gpt-oss-20b",
          "gemini-2.5-flash-thinking-off", "DeepSeek-V3-0324", "Qwen3-235B-A22B-Instruct-2507-FP8", "Kimi-K2-Instruct-0905"]

MODELS200 = ["claude-4.5-sonnet-thinking-off", "gpt-4.1-mini", "gemini-2.5-flash-thinking-off", "DeepSeek-V3-0324", "Qwen3-235B-A22B-Instruct-2507-FP8"]


def schema_bench():
    schemas = load_schemas()
    src = json.loads((ROOT / "benchmarks/data/deref/cases_fcrb.json").read_text(encoding="utf-8"))
    n = 0
    for c in src["cases"]:
        calls = c.get("calls") or [c["call"]]
        defs = []
        for call in calls:
            fn = pick(schemas, call)
            if fn and fn not in defs:
                defs.append(fn)
        if defs:
            c["premise"] = c["premise"] + "\n\nTool definition:\n" + "\n".join(json.dumps(d, ensure_ascii=False) for d in defs)
            n += 1
    out = ROOT / "benchmarks/data/deref/cases_fcrb_schema.json"
    out.write_text(json.dumps(src), encoding="utf-8")
    print("schema bench:", n, "of", len(src["cases"]), "cases carry a tool definition ->", out.name)


def schema_note_bench():
    """Same as schema_bench but the rule sentence sits INSIDE the case text, so frozen API prompts (and their hash) stay unchanged."""
    schemas = load_schemas()
    src = json.loads((ROOT / "benchmarks/data/deref/cases_fcrb.json").read_text(encoding="utf-8"))
    head = ("\n\nTool definition (a value that violates it, meaning wrong type, not one of the allowed enum values, or not in the format the "
            "description asks for, is NOT supported):\n")
    n = 0
    for c in src["cases"]:
        calls = c.get("calls") or [c["call"]]
        defs = []
        for call in calls:
            fn = pick(schemas, call)
            if fn and fn not in defs:
                defs.append(fn)
        if defs:
            c["premise"] = c["premise"] + head + "\n".join(json.dumps(d, ensure_ascii=False) for d in defs)
            n += 1
    out = ROOT / "benchmarks/data/deref/cases_fcrb_schema_note.json"
    out.write_text(json.dumps(src), encoding="utf-8")
    print("schema-note bench:", n, "of", len(src["cases"]), "->", out.name)


def bfcl_bench(models=None, tag=""):
    models = models or MODELS
    d = json.loads((ROOT / "benchmarks/data/bfcl/consensus_cases.json").read_text(encoding="utf-8"))
    cases = []
    for r in d["records"]:
        if r["model"] not in models:
            continue
        calls = [{"name": c["function"], "arguments": c["arguments"]} for c in r["calls"]]
        if not calls:
            continue
        ok = all(a["label"] == "correct" for c in r["calls"] for a in c["arg_labels"].values())
        cases.append({"id": f"{r['test_id']}|{r['model']}", "dataset": "bfcl", "query_id": r["test_id"], "split": "dev",
                      "premise": "User request: " + r["request"], "calls": calls, "call": calls[0], "label": ok,
                      "model": r["model"]})
    out = ROOT / ("benchmarks/data/bfcl/cases_bfcl_consensus%s.json" % tag)
    out.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    print("bfcl bench:", len(cases), "calls, correct", sum(c["label"] for c in cases), "wrong", sum(not c["label"] for c in cases), "->", out.name)
    # same calls, tool definitions (from the record itself) appended to the premise
    by_id = {f"{r['test_id']}|{r['model']}": r for r in d["records"]}
    for c in cases:
        allf = by_id[c["id"]]["function_schemas"]
        called = {x["name"] for x in c["calls"]}
        defs = [f for f in allf if f["name"] in called] or allf          # only the function(s) the call uses, like the fcrb condition
        c["premise"] = c["premise"] + "\n\nTool definition:\n" + "\n".join(json.dumps(x, ensure_ascii=False) for x in defs)
    out2 = ROOT / ("benchmarks/data/bfcl/cases_bfcl_consensus%s_schema.json" % tag)
    out2.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    print("bfcl schema bench ->", out2.name)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "note":
        schema_note_bench()
    elif len(sys.argv) > 1 and sys.argv[1] == "bfcl200":
        bfcl_bench(MODELS200, "_200")
    else:
        schema_bench()
        bfcl_bench()
