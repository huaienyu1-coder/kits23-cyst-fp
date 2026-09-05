#!/usr/bin/env python3
"""Extract one windowed centre-slice 2D patch per predicted-cyst component (FP C_fp_neg + TP B_tp),
pooled across all 5 CV folds, using the EXACT component definition of pooled_feature_extract.py
(same fold/case/cc/group). OPTIMISED: load pred(uint8) first + skip cases with no predicted cyst;
load imaging LAZILY, only the single needed slice per component (never the full float32 volume).
READ-ONLY; writes fm_patches.npz. Prints per-fold progress (run WITHOUT tail to see it live)."""
import sys, os, glob
sys.path.insert(0, os.path.expanduser("~/KiTS23/a3_track1_20260725"))
import numpy as np, nibabel as nib
from scipy import ndimage as ndi
from extract_features import spacing_from_affine, raw_img, raw_gt, KIDNEY, CYST, CONN

ROOT=os.path.expanduser("~/KiTS23")
FOLD_PRED = {
  0: "holdout_pipeline/soft_majority_rule3_typex",
  1: "repro_check/scratch_fold1/final_rule3_typex",
  2: "repro_check/scratch_fold2/final_rule3_typex",
  3: "repro_check/scratch_fold3/final_rule3_typex",
  4: "repro_check/scratch_fold4/final_rule3_typex",
}
BOX_MM=100.0; OUT=224; WL,WW=40.0,400.0; LO,HI=WL-WW/2, WL+WW/2

def slice_at(dataobj, coarse, k):
    idx=[slice(None)]*3; idx[coarse]=int(k)
    return np.asarray(dataobj[tuple(idx)]).astype(np.float32)

patches=[]; fold_l=[]; case_l=[]; cc_l=[]; grp_l=[]; vox_l=[]
for fold,pd in FOLD_PRED.items():
    preds=sorted(glob.glob(os.path.join(ROOT,pd)+"/KiTS23_*.nii.gz"))
    print(f"fold {fold}: {len(preds)} preds", flush=True)
    for j,p in enumerate(preds):
        cid=os.path.basename(p).replace("KiTS23_","").replace(".nii.gz","")
        pr=np.asarray(nib.load(p).dataobj).astype(np.uint8)
        if not (pr==CYST).any():
            if (j+1)%25==0: print(f"  fold{fold} {j+1}/{len(preds)}  patches={len(patches)}",flush=True)
            continue
        gt=np.asarray(nib.load(raw_gt(cid)).dataobj).astype(np.uint8)
        imn=nib.load(raw_img(cid))
        if tuple(imn.shape)!=pr.shape or gt.shape!=pr.shape:
            continue
        sp=np.asarray(spacing_from_affine(imn.affine),float); coarse=int(np.argmax(sp)); inax=[i for i in range(3) if i!=coarse]
        labp,npp=ndi.label(pr==CYST,CONN); gt_cyst=(gt==CYST); gt_has=bool(gt_cyst.any())
        for i in range(1,npp+1):
            m=labp==i; overlap=int((m&gt_cyst).sum())
            grp="C_fp_neg" if not gt_has else ("B_tp" if overlap>0 else "skip")
            if grp=="skip": continue
            com=ndi.center_of_mass(m); k=int(round(com[coarse]))
            sl=slice_at(imn.dataobj,coarse,k)                       # lazy: only this slice
            c0,c1=com[inax[0]],com[inax[1]]; s0,s1=sp[inax[0]],sp[inax[1]]
            h0=max(2,int(round(BOX_MM/2/s0))); h1=max(2,int(round(BOX_MM/2/s1)))
            y0,y1=max(0,int(c0)-h0),min(sl.shape[0],int(c0)+h0)
            x0,x1=max(0,int(c1)-h1),min(sl.shape[1],int(c1)+h1)
            crop=sl[y0:y1,x0:x1]
            if crop.size==0 or min(crop.shape)<3: continue
            crop=np.clip((crop-LO)/(HI-LO),0,1)
            crop=np.clip(ndi.zoom(crop,(OUT/crop.shape[0],OUT/crop.shape[1]),order=1),0,1)
            patches.append((crop*255).astype(np.uint8))
            fold_l.append(fold); case_l.append(cid); cc_l.append(i); grp_l.append(grp); vox_l.append(int(m.sum()))
        del pr,gt,labp
        if (j+1)%25==0: print(f"  fold{fold} {j+1}/{len(preds)}  patches={len(patches)}",flush=True)

patches=np.stack(patches)
np.savez_compressed(os.path.join(ROOT,"fm_patches.npz"),
    patches=patches, fold=np.array(fold_l), case=np.array(case_l),
    cc=np.array(cc_l), group=np.array(grp_l), vox=np.array(vox_l))
from collections import Counter
print("DONE patches:",patches.shape,"| groups:",dict(Counter(grp_l)),"(對照 CSV: FP=215, TP=724)",flush=True)
