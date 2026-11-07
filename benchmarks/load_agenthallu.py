"""Build benchmarks/data/agenthallu/cases.json from a local AgentHallu clone.

AgentHallu (Liu et al. 2026, arXiv 2601.06818), licence CC BY 4.0.
Treats the input as untrusted DATA: reads JSON only, executes nothing.
Run:  python -I benchmarks/load_agenthallu.py <clone_dir> [--all-frameworks]

Positives (label False): the attributed step of a trajectory whose
hallucination_subcategory is "Incorrect Tool Arguments", only when that step
holds exactly one tool call (otherwise the wrong call is ambiguous; those are
counted and skipped).
Negatives (label True): every tool call with non-empty arguments in
trajectories annotated is_hallucination == "false". BFCL only unless
--all-frameworks is given.
"""
import glob
import json
import os
import sys

MAX_PREMISE = 6000
ARG_CATEGORY = "Incorrect Tool Arguments"


def _flat(q):
    if isinstance(q, list):
        out = []
        for t in q:
            out.append(_flat(t))
        return "\n".join(x for x in out if x)
    return str(q)


def _j(x):
    return json.dumps(x, ensure_ascii=False)


def _premise(d, upto_idx, upto_ncalls):
    """Task plus everything preceding the target call, most recent 6000 chars."""
    parts = ["User task:\n" + _flat(d.get("question"))]
    hist = d.get("history") or []
    for i, st in enumerate(hist[: upto_idx + 1]):
        calls = st.get("tool_calls") or []
        resps = st.get("tool_responses") or []
        n = upto_ncalls if i == upto_idx else len(calls)
        if st.get("content") and i != upto_idx:
            parts.append("[assistant] " + str(st["content"]))
        for k in range(n):
            c = calls[k]
            parts.append("[tool call] %s %s" % (c.get("name"), _j(c.get("arguments"))))
            if k < len(resps):
                parts.append("[tool result] " + str(resps[k]))
    text = "\n".join(parts)
    if len(text) > MAX_PREMISE:
        text = text[-MAX_PREMISE:]
    return text


def build(root, all_frameworks=False):
    cases, skipped = [], {"multi_call_step": 0, "bad_step": 0}
    for p in sorted(glob.glob(os.path.join(root, "AgentHallu", "*", "*.json"))):
        fw = os.path.basename(os.path.dirname(p))
        if fw != "BFCL" and not all_frameworks:
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        tid = "%s/%s" % (fw, os.path.basename(p)[:-5])
        hist = d.get("history") or []
        if d.get("is_hallucination") == "true":
            if d.get("hallucination_subcategory") != ARG_CATEGORY:
                continue
            s = str(d.get("hallucination_step"))
            idx = next((i for i, st in enumerate(hist) if str(st.get("step")) == s), None)
            if idx is None:
                skipped["bad_step"] += 1
                continue
            calls = hist[idx].get("tool_calls") or []
            if len(calls) != 1:
                skipped["multi_call_step" if len(calls) > 1 else "bad_step"] += 1
                continue
            c = calls[0]
            cases.append({
                "id": "agenthallu:%s:s%s" % (tid, s), "source": "agenthallu", "split": "dev",
                "premise": _premise(d, idx, 0),
                "call": {"name": c.get("name"), "arguments": c.get("arguments") or {}},
                "label": False, "category": ARG_CATEGORY, "attributed_step": int(s),
                "framework": fw, "human_reason": d.get("hallucination_reason"),
            })
        elif d.get("is_hallucination") == "false":
            for idx, st in enumerate(hist):
                for k, c in enumerate(st.get("tool_calls") or []):
                    if not c.get("arguments"):
                        continue
                    cases.append({
                        "id": "agenthallu:%s:s%s:c%d" % (tid, st.get("step"), k),
                        "source": "agenthallu", "split": "dev",
                        "premise": _premise(d, idx, k),
                        "call": {"name": c.get("name"), "arguments": c["arguments"]},
                        "label": True, "category": "clean", "attributed_step": None,
                        "framework": fw,
                    })
    return cases, skipped


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = args[0]
    cases, skipped = build(root, "--all-frameworks" in sys.argv)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "agenthallu")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "cases.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"cases": cases, "skipped": skipped}, f, ensure_ascii=False, indent=1)
    pos = sum(1 for c in cases if not c["label"])
    print("wrote", out, "cases", len(cases), "bad(label False)", pos,
          "clean", len(cases) - pos, "skipped", skipped)


if __name__ == "__main__":
    main()
