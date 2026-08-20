# Release TODO — before setting this repo public

Staged 2026-08-06 (CC). This is a **staging skeleton**, not yet publishable. Blockers below.

## Blocked on CV / analysis (numbers must be final first)
- [ ] Fill final **5-fold mean±SD** numbers into README + paper (after CV folds 2–4).
- [ ] Run the **§4.4 train-set FP+FN recompute** (`analysis/gap3_train_fp_fn_recompute_plan.md`)
      and commit the resulting `train_fp_fn_recompute.json` under `analysis/`.
- [ ] Commit the **pre-registered classifier** result + code once run (may nuance the claim).
- [ ] Commit split JSONs to `analysis/`: seed-45 `splits_final_holdout` (391/98) and the
      `splits_final_cv5` (union 489). **Contains only case IDs, no patient data — safe to commit.**

## Code hygiene before public
- [x] Generalize **rig-specific absolute paths** — done 2026-08-20: `pipeline/rerun_pipeline.sh`,
      `analysis/{ftl_probe_eval,ftl_alpha04_eval,agreement_corroboration_test}.py`, and the two
      `r2_*.sh` now resolve their working root from `KITS23_ROOT` (default `$HOME/KiTS23`); no
      `/home/huaienyu` remains in any `.py`/`.sh`. README documents the export.
- [ ] Confirm no script **vendors** second-place code (khuhm repo = no license). Our files
      must call into a user-provided clone, not embed their source. (Design already enforces this.)
- [ ] Add a minimal `requirements.txt` (nnU-Net v2, SimpleITK, numpy, scipy).
- [ ] Add `figures/` generation scripts (Fig 2 grayscale-safe already exists in tree — move it in).
- [ ] Sweep for any hard-coded case IDs / PHI — none expected (KiTS23 is de-identified), verify.

## At submission
- [ ] Fill README **citation** BibTeX (on acceptance / arXiv).
- [ ] Put the resolved URL into the paper's **Code availability** statement
      (`submission_statements_draft.md`).
- [ ] Tag `v1.0`, set public.

## Decisions (locked 2026-08-06)
- License = **MIT** (matches kits23 toolkit; permissive for research code).
- Scope = our original code only; upstream (nnU-Net Apache-2.0, kits23 MIT, 2nd-place no-license)
  obtained by the user, **not redistributed**.
- Excludes raw images / GT / trained weights (public upstream; weights optional as release asset).

## 2026-08-20 更新（CV 完成後 + 投稿前收尾）
- [x] 5-fold CV 完成、R2 train-FP 重算、pre-registered classifier(outcome a)全部執行完，code+結果已加入(analysis/, results/, prereg/)。
- [x] 絕對路徑泛化(見 Code hygiene 上方)+ README 補 `KITS23_ROOT` 說明。JSON 檔本就無絕對路徑,已確認。
- [x] **審稿模式定案:單盲**(CBM Guide L275)→ 走公開路線,repo 投稿當天 Private→Public、URL 填入正文、tag v1.0(公開與投稿同日,不留空窗)。雙盲備援作廢。
- [ ] 投稿當天:`git tag v1.0` + 設 Public + 把 `github.com/huaienyu1-coder/kits23-cyst-fp` 填入論文 Code availability 的 4 個 placeholder。
- [ ] README citation BibTeX 待接受後補。
- [ ] (使用者)撤銷曝光的舊 PAT。
