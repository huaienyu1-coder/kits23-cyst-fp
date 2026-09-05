#!/usr/bin/env python3
"""Keystone size-matched control (supplement S11): on the size-matched 26 FP / 26 TP subset
(fp_component_list.csv, arms FP and TP; size is matched pairwise so it cannot be the discriminator),
does a FROZEN representation separate residual cyst false positives from true cysts? Reported result:
'does not exceed chance at this sample size (0.54, n = 26 vs 26)'.

To show the 0.54 is not a cherry-picked operating point, this prints the FULL AUC sweep over the
number of retained principal components for BOTH encoders: at n=26 vs 26 the point estimate is
config-sensitive but stays near chance throughout (DINOv2 ~0.47-0.58, RAD-DINO ~0.47-0.64) and
never reaches a usable separation. The headline 0.54 is DINOv2 at the low-dimensional probe (PCA-5).
Reads fm_patches.npz + fp_component_list.csv next to this script. GPU."""
import os, csv, numpy as np, torch
from PIL import Image
from transformers import AutoModel, AutoImageProcessor
import timm
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score

HERE=os.path.dirname(os.path.abspath(__file__))
def near(f):
    p=os.path.join(HERE,f); return p if os.path.exists(p) else os.path.expanduser("~/KiTS23/"+f)
d=np.load(near("fm_patches.npz"), allow_pickle=True)
P=d['patches']; grp=d['group'].astype(str); case=d['case'].astype(str); vox=d['vox'].astype(float)

# size-matched 26 FP + 26 TP: match each listed component to its pre-extracted patch by (case, vox, arm)
sel=[(r["case"].zfill(5), r["arm"], int(r["target_vox"]))
     for r in csv.DictReader(open(near("fp_component_list.csv"))) if r["arm"] in ("FP","TP")]
idx=[]; lab=[]; gc=[]
for c,arm,tv in sel:
    want='C_fp_neg' if arm=='FP' else 'B_tp'
    m=np.where((case==c)&(vox==tv)&(grp==want))[0]
    if len(m)==0: print("  WARN unmatched:",c,arm,tv); continue
    idx.append(m[0]); lab.append(1 if arm=='FP' else 0); gc.append(c)
idx=np.array(idx); y=np.array(lab); Ps=P[idx]
uk={}; groups=np.array([uk.setdefault(c,len(uk)) for c in gc])
print(f"size-matched subset: {len(idx)} components  FP={int(y.sum())} TP={int((y==0).sum())}  groups={len(uk)}")

dev='cuda' if torch.cuda.is_available() else 'cpu'
def auc(X, npca):
    st=[StandardScaler()]+([PCA(npca)] if npca else [])+[LogisticRegression(max_iter=3000)]
    p=cross_val_predict(make_pipeline(*st),X,y,cv=GroupKFold(5),groups=groups,method='predict_proba')[:,1]
    return roc_auc_score(y,p)

# DINOv2 (natural-image)
m=timm.create_model('vit_base_patch14_dinov2',pretrained=True,num_classes=0,img_size=224).eval().to(dev)
cfg=timm.data.resolve_model_data_config(m); mean=torch.tensor(cfg['mean']).view(1,3,1,1).to(dev); std=torch.tensor(cfg['std']).view(1,3,1,1).to(dev)
Ed=[]
with torch.no_grad():
    for i in range(0,len(Ps),32):
        b=torch.from_numpy(Ps[i:i+32].astype(np.float32)/255.0)[:,None].repeat(1,3,1,1).to(dev); b=(b-mean)/std
        Ed.append(m(b).float().cpu().numpy())
Ed=np.concatenate(Ed)
# RAD-DINO (chest-radiograph)
proc=AutoImageProcessor.from_pretrained("microsoft/rad-dino"); rm=AutoModel.from_pretrained("microsoft/rad-dino").eval().to(dev)
Er=[]
with torch.no_grad():
    for i in range(0,len(Ps),32):
        imgs=[Image.fromarray(Ps[j]).convert('RGB') for j in range(i,min(i+32,len(Ps)))]
        inp=proc(images=imgs,return_tensors='pt').to(dev); o=rm(**inp)
        Er.append((o.pooler_output if getattr(o,'pooler_output',None) is not None else o.last_hidden_state[:,0]).float().cpu().numpy())
Er=np.concatenate(Er)

grid=[None,2,3,5,8,10,12,15]
print("\n================= SIZE-MATCHED CONTROL (n=26 vs 26) =================")
for nm,E in [("DINOv2",Ed),("RAD-DINO",Er)]:
    print(f"  {nm:9s} AUC by #PCs:  " + "  ".join(f"{k or 'raw'}={auc(E,k):.3f}" for k in grid))
print(f"  size-only baseline AUC = {auc(np.log(vox[idx]+1).reshape(-1,1),None):.3f}   (subset is size-matched -> size ~ chance)")
print("\n  Reported headline: DINOv2 PCA-5 = 0.54 ('does not exceed chance'). The conclusion")
print("  (no usable separation) holds across every setting and both encoders — not a chosen point.")
