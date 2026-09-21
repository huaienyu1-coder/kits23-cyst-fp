"""H2 Tier-1 — is the residual-cyst-FP indistinguishability present in a PLAIN single nnU-Net,
or created by the 2nd-place vote+post-processing? Pre-registered: h2_tier1_prereg_20260919.md.
Vanilla raw single-model predictions (fold-0 hold-out, 98 cases): fullres PlainConv + ResEnc-L.
No GPU, no new training. Reuses extract_features.cc_features (0 drift from main analysis)."""
import sys, os, glob, json
sys.path.insert(0, os.path.expanduser("~/KiTS23/a3_track1_20260725"))
import numpy as np, nibabel as nib, csv
from scipy import ndimage as ndi
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
from extract_features import cc_features, spacing_from_affine, raw_img, raw_gt, KIDNEY, CYST, CONN

PREREG12=['vox','vol_mm3','mean_hu','std_hu','p5','p25','p50','p75','p95','sphericity','extent','rel_hu_kidney']
INTFEATS=['mean_hu','std_hu','rel_hu_kidney']   # + logvox, same as H3
VANILLA={
  "fullres_PlainConv": os.path.expanduser("~/KiTS23/holdout_pipeline/raw_predictions/fullres"),
  "resenc_ResidualEnc": os.path.expanduser("~/KiTS23/holdout_pipeline/raw_predictions/resenc_l"),
}

def extract(pred_dir):
    rows=[]
    preds=sorted(glob.glob(pred_dir+"/KiTS23_*.nii.gz"))
    for p in preds:
        cid=os.path.basename(p).replace("KiTS23_","").replace(".nii.gz","")
        imn=nib.load(raw_img(cid)); gtn=nib.load(raw_gt(cid)); prn=nib.load(p)
        hu=np.asarray(imn.dataobj).astype(np.float32); gt=np.asarray(gtn.dataobj).astype(np.uint8); pr=np.asarray(prn.dataobj).astype(np.uint8)
        if not (hu.shape==gt.shape==pr.shape): continue
        if not (pr==CYST).any(): continue
        sp=spacing_from_affine(imn.affine); kidney_mask=(pr==KIDNEY); gt_has=(gt==CYST).any()
        gz,gy,gx=(g.astype(np.float32) for g in np.gradient(hu)); gmag=np.sqrt(gz*gz+gy*gy+gx*gx); del gz,gy,gx
        labp,npp=ndi.label(pr==CYST,structure=CONN); gt_cyst=(gt==CYST)
        for i in range(1,npp+1):
            m=labp==i; overlap=int((m&gt_cyst).sum())
            grp="C_fp_neg" if not gt_has else ("B_tp" if overlap>0 else "skip")
            if grp=="skip": continue
            f=cc_features(m,hu,kidney_mask,sp,gmag); f.update(case=cid,group=grp,cc=i); rows.append(f)
        del hu,gmag,labp
    return rows

def batteries(rows, cyto):
    y=np.array([1 if r['group']=='C_fp_neg' else 0 for r in rows])
    case=np.array([r['case'] for r in rows])
    X12=np.array([[float(r[f]) for f in PREREG12] for r in rows],float)
    for j,f in enumerate(PREREG12):
        if f in ('vox','vol_mm3'): X12[:,j]=np.log(X12[:,j]+1)
    logvox=np.log(np.array([float(r['vox']) for r in rows])+1)
    # size-only AUC (rank of log-vox; FP=1) — orient so AUC>=.5
    a=roc_auc_score(y,logvox); size_auc=max(a,1-a)
    # radiomic-12 grouped OOF logistic
    oof=np.full(len(y),np.nan); gkf=GroupKFold(n_splits=min(5,len(set(case))))
    for tr,te in gkf.split(X12,y,case):
        if len(set(y[tr]))<2: continue
        sc=StandardScaler().fit(X12[tr]); clf=LogisticRegression(max_iter=2000,class_weight='balanced').fit(sc.transform(X12[tr]),y[tr])
        oof[te]=clf.predict_proba(sc.transform(X12[te]))[:,1]
    mo=~np.isnan(oof); rad_auc=roc_auc_score(y[mo],oof[mo]) if len(set(y[mo]))>1 else float('nan')
    # interiority vs 853 GT cysts (Mahalanobis 90% region)
    Xfp=np.column_stack([[float(r[f]) for r in rows if r['group']=='C_fp_neg'] for f in INTFEATS]+[np.log(np.array([float(r['vox']) for r in rows if r['group']=='C_fp_neg'])+1)])
    mu=cyto['mu']; ic=cyto['ic']; thr90=cyto['thr90']
    d=np.sqrt(np.einsum('ij,jk,ik->i',Xfp-mu,ic,Xfp-mu)); interior=float(np.mean(d<=thr90))
    return dict(n_fp=int(y.sum()),n_tp=int((y==0).sum()),n_fp_cases=len(set(case[y==1])),
        radiomic12_auc=round(float(rad_auc),3),size_auc=round(float(size_auc),3),
        rad_minus_size=round(float(rad_auc-size_auc),3),interiority_pct=round(100*interior))

# cyst reference distribution (N=853) for interiority — same as H3
cy=[r for r in csv.DictReader(open("gt_cyst_tumour_features.csv")) if r['group']=='cyst']
Xc=np.column_stack([[float(r[f]) for r in cy] for f in INTFEATS]+[np.log(np.array([float(r['vox']) for r in cy])+1)])
mu=Xc.mean(0); ic=np.linalg.pinv(np.cov(Xc.T)); dc=np.sqrt(np.einsum('ij,jk,ik->i',Xc-mu,ic,Xc-mu)); thr90=np.percentile(dc,90)
cyto=dict(mu=mu,ic=ic,thr90=thr90)
print(f"cyst ref N={len(cy)}  thr90(maha)={thr90:.2f}")

out={}
for name,pdir in VANILLA.items():
    print(f"\n=== {name} ({pdir}) ===",flush=True)
    rows=extract(pdir)
    with open(f"h2_tier1_{name}_features.csv","w",newline="") as fh:
        cols=["case","group","cc"]+[k for k in rows[0] if k not in ("case","group","cc")]
        w=csv.DictWriter(fh,fieldnames=cols); w.writeheader(); w.writerows(rows)
    res=batteries(rows,cyto)
    # pre-committed verdict
    replicate = (res['rad_minus_size']<=0.05) and (res['interiority_pct']>=60)
    pipespec  = (res['rad_minus_size']>0.10) or (res['interiority_pct']<40)
    res['verdict']="REPLICATES (not pipeline-specific)" if replicate else ("PIPELINE-SPECIFIC (narrow claim)" if pipespec else "MIXED")
    out[name]=res
    print(f"  FP={res['n_fp']} (from {res['n_fp_cases']} cases)  TP={res['n_tp']}")
    print(f"  radiomic-12 AUC={res['radiomic12_auc']}  size AUC={res['size_auc']}  Δ={res['rad_minus_size']}  interiority={res['interiority_pct']}%  => {res['verdict']}")

json.dump(out,open("h2_tier1_result.json","w"),indent=2)
print("\n存 h2_tier1_result.json + h2_tier1_*_features.csv")
