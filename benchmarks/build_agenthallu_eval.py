import hashlib, json, random, collections
B = r"U:\txt\mcp-hallucination-checker\benchmarks\data\agenthallu"
d = json.load(open(B + r"\cases.json", encoding="utf-8"))["cases"]
rng = random.Random(17)
pos = [c for c in d if c["label"] is False]
neg = [c for c in d if c["label"] is True]
by_traj = collections.defaultdict(list)
for c in neg:
    by_traj[c["id"].split(":")[1]].append(c)
# 93 clean calls: round-robin over clean trajectories so no trajectory dominates
trajs = sorted(by_traj)
for t in trajs:
    rng.shuffle(by_traj[t])
picked, i = [], 0
while len(picked) < 93:
    t = trajs[i % len(trajs)]
    if by_traj[t]:
        picked.append(by_traj[t].pop())
    i += 1
cases = []
for c in pos + picked:
    cases.append({"id": c["id"], "dataset": "agenthallu", "query_id": c["id"].split(":")[1], "split": "dev", "premise": c["premise"],
                  "call": c["call"], "calls": [c["call"]], "label": c["label"], "category": c["category"]})
rng.shuffle(cases)
for c in cases:
    assert "human_reason" not in c
out = B + r"\cases_eval.json"
txt = json.dumps({"cases": cases}, ensure_ascii=False)
open(out, "w", encoding="utf-8").write(txt)
print(len(cases), "cases:", collections.Counter(c["label"] for c in cases), "trajectories:", len({c["query_id"] for c in cases}))
print("sha256", hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16])
