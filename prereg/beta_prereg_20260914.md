# Pre-registration — β: does a literature-grade discriminator separate residual cyst false positives from true cyst under single-phase acquisition?
Locked 2026-09-14, BEFORE running any of the four steps. Read-only on raw imaging/GT; only derived features/models.

## Motivation
The paper's "irreducible under single-phase" claim currently rests on two comparatively weak discriminators:
a 13-feature hand-crafted logistic (out-of-fold AUC 0.68, classifier_prereg / osf.io/hzgj6) and frozen
self-supervised embeddings under a linear probe (DINOv2 0.63, RAD-DINO 0.58). The renal-mass
characterization literature reaches AUC 0.80–0.87 with richer methods, but under conditions we do NOT have:
multi-phase deep learning reaches 0.871 on ~2,400 training patients [Nature Comms 2025, s41467-025-56784-z],
and single-phase KiTS23 radiomics reaches 0.80 for tumour SUBTYPE (not cyst) on 386 PyRadiomics features
with a possible feature-selection leakage [PMC13487467]. We therefore test, honestly, whether a
literature-grade discriminator on OUR single-phase data separates the residual cyst false positives from
true cyst at a usable operating point — the load-bearing defense the paper currently asserts rather than tests.

## Materials (fixed before running)
- 215 residual cyst false-positive components (C_fp_neg, 103 cyst-negative cases) + 724 true-cyst components
  (B_tp), pooled over the five folds — the SAME component set as classifier_prereg.
- fm_patches.npz: 939 windowed 224x224 centre-slice patches for the same components.
- Single-phase KiTS23 (per-case), no phase engineering.

## Steps (each with nested case-grouped CV, outer 5 / inner 3, grouped by case)
1. **Richer hand-crafted features** — a PyRadiomics-scale set (~100–400 features: first-order, GLCM/GLRLM/
   GLSZM texture, shape), feature selection performed INSIDE the inner CV only, compared against the 13-feature set.
2. **Fine-tuned encoder** — unfreeze a pretrained encoder (DINOv2 and/or a medical encoder) and train end-to-end
   on the patches, nested CV (the frozen+linear probe was the weak version).
3. **Small CNN from scratch** on the patches — a capacity/overfit control at n=215.
4. **Credibility assessment** — is any apparent separation stable under nested CV + case-level bootstrap
   (500 resamples), or does it collapse out-of-fold / overfit at n=215 / 103 cases?

## Metrics
- Out-of-fold AUC (reported as illustration, NOT the decision criterion).
- The OPERATING-POINT trade-off (the criterion, identical to classifier_prereg): at the inner-selected
  threshold, false-positive components removed vs true-cyst components deleted; case-level, alarms cleared
  vs cases losing a true cyst. A "usable operating point" removes strictly more false positive than true cyst
  (net-positive), out of fold.

## Decision rule (LOCKED before running)
- **THESIS HOLDS (irreducible strengthened)** — if no discriminator reaches a stable net-positive usable
  operating point under honest nested CV, and/or any apparent separation is not credible (collapses out-of-fold
  or on bootstrap) at this sample size. Report as: "the ceiling resists even literature-grade discriminators,
  and no credible separator exists at the sample size this failure mode yields."
- **THESIS OVERTURNED (positive method)** — if a discriminator reaches a stable, net-positive usable operating
  point under honest nested CV. Then pivot the paper to report a cyst-FP-reducing method (a positive contribution).
- **INCONCLUSIVE** — mixed / sample-size-limited; report as such, scope claims accordingly.

## Red lines
- Feature selection and hyperparameter tuning INSIDE the inner CV only — the literature's leakage
  (LASSO / selection on full data) is exactly what we avoid, and is why some reported AUCs are inflated.
- Report the operating-point cost, not just AUC.
- No cherry-picking of features/thresholds; the operating point is inner-selected and outer-validated.
- Report overfitting/credibility honestly — this is the paper's load-bearing defense; we test it, we do not assert it.
- Whatever the four steps give, including if a method works (thesis overturned), it is reported.
