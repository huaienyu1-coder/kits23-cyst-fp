#!/usr/bin/env python3
"""Agreement-corroboration filter — LOCKED pre-reg + CLARIFICATION NOTE
(prereg_agreement_corroboration_20260811.md). The dispersion-aware repair of §7.1.
CPU, folds 0/1/2, on existing predictions; does NOT touch CV.

Rule: for each predicted-cyst CC in the FINAL prediction, KEEP iff lowres OR resenc predicts cyst
within tolerance tau (physical mm, spacing-aware EDT) of the CC; else REMOVE (relabel kidney).
Corroboration = CYST predictions only. tau in {0,2,4,6,10} mm, all reported.

Success (§3 + clarification): a single tau where, ON EVERY FOLD 0/1/2 (replication gate):
  (1) FP-alarm CASES cleared  >  cyst-positive CASES that lose >=1 TP component   [cost unit = CASES]
  (2) FP cases cleared >= ceil(0.25 * that fold's residual-FP-case count)          [per-fold proportional]
  (3) mean HEC >= that fold's own unfiltered baseline - 0.001                       [per-fold floor, self-calibrated]
Self-calibration row = unfiltered final HEC per fold (must reproduce 0.9020 / 0.8845 / 0.8836; a
mismatch would silently eat the -0.001 budget). Reports both cost units + TP-side AND FP-side
component corroboration + per-case per-tau provenance.
"""
import os, json, glob, math
import numpy as np, nibabel as nib
from scipy.ndimage import label as ndl, distance_transform_edt

K, T, C = 1, 2, 3
TAUS = [0.0, 2.0, 4.0, 6.0, 10.0]  # physical mm
GTD = "/home/huaienyu/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations"
FOLDS = {
    0: dict(final="holdout_pipeline/soft_majority_rule3_typex",
            low="holdout_pipeline/raw_predictions/lowres_plain",
            res="holdout_pipeline/raw_predictions/resenc_l"),
    1: dict(final="repro_check/scratch_fold1/final_rule3_typex",
            low="repro_check/scratch_fold1/nnUNetTrainer__nnUNetPlans__3d_lowres/fold_0/validation",
            res="repro_check/scratch_fold1/nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/fold_0/validation"),
    2: dict(final="repro_check/scratch_fold2/final_rule3_typex",
            low="repro_check/scratch_fold2/nnUNetTrainer__nnUNetPlans__3d_lowres/fold_0/validation",
            res="repro_check/scratch_fold2/nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/fold_0/validation"),
}

def hec_axes(pred, gt):
    def d(p, g):
        ps, gs = int(p.sum()), int(g.sum())
        return 1.0 if ps == 0 and gs == 0 else 2.0 * int((p & g).sum()) / (ps + gs)
    return d(pred >= 1, gt >= 1), d(pred >= 2, gt >= 2), d(pred == 2, gt == 2)

def cyst_dice(pred, gt):
    ps, gs = int((pred == C).sum()), int((gt == C).sum())
    if ps == 0 and gs == 0: return None
    return 2.0 * int(((pred == C) & (gt == C)).sum()) / (ps + gs)

def run_fold(fold, paths):
    files = sorted(glob.glob(paths["final"] + "/*.nii.gz"))
    base = dict(K=0.0, M=0.0, Tt=0.0, n=0, cd98=0.0, cdsum=0.0, cdn=0)
    per = {tau: dict(fp_cleared=0, tp_cases_affected=0, tp_comp_lost=0, fn_flip=0,
                     K=0.0, M=0.0, Tt=0.0, n=0, cd98=0.0, cdsum=0.0, cdn=0,
                     tp_comp_total=0, tp_comp_corrob=0, fp_comp_total=0, fp_comp_corrob=0,
                     detail=[]) for tau in TAUS}
    n_fp_cases = 0; n_cystpos = 0
    for f in files:
        case = os.path.basename(f); gtp = os.path.join(GTD, case)
        if not os.path.exists(gtp): continue
        nimg = nib.load(f); final = np.asarray(nimg.dataobj).astype(np.uint8)
        gt  = np.asarray(nib.load(gtp).dataobj).astype(np.uint8)
        low = np.asarray(nib.load(os.path.join(paths["low"], case)).dataobj).astype(np.uint8)
        res = np.asarray(nib.load(os.path.join(paths["res"], case)).dataobj).astype(np.uint8)
        spacing = tuple(float(z) for z in nimg.header.get_zooms()[:3])
        gt_has_cyst = (gt == C).any()
        if gt_has_cyst: n_cystpos += 1
        final_has_fp = (final == C).any() and not gt_has_cyst
        if final_has_fp: n_fp_cases += 1
        # --- self-calibration: unfiltered final baseline ---
        bK, bM, bT = hec_axes(final, gt)
        base["K"] += bK; base["M"] += bM; base["Tt"] += bT; base["n"] += 1
        bcd = cyst_dice(final, gt); base["cd98"] += (1.0 if bcd is None else bcd)
        if bcd is not None: base["cdsum"] += bcd; base["cdn"] += 1
        # --- corroboration distance (mm) to nearest L/R cyst voxel ---
        lr = (low == C) | (res == C)
        dt = distance_transform_edt(~lr, sampling=spacing) if lr.any() else None
        cc_map, n = ndl(final == C)
        ccs = []
        for i in range(1, n + 1):
            cc = cc_map == i
            mind = float(dt[cc].min()) if dt is not None else np.inf
            is_tp = bool((cc & (gt == C)).any())
            ccs.append((cc, mind, is_tp))
        for tau in TAUS:
            filt = final.copy(); tp_lost = 0; removed = 0
            for cc, mind, is_tp in ccs:
                corrob = mind <= tau
                if is_tp:
                    per[tau]["tp_comp_total"] += 1
                    if corrob: per[tau]["tp_comp_corrob"] += 1
                else:
                    per[tau]["fp_comp_total"] += 1
                    if corrob: per[tau]["fp_comp_corrob"] += 1
                if not corrob:
                    filt[cc] = K; removed += 1
                    if is_tp: tp_lost += 1
            per[tau]["tp_comp_lost"] += tp_lost
            if gt_has_cyst and tp_lost >= 1: per[tau]["tp_cases_affected"] += 1   # CASE unit (locked)
            if final_has_fp and not (filt == C).any(): per[tau]["fp_cleared"] += 1
            if gt_has_cyst and ((final == C) & (gt == C)).any() and not ((filt == C) & (gt == C)).any():
                per[tau]["fn_flip"] += 1
            Kx, Mx, Tx = hec_axes(filt, gt)
            per[tau]["K"] += Kx; per[tau]["M"] += Mx; per[tau]["Tt"] += Tx; per[tau]["n"] += 1
            cd = cyst_dice(filt, gt); per[tau]["cd98"] += (1.0 if cd is None else cd)
            if cd is not None: per[tau]["cdsum"] += cd; per[tau]["cdn"] += 1
            if removed > 0:
                per[tau]["detail"].append(dict(case=case, removed_comps=removed, tp_comp_lost=tp_lost,
                                               fp_case_cleared=bool(final_has_fp and not (filt == C).any())))
    bn = base["n"] or 1
    baseline = {"meanHEC": round((base["K"]+base["M"]+base["Tt"])/3/bn, 4),
                "K": round(base["K"]/bn,4), "M": round(base["M"]/bn,4), "T": round(base["Tt"]/bn,4),
                "cystDice_N98": round(base["cd98"]/bn,4),
                "cystDice_NaNexcl": round(base["cdsum"]/max(base["cdn"],1),4)}
    out = {"fold": fold, "n_fp_cases": n_fp_cases, "n_cystpos": n_cystpos, "n_cases": base["n"],
           "recovery_gate_need": math.ceil(0.25 * n_fp_cases), "baseline_unfiltered": baseline, "tau": {}}
    for tau in TAUS:
        p = per[tau]; nn = p["n"] or 1
        out["tau"][str(tau)] = dict(
            fp_cases_cleared=p["fp_cleared"], tp_cases_affected=p["tp_cases_affected"],
            tp_components_lost=p["tp_comp_lost"], fn_case_flips=p["fn_flip"],
            meanHEC=round((p["K"]+p["M"]+p["Tt"])/3/nn,4),
            K=round(p["K"]/nn,4), M=round(p["M"]/nn,4), T=round(p["Tt"]/nn,4),
            cystDice_N98=round(p["cd98"]/nn,4), cystDice_NaNexcl=round(p["cdsum"]/max(p["cdn"],1),4),
            TPside_corrob=round(p["tp_comp_corrob"]/max(p["tp_comp_total"],1),3), tp_comp_total=p["tp_comp_total"],
            FPside_corrob=round(p["fp_comp_corrob"]/max(p["fp_comp_total"],1),3), fp_comp_total=p["fp_comp_total"],
            detail=p["detail"])
    return out

results = {}
for fold, paths in FOLDS.items():
    print(f"=== fold {fold} ===", flush=True)
    r = run_fold(fold, paths); results[str(fold)] = r
    b = r["baseline_unfiltered"]
    print(f"  baseline(unfiltered) HEC={b['meanHEC']}  | FP cases={r['n_fp_cases']} (need>={r['recovery_gate_need']}) | cyst-pos={r['n_cystpos']}")
    for tau in TAUS:
        t = r["tau"][str(tau)]
        print(f"  tau={tau:>4}mm | FP cleared {t['fp_cases_cleared']:>2} | TP CASES affected {t['tp_cases_affected']:>2} "
              f"(comps {t['tp_components_lost']:>3}) | HEC {t['meanHEC']} (floor {round(b['meanHEC']-0.001,4)}) "
              f"| TP-corrob {t['TPside_corrob']} FP-corrob {t['FPside_corrob']}")

json.dump(results, open("agreement_corroboration_result.json", "w"), indent=2)
print("\nsaved agreement_corroboration_result.json")

def passes(fr, tau):
    t = fr["tau"][str(tau)]
    return (t["fp_cases_cleared"] > t["tp_cases_affected"]
            and t["fp_cases_cleared"] >= fr["recovery_gate_need"]
            and t["meanHEC"] >= fr["baseline_unfiltered"]["meanHEC"] - 0.001)
print("\n=== LOCKED success check (per-fold floor + per-fold >=25% + CASE cost + replication) ===")
succ = []
for tau in TAUS:
    reps = {fold: passes(results[fold], tau) for fold in results}
    print(f"  tau={tau}mm : " + " | ".join(f"fold{fold} {v}" for fold, v in reps.items())
          + f"  REPLICATED {all(reps.values())}")
    if all(reps.values()): succ.append(tau)
print("OUTCOME:", f"SUCCESS (pivot) at tau={succ}" if succ else "FAIL (agreement route closed) — no tau replicates on all folds")
