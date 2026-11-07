#!/usr/bin/env python
"""
Package the minimum set of repo files needed by kaggle/ablation_mcpevol.ipynb
into one zip that can be uploaded as a Kaggle dataset.

Included : server/ (code only), configs/, benchmarks/__init__.py,
           benchmarks/mcpevol.json, benchmarks/mcpevol_runner.py,
           requirements.txt, pyproject.toml
Excluded : __pycache__, *.pyc, egg-info, parquet, result/log json, .venv, .git,
           tests, review decks, other benchmark files.

Usage:
    python kaggle/package_for_kaggle.py                 # writes to the default scratchpad dir
    python kaggle/package_for_kaggle.py -o D:/tmp/mcp_hc_kaggle.zip

NOTE: the default output is deliberately NOT inside the repo drive (U: is nearly full).
Kaggle auto-extracts uploaded zips; the notebook auto-detects either the extracted
folder or the raw zip under /kaggle/input/<dataset>/.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DEFAULT_OUT = Path(
    r"C:\Users\GOVARDHAN SATYA\AppData\Local\Temp\claude\U--txt"
    r"\6173e509-7d57-45dc-89ce-3c72a921c864\scratchpad\mcp_hallucination_checker_kaggle.zip"
)

# (relative path or dir, is_dir)
INCLUDE = [
    ("server", True),
    ("configs", True),
    ("benchmarks/__init__.py", False),
    ("benchmarks/mcpevol.json", False),
    ("benchmarks/mcpevol_runner.py", False),
    ("requirements.txt", False),
    ("pyproject.toml", False),
]

EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", ".venv-1", "mcp_hallucination_checker.egg-info",
                ".pytest_cache", ".ruff_cache", "node_modules"}
EXCLUDE_GLOBS = ["*.pyc", "*.pyo", "*.parquet", "*.log", "*.egg-info", "*results*.json",
                 "*.zip", "*.pptx", ".DS_Store"]


def _excluded(rel: Path) -> bool:
    if any(part in EXCLUDE_DIRS or part.endswith(".egg-info") for part in rel.parts):
        return True
    name = rel.name
    # mcpevol.json is the dataset itself, not a result file
    return any(fnmatch.fnmatch(name, g) for g in EXCLUDE_GLOBS)


def iter_files():
    for rel, is_dir in INCLUDE:
        p = REPO / rel
        if not p.exists():
            print(f"WARNING: missing {rel}", file=sys.stderr)
            continue
        if is_dir:
            for f in sorted(p.rglob("*")):
                if f.is_file() and not _excluded(f.relative_to(REPO)):
                    yield f
        elif not _excluded(Path(rel)):
            yield p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if REPO in out.parents:
        print("WARNING: output is inside the repo tree; prefer a path outside it.", file=sys.stderr)

    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in iter_files():
            arc = f.relative_to(REPO).as_posix()
            zf.write(f, arc)
            n += 1
            print("  +", arc)
    size = os.path.getsize(out)
    print(f"\nWrote {out}\n{n} files, {size/1024:.1f} KiB ({size/1e6:.3f} MB)")


if __name__ == "__main__":
    main()
