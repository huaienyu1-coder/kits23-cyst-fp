#!/usr/bin/env python3
"""C (β): 3D CT-native FM probe. Can CT-FM (project-lighter, SegResEncoder) separate residual cyst
FALSE POSITIVES from TRUE cysts on the 3D sub-volumes, where radiomics=0.68 / DINOv2=0.63 / RAD-DINO=0.58
do not? Frozen encoder, multi-scale global-average-pooled embedding (fairest = strongest chance for the FM),
same case-grouped 5-fold linear probe + operating-point trade-off as the β keystone.

VERIFIED against installed lighter-zoo: SegResEncoder.from_pretrained returns a LIST of 5 stage feature maps
[(.,32,.),(.,64,.),(.,128,.),(.,256,.),(.,512,.)]; we GAP each stage and concat -> 992-d embedding.
Preprocessing = frozen-probe approximation (resize 64^3 + clip[-1024,1024]/1024); a monotone intensity
transform cannot flip whether the two classes separate. If the FM UNEXPECTEDLY separates well, re-verify the
official CT-FM transform before trusting an overturn (correct asymmetry: strong negative is robust).
"""
import os, glob, numpy as np, torch, csv, json
import torch.nn.functional as F
import SimpleITK as sitk
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score

ROOT=os.path.expanduser("~/KiTS23"); SUB=os.path.join(ROOT,"fm_subvols_3d")
rows=list(csv.DictReader(open(os.path.join(SUB,"manifest.csv"))))
y=np.array([1 if r["group"]=="C_fp_neg" else 0 for r in rows])   # 1 = FP(移除標的);0 = true cyst
vox=np.array([float(r["vox"]) for r in rows])
uk={}; groups=np.array([uk.setdefault((r["fold"],r["case"]),len(uk)) for r in rows])
print(f"components={len(rows)}  FP={int(y.sum())} TP={int((y==0).sum())} groups={len(uk)}",flush=True)

dev='cuda' if torch.cuda.is_available() else 'cpu'
from lighter_zoo import SegResEncoder
model=SegResEncoder.from_pretrained("project-lighter/ct_fm_feature_extractor").eval().to(dev)
print("CT-FM loaded, dev=",dev,flush=True)

def embed(path):
    a=sitk.GetArrayFromImage(sitk.ReadImage(path)).astype(np.float32)  # (Z,Y,X)
    x=torch.from_numpy(a)[None,None]                                   # (1,1,Z,Y,X)
    x=F.interpolate(x,size=(64,64,64),mode='trilinear',align_corners=False)
    x=torch.clamp(x,-1024,1024)/1024.0
    out=model(x.to(dev))
    fmaps=out if isinstance(out,(list,tuple)) else [out]
    e=torch.cat([f.mean(dim=(2,3,4)).reshape(-1) for f in fmaps])      # multi-scale GAP concat
    return e.float().cpu().numpy()

embs=[]
with torch.no_grad():
    for i,r in enumerate(rows):
        embs.append(embed(os.path.join(SUB,r["file"])))
        if (i+1)%100==0: print(f"  embedded {i+1}/{len(rows)}",flush=True)
E=np.stack(embs); print("CT-FM emb:",E.shape,flush=True)
np.save(os.path.join(ROOT,"fm_ctfm_emb.npy"),E)
np.save(os.path.join(ROOT,"fm_ctfm_yg.npy"),np.c_[y,groups,vox])   # 存下供再分析,不必重算 embedding

# 參考 AUC(PCA50 linear probe,與 2D FM 口徑一致)
def probe_prob(X,npca=None):
    st=[StandardScaler()]+([PCA(npca)] if npca else [])+[LogisticRegression(max_iter=3000,class_weight='balanced')]
    return cross_val_predict(make_pipeline(*st),X,y,cv=GroupKFold(5),groups=groups,method='predict_proba')[:,1]
auc=roc_auc_score(y,probe_prob(E,npca=min(50,E.shape[1])))
auc_size=roc_auc_score(y,probe_prob(np.log(vox+1).reshape(-1,1)))

# 操作點:誠實 inner-selected 門檻(beta_opeval),outer 驗證——非事後 OOF 掃門檻
from beta_opeval import honest_eval
he=honest_eval(E,y,groups)
res={"n":int(len(y)),"FP":int(y.sum()),"TP":int((1-y).sum()),"emb_dim":int(E.shape[1]),
     "pca_probe_auc":round(auc,4),"size_only_auc":round(auc_size,4),
     "honest_oof_auc":he["oof_auc"],
     "operating_point_inner_selected":{"fp_removed":he["fp_removed"],"tp_deleted":he["tp_deleted"],"net":he["net"]},
     "per_fold":he["per_fold"],"usable_operating_point":he["usable"]}
json.dump(res,open(os.path.join(ROOT,"fm_ctfm_result.json"),"w"),indent=2)
print("\n================= CT-FM RESULT =================")
print(json.dumps(res,indent=2))
print("對照:radiomic=0.68 DINOv2=0.63 RAD-DINO=0.58 size-only(2D)=0.74 | 13-feat/FT-DINOv2 0.68 CNN 0.606")
print("THESIS:", "HOLDS(無淨正操作點 / AUC≲ceiling)" if not res["usable_operating_point"] else "需複查(疑似分得開,先驗 CT-FM 官方 transform)")
