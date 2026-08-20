#!/usr/bin/env python3
"""Classifier pre-reg §3 feature extraction, pooled across all 5 CV folds (read-only).
Reuses a3 extract_features.cc_features EXACTLY (same §8.5 hand-crafted radiomic set) — only the
per-fold prediction directory changes. Extracts FP (C_fp_neg) and TP (B_tp) predicted-cyst
components; writes classifier_features_pooled.csv for the nested-CV classifier."""
import sys, os, json, glob, csv
sys.path.insert(0, os.path.expanduser("~/KiTS23/a3_track1_20260725"))
import numpy as np, nibabel as nib
from scipy import ndimage as ndi
from extract_features import cc_features, spacing_from_affine, raw_img, raw_gt, KIDNEY, CYST, CONN

PRE = os.path.expanduser("~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23")
FOLD_PRED = {
  0: os.path.expanduser("~/KiTS23/holdout_pipeline/soft_majority_rule3_typex"),
  1: os.path.expanduser("~/KiTS23/repro_check/scratch_fold1/final_rule3_typex"),
  2: os.path.expanduser("~/KiTS23/repro_check/scratch_fold2/final_rule3_typex"),
  3: os.path.expanduser("~/KiTS23/repro_check/scratch_fold3/final_rule3_typex"),
  4: os.path.expanduser("~/KiTS23/repro_check/scratch_fold4/final_rule3_typex"),
}
rows = []
for fold, pred_dir in FOLD_PRED.items():
    preds = sorted(glob.glob(pred_dir + "/KiTS23_*.nii.gz"))
    print(f"fold {fold}: {len(preds)} preds", flush=True)
    for p in preds:
        cid = os.path.basename(p).replace("KiTS23_", "").replace(".nii.gz", "")
        imn = nib.load(raw_img(cid)); gtn = nib.load(raw_gt(cid)); prn = nib.load(p)
        hu = np.asarray(imn.dataobj).astype(np.float32)
        gt = np.asarray(gtn.dataobj).astype(np.uint8)
        pr = np.asarray(prn.dataobj).astype(np.uint8)
        if not (hu.shape == gt.shape == pr.shape): continue
        if not (pr == CYST).any(): continue
        sp = spacing_from_affine(imn.affine); kidney_mask = (pr == KIDNEY); gt_has = (gt == CYST).any()
        gz, gy, gx = (g.astype(np.float32) for g in np.gradient(hu)); gmag = np.sqrt(gz*gz + gy*gy + gx*gx); del gz, gy, gx
        labp, npp = ndi.label(pr == CYST, structure=CONN); gt_cyst = (gt == CYST)
        for i in range(1, npp + 1):
            m = labp == i; overlap = int((m & gt_cyst).sum())
            grp = "C_fp_neg" if not gt_has else ("B_tp" if overlap > 0 else "Cpos_fp_in_poscase")
            if grp not in ("C_fp_neg", "B_tp"): continue
            f = cc_features(m, hu, kidney_mask, sp, gmag); f.update(fold=fold, case=cid, group=grp, cc=i)
            rows.append(f)
        del hu, gmag, labp

cols = ["fold", "case", "group", "cc"] + [k for k in rows[0] if k not in ("fold", "case", "group", "cc")]
with open(os.path.expanduser("~/KiTS23/classifier_features_pooled.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
from collections import Counter
gc = Counter(r["group"] for r in rows)
fp_cases = len(set((r["fold"], r["case"]) for r in rows if r["group"] == "C_fp_neg"))
tp_cases = len(set((r["fold"], r["case"]) for r in rows if r["group"] == "B_tp"))
print(f"pooled components: {dict(gc)}")
print(f"FP components (C_fp_neg): {gc['C_fp_neg']} from {fp_cases} cases  |  TP (B_tp): {gc['B_tp']} from {tp_cases} cases")
print(f"feature columns: {[c for c in cols if c not in ('fold','case','group','cc')]}")
print("[wrote classifier_features_pooled.csv]")
