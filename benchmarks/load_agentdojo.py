"""Build benchmarks/data/agentdojo/cases.json from AgentDojo recorded runs.

Reads JSON only (never imports or executes AgentDojo code). Usage:
  python -I load_agentdojo.py <agentdojo_repo_dir> [model1,model2,...] [max_runs_per_model]

One case per executed tool call. Fields:
  injected          run had an injection AND the call has a string/number argument leaf
                    that (a) is a whole token inside the injection text, (b) does not occur
                    in the system/user prompt, and (c) the injection text was visible in an
                    earlier tool output of the same run  ("value planting").
  attack_goal_call  injected AND the called function name appears in the ground_truth of the
                    run's injection task (static regex over the suite's injection_tasks.py;
                    name-level approximation, args are not compared).
"""
import json
import os
import re
import sys

MAX_PREMISE = 6000


def gt_functions(repo):
    """{(suite, injection_task_id): set(function names)} from source text, no import."""
    out = {}
    base = os.path.join(repo, "src", "agentdojo", "default_suites")
    for ver in sorted(os.listdir(base)):
        vdir = os.path.join(base, ver)
        if not os.path.isdir(vdir):
            continue
        for suite in os.listdir(vdir):
            p = os.path.join(vdir, suite, "injection_tasks.py")
            if not os.path.isfile(p):
                continue
            src = open(p, encoding="utf-8").read()
            parts = re.split(r"^class InjectionTask(\d+)\b", src, flags=re.M)
            for i in range(1, len(parts) - 1, 2):
                key = (suite, "injection_task_" + parts[i])
                out.setdefault(key, set()).update(
                    re.findall(r'function\s*=\s*"([A-Za-z_0-9]+)"', parts[i + 1]))
    return out


def leaves(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from leaves(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from leaves(v)
    elif isinstance(x, (str, int, float)) and not isinstance(x, bool):
        yield str(x)


def render(msg):
    role = msg.get("role")
    c = msg.get("content") or ""
    if isinstance(c, list):
        c = " ".join(b.get("content", "") if isinstance(b, dict) else str(b) for b in c)
    s = "[%s] %s" % (role, c)
    for tc in msg.get("tool_calls") or []:
        s += "\n  CALL %s(%s)" % (tc.get("function"), json.dumps(tc.get("args"), ensure_ascii=False))
    return s


def build(repo, models, max_runs):
    gt = gt_functions(repo)
    runs_dir = os.path.join(repo, "runs")
    cases = []
    for model in models:
        n = 0
        for dp, _, fs in os.walk(os.path.join(runs_dir, model)):
            for f in sorted(fs):
                if not f.endswith(".json"):
                    continue
                if max_runs and n >= max_runs:
                    break
                try:
                    d = json.load(open(os.path.join(dp, f), encoding="utf-8"))
                except Exception:
                    continue
                n += 1
                msgs = d.get("messages") or []
                inj = d.get("injections") or {}
                inj_text = "\n".join(str(v) for v in inj.values())
                snippet = re.sub(r"\s+", " ", inj_text).strip()[:60]
                prompts = " ".join(str(m.get("content")) for m in msgs
                                   if m.get("role") in ("system", "user"))
                gtf = gt.get((d.get("suite_name"), d.get("injection_task_id")), set())
                rendered = [render(m) for m in msgs]
                seen_inj = False
                k = 0
                for i, m in enumerate(msgs):
                    if m.get("role") == "tool" and snippet and snippet in re.sub(
                            r"\s+", " ", str(m.get("content"))).replace("\\n", " "):
                        seen_inj = True
                    if m.get("role") == "tool" and snippet and snippet[:25] in str(m.get("content")):
                        seen_inj = True
                    for tc in m.get("tool_calls") or []:
                        args = tc.get("args") or {}
                        hit = False
                        if inj and seen_inj:
                            for v in leaves(args):
                                v = v.strip()
                                if not v or v in prompts:
                                    continue
                                if re.search(r"(?<![\w@.])" + re.escape(v) + r"(?![\w])", inj_text):
                                    hit = True
                                    break
                        prem = "\n".join(rendered[:i])[-MAX_PREMISE:]
                        cases.append({
                            "id": "agentdojo/%s/%s/%s/%s/%s#%d" % (
                                model, d.get("suite_name"), d.get("user_task_id"),
                                d.get("attack_type"), d.get("injection_task_id"), k),
                            "source": "agentdojo", "split": "dev",
                            "premise": prem,
                            "call": {"name": tc.get("function"), "arguments": args},
                            "injected": hit,
                            "attack_goal_call": bool(hit and tc.get("function") in gtf),
                            "run_utility": d.get("utility"),
                            "run_security": d.get("security"),
                            "model": model, "suite": d.get("suite_name"),
                            "attack_type": d.get("attack_type"),
                            "injection_task_id": d.get("injection_task_id"),
                        })
                        k += 1
    return cases


if __name__ == "__main__":
    repo = sys.argv[1]
    models = (sys.argv[2] if len(sys.argv) > 2 else
              "claude-3-5-sonnet-20241022,gpt-4o-2024-05-13").split(",")
    max_runs = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    cases = build(repo, models, max_runs)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "agentdojo")
    os.makedirs(out, exist_ok=True)
    json.dump({"cases": cases}, open(os.path.join(out, "cases.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(len(cases), "cases;", sum(c["injected"] for c in cases), "injected;",
          sum(c["attack_goal_call"] for c in cases), "attack_goal_call")
