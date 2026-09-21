# Pre-registration — v2 targeted cyst-FP retraining (does a STRONG, non-diluted FP objective train the residual cyst false positives away without deleting true cysts?)
Locked 2026-09-15, BEFORE training. Read-only on raw imaging/GT; derived training only.

## Motivation
§8.4's "training-objective reshaping fails" currently rests on the v1 Focal Tversky trainer
(`nnUNetTrainerFTL_cyst`), whose FP penalty is a **global batch Tversky** in which cyst-negative
false-positive voxels are swamped by true-cyst TP+FN — a weak, diluted FP signal. A reviewer can
fairly object that the model was never strongly pushed to suppress the false positives. We therefore
retrain with a **non-diluted, directly FP-targeting** objective and test β's central prediction at the
training level: since the residual cyst false positives are image-indistinguishable from true cysts
(β: ranking AUC ~0.75 = size; texture/intensity/2D+3D FM at chance beyond size; no stable net-positive
operating point), any objective that suppresses them should suppress true cysts by a comparable amount.

## Fix over v1 (the three audited weaknesses)
1. **Non-diluted FP penalty** — L = DC_and_CE(all classes, unchanged) + λ·mean(cyst_prob over non-cyst
   GT voxels). Every false-positive voxel gets gradient; high-confidence FP dominate (voxel-level hard
   emphasis). DC+CE keeps the cyst Dice/recall term so true cysts are not trivially abandoned.
2. **Hard-negative emphasis** — intrinsic to the direct FP penalty (gradient largest where cyst_prob is
   high on non-cyst voxels = exactly the FP-alarm voxels).
3. **Highest-leverage model** — fine-tune the Fullres model (cyst-dominant, 98.8% of FP voxels) from its
   baseline checkpoint (`-pretrained_weights`), 250 epochs. (Lowres×2 stay baseline, as in the pipeline;
   escalate to all three only if Fullres alone moves the FP.)

## Materials
- Baseline Fullres checkpoint (nnUNetTrainer__nnUNetPlans__3d_fullres, fold 0, seed 45 hold-out).
- Same preprocessed Dataset500_KiTS23, same fold-0 391/98 split. No raw-data change.

## Procedure
- **AMENDMENT 2026-09-15 (locked before Fullres λ=8 finished/evaluated — not fishing): retrain ALL THREE
  pipeline models**, not Fullres alone. Rationale (co-author steer): the pipeline decides on the intersection
  of all three (lowres_plain, lowres_residual, fullres); a complete "training cannot fix it" test must retrain
  all three, else a residual FP surviving via an untrained model is uninterpretable. This closes the v1 FTL
  limitation (Fullres-only). All three baseline checkpoints exist.
- λ_fp sweep {1, 3, 8} (`nnUNetTrainerCystFP_v2_l1/l3/l8`). Start at λ=8 (most aggressive) on ALL THREE;
  evaluate the full ensemble; then fill in λ=1,3 across all three to trace the trade-off.
  - fullres = `nnUNetPlans 3d_fullres`; lowres_plain = `nnUNetPlans 3d_lowres`;
    lowres_residual = `nnUNetResEncUNetLPlans 3d_lowres`. Each fine-tuned from its baseline checkpoint_final.
- Each retrained ENSEMBLE → run the **full headline pipeline** (postprocess → post_process_tumor →
  majority_vote → hard_intersection → Rule3+TypeX), identical driver to the 0.9022/0.9020 headline.
- Self-calibration gate: baseline ensemble in this pipeline must reproduce cyst-FP 33.3% / HEC 0.9020
  before trusting the retrained runs.

## Metrics (per λ, hold-out N=98)
1. pipeline-level cyst-FP rate (cases with predicted cyst among 48 cyst-negative), vs baseline 16/48=33.3%.
2. true-cyst per-class Dice (N=98 both-empty=1; and NaN-excluded), vs baseline.
3. cyst FN (cyst-positive cases with no predicted cyst), vs baseline 2/50.
4. mean HEC + K/M/T axis split (guard tumour collateral, as v1 showed).
5. **the trade-off** — Δ(cyst-FP) vs Δ(true-cyst Dice / FN): do they move together (coupled) or can FP
   drop while true cyst is preserved?

## Decision rule (LOCKED before training)
- **THESIS HOLDS (training-bounded, strengthened)** — if no λ reduces pipeline cyst-FP below baseline
  WITHOUT increasing cyst FN or reducing true-cyst Dice; i.e. FP reduction is coupled to true-cyst loss.
  Report: "even a strong, directly FP-targeting retraining cannot separate the residual cyst false
  positives from true cysts — image-level inseparability propagates to the training objective."
- **THESIS OVERTURNED (positive method)** — if some λ reduces pipeline cyst-FP below baseline while
  preserving true-cyst Dice AND not increasing cyst FN (a clean training-level operating point). Then
  report a cyst-FP-reducing training method as a positive contribution.
- **Between** — partial/coupled; report the trade-off curve, scope claims accordingly.

## Red lines
- Report whatever the sweep gives, including if training works (overturn).
- Report the FP↔true-cyst trade-off, not just FP.
- No cherry-picking λ; report all λ run.
- Wording locked to "the pipeline and the cyst-aware objectives we tested, bounded by image-level
  inseparability" — never "no model can."
