#!/usr/bin/env python3
"""S5 — the converse of the 00470 granularity figure (S4).
Case 00522: the deterministic Type X correction removes a predicted-cyst region that
sits on annotated TUMOUR (1,480 / 1,942 removed voxels = 76% overlap ground-truth tumour;
24.7% aggregate over the hold-out). Honest message pair with S4:
  S4 (00470): the correction's failure face — a removal deleting a true cyst.
  S5 (00522): the correction's justification face — the removed benign record is on real malignancy.
Red lines (in the LaTeX caption): the correction removes the erroneous benign record; it does NOT
restore the tumour. 00522 is a cyst-POSITIVE case, not one of the 16 FP-alarm cases — say 'region'.
Grayscale-safe: GT tumour = solid contour line; removed Type X region = hatched fill (double-encoded).
READ-ONLY inputs; writes one PNG. Slice = max (Type X region ∩ GT tumour) axial slice (provenance).
"""
import numpy as np, nibabel as nib
from scipy.ndimage import label as nd_label
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from matplotlib.lines import Line2D

CID = "00522"
KIDNEY, TUMOR, CYST = 1, 2, 3
THRESH, MIN_VOX = 0.7, 3
OUT = "a3_gt391_20260725/fig_s5_00522_typeX_tumour.png"

def load(p): return np.asarray(nib.load(p).dataobj)
ct  = load(f"nnUNet_raw/Dataset500_KiTS23/imagesTr/KiTS23_{CID}_0000.nii.gz").astype(np.float32)
gt  = load(f"nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations/KiTS23_{CID}.nii.gz").astype(np.uint8)
pred     = load(f"holdout_pipeline/soft_voting/hard_intersection/KiTS23_{CID}.nii.gz").astype(np.uint8)
raw_main = load(f"holdout_pipeline/raw_predictions/fullres/KiTS23_{CID}.nii.gz").astype(np.uint8)
raw_chk  = load(f"holdout_pipeline/raw_predictions/resenc_l/KiTS23_{CID}.nii.gz").astype(np.uint8)

# --- reconstruct the flagged Type X region EXACTLY as typeX_incentive_overlap.py / post_process_typeX.py ---
typeX = np.zeros_like(pred, dtype=bool)
cc_map, n = nd_label(pred == CYST)
for i in range(1, n + 1):
    cc = cc_map == i
    sz = int(cc.sum())
    if sz < MIN_VOX:
        continue
    tv = cc & ((raw_main == TUMOR) | (raw_chk == TUMOR)) & (raw_main != CYST) & (raw_chk != CYST)
    if tv.sum() / sz >= THRESH:
        typeX |= cc
gt_tum = gt == TUMOR
overlap = typeX & gt_tum
print(f"reconstructed Type X vox={int(typeX.sum())} (json 1942)  ∩GT tumour={int(overlap.sum())} (json 1480)")

# --- max-overlap axial slice (provenance-consistent slice choice) ---
Z = int(np.bincount(np.argwhere(overlap)[:, 0], minlength=ct.shape[0]).argmax())
sl = lambda a: a[Z]
ys, xs = np.where(sl(typeX) | sl(gt_tum))
y0, y1 = max(ys.min()-30, 0), min(ys.max()+30, ct.shape[1]-1)
x0, x1 = max(xs.min()-30, 0), min(xs.max()+30, ct.shape[2]-1)
crop = lambda a: sl(a)[y0:y1, x0:x1]

WL, WW = 40, 400; vmin, vmax = WL-WW/2, WL+WW/2
sp = float(nib.load(f"nnUNet_raw/Dataset500_KiTS23/imagesTr/KiTS23_{CID}_0000.nii.gz").header.get_zooms()[1])

fig, ax = plt.subplots(1, 1, figsize=(5.4, 5.4))
ax.imshow(crop(ct), cmap="gray", vmin=vmin, vmax=vmax); ax.set_xticks([]); ax.set_yticks([])

# GT tumour: SOLID contour line (line primitive)
tm = crop(gt_tum).astype(float)
if tm.any(): ax.contour(tm, levels=[0.5], colors=["#d62728"], linewidths=2.2, linestyles="solid")
# removed Type X region: HATCHED translucent fill (pattern primitive) + thin edge
rm = crop(typeX).astype(float)
if rm.any():
    ax.contourf(rm, levels=[0.5, 1.5], colors=["#1f77b4"], alpha=0.28, hatches=["////"])
    ax.contour(rm, levels=[0.5], colors=["#1f77b4"], linewidths=1.0, linestyles="solid")

# scale bar 2 cm
bar = 20/sp
ax.add_patch(Rectangle((6, crop(ct).shape[0]-12), bar, 4, color="white"))
ax.text(6, crop(ct).shape[0]-16, "2 cm", color="white", fontsize=8)

ax.legend(handles=[
    Line2D([0], [0], color="#d62728", lw=2.2, label="Ground-truth tumour"),
    Patch(facecolor="#1f77b4", alpha=0.28, hatch="////", edgecolor="#1f77b4",
          label="Predicted cyst removed by\nType X correction"),
], loc="upper right", fontsize=8, framealpha=0.9)
ax.set_title("Case 00522 — the removed benign record overlies annotated tumour\n"
             f"(this region: {int(overlap.sum())}/{int(typeX.sum())} removed voxels on GT tumour)",
             fontsize=9)
fig.tight_layout()
fig.savefig(OUT, dpi=300, bbox_inches="tight")
print("saved", OUT, "slice z=", Z)
