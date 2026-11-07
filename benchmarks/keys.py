"""
API-key lookup that never puts a key in the repository or in a chat.

Order: (1) environment variable, (2) a private file OUTSIDE the repo: ~/.mcp_checker_keys.env
(on Windows: C:\\Users\\<you>\\.mcp_checker_keys.env), lines of the form  GROQ_API_KEY=...  (no quotes needed).

Create the file yourself in an editor; do not paste its contents into a chat or commit it.
`python benchmarks/keys.py` prints which keys are visible (names only, never values).
"""
from __future__ import annotations

import os
from pathlib import Path

KEY_FILE = Path.home() / ".mcp_checker_keys.env"
KNOWN = ("GROQ_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN")


def _file_values() -> dict:
    out = {}
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def get_key(name: str) -> str:
    return os.environ.get(name) or _file_values().get(name, "")


def main():
    vals = _file_values()
    print(f"key file: {KEY_FILE} ({'exists' if KEY_FILE.exists() else 'not found'})")
    for n in KNOWN:
        src = "environment" if os.environ.get(n) else ("key file" if vals.get(n) else "missing")
        print(f"  {n:20s} {src}")


if __name__ == "__main__":
    main()
