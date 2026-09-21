#!/usr/bin/env python3
"""PREPARED (not yet run). Extract one 3D sub-volume per predicted-cyst component (FP C_fp_neg + TP B_tp),
pooled over 5 folds, using the EXACT component definition of pooled_feature_extract.py (same fold/case/cc)
so it aligns with the 2D keystone + classifier. For the 3D CT-native FM probe (CT-FM). This half needs NO
foundation model — run any time to bank the slow data-prep. READ-ONLY on imaging/pred/gt.
Output: fm_subvols_3d/<fold>_<case>_<cc>.nii.gz (int16, ~96 mm cube, spacing preserved) + manifest.csv.
"""
import sys, os, glob, csv
sys.path.insert(0, os.path.expanduser("~/KiTS23/a3_track1_20260725"))
import numpy as np, nibabel as nib, SimpleITK as sitk
from scipy import ndimage as ndi
from extract_features import spacing_from_affine, raw_img, raw_gt, KIDNEY, CYST, CONN

ROOT=os.path.expanduser("~/KiTS23"); OUT=os.path.join(ROOT,"fm_subvols_3d"); os.makedirs(OUT,exist_ok=True)
FOLD_PRED={0:"holdout_pipeline/soft_majority_rule3_typex",
           1:"repro_check/scratch_fold1/final_rule3_typex",2:"repro_check/scratch_fold2/final_rule3_typex",
           3:"repro_check/scratch_fold3/final_rule3_typex",4:"repro_check/scratch_fold4/final_rule3_typex"}
CUBE_MM=96.0
rows=[]
for fold,pd in FOLD_PRED.items():
    for p in sorted(glob.glob(os.path.join(ROOT,pd)+"/KiTS23_*.nii.gz")):
        cid=os.path.basename(p).replace("KiTS23_","").replace(".nii.gz","")
        pr=np.asarray(nib.load(p).dataobj).astype(np.uint8)
        if not (pr==CYST).any(): continue
        gt=np.asarray(nib.load(raw_gt(cid)).dataobj).astype(np.uint8)
        imn=nib.load(raw_img(cid))
        if tuple(imn.shape)!=pr.shape or gt.shape!=pr.shape: continue
        hu=np.asarray(imn.dataobj)                        # native int16 (no float — save memory)
        sp=np.asarray(spacing_from_affine(imn.affine),float)  # (z,y,x)
        gt_cyst=(gt==CYST); gt_has=bool(gt_cyst.any())
        labp,npp=ndi.label(pr==CYST,CONN)
        for i in range(1,npp+1):
            m=labp==i; ov=int((m&gt_cyst).sum())
            grp="C_fp_neg" if not gt_has else ("B_tp" if ov>0 else "skip")
            if grp=="skip": continue
            com=ndi.center_of_mass(m); half=[max(1,int(round(CUBE_MM/2/sp[a]))) for a in range(3)]
            sl=tuple(slice(max(0,int(round(com[a]))-half[a]), min(hu.shape[a],int(round(com[a]))+half[a])) for a in range(3))
            cube=hu[sl].astype(np.int16)
            if cube.size==0 or min(cube.shape)<4: continue
            img=sitk.GetImageFromArray(cube); img.SetSpacing((float(sp[2]),float(sp[1]),float(sp[0])))
            fn=f"{fold}_{cid}_{i}.nii.gz"; sitk.WriteImage(img, os.path.join(OUT,fn))
            rows.append(dict(file=fn, fold=fold, case=cid, cc=i, group=grp, vox=int(m.sum())))
        del hu,gt,pr,labp
with open(os.path.join(OUT,"manifest.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["file","fold","case","cc","group","vox"]); w.writeheader(); w.writerows(rows)
from collections import Counter
print("sub-volumes:",len(rows),"| groups:",dict(Counter(r["group"] for r in rows)),"(對照 FP=215/TP=724)")
