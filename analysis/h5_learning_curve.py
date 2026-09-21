"""H5/H3 adjudication — separability learning curve (OOF AUC vs training-set size).
Pre-registered: h5_learningcurve_prereg_20260918.md (criteria fixed before this ran).
Question: is the FP-vs-true-cyst ceiling information-limited (curve plateaus) or sample-limited (curve rises)?
Feature sets: (A) 12 pre-reg radiomic [logistic]; (B) 851 PyRadiomics [RF]; (C) CT-FM 992-d frozen [logistic + RF].
No GPU. Outputs h5_learning_curve.json + figures/fig_learning_curve.png.
"""
import numpy as np, csv, json, collections
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

RNG_SEEDS=[0,1,2,3,4]
FRACS=[0.25,0.50,0.75,1.00]
PREREG12=['vox','vol_mm3','mean_hu','std_hu','p5','p25','p50','p75','p95','sphericity','extent','rel_hu_kidney']
# 12 pre-reg feats = §3 set (exclude min/max/elongation/margin_grad per classifier_prereg); use the documented 12.

def load_csv(path):
    rows=list(csv.DictReader(open(path)))
    case=np.array([r['case'] for r in rows])
    fold=np.array([int(r['fold']) for r in rows])
    y=np.array([1 if r['group']=='C_fp_neg' else 0 for r in rows])  # 1=FP, 0=TP
    return rows,case,fold,y

# ---- feature sets ----
rows,case,fold,y=load_csv("classifier_features_pooled.csv")
X12=np.array([[float(r[f]) for f in PREREG12] for r in rows],float)
# log-transform volume-like cols (match classifier practice)
for j,f in enumerate(PREREG12):
    if f in ('vox','vol_mm3'): X12[:,j]=np.log(X12[:,j]+1)

emb=np.load("fm_ctfm_emb.npy"); yg=np.load("fm_ctfm_yg.npy",allow_pickle=True)
assert emb.shape[0]==len(rows), f"CT-FM row mismatch {emb.shape[0]} vs {len(rows)}"
assert np.array_equal(yg[:,0].astype(int), y), "CT-FM label order != CSV group order (not row-aligned!)"
Xfm=emb.astype(float)

# 851 set (its own rows)
r851=list(csv.DictReader(open("beta_pyradiomics_features.csv")))
meta={'case','cc','fold','group'}
feat851=[k for k in r851[0].keys() if k not in meta]
X851=np.array([[float(x[k]) for k in feat851] for x in r851],float)
case851=np.array([x['case'] for x in r851]); fold851=np.array([int(x['fold']) for x in r851])
y851=np.array([1 if x['group']=='C_fp_neg' else 0 for x in r851])

def mk_clf(kind):
    if kind=='logistic': return ('scale',LogisticRegression(max_iter=2000,C=1.0,class_weight='balanced'))
    if kind=='rf': return ('none',RandomForestClassifier(n_estimators=300,min_samples_leaf=3,n_jobs=-1,class_weight='balanced'))

def oof_auc(X,case,fold,y,kind,frac,seed):
    """Rotating 5-fold OOF; within training pool subsample CASES to `frac` (grouped)."""
    scaler_mode,clf_proto=mk_clf(kind)
    oof=np.full(len(y),np.nan)
    rs=np.random.RandomState(seed*97+13)
    for t in sorted(set(fold)):
        tr=np.where(fold!=t)[0]; te=np.where(fold==t)[0]
        # subsample training CASES (grouped)
        tr_cases=np.array(sorted(set(case[tr])))
        if frac<1.0:
            k=max(2,int(round(frac*len(tr_cases))))
            sel=set(rs.choice(tr_cases,size=k,replace=False))
            tr=np.array([i for i in tr if case[i] in sel])
        Xtr,ytr,Xte=X[tr],y[tr],X[te]
        if len(set(ytr))<2 or ytr.sum()<3: continue
        from sklearn.base import clone
        clf=clone(clf_proto)
        if scaler_mode=='scale':
            sc=StandardScaler().fit(Xtr); Xtr=sc.transform(Xtr); Xte=sc.transform(Xte)
        clf.fit(Xtr,ytr)
        oof[te]=clf.predict_proba(Xte)[:,1]
    m=~np.isnan(oof)
    return roc_auc_score(y[m],oof[m]), int((y[m]==1).sum())

def curve(X,case,fold,y,kind,name):
    res={"name":name,"kind":kind,"fracs":FRACS,"auc_mean":[],"auc_seeds":[],"n_fp_train":[]}
    for frac in FRACS:
        aucs=[]; nfp=[]
        for s in RNG_SEEDS:
            a,n=oof_auc(X,case,fold,y,kind,frac,s); aucs.append(a); nfp.append(n)
            if frac==1.0: break  # deterministic; one is enough
        # n_fp_train ~ frac * pooled-4fold FP count
        pooled_fp=int((y==1).sum()*4/5)
        res["auc_mean"].append(round(float(np.mean(aucs)),4))
        res["auc_seeds"].append([round(float(a),4) for a in aucs])
        res["n_fp_train"].append(int(round(frac*pooled_fp)))
    # slope over f>=0.5 vs log N, bootstrap CI over seeds
    idx=[i for i,f in enumerate(FRACS) if f>=0.5]
    def slope_from(picks):
        xs=np.log(np.array([res["n_fp_train"][i] for i in idx],float))
        ys=np.array([picks[i] for i in idx],float)
        return np.polyfit(xs,ys,1)[0]
    boots=[]
    for _ in range(2000):
        picks={}
        for i in idx:
            seedvals=res["auc_seeds"][i]; picks[i]=float(np.random.choice(seedvals))
        boots.append(slope_from(picks))
    res["A50"]=res["auc_mean"][FRACS.index(0.50)]
    res["A100"]=res["auc_mean"][FRACS.index(1.00)]
    res["delta_A100_A50"]=round(res["A100"]-res["A50"],4)
    res["slope_logN"]=round(float(np.median(boots)),4)
    res["slope_CI"]=[round(float(np.percentile(boots,2.5)),4),round(float(np.percentile(boots,97.5)),4)]
    plateau = (res["delta_A100_A50"]<=0.02) and (res["slope_CI"][0]<=0<=res["slope_CI"][1])
    rising  = (res["delta_A100_A50"]>0.02) and (res["slope_CI"][0]>0)
    res["verdict"]="PLATEAU (information-limited)" if plateau else ("RISING (sample-limited)" if rising else "MIXED/inconclusive")
    print(f"[{name:22s}] AUC@ {dict(zip(FRACS,res['auc_mean']))}  ΔA100-A50={res['delta_A100_A50']:+.3f}  slope={res['slope_logN']:+.3f} CI{res['slope_CI']}  => {res['verdict']}")
    return res

print("=== H5/H3 learning curve (OOF AUC vs training N) ===")
out=[]
out.append(curve(X12,case,fold,y,'logistic','radiomic-12 (logistic)'))
out.append(curve(X851,case851,fold851,y851,'rf','radiomic-851 (RF)'))
out.append(curve(Xfm,case,fold,y,'logistic','CT-FM 992-d (logistic)'))
out.append(curve(Xfm,case,fold,y,'rf','CT-FM 992-d (RF, non-linear head)'))
json.dump(out,open("h5_learning_curve.json","w"),indent=2)

# figure
fig,ax=plt.subplots(figsize=(6.4,4.4))
for r in out:
    ax.plot(r["n_fp_train"],r["auc_mean"],marker="o",label=f'{r["name"]}')
ax.axhline(0.5,ls=":",c="grey",lw=1); ax.text(r["n_fp_train"][0],0.505,"chance",fontsize=8,color="grey")
ax.set_xlabel("training false-positive components (N)"); ax.set_ylabel("out-of-fold AUC")
ax.set_ylim(0.45,0.85); ax.legend(fontsize=8,loc="upper left")
plt.tight_layout(); plt.savefig("figures/fig_learning_curve.png",dpi=150); plt.close()
print("\n存 h5_learning_curve.json + figures/fig_learning_curve.png")
