# Cyst false positives as an information limit in a KiTS23 segmentation pipeline

> **Status: released (`v1.0`).** This is the version of record accompanying the submitted
> manuscript. All reported numbers are final, validated against the full five-fold
> cross-validation; every load-bearing number in the paper is backed by an artifact in
> `results/` regenerable with the scripts here.

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
analysis/      survival-test evaluators (FTL, agreement, cascade, confidence, classifier);
               train-set FP/FN recompute; pooled feature extraction + figure scripts
prereg/        pre-registered protocols (classifier, OSF-archived; agreement corroboration)
results/       result artifacts (JSON) backing every load-bearing number in the paper
figures/       released figure assets (generation scripts in analysis/)
```

## What is NOT here (obtain upstream; see licenses below)

This repo does **not** redistribute third-party code. To reproduce the full pipeline you
obtain three upstream components yourself:

| Component | Source | License |
|---|---|---|
| nnU-Net v2 (training/inference backbone) | https://github.com/MIC-DKFZ/nnUNet | Apache-2.0 |
| KiTS23 official **toolkit code** (HEC metric, data loaders) | https://github.com/neheller/kits23 | MIT |
| KiTS23 **imaging dataset + segmentation labels** | https://kits-challenge.org/kits23/ | **CC BY-NC-SA 4.0** — non-commercial, share-alike, attribution; obtain directly, we do not redistribute the images |
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

Every script resolves its local working root from the `KITS23_ROOT` environment variable
(default `$HOME/KiTS23`). Point it at your KiTS23 working tree — the directory holding
`nnUNet_raw/`, `nnUNet_preprocessed/`, `nnUNet_results/`, and `holdout_pipeline/` — before
running anything; no in-script path editing is needed:

```bash
export KITS23_ROOT=/path/to/your/KiTS23
```

1. Install nnU-Net v2 and the KiTS23 toolkit; download the dataset.
2. Train (or obtain) the three hold-out models (low-res plain, full-res plain, ResEnc-L)
   on the seed-45 fold-0 split.
3. Clone the second-place repo for `postprocess.py` / `post_process_tumor.py`.
4. Run `pipeline/rerun_pipeline.sh` — it chains the two upstream post-processing steps,
   the majority vote (`pipeline/p5_ablation.py`), and our `postprocess/` corrections.
5. Score with `eval/eval_hec_cystfp.py` (HEC + cyst FP/FN). Expected hold-out headline:
   mean HEC 0.9022 → 0.9020, cyst false-alarm 39.6% → 33.3%.

Detailed step-by-step commands are in `pipeline/rerun_pipeline.sh`; all of its paths derive
from `KITS23_ROOT` (see above), so it runs unmodified once that variable points at your tree.

## Citation

```
[BibTeX TBD on acceptance]
```

## License

This repository is **dual-licensed** by content type:

| Content | License | File |
|---|---|---|
| Our original **code** and documentation | MIT | `LICENSE` |
| Released **result tables derived from KiTS23 data** (`results/*.json`, `analysis/classifier_features_pooled.csv`) | **CC BY-NC-SA 4.0** | `LICENSE-DATA` |
| KiTS23 **imaging data** | not redistributed here — obtain from the official challenge (CC BY-NC-SA 4.0) | — |

The result tables contain only derived statistics (rates, counts, per-component radiomic
features, thresholds) and public KiTS23 case identifiers — **no voxel arrays or image
content**. Because they are computed from the KiTS23 dataset (CC BY-NC-SA 4.0), we release
them under the same CC BY-NC-SA 4.0 terms (attribution, non-commercial, share-alike) and
ask users to cite the KiTS challenge paper. Upstream code components retain their own
licenses as listed above.
