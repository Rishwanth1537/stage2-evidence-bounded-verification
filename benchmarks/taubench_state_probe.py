"""tau-bench state probe: can id-like arguments of write calls be decided by pure lookup?

Reads the recorded trajectories and initial databases of a local tau-bench clone
(data only; nothing from the clone is executed), extracts every state-changing
tool call, labels it 'suspect' / 'ok' conservatively and runs lookup checks.

Label: a write call is 'suspect' iff the trajectory reward is 0 and the call
(name + canonicalised kwargs) is not among the gold actions of that task.

Usage: python -I taubench_state_probe.py [REPO_DIR] [OUT_JSON]
"""
import copy
import json
import os
import sys
from collections import Counter, defaultdict

REPO = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\GOVARDHAN SATYA\taubench_raw\repo"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "taubench", "cases.json")
OK_SAMPLE = 300  # ok calls stored in cases.json (stats use all)

RETAIL_WRITE = {"cancel_pending_order", "exchange_delivered_order_items",
                "modify_pending_order_address", "modify_pending_order_items",
                "modify_pending_order_payment", "modify_user_address",
                "return_delivered_order_items"}
AIRLINE_WRITE = {"book_reservation", "cancel_reservation", "send_certificate",
                 "update_reservation_baggages", "update_reservation_flights",
                 "update_reservation_passengers"}
ID_KEYS = {"order_id", "user_id", "reservation_id"}
ITEM_KEYS = {"item_ids", "new_item_ids", "flights", "origin", "destination", "flight_type"}
PAY_KEYS = {"payment_method_id", "payment_id", "payment_methods"}
FILES = [("gpt-4o-retail", "retail"), ("sonnet-35-new-retail", "retail"),
         ("gpt-4o-airline", "airline"), ("sonnet-35-new-airline", "airline")]


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def canon(name, kw):
    kw = copy.deepcopy(kw)
    if "item_ids" in kw and "new_item_ids" in kw and isinstance(kw["item_ids"], list) \
            and len(kw["item_ids"]) == len(kw["new_item_ids"]):
        pairs = sorted(zip(kw["item_ids"], kw["new_item_ids"]))
        kw["item_ids"] = [a for a, _ in pairs]
        kw["new_item_ids"] = [b for _, b in pairs]
    elif isinstance(kw.get("item_ids"), list):
        kw["item_ids"] = sorted(kw["item_ids"])
    return name, json.dumps(kw, sort_keys=True)


def parse_args(a):
    if isinstance(a, str):
        try:
            return json.loads(a)
        except Exception:
            return None
    return a


def is_err(resp):
    return isinstance(resp, str) and resp.startswith("Error")


def extract_calls(traj, write_names):
    """yield (msg_index, name, kwargs, response_text)"""
    for i, m in enumerate(traj):
        if m.get("role") != "assistant" or not m.get("tool_calls"):
            continue
        for tc in m["tool_calls"]:
            fn = tc["function"]
            kw = parse_args(fn.get("arguments"))
            if kw is None:
                continue
            resp = None
            for m2 in traj[i + 1:i + 4]:
                if m2.get("role") == "tool":
                    resp = m2.get("content")
                    break
            yield i, fn["name"], kw, resp


class Probe:
    def __init__(self, domain, db):
        self.domain, self.db = domain, db

    # ---- per-trajectory state overlay -------------------------------------------------
    def check(self, name, kw, auth_user, overlay):
        """return list of flag strings (lookup-decidable violations)"""
        return (self._retail if self.domain == "retail" else self._airline)(name, kw, auth_user, overlay)

    def _retail(self, name, kw, auth, ov):
        db, f = self.db, []
        orders, users, products = db["orders"], db["users"], db["products"]
        if name == "modify_user_address":
            uid = kw.get("user_id")
            if uid not in users:
                f.append("user_missing")
            elif auth and uid != auth:
                f.append("user_not_authenticated_user")
            return f
        oid = kw.get("order_id")
        order = ov.get(oid) or orders.get(oid)
        if order is None:
            return ["order_missing"]
        if auth and order["user_id"] != auth:
            f.append("order_wrong_user")
        need = {"cancel_pending_order": "pending", "modify_pending_order_address": "pending",
                "modify_pending_order_items": "pending", "modify_pending_order_payment": "pending",
                "exchange_delivered_order_items": "delivered",
                "return_delivered_order_items": "delivered"}[name]
        if order["status"] != need:
            f.append("status_incompatible")
        owner = users.get(order["user_id"], {})
        pm = kw.get("payment_method_id")
        if "payment_method_id" in kw and pm not in owner.get("payment_methods", {}):
            f.append("payment_not_found")
        have = Counter(it["item_id"] for it in order["items"])
        want = kw.get("item_ids")
        if isinstance(want, list):
            c = Counter(want)
            if any(c[k] > have[k] for k in c):
                f.append("item_not_in_order")
        new = kw.get("new_item_ids")
        if isinstance(new, list):
            olds = {it["item_id"]: it["product_id"] for it in order["items"]}
            for k, n in enumerate(new):
                pid = None
                for p in products.values():
                    if n in p["variants"]:
                        pid = p["product_id"]
                        var = p["variants"][n]
                        break
                if pid is None:
                    f.append("new_item_missing")
                    continue
                if isinstance(want, list) and k < len(want) and olds.get(want[k]) not in (None, pid):
                    f.append("new_item_other_product")
                if not var.get("available", False):
                    f.append("new_item_unavailable")
            if isinstance(want, list) and len(want) != len(new):
                f.append("item_count_mismatch")
        if name == "modify_pending_order_payment" and order.get("payment_history") \
                and order["payment_history"][0].get("payment_method_id") == pm:
            f.append("payment_same_as_current")
        if name == "return_delivered_order_items" and pm in owner.get("payment_methods", {}):
            orig = order["payment_history"][0]["payment_method_id"]
            if owner["payment_methods"][pm]["source"] != "gift_card" and pm != orig:
                f.append("payment_not_original_or_gift")
        return f

    def _airline(self, name, kw, auth, ov):
        db, f = self.db, []
        res, users, flights = db["reservations"], db["users"], db["flights"]
        uid = kw.get("user_id")
        r = None
        if name in ("book_reservation", "send_certificate"):
            if uid not in users:
                return ["user_missing"]
            if auth and uid != auth:
                f.append("user_not_authenticated_user")
        else:
            rid = kw.get("reservation_id")
            r = ov.get(rid) or res.get(rid)
            if r is None:
                return ["reservation_missing"]
            if auth and r["user_id"] != auth:
                f.append("reservation_wrong_user")
            if r.get("status") == "cancelled":
                f.append("status_incompatible")
            uid = r["user_id"]
        pays = []
        if "payment_id" in kw:
            pays = [kw["payment_id"]]
        if isinstance(kw.get("payment_methods"), list):
            pays = [p.get("payment_id") for p in kw["payment_methods"] if isinstance(p, dict)]
        for p in pays:
            if p not in users.get(uid, {}).get("payment_methods", {}):
                f.append("payment_not_found")
        if isinstance(kw.get("flights"), list):
            for fl in kw["flights"]:
                if not isinstance(fl, dict):
                    continue
                F = flights.get(fl.get("flight_number"))
                if F is None:
                    f.append("flight_missing")
                    continue
                d = F["dates"].get(fl.get("date"))
                if d is None:
                    f.append("flight_date_missing")
                elif d.get("status") != "available":
                    f.append("flight_unavailable")
        if name == "update_reservation_passengers" and r is not None \
                and isinstance(kw.get("passengers"), list) and len(kw["passengers"]) != len(r["passengers"]):
            f.append("passenger_count_mismatch")
        return f


def diff_class(name, kw, gold_writes):
    """classify how a suspect call differs from the closest gold action of the same tool"""
    same = [g for g in gold_writes if g["name"] == name]
    if not same:
        return "extra_call_tool_not_in_gold", []
    best = None
    for g in same:
        gk = g["kwargs"]
        keys = {k for k in set(gk) | set(kw)
                if canon(name, {k: gk.get(k)})[1] != canon(name, {k: kw.get(k)})[1]}
        if best is None or len(keys) < len(best):
            best = keys
    kinds = set()
    for k in best:
        kinds.add("id" if k in ID_KEYS else "item" if k in ITEM_KEYS else "payment" if k in PAY_KEYS else "other")
    if kinds == {"id"}:
        return "id_only", sorted(best)
    if "id" in kinds:
        return "id_plus_other", sorted(best)
    return "no_id_" + "_".join(sorted(kinds)) if kinds else "no_diff_found", sorted(best)


def short(m, n=300):
    c = m.get("content") or ""
    if m.get("tool_calls"):
        c += " [calls: " + json.dumps([t["function"] for t in m["tool_calls"]])[:200] + "]"
    return {"role": m["role"], "content": c[:n]}


def main():
    dbs = {
        "retail": {k: load(os.path.join(REPO, "tau_bench", "envs", "retail", "data", k + ".json"))
                   for k in ("orders", "users", "products")},
        "airline": {k: load(os.path.join(REPO, "tau_bench", "envs", "airline", "data", k + ".json"))
                    for k in ("flights", "reservations", "users")},
    }
    cases, stats = [], defaultdict(Counter)
    for fname, dom in FILES:
        runs = load(os.path.join(REPO, "historical_trajectories", fname + ".json"))
        probe = Probe(dom, dbs[dom])
        write_names = RETAIL_WRITE if dom == "retail" else AIRLINE_WRITE
        S = stats[fname]
        for run in runs:
            gold = run["info"]["task"]["actions"]
            gold_writes = [g for g in gold if g["name"] in write_names]
            gold_set = {canon(g["name"], g["kwargs"]) for g in gold_writes}
            traj, overlay, auth = run["traj"], {}, None
            S["runs"] += 1
            S["runs_reward0"] += run["reward"] == 0
            for i, name, kw, resp in extract_calls(traj, write_names):
                # track authenticated user from read-only calls
                if name in ("find_user_id_by_email", "find_user_id_by_name_zip") and resp and not is_err(resp):
                    auth = resp.strip()
                if name == "get_user_details" and dom == "airline" and resp and not is_err(resp):
                    auth = kw.get("user_id")
                if name not in write_names:
                    continue
                flags = probe.check(name, kw, auth, overlay)
                err = is_err(resp)
                label = "suspect" if (run["reward"] == 0 and canon(name, kw) not in gold_set) else "ok"
                dc, dkeys = diff_class(name, kw, gold_writes) if label == "suspect" else (None, [])
                has_id = any(k in ID_KEYS | PAY_KEYS or k in ("item_ids", "new_item_ids", "flights") for k in kw)
                S["write_calls"] += 1
                S["has_id_arg"] += has_id
                S[label] += 1
                S[label + "_flagged"] += bool(flags)
                S[label + "_env_error"] += err
                S[label + "_flagged_env_accepted"] += bool(flags) and not err
                S[label + "_unauth"] += auth is None
                if label == "suspect":
                    S["diff_" + dc] += 1
                    S["diff_flagged_" + dc] += bool(flags)
                for fl in flags:
                    S[f"flag_{label}_{fl}"] += 1
                case = {"src": fname, "domain": dom, "task_id": run["task_id"], "trial": run["trial"],
                        "reward": run["reward"], "tool": name, "kwargs": kw, "label": label,
                        "diff_class": dc, "diff_keys": dkeys, "flags": flags, "env_error": err,
                        "env_response": (resp or "")[:160], "auth_user": auth,
                        "context": [short(m) for m in traj[max(1, i - 3):i + 1]]}
                cases.append(case)
                if not err and resp:  # overlay the state change
                    try:
                        obj = json.loads(resp)
                        key = obj.get("order_id") or obj.get("reservation_id")
                        if key:
                            overlay[key] = obj
                    except Exception:
                        pass
    # keep file small: all suspect + a deterministic sample of ok
    sus = [c for c in cases if c["label"] == "suspect"]
    ok = [c for c in cases if c["label"] == "ok"]
    step = max(1, len(ok) // OK_SAMPLE)
    keep = sus + ok[::step][:OK_SAMPLE]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source_commit": "59a200c6d575d595120f1cb70fea53cef0632f6b",
                   "label_rule": "suspect = reward 0 and call not among gold write actions of the task",
                   "n_total_calls": len(cases), "n_suspect": len(sus), "n_ok": len(ok),
                   "ok_sampled_every": step, "cases": keep}, f)
    tot = Counter()
    for k, v in stats.items():
        tot.update(v)
        print("==", k)
        for kk in sorted(v):
            print(f"  {kk}: {v[kk]}")
    print("== TOTAL")
    for kk in sorted(tot):
        print(f"  {kk}: {tot[kk]}")
    print("cases.json bytes:", os.path.getsize(OUT))


if __name__ == "__main__":
    main()
