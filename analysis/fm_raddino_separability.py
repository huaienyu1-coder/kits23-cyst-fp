#!/usr/bin/env python3
"""Keystone learned-representation probe (supplement S11), RAD-DINO variant: can a domain
foundation encoder RAD-DINO (microsoft/rad-dino; a DINOv2 ViT-B pre-trained on chest radiographs)
separate residual cyst FALSE POSITIVES from TRUE cysts on single-phase CT patches, where
hand-crafted radiomics reaches only AUC~0.68 and natural-image DINOv2 reaches 0.63? Same protocol
as fm_dinov2_separability.py (frozen embeddings, grouped 5-fold CV linear probe + size-only
control), reading the SAME fm_patches.npz so it is byte-comparable. Uses RAD-DINO's official image
processor for preprocessing. Reproduces the reported RAD-DINO AUC 0.58. GPU."""
import os, numpy as np, torch
from PIL import Image
from transformers import AutoModel, AutoImageProcessor
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
proc=AutoImageProcessor.from_pretrained("microsoft/rad-dino")
model=AutoModel.from_pretrained("microsoft/rad-dino").eval().to(dev)
embs=[]
with torch.no_grad():
    for i in range(0,len(P),32):
        imgs=[Image.fromarray(P[j]).convert('RGB') for j in range(i,min(i+32,len(P)))]
        inp=proc(images=imgs, return_tensors='pt').to(dev)          # RAD-DINO's official resize+normalise
        out=model(**inp)
        emb=out.pooler_output if getattr(out,'pooler_output',None) is not None else out.last_hidden_state[:,0]
        embs.append(emb.float().cpu().numpy())
E=np.concatenate(embs); print("RAD-DINO emb:",E.shape)

def auc_cv(X, npca=None):
    steps=[StandardScaler()]
    if npca: steps.append(PCA(npca))
    steps.append(LogisticRegression(max_iter=3000,C=1.0))
    p=cross_val_predict(make_pipeline(*steps),X,y,cv=GroupKFold(5),groups=groups,method='predict_proba')[:,1]
    return roc_auc_score(y,p)

print("\n================= RAD-DINO RESULT =================")
print(f"  RAD-DINO embedding AUC (FP vs TP) = {auc_cv(E, npca=50):.3f}   (reported 0.58)")
print(f"  size-only baseline AUC            = {auc_cv(np.log(vox+1).reshape(-1,1)):.3f}   (reported 0.74; same as DINOv2 run)")
print(f"  reference: radiomic 0.68 / DINOv2 0.63")
