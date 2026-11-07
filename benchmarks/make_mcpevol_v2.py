"""
Generate MCPEvol-Bench v2: a larger, template-based, seeded set of tool-call grounding cases.

Every case has a premise (the source context) and a hypothesis (the agent's planned action or reasoning).
Labels hold BY CONSTRUCTION: consistent cases are paraphrases of the premise; hallucinated cases mutate exactly one
fact (value, entity, action, negation flip or role swap). Half of the cases get an extra, unrelated sentence appended to
the premise, so the premise is longer than the hypothesis (the realistic situation, and the one a symmetric graph distance
penalises).

LIMITATIONS (say them out loud): synthetic and template-based, so lexical diversity is low and the set can over- or
under-state real-world difficulty; labels are correct by construction but were not checked by independent annotators.
It is a larger smoke test, not a benchmark.

Usage:  python benchmarks/make_mcpevol_v2.py [--per-template 8] [--seed 7]
Output: benchmarks/mcpevol_v2.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NAMES = ["Alice", "Bob", "Carol", "David", "Priya", "Ravi", "Maria", "Chen", "Fatima", "Omar", "Elena", "Tom"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
TIMES = ["3 PM", "9 AM", "11:30 AM", "6:45 AM", "2 PM", "4:15 PM", "8 PM", "10 AM"]
ENVS = ["production", "staging", "the QA cluster", "the demo environment"]
ITEMS = ["laptops", "monitors", "keyboards", "headsets", "chairs", "routers"]
CITIES = ["Pune", "Berlin", "Austin", "Lagos", "Osaka", "Lyon"]
SYSTEMS = ["the billing database", "the HR portal", "the build server", "the analytics workspace"]
LEVELS = ["read-only", "admin", "write", "auditor"]
ACTS = [("read", "delete"), ("open", "overwrite"), ("copy", "move"), ("summarise", "delete"), ("download", "upload")]
PATHS = ["/data/config.json", "/reports/q3.pdf", "/srv/logs/app.log", "/home/shared/budget.xlsx"]
TABLES = ["orders", "customers", "invoices", "sessions"]
HOSTS = ["web-01", "db-02", "cache-03", "api-07"]
PRIOS = ["high", "low", "medium", "critical"]
EXTRAS = [
    "The office will be closed on the following Monday for maintenance.",
    "A separate task for 14 other accounts is still pending review.",
    "The previous report listed 250 items and was filed in March.",
    "Support contacted the vendor twice about a 7-day delay on an unrelated shipment.",
    "Another request, for $9,000, was escalated to the finance lead on Friday.",
    "Version 1.9.2 of the client library was also released that week.",
]


def money(rng, lo=20, hi=900):
    return rng.choice([rng.randint(lo, hi), rng.randint(2, 40) * 100])


def other(rng, pool, avoid):
    return rng.choice([x for x in pool if x != avoid])


def bump_value(rng, n):
    return rng.choice([n * 10, max(1, n // 10), n + rng.choice([50, 100, 25]), n * 2])


def bump_version(rng, v):
    a, b, c = (int(x) for x in v.split("."))
    return rng.choice([f"{a}.{b}.{c + 1}", f"{a}.{b + 1}.0", f"{a + 1}.0.0"])


def build(rng: random.Random, per_template: int):
    cases = []

    def add(kind, ctype, label, hyp, prem, meta):
        cases.append({"hypothesis": hyp, "premise": prem, "label": label, "type": ctype, "mutation": kind, **meta})

    for _ in range(per_template):
        a, b, m = rng.sample(NAMES, 3)
        amt = money(rng); day = rng.choice(DAYS); t = rng.choice(TIMES)
        # 1. transfer
        prem = f"{a} transferred ${amt} to {b} on {day}."
        add("consistent", "content", True, f"On {day}, {a} sent ${amt} to {b}.", prem, {"template": "transfer"})
        add("value", "content", False, f"On {day}, {a} sent ${bump_value(rng, amt)} to {b}.", prem, {"template": "transfer"})
        add("entity", "content", False, f"On {day}, {a} sent ${amt} to {rng.choice([x for x in NAMES if x not in (a, b)])}.", prem, {"template": "transfer"})
        add("day", "content", False, f"On {other(rng, DAYS, day)}, {a} sent ${amt} to {b}.", prem, {"template": "transfer"})
        # 2. role swap
        prem = f"{a} paid {b} ${amt} for the consulting invoice."
        add("consistent", "role_swap", True, f"{b} received ${amt} from {a} for the consulting invoice.", prem, {"template": "pay"})
        add("role_swap", "role_swap", False, f"{b} paid {a} ${amt} for the consulting invoice.", prem, {"template": "pay"})
        # 3. deploy
        v = f"{rng.randint(1, 4)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}"; env = rng.choice(ENVS)
        prem = f"Version {v} was deployed to {env} at {t}."
        add("consistent", "content", True, f"The deployment of version {v} to {env} happened at {t}.", prem, {"template": "deploy"})
        add("version", "content", False, f"The deployment of version {bump_version(rng, v)} to {env} happened at {t}.", prem, {"template": "deploy"})
        add("env", "content", False, f"The deployment of version {v} to {other(rng, ENVS, env)} happened at {t}.", prem, {"template": "deploy"})
        # 4. file action
        act, bad = rng.choice(ACTS); path = rng.choice(PATHS)
        prem = f"The user asked the agent to {act} the file at {path}."
        add("consistent", "content", True, f"The agent will {act} {path} as requested.", prem, {"template": "file"})
        add("action", "content", False, f"The agent will {bad} {path} as requested.", prem, {"template": "file"})
        add("path", "content", False, f"The agent will {act} {other(rng, PATHS, path)} as requested.", prem, {"template": "file"})
        # 5. meeting
        room = rng.randint(100, 480)
        prem = f"The meeting is scheduled for {t} on {day} in room {room}."
        add("consistent", "content", True, f"{day}'s meeting starts at {t} in room {room}.", prem, {"template": "meeting"})
        add("time", "content", False, f"{day}'s meeting starts at {other(rng, TIMES, t)} in room {room}.", prem, {"template": "meeting"})
        add("room", "content", False, f"{day}'s meeting starts at {t} in room {room + rng.choice([1, 10, 100])}.", prem, {"template": "meeting"})
        # 6. order
        n = rng.randint(100, 999); qty = rng.randint(2, 60); item = rng.choice(ITEMS); city = rng.choice(CITIES)
        prem = f"Order #{n} for {qty} {item} was shipped to {city}."
        add("consistent", "content", True, f"{qty} {item} from order #{n} went out to {city}.", prem, {"template": "order"})
        add("qty", "content", False, f"{bump_value(rng, qty)} {item} from order #{n} went out to {city}.", prem, {"template": "order"})
        add("city", "content", False, f"{qty} {item} from order #{n} went out to {other(rng, CITIES, city)}.", prem, {"template": "order"})
        # 7. access request (role swap + level)
        sysn = rng.choice(SYSTEMS); lvl = rng.choice(LEVELS)
        prem = f"{a} requested {lvl} access to {sysn}, and {m} approved the request."
        add("consistent", "role_swap", True, f"{m} approved {a}'s request for {lvl} access to {sysn}.", prem, {"template": "access"})
        add("role_swap", "role_swap", False, f"{a} approved {m}'s request for {lvl} access to {sysn}.", prem, {"template": "access"})
        add("level", "content", False, f"{m} approved {a}'s request for {other(rng, LEVELS, lvl)} access to {sysn}.", prem, {"template": "access"})
        # 8. refund
        c = rng.choice(NAMES)
        prem = f"A refund of ${amt} was issued to customer {c} for order #{n}."
        add("consistent", "content", True, f"Customer {c} received a ${amt} refund on order #{n}.", prem, {"template": "refund"})
        add("value", "content", False, f"Customer {c} received a ${bump_value(rng, amt)} refund on order #{n}.", prem, {"template": "refund"})
        # 9. negation pairs
        prem = f"No payment was processed for order #{n}; it remains pending approval."
        add("consistent_neg", "negation", True, f"Order #{n} has not been paid.", prem, {"template": "neg_payment"})
        add("negation_flip", "negation", False, f"Payment for order #{n} was processed successfully.", prem, {"template": "neg_payment"})
        prem = f"{a} did not approve the budget of ${amt}."
        add("consistent_neg", "negation", True, f"The ${amt} budget was not approved by {a}.", prem, {"template": "neg_budget"})
        add("negation_flip", "negation", False, f"{a} approved the ${amt} budget.", prem, {"template": "neg_budget"})
        prem = f"The backup was not deleted; it is retained for {rng.choice([7, 14, 30])} days."
        add("consistent_neg", "negation", True, "The backup is still being retained.", prem, {"template": "neg_backup"})
        add("negation_flip", "negation", False, "The backup was deleted.", prem, {"template": "neg_backup"})
        # 10. database / monitoring
        rows = rng.randint(3, 900); tbl = rng.choice(TABLES); host = rng.choice(HOSTS); pct = rng.randint(55, 99)
        prem = f"The query returned {rows} rows from table {tbl}."
        add("consistent", "content", True, f"{rows} rows were returned from the {tbl} table.", prem, {"template": "query"})
        add("value", "content", False, f"{bump_value(rng, rows)} rows were returned from the {tbl} table.", prem, {"template": "query"})
        add("table", "content", False, f"{rows} rows were returned from the {other(rng, TABLES, tbl)} table.", prem, {"template": "query"})
        prem = f"CPU usage reached {pct}% on host {host} at {t}."
        add("consistent", "content", True, f"At {t}, host {host} hit {pct}% CPU.", prem, {"template": "alert"})
        add("value", "content", False, f"At {t}, host {host} hit {max(5, pct - rng.choice([20, 30, 40]))}% CPU.", prem, {"template": "alert"})
        add("host", "content", False, f"At {t}, host {other(rng, HOSTS, host)} hit {pct}% CPU.", prem, {"template": "alert"})
        # 11. ticket
        tk = f"T-{rng.randint(1000, 9999)}"; pr = rng.choice(PRIOS)
        prem = f"Ticket {tk} was assigned to {a} with {pr} priority."
        add("consistent", "content", True, f"{a} now owns ticket {tk}, which has {pr} priority.", prem, {"template": "ticket"})
        add("priority", "content", False, f"{a} now owns ticket {tk}, which has {other(rng, PRIOS, pr)} priority.", prem, {"template": "ticket"})
        add("assignee", "content", False, f"{b} now owns ticket {tk}, which has {pr} priority.", prem, {"template": "ticket"})
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-template", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "mcpevol_v2.json"))
    ap.add_argument("--prefix", default="V2")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    cases = build(rng, args.per_template)
    # drop accidental no-ops and duplicates
    out, seen = [], set()
    for c in cases:
        if not c["label"] and c["hypothesis"].strip().lower() == c["premise"].strip().lower():
            continue
        key = (c["hypothesis"], c["premise"])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    # balance the classes: keep every consistent, negation and role-swap case; down-sample content mutations
    n_true = sum(c["label"] for c in out)
    keep_false_other = [c for c in out if not c["label"] and c["type"] != "content"]
    content_false = [c for c in out if not c["label"] and c["type"] == "content"]
    rng.shuffle(content_false)
    out = [c for c in out if c["label"]] + keep_false_other + content_false[:max(0, n_true - len(keep_false_other))]
    # half of the cases get an unrelated extra sentence in the premise (premise longer than hypothesis)
    for c in out:
        c["premise_extra"] = rng.random() < 0.5
        if c["premise_extra"]:
            c["premise"] = c["premise"] + " " + rng.choice(EXTRAS)
    rng.shuffle(out)
    for i, c in enumerate(out, 1):
        c["id"] = f"{args.prefix}-{i:03d}"
    Path(args.out).write_text(json.dumps(out, indent=1))
    from collections import Counter
    print(len(out), "cases;", Counter((c["type"], c["label"]) for c in out))
    print("with extra premise sentence:", sum(c["premise_extra"] for c in out))


if __name__ == "__main__":
    main()
