# Pre-registration — v2 targeted-retraining multi-seed robustness (H4 adjudication)
Registered internally 2026-09-18, BEFORE running any additional v2 fine-tune seed or seeing its result.
Author: Huai-En Yu. Internal timestamp (git history) only; not an external OSF registration.

## Question
The training-layer conclusion --- "no penalty setting reduces the cyst false-positive rate without an
equal or greater cost in true cyst" --- rests on **single fine-tuning runs on fold 0**. The one visible
wrinkle: the three-model λ=1 run gave 17 alarm cases / 4 missed cysts, WORSE on both axes than λ=3's
16 / 2, i.e. a **non-monotonic** mild-end. A hostile reviewer (and our own harsh review, H4) reads this
as "fine-tuning noise is the same magnitude as the effect, so 'no setting helps' may be a single-run
artefact." This pre-registers the experiment that adjudicates it: **measure the run-to-run noise floor**.

## Mechanism (verified 2026-09-18)
nnU-Net v2 trains non-deterministically: `cudnn.deterministic=False`, `cudnn.benchmark=True`
(run_training.py L118-119, L196-197), and the augmentation dataloaders are constructed with `seeds=None`
(nnUNetTrainer.py L726/730). Fine-tuning fixes the **initialisation** (`-pretrained_weights` = the same
baseline checkpoint) and the **data split** (fold 0), so **an independent re-run of the identical command
is an independent seed draw**: same init, same split, same LAM_FP; only the stochastic training trajectory
(augmentation order, dropout, minibatch order, non-deterministic cuDNN) varies. No code change is needed
to obtain seeds; we re-run and archive each run's fold_0 output separately.

## Design (fullres-swap, the fig.~5 / S13 basis; the full-resolution model carries the false positives)
- λ points: **λ=3** (the load-bearing, baseline-case-identical setting) and **λ=1** (the non-monotonic blip).
- Seeds per λ: the existing single run counts as seed 1; add **3 more** per λ (→ 4 runs per λ, 6 new runs).
- Each run: fine-tune fullres 250 epochs from the baseline fold-0 checkpoint under the v2 trainer subclass;
  auto-validation produces the fold-0 predictions; run the headline pipeline (fullres-swap: this v2 fullres
  + baseline lowres + baseline resenc) via `rerun_pipeline_3model.sh`; score with `eval_hec_cystfp.py`.
- Record per run: the cyst-FP alarm-case COUNT (of 48), the alarm-case SET, the missed-cyst (FN) count,
  and mean HEC.

## Pre-committed interpretation (fixed now, before results)
Let baseline = 16 alarm cases / 2 missed cysts. For each run define a "genuine reduction" as
**alarm count < 16 WITHOUT the missed-cyst count rising above 2** (FP down without collateral).
- **ROBUST-NULL (training-layer conclusion holds at the seed level):**
  across ALL seeds at λ=3 and λ=1, NO run is a genuine reduction; AND the λ=1 and λ=3 alarm-count ranges
  OVERLAP (so the 17-vs-16 non-monotonicity sits inside run-to-run noise).
  => Manuscript states the result as **seed-robust**, and reports the measured noise band (min–max count)
  so any claimed effect must exceed it. The λ=1 blip is explicitly labelled as within the noise floor.
- **REDUCTION-FOUND (claim must be softened):**
  some seed at some λ is a genuine reduction (FP down, FN not up).
  => Report it verbatim; downgrade "no setting reduces FP without collateral" to acknowledge a
  seed-dependent partial reduction, and treat that seed as a lead rather than dismiss it.
- Report the per-λ noise band regardless of which case obtains.

## Scope, stated now (single-fold honesty)
This measures **run** variance on fold 0. It does NOT establish cross-fold generalisation of the retraining.
We commit to two honest statements: (i) the residual-FP MODE that the retraining targets is present on ALL
FIVE folds (pooled 215 FP; per-fold alarm rates 33–51%), so what is fold-0-specific is the retraining
action, not the phenomenon; (ii) cross-fold RE-TRAINING (baseline fold_1–4 checkpoints exist, so it is
feasible) is deferred to the cross-pipeline / generalisation round, where it is planned in full alongside
H2. Multi-seed here closes the single-RUN half of H4; the single-FOLD half is bounded by (i) and scheduled
by (ii).

Artifacts to produce: `h4_multiseed_result.json` (per-run count/set/FN/HEC + per-λ noise band + verdict),
archived `fold_0_seed{k}` folders, and an updated Fig.~5 / supplement S13 seed-band annotation.
