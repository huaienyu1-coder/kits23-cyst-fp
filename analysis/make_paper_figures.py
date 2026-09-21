"""定稿圖(6張)。venv python(matplotlib 3.10)。輸出 figures/*.png。
資料來源:beta_audit_result.json / beta_tradeoff_result.json / beta_caselevel_curve.json /
beta_caselevel_sizeoverlap.json / fm_ctfm_result.json + 硬碼(v2 pipeline、fold-0-vs-pooled)。"""
import json, os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
os.makedirs("figures", exist_ok=True)
def L(f):
    try: return json.load(open(f))
    except: return None
audit=L("beta_audit_result.json"); trade=L("beta_tradeoff_result.json")
clc=L("beta_caselevel_curve.json"); so=L("beta_caselevel_sizeoverlap.json"); ctfm=L("fm_ctfm_result.json")

# ---------- Fig 1: AUC-vs-size ceiling ----------
def auc_of(k): return audit.get(k,{}).get("auc")
rows=[("pre-reg 12-feat\n(fishing-proof)",auc_of("prereg12 LR") or 0.68,"#4C72B0"),
      ("PyRadiomics 851\n(RF)",auc_of("full851 RF-s0") or 0.757,"#4C72B0"),
      ("texture-only\n(no shape, RF)",auc_of("noshape RF-s0") or 0.752,"#4C72B0"),
      ("shape-only\n(size proxy)",0.752,"#DD8452"),
      ("size only\nlog(vox)",0.732,"#DD8452"),
      ("CT-FM 3D\nfrozen",(ctfm or {}).get("honest_oof_auc",0.567),"#C44E52")]
fig,ax=plt.subplots(figsize=(7,4))
xs=np.arange(len(rows)); ax.bar(xs,[r[1] for r in rows],color=[r[2] for r in rows])
ax.axhline(0.732,ls="--",c="#DD8452",lw=1.3); ax.text(len(rows)-0.5,0.738,"size ceiling ≈0.73",color="#DD8452",ha="right",fontsize=9)
ax.axhline(0.5,ls=":",c="grey",lw=1); ax.text(0,0.505,"chance",color="grey",fontsize=8)
for i,r in enumerate(rows): ax.text(i,r[1]+0.006,f"{r[1]:.2f}",ha="center",fontsize=9)
ax.set_xticks(xs); ax.set_xticklabels([r[0] for r in rows],fontsize=8); ax.set_ylim(0.45,0.82)
ax.set_ylabel("out-of-fold AUC")
plt.tight_layout(); plt.savefig("figures/fig1_auc_vs_size.png",dpi=150); plt.close()

# ---------- Fig 2: multi-seed operating point (honest rate-net) ----------
pts=[]  # (label, net, group)
for k,v in audit.items():
    if v.get("rate"):
        g=("pre-reg" if "prereg" in k else ("RF" if "RF" in k else "HGB"))
        pts.append((k,v["rate"]["net"],g))
fig,ax=plt.subplots(figsize=(7,4))
cols={"pre-reg":"#C44E52","RF":"#4C72B0","HGB":"#55A868"}
rng=np.random.RandomState(0)
for lbl,net,g in pts:
    ax.scatter(net,cols and rng.uniform(-0.15,0.15),s=70,color=cols[g],alpha=0.85,edgecolor="k",lw=0.4,zorder=3)
ax.axvline(0,c="k",lw=1); ax.set_yticks([]); ax.set_ylim(-0.5,0.5)
ax.set_xlabel("honest operating-point net  (FP removed − true cysts deleted)")
from matplotlib.lines import Line2D
ax.legend([Line2D([0],[0],marker='o',ls='',color=c,mec='k') for c in cols.values()],list(cols),loc="upper right",fontsize=8)
ax.text(-9,-0.35,"pre-reg −9\n(fishing-proof)",color="#C44E52",fontsize=8,ha="center")
plt.tight_layout(); plt.savefig("figures/fig2_multiseed_opnet.png",dpi=150); plt.close()

# ---------- Fig 3: β trade-off curve (hugging diagonal) ----------
fig,ax=plt.subplots(figsize=(6,5))
budgets=[0,1,2,3,5,10]
if trade:
    for d in trade:
        mf=d.get("maxfp")
        if not mf: continue
        ys=[mf.get(str(b),mf.get(b,0)) for b in budgets]
        ax.plot(budgets,ys,marker="o",label=d["name"][:20],lw=1.4)
ax.plot([0,10],[0,10],ls="--",c="k",lw=1.2,label="y=x (1 true cyst per FP)")
ax.set_xlabel("true-cyst components deleted (budget)"); ax.set_ylabel("false positives removed")
ax.legend(fontsize=7); ax.set_xlim(0,10); ax.set_ylim(0,15)
plt.tight_layout(); plt.savefig("figures/fig3_tradeoff_diagonal.png",dpi=150); plt.close()

# ---------- Fig 4: case-level (clearing an alarm costs harming true-cyst cases) ----------
fig,ax=plt.subplots(figsize=(6,4))
seeds=[k for k in (clc or {}) if k.startswith("seed")]
harmed=[clc[s]["first_alarm_cleared"][2] for s in seeds]; cleared=[clc[s]["first_alarm_cleared"][1] for s in seeds]
x=np.arange(len(seeds)); w=0.35
ax.bar(x-w/2,cleared,w,label="alarm cases cleared",color="#55A868")
ax.bar(x+w/2,harmed,w,label="true-cyst cases harmed",color="#C44E52")
for i,h in enumerate(harmed): ax.text(i+w/2,h+0.3,str(h),ha="center",fontsize=9)
ax.set_xticks(x); ax.set_xticklabels([s.replace("seed","seed ") for s in seeds])
ax.set_ylabel("cases"); ax.set_ylim(0,15)
ax.legend(fontsize=9); plt.tight_layout(); plt.savefig("figures/fig4_caselevel.png",dpi=150); plt.close()

# ---------- Fig 5: v2 λ retraining trade-off (硬碼 fullres-swap pipeline) ----------
lam=["baseline","λ=1","λ=3","λ=5","λ=8"]; fp=[33.3,37.5,33.3,35.4,18.8]; fn=[2,4,2,1,5]; T=[0.851,0.840,0.846,0.852,0.844]
xi=[0,1,2,3,4]
fig,ax=plt.subplots(figsize=(6.5,4)); ax2=ax.twinx()
xok=[i for i,v in enumerate(fp) if v is not None]
ax.plot([xi[i] for i in xok],[fp[i] for i in xok],marker="o",color="#4C72B0",label="cyst-FP %")
# H4 multi-seed run-to-run band (fullres-swap FP %) on λ=1 (xi=1) and λ=3 (xi=2): four-seed spread
FP_SEED_PCT={1:[37.5,31.2,37.5,37.5], 2:[33.3,33.3,35.4,33.3]}
for xidx,vv in FP_SEED_PCT.items():
    ax.errorbar(xi[xidx], fp[xidx], yerr=[[fp[xidx]-min(vv)],[max(vv)-fp[xidx]]],
                fmt='none', ecolor="#4C72B0", capsize=4, elinewidth=1.2, alpha=0.75)
ax.plot([xi[i] for i in xok],[fn[i]*5 for i in xok],marker="s",color="#C44E52",label="cyst FN (×5 scale)")
ax2.plot([xi[i] for i in xok],[T[i] for i in xok],marker="^",color="#55A868",label="tumour Dice (T)")
ax.set_xticks(xi); ax.set_xticklabels(lam); ax.set_ylabel("cyst-FP % / FN×5",color="#4C72B0")
ax2.set_ylabel("tumour Dice",color="#55A868"); ax2.set_ylim(0.83,0.855)
pass  # fig5 title in LaTeX caption
l1,la1=ax.get_legend_handles_labels(); l2,la2=ax2.get_legend_handles_labels(); ax.legend(l1+l2,la1+la2,fontsize=8,loc="center left")
plt.tight_layout(); plt.savefig("figures/fig5_v2_lambda.png",dpi=150); plt.close()

# ---------- Fig 6: fold-0 vs pooled 5-fold (三個修正) ----------
fig,axs=plt.subplots(1,3,figsize=(11,3.6))
# Type X collateral: fold-0 clean vs folds with GT-cyst>tumour deleted (ratio)
axs[0].bar(["fold0","fold1","fold2","fold3","fold4"],[0.3,4.5,0.5,0.4,10.4],color=["#55A868","#C44E52","#55A868","#55A868","#C44E52"])
axs[0].axhline(1,ls="--",c="k",lw=1); axs[0].set_ylabel("GT-cyst / tumour deleted (ratio)")
axs[0].set_title("(a)"); axs[0].set_yscale("log")
# taxonomy: fullres vs resenc participation across folds
axs[1].plot(range(5),[98.8,96.2,84.3,99.2,97.2],marker="o",color="#4C72B0",label="full-res")
axs[1].plot(range(5),[23.4,74,50,40,37],marker="s",color="#DD8452",label="ResEnc-L (range 23–74)")
axs[1].set_xticks(range(5)); axs[1].set_xticklabels([f"f{i}" for i in range(5)]); axs[1].set_ylabel("FP-voxel participation %")
axs[1].set_title("(b)"); axs[1].legend(fontsize=8)
# location: fold-0 vs pooled tumour-touch %
axs[2].bar(["fold-0\n(reported)","pooled 5-fold"],[7.7,17.2],color=["#DD8452","#4C72B0"])
axs[2].text(0,8,"'2/26, 89 mm'",ha="center",fontsize=8); axs[2].text(1,18,"37/215",ha="center",fontsize=8)
axs[2].set_ylim(0,20); axs[2].set_ylabel("FP touching tumour %"); axs[2].set_title("(c)")
plt.tight_layout(); plt.savefig("figures/fig6_fold0_vs_pooled.png",dpi=150); plt.close()

print("DONE — figures/:", sorted(os.listdir("figures")))
