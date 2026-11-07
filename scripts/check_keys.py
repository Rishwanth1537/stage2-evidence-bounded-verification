"""
Utility to check presence of required API keys without logging, printing,
or leaking key values, prefixes, or lengths.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"

KEY_NAMES: List[str] = [
    "GROQ_API_KEY",
    "NVIDIA_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "HF_TOKEN",
    "CUSTOM_API_KEY",
]


def load_env_file(path: Path) -> Dict[str, str]:
    """Parse key=value pairs from a .env file safely."""
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                out[k] = v
    except Exception:
        pass
    return out


def get_key_status(env_path: Path = ENV_FILE) -> Dict[str, bool]:
    """Return dictionary of {key_name: is_set}."""
    file_vars = load_env_file(env_path)
    status: Dict[str, bool] = {}
    for name in KEY_NAMES:
        val = os.environ.get(name) or file_vars.get(name)
        status[name] = bool(val and val.strip())
    return status


def print_key_status(status: Dict[str, bool]) -> str:
    """Format output: strictly variable names and SET/UNSET only."""
    lines = []
    for name, is_set in status.items():
        state = "SET" if is_set else "UNSET"
        lines.append(f"{name:20s}: {state}")
    output = "\n".join(lines)
    return output


def main():
    status = get_key_status()
    print(print_key_status(status))


if __name__ == "__main__":
    main()
