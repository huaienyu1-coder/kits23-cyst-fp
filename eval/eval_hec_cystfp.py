#!/usr/bin/env python3
"""Clean, self-contained HEC (volumetric Dice) + cyst-FP evaluator (READ-ONLY).
Reproduction-check: run on the existing headline folders and confirm the known
numbers (hard_intersection 0.9022 / 39.6%; soft_majority_rule3_typex 0.9020 / 33.3%)
before trusting any FTL-swapped result. No dependency on compute_official_metrics.py
(whose fold_all NOTE does not apply to the hold-out — CLAUDE.md)."""
import os, sys, json
import numpy as np
import SimpleITK as sitk

GT = os.path.expanduser("~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations")

def arr(p): return sitk.GetArrayFromImage(sitk.ReadImage(str(p)))

def dice(a, b):
    a = a.astype(bool); b = b.astype(bool)
    s = a.sum() + b.sum()
    if s == 0: return 1.0            # both-empty convention (never triggers for K/M/T on hold-out)
    return 2.0 * np.logical_and(a, b).sum() / s

def hec(pred, gt):
    k = dice(pred >= 1, gt >= 1)     # Kidney = kidney ∪ tumour ∪ cyst
    m = dice(pred >= 2, gt >= 2)     # Masses = tumour ∪ cyst
    t = dice(pred == 2, gt == 2)     # Tumour
    return k, m, t, (k + m + t) / 3.0

def evaluate(pred_dir):
    cases = sorted(f for f in os.listdir(pred_dir) if f.endswith(".nii.gz"))
    K = M = T = MN = 0.0
    n = 0
    gt_neg = 0; fp = 0; fn = 0; gt_pos = 0
    for f in cases:
        g = arr(os.path.join(GT, f))
        p = arr(os.path.join(pred_dir, f))
        k, m, t, mn = hec(p, g)
        K += k; M += m; T += t; MN += mn; n += 1
        gt_has = bool((g == 3).any()); pr_has = bool((p == 3).any())
        if gt_has:
            gt_pos += 1
            if not pr_has: fn += 1
        else:
            gt_neg += 1
            if pr_has: fp += 1
    return {
        "n": n,
        "kidney_dc": round(K / n, 4), "masses_dc": round(M / n, 4),
        "tumor_dc": round(T / n, 4), "mean_dc": round(MN / n, 4),
        "cyst_fp_cases": fp, "cyst_neg_cases": gt_neg,
        "cyst_fp_rate": round(fp / gt_neg, 4) if gt_neg else None,
        "cyst_fn_cases": fn, "cyst_pos_cases": gt_pos,
    }

if __name__ == "__main__":
    results = []
    for d in sys.argv[1:]:
        r = evaluate(d); r["dir"] = d
        print(f"\n{d}")
        print(f"  HEC  K={r['kidney_dc']} M={r['masses_dc']} T={r['tumor_dc']} mean={r['mean_dc']}  (n={r['n']})")
        print(f"  cyst FP {r['cyst_fp_cases']}/{r['cyst_neg_cases']} = {r['cyst_fp_rate']:.1%}"
              f" | FN {r['cyst_fn_cases']}/{r['cyst_pos_cases']}")
        results.append(r)
    _jp = os.environ.get("EVAL_JSON")
    if _jp:
        json.dump(results, open(_jp, "w"), indent=2)
        print(f"  [wrote {_jp}]")
