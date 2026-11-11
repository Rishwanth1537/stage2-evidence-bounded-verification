"""
benchmarks/p6c_steps134.py
Prompt 6C Steps 1, 3, and 4:
  - Step 1: Recompute strict FBR for baseline (premise only) and provenance
    (premise + earlier_tool_outputs) under BOTH denominators (all 2,423 calls
    and 2,114 calls with args) with fast cluster-bootstrap CIs (B=10,000),
    plus the same on X1-DEV (1,697 / 1,480).
  - Step 3: X1-DEV residual taxonomy and fuzzy threshold sweep.
  - Step 4: Missing cost side on X1-DEV ONLY:
    synthetic absent-value (reusing make_argground_bench.py mutate logic) and
    visible-but-wrong (same field type from user turn or earlier tool output
    of the same task), across implemented evidence configs (i) user text only
    and (ii) + earlier tool outputs, and across fuzzy sweep thresholds
    [0.88, 0.82, 0.76, 0.70, 0.65].
    Configs (iii) schema defaults, (iv) derivation rules, (v) all are NOT
    implemented (Prompt 6 v2 not yet run) and are reported as missing.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from server.pipeline.arg_ground import check_arguments, numbers_in_detailed  # noqa: E402
from benchmarks.provenance_grounding import build_provenance_context  # noqa: E402
from benchmarks.splits import load_split, _get_mcpatlas_x1_clusters  # noqa: E402
from benchmarks.stats import fast_cluster_bootstrap_ratio, wilson_ci  # noqa: E402
from benchmarks.residual_analysis import is_grounded_fast, classify_arg, ORDERED_CATS  # noqa: E402
from benchmarks.fuzzy_sweep import score_arg, THRESHOLDS  # noqa: E402
from benchmarks.make_argground_bench import appears, norm  # noqa: E402


def _cid_of(c: Dict[str, Any]) -> str:
    return str(c.get("cluster_id") or c.get("task_id") or c["id"].rsplit("-", 1)[0])


def _worker_eval_call(item: Tuple[str, str, Dict[str, Any], str, List[str]]) -> Tuple[str, str, int, int, int]:
    cid_call, cluster_id, args, premise, earlier = item
    n_args = len(args)
    if n_args == 0:
        return cid_call, cluster_id, 0, 0, 0
    vb = check_arguments(args, premise)
    b_base = int(any(v.verdict == "UNGROUNDED" for v in vb))
    ev = build_provenance_context(premise, earlier)
    vp = check_arguments(args, ev)
    b_prov = int(any(v.verdict == "UNGROUNDED" for v in vp))
    return cid_call, cluster_id, n_args, b_base, b_prov


def _worker_eval_pair(item: Tuple[str, Dict[str, Any], str, str]) -> Tuple[str, int, int]:
    """Evaluate one call's args against (premise, evidence)."""
    cluster_id, args, premise, evidence = item
    if not args:
        return cluster_id, 0, 0
    try:
        vb = check_arguments(args, premise)
        db = int(any(v.verdict == "UNGROUNDED" for v in vb))
    except Exception:
        db = 0
    try:
        vp = check_arguments(args, evidence)
        dp = int(any(v.verdict == "UNGROUNDED" for v in vp))
    except Exception:
        dp = 0
    return cluster_id, db, dp


def cluster_ratio_ci(flags: List[int], cluster_ids: List[str], B: int = 10000, seed: int = 0) -> Dict[str, Any]:
    if not flags:
        return {"n": 0, "k": 0, "rate": None, "ci95": [None, None]}
    c_num: Dict[str, int] = defaultdict(int)
    c_den: Dict[str, int] = defaultdict(int)
    for f, cid in zip(flags, cluster_ids):
        c_num[cid] += int(f)
        c_den[cid] += 1
    keys = sorted(c_den.keys())
    num_k = np.array([c_num[k] for k in keys], dtype=float)
    den_k = np.array([c_den[k] for k in keys], dtype=float)
    est, lo, hi = fast_cluster_bootstrap_ratio(num_k, den_k, B=B, seed=seed)
    return {
        "n": len(flags),
        "k": int(sum(flags)),
        "rate": round(est, 4),
        "ci95": [round(lo, 4), round(hi, 4)],
    }


def _is_valid_str_candidate(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    s = v.strip()
    if len(s) < 2 or len(s) > 60:
        return False
    if not any(ch.isalnum() for ch in s):
        return False
    # Avoid numeric-looking strings that trigger arg_ground float coercion on commas
    if re.fullmatch(r"[\d,\s.\-]+", s):
        return False
    return True


def _extract_json_strings(obj: Any, out: List[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _extract_json_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _extract_json_strings(v, out)
    elif isinstance(obj, str) and _is_valid_str_candidate(obj):
        out.append(obj.strip())


def _extract_visible_candidates(premise: str, earlier: List[str]) -> Tuple[List[str], List[float]]:
    """Extract plausible same-type string and numeric candidates visible in premise or earlier outputs."""
    str_cands: List[str] = []
    # 1) Parse JSON structures in earlier tool outputs
    for out_txt in earlier:
        t = str(out_txt).strip()
        if t.startswith("{") or t.startswith("["):
            try:
                parsed = json.loads(t)
                _extract_json_strings(parsed, str_cands)
            except Exception:
                pass
    # 2) Quoted strings in earlier tool outputs and premise
    full_text = premise + "\n" + "\n".join(str(x) for x in earlier)
    for m in re.finditer(r'["\']([^"\'\n\r]{2,60})["\']', full_text):
        cand = m.group(1).strip()
        if _is_valid_str_candidate(cand):
            str_cands.append(cand)
    # 3) Capitalized / identifier-like tokens in premise + earlier outputs
    for m in re.finditer(r'\b([A-Za-z][A-Za-z0-9_\-./]{2,40})\b', full_text):
        cand = m.group(1).strip()
        if _is_valid_str_candidate(cand):
            str_cands.append(cand)

    # Deduplicate preserving order
    seen_s = set()
    uniq_str = []
    for s in str_cands:
        nl = norm(s)
        if nl and nl not in seen_s:
            seen_s.add(nl)
            uniq_str.append(s)

    nums, _ = numbers_in_detailed(full_text)
    uniq_num = sorted(x for x in nums if isinstance(x, (int, float)) and abs(x) < 1e12)
    return uniq_str, uniq_num


def step1_denominators(max_workers: int = 4) -> Dict[str, Any]:
    print("=" * 72)
    print("STEP 1: DENOMINATORS (Full 2,423 MCP-Atlas & X1-DEV, B=10,000)")
    print("=" * 72)
    data_path = ROOT / "benchmarks" / "data" / "mcpatlas" / "cases_v2.json"
    all_cases = json.loads(data_path.read_text(encoding="utf-8"))["cases"]
    dev_clusters, _ = _get_mcpatlas_x1_clusters()

    work = [
        (
            c["id"],
            _cid_of(c),
            (c.get("call") or {}).get("arguments") or {},
            c.get("premise") or "",
            c.get("earlier_tool_outputs") or [],
        )
        for c in all_cases
    ]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        rows = list(ex.map(_worker_eval_call, work, chunksize=50))
    print(f"Evaluated {len(rows)} calls with check_arguments in {time.perf_counter() - t0:.1f}s")

    def summarize(subset_rows):
        all_cids = [r[1] for r in subset_rows]
        all_base = [r[3] for r in subset_rows]
        all_prov = [r[4] for r in subset_rows]
        arg_rows = [r for r in subset_rows if r[2] > 0]
        arg_cids = [r[1] for r in arg_rows]
        arg_base = [r[3] for r in arg_rows]
        arg_prov = [r[4] for r in arg_rows]
        return {
            "all_calls_baseline": cluster_ratio_ci(all_base, all_cids, B=10000, seed=0),
            "all_calls_provenance": cluster_ratio_ci(all_prov, all_cids, B=10000, seed=0),
            "with_args_baseline": cluster_ratio_ci(arg_base, arg_cids, B=10000, seed=0),
            "with_args_provenance": cluster_ratio_ci(arg_prov, arg_cids, B=10000, seed=0),
        }

    full_res = summarize(rows)
    dev_rows = [r for r in rows if r[1] in dev_clusters]
    dev_res = summarize(dev_rows)

    for scope, res in [("FULL DATASET (2,423 all / 2,114 with args)", full_res),
                       ("X1-DEV ONLY (1,697 all / 1,480 with args)", dev_res)]:
        print(f"\n### {scope}")
        print("| Denominator | System | Blocked | Total | Rate | Cluster-Boot 95% CI (B=10,000) |")
        print("|---|---|---|---|---|---|")
        for key, d_label, s_label in [
            ("all_calls_baseline", "All calls", "Baseline (premise only)"),
            ("all_calls_provenance", "All calls", "Provenance (+ earlier outputs)"),
            ("with_args_baseline", "Calls with args", "Baseline (premise only)"),
            ("with_args_provenance", "Calls with args", "Provenance (+ earlier outputs)"),
        ]:
            d = res[key]
            print(f"| {d_label} | {s_label} | {d['k']} | {d['n']} | {d['rate']*100:.1f}% | [{d['ci95'][0]*100:.1f}%, {d['ci95'][1]*100:.1f}%] |")

    return {"full": full_res, "x1_dev": dev_res}


def step3_x1_dev_taxonomy_and_sweep(dev_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    print("\n" + "=" * 72)
    print("STEP 3: X1-DEV ONLY RESIDUAL TAXONOMY & FUZZY THRESHOLD SWEEP")
    print("=" * 72)

    # 3a: Residual taxonomy on X1-DEV (residual_analysis.py logic)
    arg_cats: Counter = Counter()
    call_dom: Counter = Counter()
    first_dom: Counter = Counter()
    later_dom: Counter = Counter()
    names_ungrounded: Counter = Counter()
    n_residual_calls = 0
    n_with_args = 0

    for c in dev_cases:
        args = (c.get("call") or {}).get("arguments") or {}
        if not args:
            continue
        n_with_args += 1
        premise = c.get("premise") or ""
        earlier = c.get("earlier_tool_outputs") or []
        step_idx = c.get("step_index", 1)
        ev = build_provenance_context(premise, earlier)

        cats = []
        for k, v in args.items():
            if isinstance(v, bool) or v is None:
                continue
            sv = str(v)
            if not sv.strip():
                continue
            if not is_grounded_fast(sv, ev):
                cat = classify_arg(k, sv)
                arg_cats[cat] += 1
                names_ungrounded[k] += 1
                cats.append(cat)
        if cats:
            n_residual_calls += 1
            dom = Counter(cats).most_common(1)[0][0]
            call_dom[dom] += 1
            if step_idx == 1:
                first_dom[dom] += 1
            else:
                later_dom[dom] += 1

    total_res_args = sum(arg_cats.values())
    print(f"\nResidual Taxonomy on X1-DEV (fast substring heuristic; {n_residual_calls}/{n_with_args} calls, {total_res_args} args):")
    print("| Category | Args | Share | Wilson 95% CI | Residual calls (dom) |")
    print("|---|---|---|---|---|")
    tax_rows = {}
    for cat in ORDERED_CATS:
        cnt = arg_cats[cat]
        sh = cnt / total_res_args if total_res_args else 0.0
        lo, hi = wilson_ci(cnt, total_res_args) if total_res_args else (0.0, 0.0)
        print(f"| {cat} | {cnt} | {sh*100:.1f}% | [{lo*100:.1f}%, {hi*100:.1f}%] | {call_dom[cat]} |")
        tax_rows[cat] = {"args": cnt, "share": round(sh, 4), "wilson95": [round(lo, 4), round(hi, 4)], "calls_dom": call_dom[cat]}

    # 3b: Fuzzy sweep on X1-DEV (fuzzy_sweep.py logic)
    call_scores_prov = []
    call_cids = []
    for c in dev_cases:
        args = (c.get("call") or {}).get("arguments") or {}
        if not args:
            continue
        str_args = {k: str(v) for k, v in args.items() if isinstance(v, str) and str(v).strip() and not isinstance(v, bool)}
        if not str_args:
            continue
        ev = build_provenance_context(c.get("premise") or "", c.get("earlier_tool_outputs") or [])
        call_scores_prov.append(min(score_arg(k, v, ev) for k, v in str_args.items()))
        call_cids.append(_cid_of(c))

    print(f"\nFuzzy Token-Recall Sweep on X1-DEV (clean FBR, n={len(call_scores_prov)} calls with string args):")
    print("| Threshold | Blocked | Clean FBR | Cluster-Boot 95% CI |")
    print("|---|---|---|---|")
    sweep_rows = []
    for thr in THRESHOLDS:
        flags = [int(s < thr) for s in call_scores_prov]
        st = cluster_ratio_ci(flags, call_cids, B=10000, seed=0)
        print(f"| {thr:.2f} | {st['k']} | {st['rate']*100:.1f}% | [{st['ci95'][0]*100:.1f}%, {st['ci95'][1]*100:.1f}%] |")
        sweep_rows.append({"threshold": thr, **st})

    return {
        "n_with_args": n_with_args,
        "n_residual_calls": n_residual_calls,
        "total_residual_args": total_res_args,
        "taxonomy": tax_rows,
        "top_names": names_ungrounded.most_common(10),
        "fuzzy_sweep_clean": sweep_rows,
    }


def step4_cost_side(dev_cases: List[Dict[str, Any]], max_workers: int = 4) -> Dict[str, Any]:
    print("\n" + "=" * 72)
    print("STEP 4: THE MISSING COST SIDE (X1-DEV ONLY, SYNTHETIC INJECTIONS)")
    print("=" * 72)
    rng = random.Random(42)

    # Build pool of valid string values from X1-DEV (make_argground_bench.py style)
    pool: Dict[Any, List[str]] = defaultdict(list)
    for c in dev_cases:
        call = c.get("call") or {}
        tname = call.get("name", "")
        for k, v in (call.get("arguments") or {}).items():
            if _is_valid_str_candidate(v):
                pool[(tname, k)].append(v.strip())
                pool[("*", k)].append(v.strip())

    # 1. Build ABSENT-VALUE synthetic injections (reusing make_argground_bench.py logic)
    absent_items = []
    # 2. Build VISIBLE-BUT-WRONG synthetic injections (same field type, visible in user turn or earlier tool outputs)
    visible_items = []

    for c in dev_cases:
        call = c.get("call") or {}
        args = call.get("arguments") or {}
        if not args:
            continue
        tname = call.get("name", "")
        premise = c.get("premise") or ""
        earlier = c.get("earlier_tool_outputs") or []
        ev = build_provenance_context(premise, earlier)
        cid = _cid_of(c)

        # Eligible keys: checkable types (str non-empty valid, int, float; exclude bool)
        keys = [
            k for k, v in args.items()
            if (isinstance(v, (int, float)) and not isinstance(v, bool))
            or _is_valid_str_candidate(v)
        ]

        # --- Absent-value mutation ---
        keys_abs = list(keys)
        rng.shuffle(keys_abs)
        for k in keys_abs:
            v = args[k]
            new_val = None
            kind = None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cands = [v * 10 + 7, v + rng.choice([13, 37, 99, 251]), v * 2 + 3]
                rng.shuffle(cands)
                for cand in cands:
                    cand = int(cand) if isinstance(v, int) else round(float(cand), 2)
                    if cand != v and not appears(cand, ev):
                        new_val, kind = cand, "number_shift"
                        break
            else:
                options = [
                    x for x in pool.get((tname, k), []) + pool.get(("*", k), [])
                    if norm(x) != norm(v) and not appears(x, ev)
                ]
                if options:
                    new_val, kind = rng.choice(options), "string_swap"
            if new_val is not None:
                absent_items.append({
                    "id": c["id"],
                    "cluster_id": cid,
                    "orig_args": args,
                    "inj_args": {**args, k: new_val},
                    "mut_key": k,
                    "mut_type": "num" if isinstance(v, (int, float)) else "str",
                    "kind": kind,
                    "premise": premise,
                    "evidence": ev,
                })
                break

        # --- Visible-but-wrong mutation ---
        vis_strs, vis_nums = _extract_visible_candidates(premise, earlier)
        keys_vis = list(keys)
        rng.shuffle(keys_vis)
        for k in keys_vis:
            v = args[k]
            new_val = None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cands = [
                    (int(x) if isinstance(v, int) and float(x).is_integer() else x)
                    for x in vis_nums
                    if abs(float(x) - float(v)) > 1e-6
                ]
                if cands:
                    new_val = rng.choice(cands)
            else:
                nv = norm(v)
                cands = [
                    x for x in vis_strs
                    if norm(x) != nv and norm(x) not in nv and nv not in norm(x)
                ]
                if cands:
                    new_val = rng.choice(cands)
            if new_val is not None:
                visible_items.append({
                    "id": c["id"],
                    "cluster_id": cid,
                    "orig_args": args,
                    "inj_args": {**args, k: new_val},
                    "mut_key": k,
                    "mut_type": "num" if isinstance(v, (int, float)) else "str",
                    "premise": premise,
                    "evidence": ev,
                })
                break

    print(f"Eligible synthetic injections on X1-DEV (out of 1,480 calls with args):")
    print(f"  Absent-value (SYNTHETIC)     : {len(absent_items)} calls "
          f"(str={sum(1 for x in absent_items if x['mut_type']=='str')}, num={sum(1 for x in absent_items if x['mut_type']=='num')})")
    print(f"  Visible-but-wrong (SYNTHETIC): {len(visible_items)} calls "
          f"(str={sum(1 for x in visible_items if x['mut_type']=='str')}, num={sum(1 for x in visible_items if x['mut_type']=='num')})")

    # Evaluate check_arguments (FUZZY=0.88) for config (i) premise-only and (ii) + earlier_tool_outputs
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        abs_clean_res = list(ex.map(_worker_eval_pair, [(x["cluster_id"], x["orig_args"], x["premise"], x["evidence"]) for x in absent_items], chunksize=40))
        abs_inj_res   = list(ex.map(_worker_eval_pair, [(x["cluster_id"], x["inj_args"],  x["premise"], x["evidence"]) for x in absent_items], chunksize=40))
        vis_clean_res = list(ex.map(_worker_eval_pair, [(x["cluster_id"], x["orig_args"], x["premise"], x["evidence"]) for x in visible_items], chunksize=40))
        vis_inj_res   = list(ex.map(_worker_eval_pair, [(x["cluster_id"], x["inj_args"],  x["premise"], x["evidence"]) for x in visible_items], chunksize=40))
    print(f"Evaluated check_arguments across synthetic sets in {time.perf_counter() - t0:.1f}s")

    # Summarize configs (i) and (ii)
    def summ_pair(clean_res, inj_res):
        cids = [r[0] for r in clean_res]
        return {
            "cfg_i_clean_fbr": cluster_ratio_ci([r[1] for r in clean_res], cids),
            "cfg_i_det": cluster_ratio_ci([r[1] for r in inj_res], cids),
            "cfg_ii_clean_fbr": cluster_ratio_ci([r[2] for r in clean_res], cids),
            "cfg_ii_det": cluster_ratio_ci([r[2] for r in inj_res], cids),
        }

    abs_summary = summ_pair(abs_clean_res, abs_inj_res)
    vis_summary = summ_pair(vis_clean_res, vis_inj_res)

    print("\n### Evidence Configurations (i)-(v) on X1-DEV (check_arguments, FUZZY=0.88):")
    print("| Config | Absent-Val Eligible | Absent Det [CI] | Clean FBR on Absent-Set [CI] | Visible-Wrong Eligible | Visible-Wrong Det [CI] | Clean FBR on Visible-Set [CI] |")
    print("|---|---|---|---|---|---|---|")
    for cfg_name, k_det, k_cfb in [
        ("(i) User text only", "cfg_i_det", "cfg_i_clean_fbr"),
        ("(ii) + Earlier tool outputs", "cfg_ii_det", "cfg_ii_clean_fbr"),
    ]:
        ad, ac = abs_summary[k_det], abs_summary[k_cfb]
        vd, vc = vis_summary[k_det], vis_summary[k_cfb]
        print(
            f"| {cfg_name} | {ad['n']} | {ad['rate']*100:.1f}% [{ad['ci95'][0]*100:.1f}, {ad['ci95'][1]*100:.1f}] | "
            f"{ac['rate']*100:.1f}% [{ac['ci95'][0]*100:.1f}, {ac['ci95'][1]*100:.1f}] | "
            f"{vd['n']} | {vd['rate']*100:.1f}% [{vd['ci95'][0]*100:.1f}, {vd['ci95'][1]*100:.1f}] | "
            f"{vc['rate']*100:.1f}% [{vc['ci95'][0]*100:.1f}, {vc['ci95'][1]*100:.1f}] |"
        )
    for cfg_name in ["(iii) + Schema defaults", "(iv) + Derivation rules", "(v) All"]:
        print(f"| {cfg_name} | NOT IMPLEMENTED (Prompt 6 v2 not run) | - | - | - | - | - |")

    # Now run the fuzzy sweep (token_recall on string args) across thresholds [0.88, 0.82, 0.76, 0.70, 0.65]
    # for both (i) user text only and (ii) + earlier tool outputs
    def min_token_score(args: Dict[str, Any], text: str) -> Optional[float]:
        s_args = {k: str(v) for k, v in args.items() if isinstance(v, str) and str(v).strip() and not isinstance(v, bool)}
        if not s_args:
            return None
        return min(score_arg(k, v, text) for k, v in s_args.items())

    # Precompute scores on clean, absent (string-mutated), visible-but-wrong (string-mutated)
    clean_str_records = []
    for c in dev_cases:
        args = (c.get("call") or {}).get("arguments") or {}
        prem = c.get("premise") or ""
        ev = build_provenance_context(prem, c.get("earlier_tool_outputs") or [])
        s_i = min_token_score(args, prem)
        s_ii = min_token_score(args, ev)
        if s_i is not None:
            clean_str_records.append((_cid_of(c), s_i, s_ii))

    abs_str_records = [
        (x["cluster_id"], min_token_score(x["inj_args"], x["premise"]), min_token_score(x["inj_args"], x["evidence"]))
        for x in absent_items if x["mut_type"] == "str"
    ]
    vis_str_records = [
        (x["cluster_id"], min_token_score(x["inj_args"], x["premise"]), min_token_score(x["inj_args"], x["evidence"]))
        for x in visible_items if x["mut_type"] == "str"
    ]

    print(f"\n### Fuzzy Sweep Detection vs Clean FBR on X1-DEV (token_recall on string args; clean n={len(clean_str_records)}, absent str n={len(abs_str_records)}, visible-wrong str n={len(vis_str_records)}):")
    print("| Config | Threshold | Clean FBR [CI] | Absent Det [CI] | Visible-Wrong Det [CI] | Precision (1:1 Absent vs Clean) |")
    print("|---|---|---|---|---|---|")
    sweep_cost_rows = []
    for cfg_idx, cfg_label in [(1, "(i) User text only"), (2, "(ii) + Earlier outputs")]:
        for thr in THRESHOLDS:
            c_flags = [int(r[cfg_idx] < thr) for r in clean_str_records]
            c_cids = [r[0] for r in clean_str_records]
            a_flags = [int(r[cfg_idx] < thr) for r in abs_str_records]
            a_cids = [r[0] for r in abs_str_records]
            v_flags = [int(r[cfg_idx] < thr) for r in vis_str_records]
            v_cids = [r[0] for r in vis_str_records]

            c_st = cluster_ratio_ci(c_flags, c_cids, B=10000, seed=0)
            a_st = cluster_ratio_ci(a_flags, a_cids, B=10000, seed=0)
            v_st = cluster_ratio_ci(v_flags, v_cids, B=10000, seed=0)
            # Precision under equal prevalence (TPR / (TPR + FPR))
            tpr = a_st["rate"] or 0.0
            fpr = c_st["rate"] or 0.0
            prec_bal = tpr / (tpr + fpr) if (tpr + fpr) > 0 else 0.0
            print(
                f"| {cfg_label} | {thr:.2f} | {c_st['rate']*100:.1f}% [{c_st['ci95'][0]*100:.1f}, {c_st['ci95'][1]*100:.1f}] | "
                f"{a_st['rate']*100:.1f}% [{a_st['ci95'][0]*100:.1f}, {a_st['ci95'][1]*100:.1f}] | "
                f"{v_st['rate']*100:.1f}% [{v_st['ci95'][0]*100:.1f}, {v_st['ci95'][1]*100:.1f}] | "
                f"{prec_bal*100:.1f}% |"
            )
            sweep_cost_rows.append({
                "config": cfg_label,
                "threshold": thr,
                "clean_fbr": c_st,
                "absent_det": a_st,
                "visible_det": v_st,
                "precision_balanced": round(prec_bal, 4),
            })

    return {
        "absent_eligible": len(absent_items),
        "visible_eligible": len(visible_items),
        "absent_check_arguments": abs_summary,
        "visible_check_arguments": vis_summary,
        "fuzzy_sweep_cost": sweep_cost_rows,
    }


def main():
    max_workers = min(4, os.cpu_count() or 1)
    s1 = step1_denominators(max_workers=max_workers)
    dev_cases = load_split("mcpatlas_x1", split="dev")
    s3 = step3_x1_dev_taxonomy_and_sweep(dev_cases)
    s4 = step4_cost_side(dev_cases, max_workers=max_workers)

    out_path = ROOT / "benchmarks" / "p6c_steps134_dev.json"
    out_path.write_text(json.dumps({"step1": s1, "step3": s3, "step4": s4}, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
