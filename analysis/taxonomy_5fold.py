import os, glob, numpy as np, nibabel as nib
R=os.environ.get("KITS23_ROOT", os.path.expanduser("~/KiTS23")); GT=R+"/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations"
V="fold_0/validation"; C=3
def p(*a): return os.path.join(R,*a)
F={0:dict(fin="holdout_pipeline/soft_majority_rule3_typex",Ff="holdout_pipeline/raw_predictions/fullres",Rr="holdout_pipeline/raw_predictions/resenc_l",Ll="holdout_pipeline/raw_predictions/lowres_plain")}
for k in (1,2,3,4):
    b=f"repro_check/scratch_fold{k}"
    F[k]=dict(fin=f"{b}/final_rule3_typex",Ff=f"{b}/nnUNetTrainer__nnUNetPlans__3d_fullres/{V}",Rr=f"{b}/nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/{V}",Ll=f"{b}/nnUNetTrainer__nnUNetPlans__3d_lowres/{V}")
def ld(f): return np.asarray(nib.load(f).dataobj,dtype=np.uint8)
print(f"{'fold':>4} {'FPcase':>6} {'FPvox':>8} {'F_cyst%':>8} {'R_cyst%':>8} {'L_cyst%':>8}   (F=fullres R=resenc L=lowres)")
for k,d in F.items():
    tot=nc=pcF=pcR=pcL=0
    for x in sorted(glob.glob(p(d['fin'])+"/KiTS23_*.nii.gz")):
        fn=os.path.basename(x)
        try: gt=ld(os.path.join(GT,fn))
        except: continue
        if (gt==C).sum()>0: continue
        try:
            fin=ld(x); rF=ld(p(d['Ff'],fn)); rR=ld(p(d['Rr'],fn)); rL=ld(p(d['Ll'],fn))
        except: continue
        if not (fin.shape==rF.shape==rR.shape==rL.shape): continue
        fp=(fin==C)
        if not fp.any(): continue
        nc+=1; tot+=int(fp.sum())
        pcF+=int((fp&(rF==C)).sum()); pcR+=int((fp&(rR==C)).sum()); pcL+=int((fp&(rL==C)).sum())
    if tot: print(f"{k:>4} {nc:>6} {tot:>8} {100*pcF/tot:>7.1f}% {100*pcR/tot:>7.1f}% {100*pcL/tot:>7.1f}%")
print("\n(fold-0 canonical: 16 案 / ~8164 vox / F 98.8% / R 23.4%)")
