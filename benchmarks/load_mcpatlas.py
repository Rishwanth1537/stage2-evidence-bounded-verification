"""Build benchmarks/data/mcpatlas/cases.json from the MCP-Atlas parquet (gold trajectories).

Reads parquet/JSON only; never executes anything from the data.
Usage: python -I -X utf8 load_mcpatlas.py <MCP-Atlas.parquet> [out_dir]

Every tool call in the reference TRAJECTORY becomes one case with label True
(gold call is correct). No incorrect calls exist in this dataset.
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


def main():
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "data" / "mcpatlas"
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = build(src)
    (out_dir / "cases.json").write_text(
        json.dumps({"cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(cases)} cases to {out_dir / 'cases.json'}")


if __name__ == "__main__":
    main()
