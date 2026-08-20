# Cyst false positives as an information limit in a KiTS23 segmentation pipeline

> **Status: pre-release staging.** Reported numbers are being finalized against a full
> 5-fold cross-validation; this repository will be tagged `v1.0` and made public when the
> paper is submitted. Do not cite the numbers here until then.

Code and analyses accompanying the paper *Under the aggregate: a mechanism-level diagnosis of irreducible cyst false positives in a KiTS23 segmentation pipeline* (Huai-En Yu, Chung-Shan Yu).
This is a **diagnostic** study: rather than pushing a leaderboard score, it shows that the
residual **cyst false positives** of a strong second-place KiTS23 pipeline are an
*information limit* (single-phase acquisition + annotation), not a tuning failure — and it
contributes a deterministic correction for one code-level component of the error (the
"Type X" tumour-to-cyst mislabelling).

## What is here (our original code)

```
pipeline/      reproduction driver + majority-vote ablation
postprocess/   our contributions: Type X detector, Rule-3 size filter;
               + the cross-scale cyst filter (a documented negative result)
eval/          Hierarchical Evaluation Class (HEC) + cyst false-positive/negative evaluators;
               Wilson CIs and residual-FP size distribution
analysis/      FTL survival-test evaluators; §4.4 train-set FP/FN recompute spec
prereg/        pre-registered protocol for the multivariate cyst-FP classifier
figures/       figure-generation scripts  [TBD]
```

## What is NOT here (obtain upstream; see licenses below)

This repo does **not** redistribute third-party code. To reproduce the full pipeline you
obtain three upstream components yourself:

| Component | Source | License |
|---|---|---|
| nnU-Net v2 (training/inference backbone) | https://github.com/MIC-DKFZ/nnUNet | Apache-2.0 |
| KiTS23 official toolkit (dataset + HEC metric) | https://github.com/neheller/kits23 | MIT |
| Second-place pipeline (Uhm et al. 2024) — `postprocess.py`, `post_process_tumor.py` | https://github.com/khuhm/KiTS23-2nd-place | **no license (all rights reserved)** — obtain directly; we do not redistribute it |

> The second-place repository carries no license, so its files cannot be legally
> redistributed. Our driver calls into a local clone you provide; it does not vendor
> their code.

## Data

The **KiTS23** dataset (fully de-identified, public) is available via the official
challenge repository (https://github.com/neheller/kits23) and
https://kits-challenge.org/kits23/ . No patient data are contained in this repository.
The case-level train/hold-out split (seed 45, 391/98) and the 5-fold CV split are provided
as JSON under `analysis/` so every reported number is reproducible.

## Reproduce (outline)

1. Install nnU-Net v2 and the KiTS23 toolkit; download the dataset.
2. Train (or obtain) the three hold-out models (low-res plain, full-res plain, ResEnc-L)
   on the seed-45 fold-0 split.
3. Clone the second-place repo for `postprocess.py` / `post_process_tumor.py`.
4. Run `pipeline/rerun_pipeline.sh` — it chains the two upstream post-processing steps,
   the majority vote (`pipeline/p5_ablation.py`), and our `postprocess/` corrections.
5. Score with `eval/eval_hec_cystfp.py` (HEC + cyst FP/FN). Expected hold-out headline:
   mean HEC 0.9022 → 0.9020, cyst false-alarm 39.6% → 33.3%.

Detailed step-by-step paths are in `pipeline/rerun_pipeline.sh` (currently rig-specific;
paths are being generalized before public release — see `RELEASE_TODO.md`).

## Citation

```
[BibTeX TBD on acceptance]
```

## License

Our original code and documentation are released under the MIT License (see `LICENSE`).
Upstream components retain their own licenses as listed above.
