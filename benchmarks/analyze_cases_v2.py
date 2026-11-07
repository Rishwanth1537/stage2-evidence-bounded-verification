import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def analyze_v2():
    v2_data = json.loads((ROOT / "benchmarks/data/mcpatlas/cases_v2.json").read_text(encoding="utf-8"))["cases"]
    n_total = len(v2_data)

    # 1. Inventory Report
    calls_with_earlier_outputs = 0
    step_indices = []
    output_lens = []

    for c in v2_data:
        step = c["step_index"]
        step_indices.append(step)
        outputs = c["earlier_tool_outputs"]
        if outputs and len(outputs) > 0:
            calls_with_earlier_outputs += 1
        total_len = sum(len(o) for o in outputs)
        output_lens.append(total_len)

    step_1_calls = sum(1 for s in step_indices if s == 1)
    step_dist = Counter(step_indices)
    max_output_len = max(output_lens)
    median_output_len = statistics.median(output_lens)

    print("=== INVENTORY REPORT (cases_v2.json) ===")
    print(f"Total calls: {n_total}")
    print(f"Calls with >= 1 earlier tool output: {calls_with_earlier_outputs} ({calls_with_earlier_outputs/n_total:.1%})")
    print(f"Calls that are step 1 (no earlier outputs): {step_1_calls} ({step_1_calls/n_total:.1%})")
    print(f"Distribution of step_index: {dict(sorted(step_dist.items()))}")
    print(f"Earlier output length per call (chars): max={max_output_len}, median={median_output_len:.1f}")

    # 2. MECHANICAL ORIGIN CHECK FOR TOP 30 PAIRS FROM PROMPT 5
    # Load Prompt 5 top 30 pairs from RESULT_VERIFICATION.md
    # We test on matching cases in the respective datasets!
    # For mcpatlas cases, we search c['user_prompt'] and c['earlier_tool_outputs'].
    
    # Pre-index mcpatlas by ID
    mcpatlas_by_id = {c["id"]: c for c in v2_data}

    # Load argground and deref_cfb cases via load_split
    sys.path.insert(0, str(ROOT))
    from benchmarks.splits import load_split
    from benchmarks.ablate_normalizers import _load_deref_schema_notes
    argground_data = load_split("argground", "dev")
    cfb_data = load_split("cfb", "dev")
    cfb_schemas = _load_deref_schema_notes("cfb")

    # The 30 pairs from Prompt 5:
    top_30_pairs = [
        ("mcpatlas", "base_id", "appIF9byLfQwdHqE2"),
        ("mcpatlas", "database", "video_game_store"),
        ("mcpatlas", "field_name", "Date"),
        ("mcpatlas", "interval", "1d"),
        ("mcpatlas", "table_name", "Sales Expenses"),
        ("mcpatlas", "path", "/data"),
        ("mcpatlas", "collection", "Purchase History"),
        ("mcpatlas", "languageId", "python"),
        ("mcpatlas", "symbol", "BTC"),
        ("mcpatlas", "command", "ls"),
        ("mcpatlas", "collection", "Customers"),
        ("mcpatlas", "path", "/data/Top Movies.csv"),
        ("mcpatlas", "path", "/data/repos"),
        ("argground", "symbol", "MSFT"),
        ("mcpatlas", "database_id", "21b97551-844e-8090-b48d-d33c1c2be7f8"),
        ("mcpatlas", "table_name", "Turnover Retention"),
        ("mcpatlas", "database_id", "21b97551-844e-8068-b387-fe7a56b04348"),
        ("mcpatlas", "collection", "Delivery Logistics"),
        ("mcpatlas", "max_records", "10"),
        ("mcpatlas", "path", "/data/Crime_records.csv"),
        ("mcpatlas", "command", "ls /data"),
        ("mcpatlas", "source", "en-EN"),
        ("deref_cfb", "sortBy", "attr_book_score"),
        ("mcpatlas", "collection", "Social Media"),
        ("mcpatlas", "channel_id", "C093FF10B5J"),
        ("mcpatlas", "target", "es-ES"),
        ("mcpatlas", "table_name", "Inventory Levels Turnover"),
        ("mcpatlas", "path", "/data/CoinbaseTradeHistory.csv"),
        ("deref_cfb", "pick_up_time", "08:00"),
        ("mcpatlas", "repo_path", "/data/repos/snake-game"),
    ]

    print("\n=== MECHANICAL ORIGIN CHECK: TOP 30 PAIRS (P5) ===")
    results_table = []
    tot_user = 0
    tot_tool_out = 0
    tot_schema = 0
    tot_nowhere = 0
    tot_matched = 0

    for rank, (ds, arg, val) in enumerate(top_30_pairs, 1):
        in_user = 0
        in_out = 0
        in_sch = 0
        nowhere = 0
        matched = 0

        if ds == "mcpatlas":
            # Search across all mcpatlas calls where this arg=val was passed
            for c in v2_data:
                args = c["call"].get("arguments", {})
                if str(args.get(arg)) == val:
                    matched += 1
                    found_user = val in c["user_prompt"]
                    found_out = any(val in out for out in c["earlier_tool_outputs"])
                    found_sch = False  # mcpatlas has no schema in dataset
                    if found_user:
                        in_user += 1
                    elif found_out:
                        in_out += 1
                    elif found_sch:
                        in_sch += 1
                    else:
                        nowhere += 1
        elif ds == "argground":
            for c in argground_data:
                args = c["call"].get("arguments", {})
                if str(args.get(arg)) == val:
                    matched += 1
                    found_user = val in c.get("premise", "")
                    found_out = False
                    found_sch = False
                    if found_user:
                        in_user += 1
                    elif found_out:
                        in_out += 1
                    elif found_sch:
                        in_sch += 1
                    else:
                        nowhere += 1
        elif ds == "deref_cfb":
            for c in cfb_data:
                call = c.get("call") or c.get("calls", [{}])[0]
                args = call.get("arguments", {})
                if str(args.get(arg)) == val:
                    matched += 1
                    found_user = val in c.get("dialogue", "")
                    found_out = False
                    # Check schema
                    cid = c.get("id", "")
                    schema = cfb_schemas.get(cid)
                    if schema:
                        props = schema.get("properties", {})
                        if arg in props:
                            arg_prop = props[arg]
                            enum_vals = [str(x) for x in arg_prop.get("enum", [])]
                            default_val = str(arg_prop.get("default", ""))
                            if val in enum_vals or val == default_val or val in str(arg_prop):
                                found_sch = True
                    if found_user:
                        in_user += 1
                    elif found_out:
                        in_out += 1
                    elif found_sch:
                        in_sch += 1
                    else:
                        nowhere += 1

        tot_user += in_user
        tot_tool_out += in_out
        tot_schema += in_sch
        tot_nowhere += nowhere
        tot_matched += matched

        results_table.append({
            "rank": rank,
            "dataset": ds,
            "arg": arg,
            "val": val,
            "matched": matched,
            "in_user": in_user,
            "in_tool_output": in_out,
            "in_schema": in_sch,
            "nowhere": nowhere,
        })
        print(f"Rank {rank:2d} [{ds:<9}] {arg:<12} = {val:<38} | Matched: {matched:3d} | User: {in_user:3d} | ToolOut: {in_out:3d} | Schema: {in_sch:3d} | Nowhere: {nowhere:3d}")

    print("\n=== TOTALS ACROSS TOP 30 PAIRS ===")
    print(f"Total matched calls: {tot_matched}")
    print(f"Appears in user prompt: {tot_user} ({tot_user/tot_matched:.1%})")
    print(f"Appears in earlier tool output: {tot_tool_out} ({tot_tool_out/tot_matched:.1%})")
    print(f"Appears in tool schema: {tot_schema} ({tot_schema/tot_matched:.1%})")
    print(f"Appears nowhere: {tot_nowhere} ({tot_nowhere/tot_matched:.1%})")

    # Save to JSON for report generation
    (ROOT / "review/mcpatlas_origin_check.json").write_text(json.dumps({
        "inventory": {
            "n_total": n_total,
            "calls_with_earlier_outputs": calls_with_earlier_outputs,
            "step_1_calls": step_1_calls,
            "step_dist": dict(sorted(step_dist.items())),
            "max_output_len": max_output_len,
            "median_output_len": median_output_len,
        },
        "results_table": results_table,
        "totals": {
            "matched": tot_matched,
            "in_user": tot_user,
            "in_tool_output": tot_tool_out,
            "in_schema": tot_schema,
            "nowhere": tot_nowhere,
        }
    }, indent=2), encoding="utf-8")

if __name__ == "__main__":
    analyze_v2()
