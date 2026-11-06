import os, glob, numpy as np, nibabel as nib
from scipy.ndimage import label as nd_label
R=os.environ.get("KITS23_ROOT", os.path.expanduser("~/KiTS23")); GT=os.path.join(R,"nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations")
def p(*a): return os.path.join(R,*a)
V="fold_0/validation"
F={0:("holdout_pipeline/soft_voting/hard_intersection","holdout_pipeline/raw_predictions/fullres","holdout_pipeline/raw_predictions/resenc_l")}
for k in (1,2,3,4):
    b=f"repro_check/scratch_fold{k}"
    F[k]=(f"{b}/hard_intersection",f"{b}/nnUNetTrainer__nnUNetPlans__3d_fullres/{V}",f"{b}/nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/{V}")
T,MV,CY,TU,KI=0.7,3,3,2,1
def ld(f): return np.asarray(nib.load(f).dataobj,dtype=np.uint8)
def dice(a,b):
    a=a.astype(bool);b=b.astype(bool); s=int(a.sum())+int(b.sum())
    if a.sum()==0 and b.sum()==0: return np.nan
    return 2.0*int((a&b).sum())/s if s else 1.0
def hec(pr,g): return [dice(pr>=1,g>=1),dice(pr>=2,g>=2),dice(pr==2,g==2)]
print(f"{'fold':>4} {'n':>4} {'cystFP_before':>13} {'cystFP_after':>12} {'cystDice_b':>10} {'cystDice_a':>10} {'dHEC':>8} {'TXrm_cyst':>9} {'TXrm_tum':>8} {'TXrm_oth':>8} {'TXccs':>6}")
allrows=[]
for k,(mm,rf,rc) in F.items():
    cases=sorted(glob.glob(p(mm)+"/KiTS23_*.nii.gz")); n=0
    hb=np.zeros(3);ha=np.zeros(3);hn=np.zeros(3)
    neg=fpb=fpa=0; db_s=da_s=dn=0.0; rem_cy=rem_tu=rem_ot=txcc=0; miss=0
    for c in cases:
        fn=os.path.basename(c)
        try:
            pr=ld(c); rF=ld(p(rf,fn)); rC=ld(p(rc,fn)); g=ld(os.path.join(GT,fn))
        except: miss+=1; continue
        if not (pr.shape==rF.shape==rC.shape==g.shape): miss+=1; continue
        n+=1; out=pr.copy(); cc,ncc=nd_label(pr==CY); txm=np.zeros_like(pr,bool)
        for i in range(1,ncc+1):
            mi=cc==i; sz=int(mi.sum())
            if sz<MV: out[mi]=KI; continue
            tx=mi&((rF==TU)|(rC==TU))&(rF!=CY)&(rC!=CY)
            if tx.sum()/sz>=T: out[mi]=KI; txm|=mi; txcc+=1
        # HEC before/after
        for ax,(vb,va) in enumerate(zip(hec(pr,g),hec(out,g))):
            if not np.isnan(vb): hb[ax]+=vb; hn[ax]+=1
            if not np.isnan(va): ha[ax]+=va
        # cyst FP on cyst-negative
        if not (g==CY).any():
            neg+=1; fpb+=int((pr==CY).any()); fpa+=int((out==CY).any())
        # cyst dice N=all (empty->1)
        vb=dice(pr==CY,g==CY); va=dice(out==CY,g==CY)
        db_s+=(vb if not np.isnan(vb) else 1.0); da_s+=(va if not np.isnan(va) else 1.0); dn+=1
        # collateral of TypeX-removed
        rem_cy+=int((txm&(g==CY)).sum()); rem_tu+=int((txm&(g==TU)).sum()); rem_ot+=int((txm&~((g==CY)|(g==TU))).sum())
    hbm=hb/np.maximum(hn,1); ham=ha/np.maximum(hn,1)
    dhec=ham.mean()-hbm.mean()
    row=dict(fold=k,n=n,fpb=fpb,neg=neg,fpa=fpa,db=db_s/max(dn,1),da=da_s/max(dn,1),dhec=dhec,rc=rem_cy,rt=rem_tu,ro=rem_ot,tx=txcc,miss=miss)
    allrows.append(row)
    print(f"{k:>4} {n:>4} {str(fpb)+'/'+str(neg):>13} {str(fpa)+'/'+str(neg):>12} {db_s/max(dn,1):>10.4f} {da_s/max(dn,1):>10.4f} {dhec:>+8.4f} {rem_cy:>9} {rem_tu:>8} {rem_ot:>8} {txcc:>6}  miss={miss}")
print("\n== 判準檢查(每折)==")
for r in allrows:
    ok_fp = r['fpa']<=r['fpb']; ok_dice=r['da']>=r['db']-1e-9; ok_hec=r['dhec']>=-0.001; ok_col=r['rc']<r['rt']
    verdict="PASS" if (ok_fp and ok_dice and ok_hec and ok_col) else "FAIL-ish"
    print(f"  fold{r['fold']}: FP↓{ok_fp} Dice↑{ok_dice} HEC≥-.001 {ok_hec}({r['dhec']:+.4f}) cyst<tum {ok_col}({r['rc']}<{r['rt']}) -> {verdict}")
