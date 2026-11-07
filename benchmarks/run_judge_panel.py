"""
Run the dev-half judge panel in one command.  Reads benchmarks/judge_panel.json, skips every judge whose key is not
available, skips runs whose result file already exists (the response cache also makes re-runs free), and prints a summary.

  python benchmarks/run_judge_panel.py --list             # what would run and which keys are present
  python benchmarks/run_judge_panel.py                    # dev halves only
  python benchmarks/run_judge_panel.py --only claude-opus # one entry (substring of its name)

Test halves are deliberately not available here: use llm_judge_args.py --split test --allow-test once per frozen configuration.
PRIVACY: benchmark text is sent to every provider in the panel.  Hosted-model cost: the Anthropic and OpenRouter entries are billed.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from keys import get_key  # noqa: E402

DATASETS = {
    "fcrb": {"bench": "benchmarks/data/deref/cases_fcrb.json", "limit": 200, "extra": []},
    "cfb": {"bench": "benchmarks/data/deref/cases_cfb.json", "limit": 100, "extra": ["--max-context-chars", "3000"]},
    "injected": {"bench": None, "limit": 200, "extra": []},
}


def result_path(entry, ds):
    safe = entry["model"].replace("/", "_").replace("-", "_").replace(".", "_")
    tag = {"fcrb": "fcrb", "cfb": "cfb", "injected": "injected"}[ds]
    return ROOT / "benchmarks" / f"panel_{tag}_{entry['provider']}_{safe}_dev_v0.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default=str(ROOT / "benchmarks" / "judge_panel.json"))
    ap.add_argument("--only", default=None)
    ap.add_argument("--datasets", default="fcrb,cfb,injected")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    panel = json.loads(Path(a.panel).read_text(encoding="utf-8"))["judges"]
    summary = []
    for e in panel:
        if a.only and a.only not in e["name"]:
            continue
        key_name = e.get("key_env") or {"groq": "GROQ_API_KEY", "nvidia": "NVIDIA_API_KEY", "gemini": "GEMINI_API_KEY",
                                         "openrouter": "OPENROUTER_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(e["provider"])
        have = bool(get_key(key_name)) if key_name else False
        print(f"[{e['name']}] {e['provider']}/{e['model']}  key {key_name}: {'present' if have else 'MISSING'}"
              f"{'  (billed)' if e.get('billed') else ''}")
        if str(e['model']).startswith('REPLACE'):
            print('  model id not set in judge_panel.json: skipped')
            continue
        if a.list or not have:
            continue
        for ds in a.datasets.split(","):
            cfg = DATASETS[ds]
            out = result_path(e, ds)
            if out.exists():
                print(f"  {ds}: exists, skipped ({out.name})")
                continue
            rpm = e.get("rpm_long" if ds == "cfb" else "rpm", 10)
            cmd = [sys.executable, "-u", str(ROOT / "benchmarks" / "llm_judge_args.py"), "--provider", e["provider"], "--model", e["model"],
                   "--split", "dev", "--limit", str(e.get("limit", {}).get(ds, cfg["limit"])), "--rpm", str(rpm), "--out", str(out)] + cfg["extra"]
            if cfg["bench"]:
                cmd += ["--bench", str(ROOT / cfg["bench"])]
            if e["provider"] == "custom":
                cmd += ["--base-url", e["base_url"], "--key-env", e["key_env"]]
            print("  running", ds, flush=True)
            r = subprocess.run(cmd, cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
            if r.returncode != 0:
                print(f"  {ds}: FAILED (exit {r.returncode}); partial replies are cached, re-run to resume")
                break
        for ds in a.datasets.split(","):
            p = result_path(e, ds)
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                j, c = d["judge"], d["deterministic_checker_same_cases"]
                summary.append((e["name"], ds, j, c, d["mcnemar_exact_judge_vs_checker"]["p"]))
    if summary:
        print("\njudge | dataset | judge FBR / det | checker FBR / det | unparseable | p")
        for n, ds, j, c, p in summary:
            print(f"{n} | {ds} | {j['false_block_rate']:.3f} / {j['detection_rate']:.3f} | {c['false_block_rate']:.3f} / "
                  f"{c['detection_rate']:.3f} | {j['n_unparseable']} | {p:.4f}")


if __name__ == "__main__":
    main()
