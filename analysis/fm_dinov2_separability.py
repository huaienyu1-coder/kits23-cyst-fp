#!/usr/bin/env python3
"""Keystone learned-representation probe (supplement S11): can a strong self-supervised visual
encoder (DINOv2, no task training) separate residual cyst FALSE POSITIVES from TRUE cysts on
single-phase CT patches, where hand-crafted radiomics reaches only AUC~0.68? Grouped 5-fold CV
linear probe on frozen embeddings + size-only baseline (control) + Frechet distance. GPU.

Runnable from the released artifact: reads fm_patches.npz sitting next to this script (the raw
imaging is not redistributable; the pre-extracted centre-slice patches are). Reproduces the
reported DINOv2 AUC 0.63 (size-only 0.74). Patch extraction provenance: fm_extract_patches.py."""
import os, numpy as np, torch, timm
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score

HERE=os.path.dirname(os.path.abspath(__file__))
NPZ=os.path.join(HERE,"fm_patches.npz")
if not os.path.exists(NPZ): NPZ=os.path.expanduser("~/KiTS23/fm_patches.npz")
d=np.load(NPZ, allow_pickle=True)
P=d['patches']; grp=d['group'].astype(str); fold=d['fold'].astype(int); case=d['case'].astype(str); vox=d['vox'].astype(float)
y=(grp=='C_fp_neg').astype(int)            # 1=FP, 0=TP(true cyst)
uk={}; groups=np.array([uk.setdefault((f,c),len(uk)) for f,c in zip(fold,case)])
print(f"patches={P.shape}  FP={int(y.sum())} TP={int((y==0).sum())}  groups={len(uk)}")

dev='cuda' if torch.cuda.is_available() else 'cpu'
model=timm.create_model('vit_base_patch14_dinov2', pretrained=True, num_classes=0, img_size=224).eval().to(dev)
cfg=timm.data.resolve_model_data_config(model)
mean=torch.tensor(cfg['mean']).view(1,3,1,1).to(dev); std=torch.tensor(cfg['std']).view(1,3,1,1).to(dev)
embs=[]
with torch.no_grad():
    for i in range(0,len(P),64):
        b=torch.from_numpy(P[i:i+64].astype(np.float32)/255.0)[:,None].repeat(1,3,1,1).to(dev)
        b=(b-mean)/std
        embs.append(model(b).float().cpu().numpy())
E=np.concatenate(embs); print("DINOv2 emb:",E.shape)

def auc_cv(X, npca=None):
    steps=[StandardScaler()]
    if npca: steps.append(PCA(npca))
    steps.append(LogisticRegression(max_iter=3000,C=1.0))
    pipe=make_pipeline(*steps)
    p=cross_val_predict(pipe,X,y,cv=GroupKFold(5),groups=groups,method='predict_proba')[:,1]
    return roc_auc_score(y,p)

auc_emb=auc_cv(E, npca=50)
auc_size=auc_cv(np.log(vox+1).reshape(-1,1))
def frechet(a,b,k=30):
    pc=PCA(k).fit(np.vstack([a,b])); a,b=pc.transform(a),pc.transform(b)
    ma,mb=a.mean(0),b.mean(0); ca,cb=np.cov(a,rowvar=False),np.cov(b,rowvar=False)
    from scipy.linalg import sqrtm
    cov=sqrtm(ca@cb); cov=cov.real if np.iscomplexobj(cov) else cov
    return float((ma-mb)@(ma-mb)+np.trace(ca+cb-2*cov))
print("\n================= RESULT =================")
print(f"  DINOv2 embedding  AUC (FP vs TP) = {auc_emb:.3f}   (reported 0.63)")
print(f"  size-only baseline AUC           = {auc_size:.3f}   (reported 0.74; control: is DINOv2 only using size?)")
print(f"  radiomic reference AUC           = 0.68            (hand-crafted, classifier_result.json)")
print(f"  Frechet(FP,TP) in emb(PCA30)     = {frechet(E[y==1],E[y==0]):.2f}")
