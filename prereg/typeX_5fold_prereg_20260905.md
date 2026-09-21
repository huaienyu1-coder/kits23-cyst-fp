# Pre-registration — Type X correction, five-fold robustness recompute
Locked 2026-09-05, BEFORE inspecting folds 1–4 results. Read-only re-derivation on existing predictions.

## Question
Contribution (a) — the deterministic Type X correction — and its reported benefit are established on
fold-0 (N=98), which the manuscript itself calls "the most favourable of five folds." Does the
correction's benefit hold across **all five CV folds**, or is it fold-0-lucky?

## Materials (per fold, all already on disk; no retraining, no raw-data access)
- baseline post-vote prediction (pair-intersection):
  fold0 `holdout_pipeline/soft_voting/hard_intersection`; fold1–4 `repro_check/scratch_fold{k}/hard_intersection`
- raw-main (Fullres) + raw-chk (ResEnc-L) single-model predictions (same fold dirs)
- GT `nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations`

## Procedure (identical detector as headline)
Apply `post_process_typeX.py` logic per case: for each predicted-cyst CC, TypeX voxels =
`cc ∧ ((rawF==tumour)∨(rawR==tumour)) ∧ (rawF≠cyst) ∧ (rawR≠cyst)`; remove CC (→kidney) if
fraction ≥ **t=0.7**; also Rule-3 size filter min_vox=3. Identical to the submitted headline.

## Metrics recorded per fold
1. ΔHEC = mean-HEC(after) − mean-HEC(before), 3-axis, over the fold's val cases.
2. cyst FP (cases with predicted cyst among cyst-negative), before vs after.
3. per-class cyst Dice (N=all, both-empty→1) and NaN-excluded, before vs after.
4. **collateral**: of all Type-X-removed voxels, share that is GT-cyst (a true cyst wrongly deleted)
   vs GT-tumour (a malignant record correctly cleaned) vs GT-kidney/bg.

## Self-calibration gate (fold-0 must reproduce the paper)
fold-0 must reproduce: ~3 Type-X CCs / ~742 removed vox, cyst FP 39.6%→33.3%, cyst Dice ≈ +0.036,
ΔHEC ≈ −0.0002. If fold-0 does NOT reproduce → STOP (pipeline drift), folds 1–4 untrustworthy.

## Decision rule (LOCKED before seeing folds 1–4)
- **PASS** (correction is fold-robust; contribution (a) stands as a general claim) — on **≥4/5 folds ALL of**:
  (i) cyst FP non-increasing; (ii) cyst Dice non-decreasing; (iii) ΔHEC ≥ −0.001 (negligible, matching
  the "consequence-free" framing); (iv) removed GT-cyst voxels < removed GT-tumour voxels.
- **FAIL** (must rewrite/scope (a)) — if on **≥2 folds** any of: cyst Dice decreases; ΔHEC < −0.001;
  or GT-cyst-deleted > GT-tumour-cleaned. Then (a) cannot be claimed as a general deterministic
  correction; it must be scoped to fold-0 or reframed (the honest outcome we want to know early).
- Between (mixed 3/5) → report as "fold-dependent", scope claims accordingly.

## Red line
Report whatever the five folds give, including if it weakens (a). This is a pre-committed robustness
test, not a search for a favourable framing.
