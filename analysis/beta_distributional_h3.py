"""H3 分佈式論證:殘餘 cyst FP 是否落在 N=853 標註囊腫的特徵分佈「內部」?
若是 interior points(而非 outlier)→「不可分」是結構性(佔同一特徵空間)、非小-N 樣本限制。
FP 特徵 from classifier_features_pooled.csv(group C_fp_neg,215);囊腫 from gt_cyst_tumour_features.csv
(group cyst,853=全 489 案 GT,'N=900' definitional breadth)。同 cc_features 定義、可比。"""
import numpy as np, csv, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
FEATS=['mean_hu','std_hu','rel_hu_kidney']
def load(path,grp):
    r=[x for x in csv.DictReader(open(path)) if x['group']==grp]
    d={f:np.array([float(x[f]) for x in r],float) for f in FEATS}
    d['logvox']=np.log(np.array([float(x['vox']) for x in r],float)+1); d['n']=len(r); return d
fp=load("classifier_features_pooled.csv","C_fp_neg")
cy=load("gt_cyst_tumour_features.csv","cyst")
ALL=FEATS+['logvox']; res={"n_fp":fp['n'],"n_cyst":cy['n']}
print(f"FP n={fp['n']}  GT 囊腫 n={cy['n']}")
# 指標1:每特徵 FP 落在囊腫[5,95]內
res["envelope_pct"]={}
print("\n=== 每特徵:FP 落在囊腫[5,95]內 ===")
for f in ALL:
    lo,hi=np.percentile(cy[f],[5,95]); frac=float(np.mean((fp[f]>=lo)&(fp[f]<=hi)))
    res["envelope_pct"][f]=round(100*frac); print(f"  {f:14s} cyst[5,95]=[{lo:.1f},{hi:.1f}] FP內={100*frac:.0f}%")
# 指標2:多變量 Mahalanobis(囊腫 mean/cov)
Xc=np.column_stack([cy[f] for f in ALL]); Xf=np.column_stack([fp[f] for f in ALL])
mu=Xc.mean(0); ic=np.linalg.pinv(np.cov(Xc.T))
maha=lambda X:np.sqrt(np.einsum('ij,jk,ik->i',X-mu,ic,X-mu))
mc,mf=maha(Xc),maha(Xf); thr90=np.percentile(mc,90)
res["multivariate_interior_pct"]=round(100*float(np.mean(mf<=thr90)))
res["maha_median_fp"]=round(float(np.median(mf)),2); res["maha_median_cyst"]=round(float(np.median(mc)),2)
print(f"\n=== 多變量:含90%囊腫區域內 FP={res['multivariate_interior_pct']}% | Maha中位 FP={res['maha_median_fp']} vs 囊腫={res['maha_median_cyst']}")
# 指標3:重疊係數
res["overlap"]={}
for f in ALL:
    lo,hi=min(cy[f].min(),fp[f].min()),max(cy[f].max(),fp[f].max()); b=np.linspace(lo,hi,40)
    hc,_=np.histogram(cy[f],b,density=True); hf,_=np.histogram(fp[f],b,density=True)
    res["overlap"][f]=round(float(np.sum(np.minimum(hc,hf))*(b[1]-b[0])),2)
print("重疊係數:",res["overlap"])
json.dump(res,open("beta_distributional_h3.json","w"),indent=2)

# 圖:FP(三角)嵌在囊腫(點)特徵雲 — attenuation × heterogeneity
fig,ax=plt.subplots(figsize=(6,4.6))
ax.scatter(cy['mean_hu'],cy['std_hu'],s=10,c="#9DB4C0",alpha=0.45,label=f"annotated cysts (n={cy['n']})",edgecolor="none")
ax.scatter(fp['mean_hu'],fp['std_hu'],s=34,marker="^",c="#C44E52",alpha=0.8,edgecolor="k",lw=0.3,label=f"residual false positives (n={fp['n']})")
# 囊腫 [5,95] 方框(central 90% per-axis envelope)
x5,x95=np.percentile(cy['mean_hu'],[5,95]); y5,y95=np.percentile(cy['std_hu'],[5,95])
ax.add_patch(plt.Rectangle((x5,y5),x95-x5,y95-y5,fill=False,ls="--",ec="#4C72B0",lw=1.3))
ax.text(x95,y95+1,"cyst central-90% envelope",color="#4C72B0",fontsize=8,ha="right")
ax.set_xlabel("mean attenuation (HU)"); ax.set_ylabel("attenuation heterogeneity (SD, HU)")
ax.set_xlim(-100,200); ax.set_ylim(0,90); ax.legend(fontsize=8,loc="upper right")
plt.tight_layout(); plt.savefig("figures/fig_interiority.png",dpi=150); plt.close()
print("\n存 beta_distributional_h3.json + figures/fig_interiority.png")
