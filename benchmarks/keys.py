"""
API-key lookup that loads from environment variables and the project-root .env only.
Never prints or leaks key values or prefixes.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / ".env"
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
    """Return key value from environment or project-root .env."""
    return os.environ.get(name) or _file_values().get(name, "")


def main():
    vals = _file_values()
    print(f"key file: {KEY_FILE.name} ({'exists' if KEY_FILE.exists() else 'not found'})")
    for n in KNOWN:
        src = "environment" if os.environ.get(n) else (".env" if vals.get(n) else "missing")
        print(f"  {n:20s} {src}")


if __name__ == "__main__":
    main()
