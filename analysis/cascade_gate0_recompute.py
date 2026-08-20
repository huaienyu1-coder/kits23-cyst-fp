#!/usr/bin/env python3
"""§8.3 cascade Gate-0 provenance recompute (CPU, read-only).
Original definition: crop to the PREDICTED kidney bounding box (soft-majority prediction,
foreground label>=1), expanded by 10mm / 20mm; count GT cyst (label 3) voxels that fall
OUTSIDE the crop, summed over the canonical hold-out (fold-0 val, N=98).
Sources the paper claim: 'cropping to the kidney bbox removes 0 of 479,873 GT cyst voxels'
at both 10 and 20 mm margins. Writes cascade_gate0_result.json."""
import json, os, numpy as np, SimpleITK as sitk

PRE  = os.path.expanduser("~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23")
GT   = PRE + "/gt_segmentations"
PRED = os.path.expanduser("~/KiTS23/holdout_pipeline/soft_majority_rule3_typex")  # predicted kidney ROI source
cv   = json.load(open(PRE + "/splits_final_cv5.json"))
cases = sorted(cv[0]["val"])   # canonical hold-out 98

def outside_count(shape, kidney_mask, cyst_mask, spacing, margin_mm):
    """count cyst voxels outside (predicted-kidney bbox + margin)."""
    if kidney_mask.sum() == 0:
        return int(cyst_mask.sum())          # no predicted kidney -> all cyst 'outside' (conservative)
    idx = np.array(np.where(kidney_mask)); lo = idx.min(axis=1); hi = idx.max(axis=1)
    sp = np.array([spacing[2], spacing[1], spacing[0]])          # array axes (z,y,x)
    mv = np.ceil(margin_mm / sp).astype(int)
    lo = np.maximum(lo - mv, 0); hi = np.minimum(hi + mv, np.array(shape) - 1)
    inside = np.zeros(shape, dtype=bool)
    inside[lo[0]:hi[0]+1, lo[1]:hi[1]+1, lo[2]:hi[2]+1] = True
    return int((cyst_mask & ~inside).sum())

tot_cyst = out10 = out20 = ncase_cyst = shape_mismatch = 0
per_case = []
for c in cases:
    gp, pp = f"{GT}/{c}.nii.gz", f"{PRED}/{c}.nii.gz"
    if not (os.path.exists(gp) and os.path.exists(pp)): continue
    gimg = sitk.ReadImage(gp); gt = sitk.GetArrayFromImage(gimg)
    pred = sitk.GetArrayFromImage(sitk.ReadImage(pp))
    if gt.shape != pred.shape:                      # align safety
        shape_mismatch += 1; continue
    cyst = (gt == 3); nc = int(cyst.sum())
    if nc == 0: continue
    ncase_cyst += 1; tot_cyst += nc
    kidney_roi = (pred >= 1)                          # predicted kidney ROI (foreground)
    o10 = outside_count(gt.shape, kidney_roi, cyst, gimg.GetSpacing(), 10)
    o20 = outside_count(gt.shape, kidney_roi, cyst, gimg.GetSpacing(), 20)
    out10 += o10; out20 += o20
    if o10 or o20:
        per_case.append({"case": c, "cyst_vox": nc, "outside_10mm": o10, "outside_20mm": o20})

res = {
    "definition": "GT cyst (label 3) voxels outside PREDICTED-kidney-ROI bbox (soft_majority_rule3_typex, label>=1) + margin, summed over canonical hold-out (fold-0 val, N=98)",
    "n_cases_with_cyst": ncase_cyst, "total_gt_cyst_voxels": tot_cyst,
    "cyst_voxels_outside_pred_kidney_bbox_10mm": out10,
    "cyst_voxels_outside_pred_kidney_bbox_20mm": out20,
    "shape_mismatch_cases": shape_mismatch,
    "cases_with_any_outside": per_case,
    "paper_claim": "0 of 479,873 GT cyst voxels removed by kidney-bbox crop at 10 and 20 mm",
}
json.dump(res, open(os.path.expanduser("~/KiTS23/cascade_gate0_result.json"), "w"), indent=2)
print(f"total GT cyst voxels = {tot_cyst}  (paper: 479,873)")
print(f"outside PRED-kidney-bbox +10mm = {out10} ; +20mm = {out20}  (paper: 0 / 0)")
print(f"cases with cyst = {ncase_cyst} ; shape-mismatch = {shape_mismatch}")
