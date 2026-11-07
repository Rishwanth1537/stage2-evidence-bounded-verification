"""Build benchmarks/data/mcpatlas/cases.json and cases_v2.json from the MCP-Atlas parquet (gold trajectories).

Reads parquet/JSON only; never executes anything from the data.
Usage: python -I -X utf8 load_mcpatlas.py <MCP-Atlas.parquet> [out_dir]

Every tool call in the reference TRAJECTORY becomes one case with label True
(gold call is correct). No incorrect calls exist in this dataset.

v1 (cases.json) stores premise, call, and basic metadata.
v2 (cases_v2.json) additionally stores:
  - task_id (cluster_id)
  - step_index within trajectory (1-based)
  - user_prompt
  - tool_schema (None if not present)
  - earlier_tool_outputs (list of output texts from prior turns in the trajectory)
"""
import json
import sys
from pathlib import Path

import pandas as pd


def build(parquet_path):
    df = pd.read_parquet(parquet_path)
    cases = []
    for _, row in df.iterrows():
        traj = json.loads(row["TRAJECTORY"])
        k = 0
        for msg in traj:
            if msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls") or []:
                fn = tc["function"]
                args = json.loads(fn["arguments"]) if fn.get("arguments") else {}
                cases.append({
                    "id": f"mcpatlas-{row['TASK']}-{k}",
                    "source": "mcpatlas",
                    "split": "dev",
                    "premise": row["PROMPT"],
                    "call": {"name": fn["name"], "arguments": args},
                    "label": True,
                })
                k += 1
    return cases


def build_v2(parquet_path, max_output_chars=None):
    """Build cases_v2 preserving all earlier tool outputs in the trajectory."""
    df = pd.read_parquet(parquet_path)
    cases = []
    truncated_outputs_count = 0
    for _, row in df.iterrows():
        traj = json.loads(row["TRAJECTORY"])
        task_id = f"mcpatlas-{row['TASK']}"
        prompt = row["PROMPT"]
        earlier_outputs = []
        k = 0
        for msg in traj:
            role = msg.get("role")
            if role == "tool":
                parts = []
                for item in msg.get("content", []):
                    if isinstance(item, dict) and "text" in item:
                        parts.append(item["text"])
                    elif isinstance(item, str):
                        parts.append(item)
                out_text = "\n".join(parts)
                if max_output_chars is not None and len(out_text) > max_output_chars:
                    out_text = out_text[:max_output_chars]
                    truncated_outputs_count += 1
                earlier_outputs.append(out_text)
            elif role == "assistant":
                for tc in msg.get("tool_calls") or []:
                    fn = tc["function"]
                    args = json.loads(fn["arguments"]) if fn.get("arguments") else {}
                    cases.append({
                        "id": f"mcpatlas-{row['TASK']}-{k}",
                        "task_id": task_id,
                        "cluster_id": task_id,
                        "step_index": k + 1,
                        "source": "mcpatlas",
                        "split": "dev",
                        "premise": prompt,
                        "user_prompt": prompt,
                        "call": {"name": fn["name"], "arguments": args},
                        "label": True,
                        "tool_schema": None,
                        "earlier_tool_outputs": list(earlier_outputs),
                    })
                    k += 1
    if truncated_outputs_count > 0:
        print(f"Truncated {truncated_outputs_count} tool outputs exceeding {max_output_chars} chars.")
    else:
        print("No truncation applied; 100% of tool output text preserved.")
    return cases


def main():
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "data" / "mcpatlas"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Old format (cases.json)
    cases_v1 = build(src)
    (out_dir / "cases.json").write_text(
        json.dumps({"cases": cases_v1}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(cases_v1)} cases to {out_dir / 'cases.json'}")

    # 2. New format (cases_v2.json)
    cases_v2 = build_v2(src, max_output_chars=None)
    (out_dir / "cases_v2.json").write_text(
        json.dumps({"cases": cases_v2}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(cases_v2)} cases to {out_dir / 'cases_v2.json'}")


if __name__ == "__main__":
    main()

