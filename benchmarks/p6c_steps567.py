"""
benchmarks/p6c_steps567.py
Prompt 6C Steps 5, 6, 7 (fast, deterministic, dev-only, no API calls):
  - Step 5: Conformal reporting from ask_policy.py (p05, p50, p95, mean, share <= alpha)
  - Step 6: Consensus vs number of models (k = 1, 2, 3, 5, 10, 20, 30) on BFCL
            for (a) all wrong arguments and (b) strong-error subset, 200 draws + cluster bootstrap CI
  - Step 7: Tau-bench accepted vs rejected calls state-lookup evaluation
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from analyze_consensus import canon  # noqa: E402
from scipy.stats import rankdata  # noqa: E402
import ask_policy  # noqa: E402
from decidability import label_bfcl  # noqa: E402
from stats import wilson_ci  # noqa: E402


def fast_auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Exact Mann-Whitney AUROC in O(n log n) via rankdata."""
    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(scores, method="average")
    u = float(ranks[labels].sum()) - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def fast_tpr_at_fbr(labels: np.ndarray, scores: np.ndarray, max_fbr: float) -> float:
    """Exact largest TPR with FBR <= max_fbr using sorted scores in O(n log n)."""
    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.0
    order = np.argsort(-scores, kind="mergesort")
    s_sorted = scores[order]
    l_sorted = labels[order]
    # Group ties: evaluate only at the end of each tied block
    tp_cum = np.cumsum(l_sorted)
    fp_cum = np.cumsum(~l_sorted)
    tie_ends = np.r_[np.nonzero(np.diff(s_sorted) != 0)[0], len(s_sorted) - 1]
    fbrs = fp_cum[tie_ends] / n_neg
    tprs = tp_cum[tie_ends] / n_pos
    valid = fbrs <= max_fbr
    return float(tprs[valid].max()) if valid.any() else 0.0


def step5_conformal():
    print("=" * 72)
    print("STEP 5: CONFORMAL REPORTING (ask_policy.py logic, dev data only)")
    print("=" * 72)
    from decidability import bfcl_call_status

    base_rows = ask_policy.build_rows()
    st = bfcl_call_status()
    strong_rows = [r for r in base_rows if st.get(r["test"] + "|" + r["model"], "correct") != "weak_only"]

    results = {}
    for label, rows in [("all_labels", base_rows), ("strong_errors", strong_rows)]:
        ok = np.array([r["ok"] for r in rows])
        cons = np.array([r["cons"] for r in rows])
        tests = np.array([r["test"] for r in rows])
        ut = np.unique(tests)
        rng = np.random.default_rng(0)  # identical seed to ask_policy.py

        print(f"\n### Subset: {label} (n_calls={len(rows)}, n_wrong={int((~ok).sum())})")
        print("| alpha | Rule | Mean ask (correct) | p05 / p50 / p95 ask | Splits <= alpha | Wrong caught (mean) | p05 / p50 / p95 caught |")
        print("|---|---|---|---|---|---|---|")

        sub_out = {}
        for alpha in (0.05, 0.10, 0.20):
            agg = defaultdict(list)
            for _ in range(1000):
                perm = rng.permutation(ut)
                half = set(perm[: len(ut) // 2].tolist())
                cal = np.array([t in half for t in tests])
                te = ~cal
                for name in ("consensus", "consensus_pac", "consensus_cluster", "consensus_boot"):
                    if name == "consensus_boot":
                        tau = ask_policy.boot_tau(cons[cal & ok], tests[cal & ok], alpha)
                    elif name == "consensus_cluster":
                        tau = ask_policy.cluster_tau(cons[cal & ok], tests[cal & ok], alpha)
                    elif name == "consensus_pac":
                        tau = ask_policy.pac_tau(cons[cal & ok], alpha)
                    else:
                        tau = ask_policy.conformal_tau(cons[cal & ok], alpha)
                    ask = cons >= tau
                    agg[name + "_rc"].append(float(ask[te & ok].mean()))
                    agg[name + "_cw"].append(float(ask[te & ~ok].mean()))

            alpha_res = {}
            for name, desc in [
                ("consensus", "item-level conformal"),
                ("consensus_pac", "item-level PAC (CP)"),
                ("consensus_cluster", "cluster Hoeffding"),
                ("consensus_boot", "cluster bootstrap"),
            ]:
                rc = np.array(agg[name + "_rc"])
                cw = np.array(agg[name + "_cw"])
                rc_q = np.percentile(rc, [5, 50, 95])
                cw_q = np.percentile(cw, [5, 50, 95])
                share = float((rc <= alpha).mean())
                alpha_res[name] = {
                    "mean_ask_correct": round(float(rc.mean()), 4),
                    "p05_p50_p95_ask": [round(float(x), 4) for x in rc_q],
                    "share_splits_within_alpha": round(share, 4),
                    "mean_wrong_caught": round(float(cw.mean()), 4),
                    "p05_p50_p95_caught": [round(float(x), 4) for x in cw_q],
                }
                print(
                    f"| {alpha:.2f} | {name} ({desc}) | {rc.mean()*100:.1f}% | "
                    f"{rc_q[0]*100:.1f}% / {rc_q[1]*100:.1f}% / {rc_q[2]*100:.1f}% | "
                    f"{share*100:.1f}% | {cw.mean()*100:.1f}% | "
                    f"{cw_q[0]*100:.1f}% / {cw_q[1]*100:.1f}% / {cw_q[2]*100:.1f}% |"
                )
            sub_out[str(alpha)] = alpha_res
        results[label] = sub_out
    return results


def step6_consensus_curve():
    print("\n" + "=" * 72)
    print("STEP 6: CONSENSUS vs NUMBER OF MODELS (BFCL cross-model)")
    print("=" * 72)
    d = json.loads((ROOT / "benchmarks/data/bfcl/consensus_cases.json").read_text(encoding="utf-8"))
    idx = d["consensus_index"]
    all_models = sorted(d["meta"]["models"])

    # Identify weak argument instances using decidability.py label_bfcl()
    dec_rows = label_bfcl()
    weak_keys = set()
    for r in dec_rows:
        if not r["correct"] and str(r.get("class", "")).startswith("WEAK_"):
            # r["item"] is f"{test_id}|{model}|{gold_call_index}|{arg}"
            parts = r["item"].split("|")
            slot = f"{parts[0]}|{parts[2]}|{parts[3]}"
            weak_keys.add((slot, parts[1]))

    # Pre-encode slots -> {model_idx: (canon_val_id, is_wrong, is_weak)}
    model_to_i = {m: i for i, m in enumerate(all_models)}
    M = len(all_models)
    slots = []
    val_vocab = {}

    for slot, pm in idx.items():
        if len(pm) < 5:
            continue  # match analyze_consensus.py slot filter
        test_id = slot.split("|")[0]
        row = []
        for m, info in pm.items():
            mi = model_to_i[m]
            cv = canon(info["value"])
            vid = val_vocab.setdefault(cv, len(val_vocab))
            w = info["label"] != "correct"
            wk = (slot, m) in weak_keys
            row.append((mi, vid, w, wk))
        slots.append((test_id, row))

    # Build dense matrices (S x M)
    S = len(slots)
    val_mat = np.full((S, M), -1, dtype=np.int32)
    wrong_mat = np.zeros((S, M), dtype=bool)
    weak_mat = np.zeros((S, M), dtype=bool)
    present_mat = np.zeros((S, M), dtype=bool)
    slot_tests = np.array([s[0] for s in slots])
    ut = np.unique(slot_tests)
    test_to_slot_indices = [np.where(slot_tests == t)[0] for t in ut]
    n_tests = len(ut)

    for si, (_, row) in enumerate(slots):
        for mi, vid, w, wk in row:
            present_mat[si, mi] = True
            val_mat[si, mi] = vid
            wrong_mat[si, mi] = w
            weak_mat[si, mi] = wk

    K_LIST = [1, 2, 3, 5, 10, 20, 30]
    N_DRAWS = 200
    rng = np.random.default_rng(42)

    def eval_subset_cluster(model_idx, slot_indices, strong_only: bool):
        p = present_mat[np.ix_(slot_indices, model_idx)]
        v = val_mat[np.ix_(slot_indices, model_idx)]
        w = wrong_mat[np.ix_(slot_indices, model_idx)]
        wk = weak_mat[np.ix_(slot_indices, model_idx)]

        # Valid cells: present, and at least 2 models present in the slot for this subset
        n_pres = p.sum(axis=1, keepdims=True)
        valid = p & (n_pres >= 2)
        if strong_only:
            # Drop weak-only wrong instances (matches strong-error filtering)
            valid = valid & (~wk)

        if not valid.any():
            return float("nan"), float("nan"), float("nan")

        # Count how many models in subset share the exact same canonical value in each slot
        # v is S' x k. Compare v[:, :, None] == v[:, None, :]
        same = (v[:, :, None] == v[:, None, :]) & p[:, :, None] & p[:, None, :]
        agree_cnt = same.sum(axis=2) - 1  # exclude self
        dis = 1.0 - agree_cnt / np.maximum(n_pres - 1, 1)

        scores = dis[valid]
        labels = w[valid]
        if not labels.any() or (~labels).sum() == 0:
            return float("nan"), float("nan"), float("nan")
        au = fast_auroc(labels, scores)
        d5 = fast_tpr_at_fbr(labels, scores, 0.05)
        d10 = fast_tpr_at_fbr(labels, scores, 0.10)
        return au, d5, d10

    all_slot_idx = np.arange(S)
    out = {}

    for mode, strong_only in [("all_wrong", False), ("strong_errors", True)]:
        print(f"\n### Mode: {mode}")
        print("| k (models) | AUROC [95% CI] | Det @ 5% FBR [95% CI] | Det @ 10% FBR [95% CI] |")
        print("|---|---|---|---|")
        mode_res = []
        for k in K_LIST:
            if k == 1:
                # 1 model has 0 peers; peer disagreement undefined
                print("| 1 | N/A (0 peers; trivial 0.500) | N/A | N/A |")
                mode_res.append({"k": 1, "note": "0 peers; peer disagreement undefined"})
                continue

            if k == 30:
                m_idx = np.arange(M)
                au_pt, d5_pt, d10_pt = eval_subset_cluster(m_idx, all_slot_idx, strong_only)
                # Cluster bootstrap by conversation (B=1000)
                boot_au, boot_d5, boot_d10 = [], [], []
                for _ in range(1000):
                    picks = rng.integers(0, n_tests, size=n_tests)
                    b_slots = np.concatenate([test_to_slot_indices[p] for p in picks])
                    au, d5, d10 = eval_subset_cluster(m_idx, b_slots, strong_only)
                    if not math.isnan(au):
                        boot_au.append(au)
                        boot_d5.append(d5)
                        boot_d10.append(d10)
            else:
                # 200 draws: each draw samples k models AND resamples conversations (cluster bootstrap)
                # Also compute point mean across 200 model draws on original 200 conversations
                pt_au, pt_d5, pt_d10 = [], [], []
                boot_au, boot_d5, boot_d10 = [], [], []
                for _ in range(N_DRAWS):
                    m_idx = rng.choice(M, size=k, replace=False)
                    au, d5, d10 = eval_subset_cluster(m_idx, all_slot_idx, strong_only)
                    if not math.isnan(au):
                        pt_au.append(au)
                        pt_d5.append(d5)
                        pt_d10.append(d10)
                    picks = rng.integers(0, n_tests, size=n_tests)
                    b_slots = np.concatenate([test_to_slot_indices[p] for p in picks])
                    bau, bd5, bd10 = eval_subset_cluster(m_idx, b_slots, strong_only)
                    if not math.isnan(bau):
                        boot_au.append(bau)
                        boot_d5.append(bd5)
                        boot_d10.append(bd10)
                au_pt = float(np.mean(pt_au))
                d5_pt = float(np.mean(pt_d5))
                d10_pt = float(np.mean(pt_d10))

            au_ci = np.percentile(boot_au, [2.5, 97.5])
            d5_ci = np.percentile(boot_d5, [2.5, 97.5])
            d10_ci = np.percentile(boot_d10, [2.5, 97.5])
            print(
                f"| {k} | {au_pt:.3f} [{au_ci[0]:.3f}, {au_ci[1]:.3f}] | "
                f"{d5_pt*100:.1f}% [{d5_ci[0]*100:.1f}%, {d5_ci[1]*100:.1f}%] | "
                f"{d10_pt*100:.1f}% [{d10_ci[0]*100:.1f}%, {d10_ci[1]*100:.1f}%] |"
            )
            mode_res.append({
                "k": k,
                "auroc": round(au_pt, 4),
                "auroc_ci95": [round(float(au_ci[0]), 4), round(float(au_ci[1]), 4)],
                "det_fbr5": round(d5_pt, 4),
                "det_fbr5_ci95": [round(float(d5_ci[0]), 4), round(float(d5_ci[1]), 4)],
                "det_fbr10": round(d10_pt, 4),
                "det_fbr10_ci95": [round(float(d10_ci[0]), 4), round(float(d10_ci[1]), 4)],
            })
        out[mode] = mode_res
    return out


def step7_taubench():
    print("\n" + "=" * 72)
    print("STEP 7: TAU-BENCH REJECTED CALLS")
    print("=" * 72)
    tau = json.loads((ROOT / "benchmarks/data/taubench/cases.json").read_text(encoding="utf-8"))
    cases = tau["cases"]

    accepted = [c for c in cases if not c.get("env_error", False)]
    rejected = [c for c in cases if c.get("env_error", False)]
    # Check also for no-op / error strings in env_response even if env_error=False
    resp_err_in_acc = [
        c for c in accepted
        if isinstance(c.get("env_response"), str) and ("error" in c["env_response"].lower()[:20] or "no-op" in c["env_response"].lower())
    ]

    EXISTENCE_FLAGS = {"order_missing", "user_missing", "reservation_missing", "payment_not_found", "item_not_in_order", "new_item_missing"}

    def stats_for(sub):
        n = len(sub)
        any_flag = sum(1 for c in sub if c.get("flags"))
        exist_flag = sum(1 for c in sub if any(f in EXISTENCE_FLAGS for f in (c.get("flags") or [])))
        suspect = [c for c in sub if c.get("label") == "suspect"]
        ok = [c for c in sub if c.get("label") == "ok"]
        susp_any = sum(1 for c in suspect if c.get("flags"))
        susp_exist = sum(1 for c in suspect if any(f in EXISTENCE_FLAGS for f in (c.get("flags") or [])))
        ok_any = sum(1 for c in ok if c.get("flags"))
        ok_exist = sum(1 for c in ok if any(f in EXISTENCE_FLAGS for f in (c.get("flags") or [])))
        flag_counts = Counter(f for c in sub for f in (c.get("flags") or []))
        return {
            "n_total": n,
            "n_suspect": len(suspect),
            "n_ok": len(ok),
            "any_probe_flag": any_flag,
            "existence_flag": exist_flag,
            "suspect_any_flag": susp_any,
            "suspect_existence_flag": susp_exist,
            "suspect_any_ci": [round(x, 4) for x in wilson_ci(susp_any, len(suspect))] if suspect else None,
            "ok_any_flag": ok_any,
            "ok_existence_flag": ok_exist,
            "flag_breakdown": dict(flag_counts),
        }

    acc_stats = stats_for(accepted)
    rej_stats = stats_for(rejected)

    print(f"Total stored cases: {len(cases)} (from {tau.get('n_total_calls')} total calls: {tau.get('n_suspect')} suspect + {tau.get('n_ok')} ok sampled 1-in-{tau.get('ok_sampled_every')})")
    print(f"Accepted (env_error=False): {acc_stats['n_total']} ({acc_stats['n_suspect']} suspect, {acc_stats['n_ok']} ok)")
    print(f"  Flagged by Probe (any flag)      : {acc_stats['any_probe_flag']} / {acc_stats['n_total']} (suspect: {acc_stats['suspect_any_flag']}/{acc_stats['n_suspect']})")
    print(f"  Flagged by existence-only subset : {acc_stats['existence_flag']} / {acc_stats['n_total']}")
    print(f"  (Accepted calls with 'error' in prefix of env_response: {len(resp_err_in_acc)})")
    print(f"Rejected (env_error=True) : {rej_stats['n_total']} ({rej_stats['n_suspect']} suspect, {rej_stats['n_ok']} ok)")
    print(f"  Flagged by Probe (any flag)      : {rej_stats['any_probe_flag']} / {rej_stats['n_total']} ({rej_stats['any_probe_flag']/rej_stats['n_total']*100:.1f}%)")
    print(f"    - among suspect: {rej_stats['suspect_any_flag']}/{rej_stats['n_suspect']} = {rej_stats['suspect_any_flag']/rej_stats['n_suspect']*100:.1f}% {rej_stats['suspect_any_ci']}")
    print(f"    - among ok     : {rej_stats['ok_any_flag']}/{rej_stats['n_ok']} = {rej_stats['ok_any_flag']/rej_stats['n_ok']*100:.1f}%")
    print(f"  Flagged by existence-only subset : {rej_stats['existence_flag']} / {rej_stats['n_total']} ({rej_stats['existence_flag']/rej_stats['n_total']*100:.1f}%)")
    print(f"  Flag breakdown on rejected calls : {rej_stats['flag_breakdown']}")
    return {"accepted": acc_stats, "rejected": rej_stats, "resp_err_in_acc": len(resp_err_in_acc)}


if __name__ == "__main__":
    s5 = step5_conformal()
    s6 = step6_consensus_curve()
    s7 = step7_taubench()
    out_path = ROOT / "benchmarks" / "p6c_steps567_dev.json"
    out_path.write_text(json.dumps({"step5": s5, "step6": s6, "step7": s7}, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
