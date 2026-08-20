#!/usr/bin/env python3
"""§8.6/D1 confidence provenance recompute (CPU, read-only).
Pinned definition (2026-08-18): for each predicted-cyst connected component (26-connectivity,
same population as a3 separability): FP group = C_fp_neg (cyst-negative cases), TP group = B_tp
(overlaps GT cyst in cyst-positive cases). Statistic = mean of the FULL-RESOLUTION model's
cyst-channel softmax over the component's voxels (full-res drives 98.8% of the FP voxels).
The paper's 0.84-0.98 (§8.6) had no artifact and its definition was lost; the recomputed range
REPLACES it (pre-declared honesty clause in the evidence index). Writes confidence_recompute.json.

Alignment: prediction & GT are in nibabel/raw space; the nnUNet .npz is stored flipped on all
three axes (CLAUDE.md known-bug), so the cyst channel is np.flip(..,(0,1,2)) before indexing.
A sanity check prints mean cyst-softmax over all predicted-cyst voxels (must be high if aligned)."""
import json, os, numpy as np, nibabel as nib
from scipy import ndimage as ndi

PRE   = os.path.expanduser("~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23")
RAW   = os.path.expanduser("~/KiTS23/kits23/dataset")
PREDD = os.path.expanduser("~/KiTS23/holdout_pipeline/soft_majority_rule3_typex")
FR    = os.path.expanduser("~/KiTS23/nnUNet_results/Dataset500_KiTS23/nnUNetTrainer__nnUNetPlans__3d_fullres/fold_0/validation")
cv    = json.load(open(PRE + "/splits_final_cv5.json"))
cases = sorted(cv[0]["val"])
CYST = 3; CONN = np.ones((3, 3, 3), dtype=int)

def cid5(c): return c.replace("KiTS23_", "")

fp, tp = [], []          # (case, cc, conf, centroid_x, vox)
sane_num = sane_den = 0
for c in cases:
    cid = cid5(c)
    pp = f"{PREDD}/KiTS23_{cid}.nii.gz"; gp = f"{RAW}/case_{cid}/segmentation.nii.gz"; np_p = f"{FR}/KiTS23_{cid}.npz"
    if not (os.path.exists(pp) and os.path.exists(gp) and os.path.exists(np_p)): continue
    pr = np.asarray(nib.load(pp).dataobj); gt = np.asarray(nib.load(gp).dataobj)
    pr_has = (pr == CYST).any(); gt_has = (gt == CYST).any()
    if not pr_has: continue
    prob = np.load(np_p)["probabilities"]
    cystprob = np.flip(prob[3], (0, 1, 2)).astype(np.float32); del prob
    if cystprob.shape != pr.shape: continue
    sane_num += float(cystprob[pr == CYST].sum()); sane_den += int((pr == CYST).sum())
    labp, npp = ndi.label(pr == CYST, structure=CONN)
    gt_cyst = (gt == CYST)
    for i in range(1, npp + 1):
        m = labp == i
        conf = float(cystprob[m].mean()); cx = float(np.where(m)[2].mean()); v = int(m.sum())
        if not gt_has:                       fp.append((cid, i, conf, cx, v))     # C_fp_neg
        elif int((m & gt_cyst).sum()) > 0:   tp.append((cid, i, conf, cx, v))     # B_tp
    del cystprob, labp

def stats(g):
    v = sorted(x[2] for x in g)
    return {"n": len(v), "min": round(v[0],3), "max": round(v[-1],3),
            "median": round(v[len(v)//2],3), "q1": round(v[len(v)//4],3), "q3": round(v[3*len(v)//4],3)} if v else {}

# L/R robustness: split by centroid-x median
allcx = sorted(x[3] for x in fp + tp); mid = allcx[len(allcx)//2] if allcx else 0
def side_stats(g, lo): return stats([x for x in g if (x[3] < mid) == lo])

res = {
  "definition": "mean full-res cyst-channel softmax per predicted-cyst CC (26-conn); FP=C_fp_neg, TP=B_tp; N=98 hold-out",
  "sanity_mean_cystprob_over_predicted_cyst": round(sane_num/max(sane_den,1), 3),
  "FP_C_fp_neg": stats(fp), "TP_B_tp": stats(tp),
  "overlap": "FP range within TP range" if (fp and tp and min(x[2] for x in fp) >= min(x[2] for x in tp) and max(x[2] for x in fp) <= max(x[2] for x in tp)) else "see ranges",
  "FP_left": side_stats(fp, True), "FP_right": side_stats(fp, False),
  "TP_left": side_stats(tp, True), "TP_right": side_stats(tp, False),
  "paper_claim_replaced": "0.84-0.98 (§8.6, definition lost -> recomputed range is canonical)",
}
json.dump(res, open(os.path.expanduser("~/KiTS23/confidence_recompute.json"), "w"), indent=2)
print("SANITY mean cyst-softmax over predicted-cyst voxels =", res["sanity_mean_cystprob_over_predicted_cyst"], "(must be high, >0.5, else axis-flip wrong)")
print("FP (C_fp_neg):", res["FP_C_fp_neg"])
print("TP (B_tp):", res["TP_B_tp"])
