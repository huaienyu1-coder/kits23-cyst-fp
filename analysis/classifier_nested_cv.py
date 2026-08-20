#!/usr/bin/env python3
"""Pre-registered multivariate radiomic classifier (frozen classifier_prereg_20260801.md).
Separates residual FP (C_fp_neg) from true cyst (B_tp) on pooled 5-fold components.
Nested GroupKFold-by-case; simple regularized logistic model; hyperparameter C AND operating-point
threshold both selected on INNER, validated on OUTER. §5 success (component level, per §2/prechecks)
= outer-fold safe point recovering >=25% FP net-positive -> §6(b); else §6(a). Case level reported
alongside. `--selfcheck` runs Gates 3+4 only."""
import argparse, json, csv, os, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score

FEATURES = ["mean_hu","std_hu","p5","p25","p50","p75","p95","vol_mm3","extent","sphericity","margin_grad","rel_hu_kidney"]
EXCLUDED = ["min_hu","max_hu","elongation","vox"]
SIZE_THRESH = 267.0; RECOVERY = 0.25; CGRID = [0.1, 1.0, 10.0]
RNG = np.random.RandomState(45)

def load():
    rows = [r for r in csv.DictReader(open(os.path.expanduser("~/KiTS23/classifier_features_pooled.csv")))
            if r["group"] in ("C_fp_neg", "B_tp")]
    X = np.array([[float(r[f]) for f in FEATURES] for r in rows], float)
    y = np.array([1 if r["group"] == "C_fp_neg" else 0 for r in rows])
    g = np.array([f"{r['fold']}_{r['case']}" for r in rows])
    vox = np.array([float(r["vox"]) for r in rows])
    return rows, X, y, g, vox

def selfcheck(rows, X, y, g, vox):
    hdr = list(rows[0].keys())
    print("=== Gate 4: feature set == §3 locked set ===")
    assert len(FEATURES) == 12 and not any(f in FEATURES for f in EXCLUDED) and all(f in hdr for f in FEATURES)
    print(f"  features (12): {FEATURES}\n  excluded: {EXCLUDED}  ✅")
    n = int(np.isnan(X).sum()) + int(np.isinf(X).sum()); assert n == 0, f"{n} nan/inf in §3 features"
    print(f"=== nan/inf: 0 ✅ (X {X.shape}) ===")
    for i, (tr, te) in enumerate(GroupKFold(5).split(X, y, g)):
        assert not (set(g[tr]) & set(g[te])), f"outer fold {i} LEAKAGE"
    print("=== Gate 3: 5 outer folds, 0 shared cases (GroupKFold by case) ✅ ===")
    print(f"=== population: FP {int(y.sum())} / TP {int((y==0).sum())} / cases {len(set(g))} ; "
          f"size@{SIZE_THRESH:.0f}: small {int((vox<SIZE_THRESH).sum())} large {int((vox>=SIZE_THRESH).sum())} ===")
    print("SELF-CHECK: ALL PASS ✅")

def pick_threshold(s, yv):
    best_t, best_net = None, 0
    for t in np.unique(s):
        rm = s >= t; net = int((rm & (yv==1)).sum()) - int((rm & (yv==0)).sum())
        if net > best_net: best_net, best_t = net, t
    return best_t

def nested_cv(X, y, g, vox):
    oof_s = np.full(len(y), np.nan); oof_rm = np.zeros(len(y), bool); settings = []
    for fi, (tr, te) in enumerate(GroupKFold(5).split(X, y, g)):
        bestC, bestauc = 1.0, -1
        for C in CGRID:
            au = []
            for itr, ite in GroupKFold(3).split(X[tr], y[tr], g[tr]):
                if len(np.unique(y[tr][itr])) < 2 or len(np.unique(y[tr][ite])) < 2: continue
                m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000, class_weight="balanced"))
                m.fit(X[tr][itr], y[tr][itr]); au.append(roc_auc_score(y[tr][ite], m.predict_proba(X[tr][ite])[:,1]))
            if au and np.mean(au) > bestauc: bestauc, bestC = np.mean(au), C
        iscore = np.full(len(tr), np.nan)
        for itr, ite in GroupKFold(3).split(X[tr], y[tr], g[tr]):
            if len(np.unique(y[tr][itr])) < 2: continue
            m = make_pipeline(StandardScaler(), LogisticRegression(C=bestC, max_iter=2000, class_weight="balanced"))
            m.fit(X[tr][itr], y[tr][itr]); iscore[ite] = m.predict_proba(X[tr][ite])[:,1]
        ok = ~np.isnan(iscore); t_star = pick_threshold(iscore[ok], y[tr][ok])
        m = make_pipeline(StandardScaler(), LogisticRegression(C=bestC, max_iter=2000, class_weight="balanced"))
        m.fit(X[tr], y[tr]); s = m.predict_proba(X[te])[:,1]; oof_s[te] = s
        if t_star is not None: oof_rm[te] = s >= t_star
        settings.append({"outer_fold": fi, "inner_selected_C": bestC, "inner_mean_AUC": round(float(bestauc),3),
                         "inner_selected_threshold": None if t_star is None else round(float(t_star),3),
                         "outer_test_n": int(len(te))})
    return oof_s, oof_rm, settings

def auc_ci(y, s, g, n=2000):
    cases = np.array(sorted(set(g))); m = {c:i for i,c in enumerate(cases)}; idx = np.array([m[c] for c in g])
    aucs = []
    for _ in range(n):
        bc = RNG.choice(len(cases), len(cases), replace=True)
        sel = np.concatenate([np.where(idx==c)[0] for c in bc])
        if len(np.unique(y[sel])) < 2: continue
        aucs.append(roc_auc_score(y[sel], s[sel]))
    return [round(float(np.percentile(aucs,2.5)),3), round(float(np.percentile(aucs,97.5)),3)]

def comp_summary(y, s, rm, tag):
    fp, tp = int((y==1).sum()), int((y==0).sum())
    fr, tl = int((rm & (y==1)).sum()), int((rm & (y==0)).sum())
    auc = round(roc_auc_score(y, s),3) if len(np.unique(y))==2 else None
    return {"tag":tag,"FP_comp":fp,"TP_comp":tp,"FP_removed":fr,"TP_lost":tl,
            "recovery_frac":round(fr/fp,3) if fp else 0,"net_positive":bool(fr>tl),
            "meaningful_ge25pct":bool(fr>tl and fp and fr/fp>=RECOVERY),"outer_AUC_illustration":auc}

def case_summary(y, rm, g):
    fp_cases = sorted(set(g[y==1])); tp_cases = sorted(set(g[y==0]))
    cleared = sum(1 for c in fp_cases if (rm[(g==c)&(y==1)]).all())     # all FP comps of the case removed
    harmed  = sum(1 for c in tp_cases if (rm[(g==c)&(y==0)]).any())     # a true cyst comp lost
    return {"FP_cases":len(fp_cases),"FP_cases_cleared":cleared,"TP_cases":len(tp_cases),
            "TP_cases_harmed":harmed,"case_recovery_frac":round(cleared/len(fp_cases),3) if fp_cases else 0,
            "case_net_positive":bool(cleared>harmed)}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--selfcheck", action="store_true"); a = ap.parse_args()
    rows, X, y, g, vox = load(); selfcheck(rows, X, y, g, vox)
    if a.selfcheck: print("\n[--selfcheck] stopping before analysis."); raise SystemExit
    s, rm, settings = nested_cv(X, y, g, vox)
    sm, lg = vox < SIZE_THRESH, vox >= SIZE_THRESH
    res = {"model":"LogisticRegression(L2, class_weight=balanced), StandardScaler; nested GroupKFold-by-case outer=5 inner=3",
           "hyperparameter_and_threshold":"C and operating-point threshold BOTH selected on inner, validated on outer (see per_fold_settings)",
           "per_fold_settings": settings,
           "component_level":{"overall":comp_summary(y,s,rm,"overall"),
                              "small_lt267":comp_summary(y[sm],s[sm],rm[sm],"small"),
                              "large_ge267":comp_summary(y[lg],s[lg],rm[lg],"large")},
           "case_level_alongside": case_summary(y, rm, g),
           "outer_AUC_overall":round(roc_auc_score(y,s),3), "outer_AUC_95CI_bootstrap_by_case":auc_ci(y,s,g),
           "AUC_note":"AUC is illustration only; the pre-registered criterion is the held-out safe operating point (§5/§7).",
           "criterion":"§5 component-level: FP_removed>TP_lost and recovery>=25% on held-out -> §6(b); else §6(a). Case level alongside.",
           "baselines":"§8.5 univariate AUC<=0.66 / no safe point; deployed Rule-3 size filter"}
    res["OUTCOME"] = "(b) pivot" if res["component_level"]["overall"]["meaningful_ge25pct"] else "(a) ceiling confirmed at N=215 components / 103 cases"
    json.dump(res, open(os.path.expanduser("~/KiTS23/classifier_result.json"),"w"), indent=2)
    print("\n=== RESULT ===")
    print("  component overall:", res["component_level"]["overall"])
    print("  component small:  ", res["component_level"]["small_lt267"])
    print("  component large:  ", res["component_level"]["large_ge267"])
    print("  case-level:       ", res["case_level_alongside"])
    print(f"  outer AUC {res['outer_AUC_overall']} 95%CI {res['outer_AUC_95CI_bootstrap_by_case']}")
    print(f"  OUTCOME: {res['OUTCOME']}")
