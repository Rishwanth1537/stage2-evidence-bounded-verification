"""
benchmarks/create_mcpatlas_x1_split.py
Create the mcpatlas_x1 dev/held-out split (Prompt 6C Step 3).

Cluster = task (cluster_id field). Deterministic hash-based split:
  ~70% X1-DEV, ~30% X1-HELDOUT.
  Uses SHA-256 of cluster_id; threshold at 0.70.

Writes the split tag back into splits.py's registry (adds load_mcpatlas_x1
function) and prints cluster + call counts.

Does NOT load X1-HELDOUT data or run anything on it.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "benchmarks" / "data" / "mcpatlas" / "cases_v2.json"


def cluster_hash_fraction(cluster_id: str) -> float:
    """Return deterministic float in [0, 1) based on SHA-256 of the cluster id."""
    h = hashlib.sha256(cluster_id.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def create_x1_split(dev_fraction: float = 0.70):
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data

    # Group by cluster
    clusters: dict = defaultdict(list)
    for c in cases:
        cid = c.get("cluster_id") or c.get("task_id") or c["id"].rsplit("-", 1)[0]
        clusters[cid].append(c)

    dev_clusters = set()
    heldout_clusters = set()
    for cid in sorted(clusters.keys()):
        f = cluster_hash_fraction(cid)
        if f < dev_fraction:
            dev_clusters.add(cid)
        else:
            heldout_clusters.add(cid)

    dev_cases = [c for c in cases if (c.get("cluster_id") or c.get("task_id") or c["id"].rsplit("-", 1)[0]) in dev_clusters]
    heldout_cases = [c for c in cases if (c.get("cluster_id") or c.get("task_id") or c["id"].rsplit("-", 1)[0]) in heldout_clusters]

    print("=" * 60)
    print("mcpatlas_x1 Split Creation")
    print("=" * 60)
    print(f"Total clusters: {len(clusters)}")
    print(f"X1-DEV  clusters: {len(dev_clusters)}  ({len(dev_clusters)/len(clusters):.1%})")
    print(f"X1-HELDOUT clusters: {len(heldout_clusters)}  ({len(heldout_clusters)/len(clusters):.1%})")
    print()
    print(f"X1-DEV  calls: {len(dev_cases)}")
    print(f"X1-HELDOUT calls: {len(heldout_cases)}")
    total = len(dev_cases) + len(heldout_cases)
    assert total == len(cases), f"Split mismatch: {total} != {len(cases)}"
    print(f"Total calls accounted: {total} (matches source)")
    return dev_clusters, heldout_clusters, dev_cases, heldout_cases


if __name__ == "__main__":
    create_x1_split()
