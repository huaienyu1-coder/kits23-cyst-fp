# Pre-registration — separability learning curve (H5/H3 adjudication)
Registered internally 2026-09-18, BEFORE running `h5_learning_curve.py` or seeing any learning-curve result.
Author: Huai-En Yu. Internal timestamp only (git history); not an external OSF registration.

## Question
Is the residual-cyst-FP-vs-true-cyst separability ceiling **information-limited** (a property of
single-phase acquisition) or **sample-/capacity-limited** (a stronger discriminator, or 10x more data,
would separate them)? This adjudicates the two standing objections:
- H3: "how do you know it is not just small N (215 FP)?"
- H5: "you only used FROZEN linear probes; a non-linear head or a fine-tuned representation might separate."

## Data (fixed, already extracted — no re-extraction)
- Components: 215 residual-FP + 724 true-cyst (true-positive) components, pooled over the 5 case-grouped folds.
- Grouping: by case; the pre-assigned `fold` column defines the outer CV.
- Feature sets:
  - (A) 12 pre-registered hand-crafted radiomic features (`classifier_features_pooled.csv`) — logistic (matches osf.io/hzgj6).
  - (B) 851 PyRadiomics features (`beta_pyradiomics_features.csv`) — random forest (non-linear, matches the multi-seed panel).
  - (C) CT-FM 3D frozen embedding, 992-d (`fm_ctfm_emb.npy` + labels `fm_ctfm_yg.npy`) — BOTH logistic AND random forest.
    The RF-on-(C) is the direct test of "a NON-LINEAR head on the learned representation could separate."

## Design — learning curve
Rotating 5-fold OOF (each fold held out once). Within the 4-fold training pool, subsample TRAINING CASES
(grouped, so all components of a case move together) at fractions f in {0.25, 0.50, 0.75, 1.00},
each with 5 independent subsample seeds. For each (feature set, classifier, f, seed) record the
out-of-fold AUC on the held-out fold. Report mean OOF AUC vs effective number of training FP components.
Feature standardisation and model fitting occur strictly inside the training pool (no leakage).

## Pre-committed interpretation (decided now, before results)
Let A50 = mean OOF AUC at f=0.50 and A100 = mean OOF AUC at f=1.00; let s = slope of OOF AUC vs
log(N_train_FP) estimated over f>=0.50, with a 95% CI from the subsample-seed bootstrap.
- **PLATEAU => information-limited (ceiling is NOT a small-N artefact):**
  (A100 - A50) <= 0.02  AND the slope CI includes 0.
  => Conclusion for the paper: "the separability does not improve as training data grows toward the full
  pooled set; the ceiling is information-limited within the range we can measure, not merely sample-limited."
- **RISING => partly sample-/capacity-limited (claim MUST be softened):**
  (A100 - A50) > 0.02  AND slope CI strictly > 0.
  => Conclusion: report the positive slope honestly; downgrade the ceiling claim toward "bounded within
  the available sample; a larger cohort might separate," and say so in the manuscript.
- If the two criteria disagree (mixed): report both numbers verbatim and treat as inconclusive — no strengthening.

## Honest scope limit (committed now)
A plateau at N=215 is the strongest empirical evidence obtainable WITHOUT new data; it does not prove the
curve stays flat at N>>215. We will state exactly this. The learning curve upgrades "we assert small-N is
not the issue" to "we measured the curve and it plateaus up to the maximum N available."

## GPU follow-up (separate pre-commit, runs after the lambda=5 job frees the GPU)
CT-FM encoder adaptation via parameter-efficient fine-tuning (LoRA or last-block unfreeze) on the raw
sub-volumes, under the SAME nested case-grouped CV, OOF AUC. Pre-commit: a fine-tuned OOF AUC that does
NOT exceed the frozen OOF AUC by more than 0.03 = "adapting the representation does not recover a
separating signal" (i.e. the frozen result is not a frozen-probe artefact). Reported whichever way it falls.
