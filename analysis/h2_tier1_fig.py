"""H2 Tier-1 figure: raw single-model residual cyst FP are interior points of the annotated-cyst
distribution, across two encoder architectures (vanilla PlainConv fullres + ResidualEncoder).
Parallels the main-text fig_interiority. Uses h2_tier1_*_features.csv + gt_cyst_tumour_features.csv."""
import csv, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

def load(path, grp):
    r=[x for x in csv.DictReader(open(path)) if x['group']==grp]
    return np.array([float(x['mean_hu']) for x in r]), np.array([float(x['std_hu']) for x in r])

cy_x, cy_y = load("gt_cyst_tumour_features.csv","cyst")   # N=853 annotated cysts
panels=[("h2_tier1_fullres_PlainConv_features.csv","(a) full-resolution (PlainConv)"),
        ("h2_tier1_resenc_ResidualEnc_features.csv","(b) residual-encoder (ResidualEnc)")]
x5,x95=np.percentile(cy_x,[5,95]); y5,y95=np.percentile(cy_y,[5,95])

fig,axs=plt.subplots(1,2,figsize=(10,4.4),sharex=True,sharey=True)
for ax,(csvf,ttl) in zip(axs,panels):
    fp_x,fp_y=load(csvf,"C_fp_neg")
    ax.scatter(cy_x,cy_y,s=9,c="#9DB4C0",alpha=0.40,edgecolor="none",label=f"annotated cysts (n={len(cy_x)})")
    ax.scatter(fp_x,fp_y,s=42,marker="^",c="#C44E52",alpha=0.85,edgecolor="k",lw=0.3,
               label=f"raw FP (n={len(fp_x)})")
    ax.add_patch(plt.Rectangle((x5,y5),x95-x5,y95-y5,fill=False,ls="--",ec="#4C72B0",lw=1.3))
    ax.set_xlabel("mean attenuation (HU)"); ax.set_title(ttl,fontsize=10)
    ax.set_xlim(-100,200); ax.set_ylim(0,90); ax.legend(fontsize=8,loc="upper right")
axs[0].set_ylabel("attenuation heterogeneity (SD, HU)")
axs[0].text(x95,y95+1,"cyst central-90%",color="#4C72B0",fontsize=8,ha="right")
plt.tight_layout(); plt.savefig("figures/fig_h2_tier1_interiority.png",dpi=150); plt.close()
print("存 figures/fig_h2_tier1_interiority.png")
