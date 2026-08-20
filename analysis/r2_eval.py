#!/usr/bin/env python3
"""R2/Gap-3 eval: per-model case-level cyst FP-alarm + FN on train(391) and hold-out(98).
Reuses eval_hec_cystfp.py's exact definition: FP = GT-no-cyst & pred-has-any-cyst-voxel;
FN = GT-has-cyst & pred-no-cyst. Read-only. Writes train_fp_fn_recompute.json."""
import json, os, glob, SimpleITK as sitk, numpy as np

PRE = os.path.expanduser("~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23")
RES = os.path.expanduser("~/KiTS23/nnUNet_results/Dataset500_KiTS23")
GT  = PRE + "/gt_segmentations"
sp  = json.load(open(PRE + "/splits_final.json"))
train_cases = sorted(sp[0]["train"]); holdout_cases = sorted(sp[0]["val"])

DIRS = {
  ("lowres", "train"):   "repro_check/r2_pred_lowres_train",
  ("resenc", "train"):   "repro_check/r2_pred_resenc_train",
  ("lowres", "holdout"): RES + "/nnUNetTrainer__nnUNetPlans__3d_lowres/fold_0/validation",
  ("resenc", "holdout"): RES + "/nnUNetTrainerResEncUNetLPlans" if False else RES + "/nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/fold_0/validation",
}

def has_cyst(p):
    a = sitk.GetArrayFromImage(sitk.ReadImage(p)); return bool((a == 3).any())

def rate(model, side, cases, d):
    fp = neg = fn = pos = 0; missing = 0
    for c in cases:
        gp = f"{GT}/{c}.nii.gz"; pp = f"{d}/{c}.nii.gz"
        if not (os.path.exists(gp) and os.path.exists(pp)): missing += 1; continue
        g = has_cyst(gp); p = has_cyst(pp)
        if g: pos += 1;  fn += (0 if p else 1)
        else: neg += 1;  fp += (1 if p else 0)
    return {"model": model, "side": side, "n": len(cases) - missing, "missing": missing,
            "cyst_fp_cases": fp, "gt_cyst_neg_cases": neg,
            "cyst_fp_rate": round(fp/neg, 4) if neg else None,
            "cyst_fn_cases": fn, "gt_cyst_pos_cases": pos,
            "cyst_fn_rate": round(fn/pos, 4) if pos else None}

# --- self-calibration: the newly-written counter must reproduce a KNOWN quantity before we trust
# it. Correct target = the canonical pipeline baseline (soft_voting/hard_intersection), which is
# known to give cyst FP 19/48 (39.6%) + FN 2/50. (Not the per-model preds -- see prechecks flag.)
CALIB = os.path.expanduser("~/KiTS23/holdout_pipeline/soft_voting/hard_intersection")
cal = rate("pipeline-baseline", "calib", holdout_cases, CALIB)
assert cal["cyst_fp_cases"] == 19 and cal["gt_cyst_neg_cases"] == 48 and cal["cyst_fn_cases"] == 2, (
    f"CALIBRATION FAILED: pipeline baseline gave FP {cal['cyst_fp_cases']}/{cal['gt_cyst_neg_cases']} "
    f"FN {cal['cyst_fn_cases']} (expect 19/48, FN 2) -- counter untrustworthy, aborting")
print(f"CALIBRATION OK: pipeline baseline reproduces FP {cal['cyst_fp_cases']}/{cal['gt_cyst_neg_cases']}"
      f" (39.6%) + FN {cal['cyst_fn_cases']}/{cal['gt_cyst_pos_cases']} -> counter trusted")

out = {"definition": "case-level cyst FP = GT-no-cyst & pred-has-any-cyst-voxel; FN = GT-cyst & pred-no-cyst (== eval_hec_cystfp.py)",
       "calibration_pipeline_baseline": cal,
       "train_n": len(train_cases), "holdout_n": len(holdout_cases), "results": {}, "ratios": {}}
for m in ("lowres", "resenc"):
    tr = rate(m, "train", train_cases, DIRS[(m, "train")])
    ho = rate(m, "holdout", holdout_cases, DIRS[(m, "holdout")])
    out["results"][m] = {"train": tr, "holdout": ho}
    if tr["cyst_fp_rate"] and ho["cyst_fp_rate"]:
        out["ratios"][m] = {"fp_train_over_holdout": round(tr["cyst_fp_rate"]/ho["cyst_fp_rate"], 3),
                            "fn_train": tr["cyst_fn_rate"], "fn_holdout": ho["cyst_fn_rate"]}
json.dump(out, open(os.path.expanduser("~/KiTS23/train_fp_fn_recompute.json"), "w"), indent=2)
for m in ("lowres", "resenc"):
    r = out["results"][m]
    print(f"{m}: train FP {r['train']['cyst_fp_rate']} ({r['train']['cyst_fp_cases']}/{r['train']['gt_cyst_neg_cases']}) "
          f"| holdout FP {r['holdout']['cyst_fp_rate']} ({r['holdout']['cyst_fp_cases']}/{r['holdout']['gt_cyst_neg_cases']}) "
          f"| ratio {out['ratios'].get(m,{}).get('fp_train_over_holdout')} "
          f"|| FN train {r['train']['cyst_fn_rate']} holdout {r['holdout']['cyst_fn_rate']}")
print("[wrote train_fp_fn_recompute.json]")
