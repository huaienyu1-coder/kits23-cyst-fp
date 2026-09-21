# Pre-registration — H2 Tier-1: is the residual-cyst-FP ceiling specific to the 2nd-place pipeline?
Registered internally 2026-09-19, BEFORE extracting or inspecting any vanilla-nnU-Net FP feature.
Author: Huai-En Yu. Internal timestamp (git history) only.

## Question
Our indistinguishability finding is measured on the 2nd-place pipeline's residual cyst FP (3-model
pair-intersection vote + kidney/tumour post-processing + Type X/Rule3). A reviewer asks: is the
"indistinguishable from true cyst" property created by that specific vote+post-processing, or is it
already present in a PLAIN single nnU-Net? Tier-1 tests this on models we already have, no new training.

## Data (existing raw predictions, fold-0 hold-out, 98 cases)
- Vanilla A = raw **3d_fullres PlainConv** single-model predictions (`holdout_pipeline/raw_predictions/fullres`),
  NO vote, NO kidney/tumour PP, NO Type X/Rule3.
- Vanilla B = raw **ResEnc-L ResidualEncoder** single-model predictions (`.../raw_predictions/resenc_l`)
  — a genuinely different ENCODER architecture (still nnU-Net family).
- Residual cyst FP = predicted-cyst connected components with zero GT-cyst overlap in cyst-NEGATIVE cases
  (group C_fp_neg); true cyst = predicted-cyst CC overlapping GT cyst (group B_tp). Same `cc_features`
  hand-crafted radiomic set as the main analysis (reuse `extract_features.cc_features`, 0 drift).
- Reference cyst distribution for interiority = the N=853 annotated GT cysts (`gt_cyst_tumour_features.csv`).

## Metrics (same battery as the main analysis)
1. Radiomic-12 logistic OOF AUC (FP vs TP), case-grouped CV.
2. Size-only AUC (log voxels).
3. Multivariate distributional interiority: % of vanilla FP falling inside the region containing 90% of
   the N=853 annotated cysts (Mahalanobis on [mean_hu, std_hu, rel_hu_kidney, log-vox]) — same as H3.

## Pre-committed interpretation (fixed now, before results)
For EACH vanilla model:
- **REPLICATES (ceiling is NOT the 2nd-place pipeline's artefact):**
  (radiomic-12 AUC − size-only AUC) <= 0.05  [no appearance signal beyond size]  AND
  multivariate interiority >= 60%  [FP interior to the annotated-cyst distribution].
  => the indistinguishability is present in a plain single model; the ceiling generalises beyond the
  2nd-place vote+post-processing. Report as broadening the claim from "this pipeline" to "nnU-Net on this task."
- **PIPELINE-SPECIFIC (thesis must narrow):**
  (radiomic-12 AUC − size-only AUC) > 0.10 with a usable operating point,  OR  interiority < 40%.
  => the ceiling is a property of the 2nd-place pipeline; narrow the manuscript's generalisation and say so.
- Mixed / in-between: report all three numbers verbatim; no strengthening.

## Scope stated now (honesty)
Tier-1 isolates "3-model vote + post-processing vs a plain single model" and contrasts two ENCODER
architectures (PlainConv vs ResidualEncoder), but BOTH are nnU-Net-family, same preprocessing. It does NOT
establish a different FRAMEWORK/architecture-family — that is Tier-2 (2b, a MONAI SegResNet control, the
first-place's own backbone), planned separately in `h2_crosspipeline_plan.md`. Fold-0 only here (the same
hold-out as the main analysis); pooling folds 1-4 needs extra inference and is a later extension.

Artifacts: `h2_tier1_{fullres,resenc}_features.csv`, `h2_tier1_result.json`, `figures/fig_h2_tier1_interiority.png`.
