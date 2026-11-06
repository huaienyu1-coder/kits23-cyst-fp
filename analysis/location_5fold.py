import os, glob, numpy as np, SimpleITK as sitk, scipy.ndimage as ndi
from scipy.stats import mannwhitneyu
R=os.environ.get("KITS23_ROOT", os.path.expanduser("~/KiTS23")); GT=R+"/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations"
FIN={0:"holdout_pipeline/soft_majority_rule3_typex"}
for k in (1,2,3,4): FIN[k]=f"repro_check/scratch_fold{k}/final_rule3_typex"
CONN=np.ones((3,3,3),int); CY,TU=3,2
def arr(f):
    im=sitk.ReadImage(f); return sitk.GetArrayFromImage(im), np.array(im.GetSpacing()[::-1],float)
def bbox(m,pad=4):
    idx=np.where(m); return tuple(slice(max(0,i.min()-pad),i.max()+pad+1) for i in idx)
res={"FP":[], "TP":[]}
for k,fin in FIN.items():
    for pf in sorted(glob.glob(os.path.join(R,fin,"KiTS23_*.nii.gz"))):
        fn=os.path.basename(pf); gf=os.path.join(GT,fn)
        if not os.path.exists(gf): continue
        try: pred,sp=arr(pf); gt,_=arr(gf)
        except: continue
        if pred.shape!=gt.shape: continue
        gt_has=bool((gt==CY).any()); organ=(gt>=1); tum=(gt==TU)
        lab,n=ndi.label(pred==CY,CONN)
        for i in range(1,n+1):
            cc=lab==i; sz=int(cc.sum()); ov=int((cc&(gt==CY)).sum())
            if not gt_has: arm="FP"
            elif ov>0: arm="TP"
            else: continue
            sl=bbox(organ|cc); oc,ccl,tc=organ[sl],cc[sl],tum[sl]
            edt=ndi.distance_transform_edt(oc,sampling=sp); depth=edt[ccl]
            exo=float((~oc & ccl).sum())/sz
            touch=bool((ndi.binary_dilation(ccl,iterations=1)&tc).any())
            if tc.any():
                dt=ndi.distance_transform_edt(~tc,sampling=sp); ctr=tuple(int(round(x)) for x in ndi.center_of_mass(ccl)); dtm=float(dt[ctr])
            else: dtm=float('inf')
            res[arm].append(dict(fold=k,vox=sz,depth=float(np.median(depth)),exo=exo,touch=touch,dtm=dtm))
def med(a,kk): return np.median([x[kk] for x in a])
for arm in ("FP","TP"):
    a=res[arm]
    print(f"{arm}: n={len(a)}  depth_med={med(a,'depth'):.2f}mm  exo_med={med(a,'exo'):.3f}  vox_med={med(a,'vox'):.0f}  touch={sum(x['touch'] for x in a)}/{len(a)} ({100*sum(x['touch'] for x in a)/len(a):.1f}%)")
print("\nFP vs TP (Mann-Whitney, pooled 5-fold):")
for kf in ("depth","exo","vox"):
    fp=[x[kf] for x in res["FP"]]; tp=[x[kf] for x in res["TP"]]
    p=mannwhitneyu(fp,tp,alternative='two-sided')[1]
    print(f"  {kf:6s}: FP_med={np.median(fp):.3f}  TP_med={np.median(tp):.3f}  p={p:.4f}  {'indistinguishable' if p>=0.05 else 'DIFFERS'}")
fd=[x['dtm'] for x in res['FP'] if np.isfinite(x['dtm'])]
print(f"  FP dist_to_tumour median={np.median(fd):.1f}mm (n_with_tumour={len(fd)})")
print("\n(對照 fold-0 26v26: depth 4.1 vs 4.5 p=0.72 / exo p=0.22 / touch 2/26 / 89mm)")
