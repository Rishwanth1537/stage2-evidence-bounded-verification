"""
Load the public DeRef data (Ma et al., arXiv 2610.18497; Hugging Face `lm2445/DeRef`, Apache-2.0) into our common case format.

  python benchmarks/load_deref.py --download            # fetches fcrb.jsonl (3.7 MB) and cfb.jsonl (28.5 MB) into benchmarks/data/deref/
  python benchmarks/load_deref.py --dir <folder with the two jsonl files>

Output (git-ignored): benchmarks/data/deref/cases_fcrb.json and cases_cfb.json
Each case: id, dataset, query_id, split ('dev'/'test'), premise (request + history as text), calls [{name, arguments}],
call (= calls[0], for scripts that expect one), label (True = the dataset's 'correct' call), args_meta [per-argument label and
derivation path, in_analysis flag].

Split: by query_id, 50/50, seed 11, so all calls of one query are on the same side.  Labels and derivation paths are the dataset
authors' own automatic labels (see their paper), not ours.  fintrace (131 MB, rule-made errors) is not loaded here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmarks" / "data" / "deref"
URL = "https://huggingface.co/datasets/lm2445/DeRef/resolve/main/data/{}.jsonl"
SPLIT_SEED = 11


def download(name: str, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{name}.jsonl"
    if not dest.exists():
        print("downloading", URL.format(name))
        with urllib.request.urlopen(urllib.request.Request(URL.format(name), headers={"User-Agent": "mcp-hallucination-checker"}), timeout=300) as r:
            dest.write_bytes(r.read())
    return dest


def render_context(row) -> str:
    parts = [f"User request: {row.get('request') or ''}"]
    for h in row.get("history") or []:
        parts.append(f"[{h.get('label', h.get('kind', ''))}] {h.get('name', '')}: {h.get('text', '')}".replace(": :", ":"))
    return "\n".join(parts)


def build(name: str, src: Path):
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]
    qids = sorted({r["query_id"] for r in rows})
    random.Random(SPLIT_SEED).shuffle(qids)
    dev_q = set(qids[: len(qids) // 2])
    cases = []
    for r in rows:
        calls = [{"name": c["name"], "arguments": c["arguments"]} for c in r["calls"]]
        cases.append({
            "id": f"{name}:{r['item_id']}", "dataset": name, "query_id": r["query_id"],
            "split": "dev" if r["query_id"] in dev_q else "test",
            "premise": render_context(r), "calls": calls, "call": calls[0],
            "label": r["call_label"] == "correct", "mutation": None,
            "args_meta": [{"name": a["name"], "value": a["value"], "label": a["label"], "path": a["path"],
                           "in_analysis": bool(a.get("in_analysis")), "call_index": a.get("call_index", 0)} for a in r["arguments"]],
        })
    meta = {"source": "lm2445/DeRef (Apache-2.0), arXiv 2610.18497", "dataset": name, "split_seed": SPLIT_SEED,
            "n_cases": len(cases), "n_correct": sum(c["label"] for c in cases),
            "n_dev": sum(c["split"] == "dev" for c in cases), "n_test": sum(c["split"] == "test" for c in cases),
            "sha256_source": hashlib.sha256(src.read_bytes()).hexdigest()[:16],
            "label_note": "labels and derivation paths are the dataset authors' automatic labels"}
    return {"meta": meta, "cases": cases}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DATA))
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    folder = Path(a.dir)
    for name in ("fcrb", "cfb"):
        src = download(name, folder) if a.download else folder / f"{name}.jsonl"
        if not src.exists():
            raise SystemExit(f"{src} not found; use --download")
        out = build(name, src)
        dest = DATA / f"cases_{name}.json"
        DATA.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out))
        print(name, json.dumps(out["meta"]), "->", dest)


if __name__ == "__main__":
    main()
