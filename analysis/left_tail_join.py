#!/usr/bin/env python3
"""Pre-declared (2026-08-18) test of the left-tail mechanism hypothesis for §8.6 confidence.
Hypothesis: FP components in the low-confidence left tail (full-res cyst-softmax mean < 0.88)
are cases where the full-res model saw TUMOUR (Type X family), not cyst. NON-circular test:
low cyst-softmax could be tumour/kidney/bg -- the hypothesis specifically predicts tumour.
Criterion (locked before looking): among the 26 FP (C_fp_neg) components, the mean fraction of
voxels whose full-res argmax == tumour(2) should be substantially HIGHER in the low-confidence
group than in the high-confidence group. FP side only. Writes left_tail_join.json."""
import json, os, numpy as np, nibabel as nib
from scipy import ndimage as ndi

PRE   = os.path.expanduser("~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23")
RAW   = os.path.expanduser("~/KiTS23/kits23/dataset")
PREDD = os.path.expanduser("~/KiTS23/holdout_pipeline/soft_majority_rule3_typex")
FR    = os.path.expanduser("~/KiTS23/nnUNet_results/Dataset500_KiTS23/nnUNetTrainer__nnUNetPlans__3d_fullres/fold_0/validation")
cases = sorted(json.load(open(PRE + "/splits_final_cv5.json"))[0]["val"])
CYST, TUMOUR = 3, 2; CONN = np.ones((3, 3, 3), dtype=int); Q1 = 0.88

comps = []   # per FP component: conf, frac_tumour, frac_cyst, frac_kidney, frac_bg, vox
for c in cases:
    cid = c.replace("KiTS23_", "")
    pp, gp, npp_ = f"{PREDD}/KiTS23_{cid}.nii.gz", f"{RAW}/case_{cid}/segmentation.nii.gz", f"{FR}/KiTS23_{cid}.npz"
    if not (os.path.exists(pp) and os.path.exists(gp) and os.path.exists(npp_)): continue
    pr = np.asarray(nib.load(pp).dataobj); gt = np.asarray(nib.load(gp).dataobj)
    if (gt == CYST).any() or not (pr == CYST).any(): continue      # FP side = cyst-negative cases only
    prob = np.flip(np.load(npp_)["probabilities"], (1, 2, 3))       # align all 4 channels to SITK space
    argmax = prob.argmax(0).astype(np.int8); cystp = prob[3].astype(np.float32); del prob
    if argmax.shape != pr.shape: continue
    lab, n = ndi.label(pr == CYST, structure=CONN)
    for i in range(1, n + 1):
        m = lab == i; v = int(m.sum()); am = argmax[m]
        comps.append({"case": cid, "cc": i, "vox": v, "conf": round(float(cystp[m].mean()), 3),
                      "frac_tumour": round(float((am == 2).mean()), 3),
                      "frac_cyst":   round(float((am == 3).mean()), 3),
                      "frac_kidney": round(float((am == 1).mean()), 3),
                      "frac_bg":     round(float((am == 0).mean()), 3)})
    del argmax, cystp, lab

low  = [x for x in comps if x["conf"] <  Q1]
high = [x for x in comps if x["conf"] >= Q1]
def mean(g, k): return round(sum(x[k] for x in g) / max(len(g), 1), 3)
res = {
    "n_fp_components": len(comps), "q1_split": Q1,
    "low_conf": {"n": len(low), "mean_frac_tumour": mean(low, "frac_tumour"),
                 "mean_frac_cyst": mean(low, "frac_cyst"), "mean_frac_kidney": mean(low, "frac_kidney"),
                 "mean_frac_bg": mean(low, "frac_bg"), "mean_conf": mean(low, "conf")},
    "high_conf": {"n": len(high), "mean_frac_tumour": mean(high, "frac_tumour"),
                  "mean_frac_cyst": mean(high, "frac_cyst"), "mean_conf": mean(high, "conf")},
    "components": sorted(comps, key=lambda x: x["conf"]),
    "prereg_criterion": "low-conf mean_frac_tumour >> high-conf mean_frac_tumour  => hypothesis holds",
}
json.dump(res, open(os.path.expanduser("~/KiTS23/left_tail_join.json"), "w"), indent=2)
print(f"FP components: {len(comps)}  (expect 26)")
print(f"LOW-conf (<{Q1}): n={len(low)}  mean fullres argmax=tumour frac = {res['low_conf']['mean_frac_tumour']}  (cyst {res['low_conf']['mean_frac_cyst']}, kidney {res['low_conf']['mean_frac_kidney']})")
print(f"HIGH-conf(>={Q1}): n={len(high)} mean fullres argmax=tumour frac = {res['high_conf']['mean_frac_tumour']}  (cyst {res['high_conf']['mean_frac_cyst']})")
print("--- lowest-confidence FP components ---")
for x in res["components"][:6]:
    print(f"  {x['case']} cc{x['cc']} vox={x['vox']} conf={x['conf']} | fullres argmax: tumour={x['frac_tumour']} cyst={x['frac_cyst']} kidney={x['frac_kidney']} bg={x['frac_bg']}")
