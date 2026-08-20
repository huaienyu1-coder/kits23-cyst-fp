"""
Cyst-aware post-processing for KiTS23 predictions.

Applies two rules to reduce cyst false positives:
  Rule 1 (in-kidney): remove cyst regions not within dilated kidney mask
  Rule 3 (tiny size): remove cyst regions < MIN_CYST_VOXELS (default 3)

Rule 2 (confidence threshold) is not implemented here — requires raw softmax
.npz files which are only available for the unprocessed model outputs.

Background (D-3 hold-out analysis, 98 cases, Step 2 pairB):
  - Case-level FP alarm: 19/48 non-cyst cases (39.6%) — dominant problem
  - Voxel-level under-segment: pred/GT ratio = 0.935 — secondary problem
  - FP alarms range from 2 to 1146 voxels

Usage:
  python cyst_aware_postprocess.py \\
      --input holdout_pipeline/step2_tumor_postprocess/pairB \\
      --output holdout_pipeline/cyst_postprocess/pairB \\
      --gt nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations \\
      [--dilation 5] [--min-vox 3] [--dry-run]
"""

import argparse
import os
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import binary_dilation, label as nd_label


KIDNEY_LABELS = (1, 2)   # kidney tissue + tumor, both within kidney parenchyma
CYST_LABEL = 3
MIN_CYST_VOXELS_DEFAULT = 3
DILATION_VOXELS_DEFAULT = 5


def process_one(pred_path: Path, out_path: Path, dilation: int, min_vox: int) -> dict:
    img = nib.load(str(pred_path))
    pred = np.asarray(img.dataobj).astype(np.uint8)

    cyst_mask = pred == CYST_LABEL
    if not cyst_mask.any():
        nib.save(img, str(out_path))
        return {"removed_rule1": 0, "removed_rule3": 0, "kept": 0, "total_cc": 0}

    # Build kidney base mask (exclude cyst to avoid circularity)
    kidney_base = np.zeros(pred.shape, dtype=bool)
    for lbl in KIDNEY_LABELS:
        kidney_base |= (pred == lbl)

    # Dilate to allow tolerance at kidney boundary
    if dilation > 0:
        kidney_dilated = binary_dilation(kidney_base, iterations=dilation)
    else:
        kidney_dilated = kidney_base

    # Connected components of predicted cyst
    cc_map, n_cc = nd_label(cyst_mask)

    removed_rule3 = 0
    removed_rule1 = 0
    kept = 0

    for cc_id in range(1, n_cc + 1):
        cc = cc_map == cc_id
        size = int(cc.sum())

        # Rule 3: tiny size filter (noise-level only)
        if size < min_vox:
            pred[cc] = 0
            removed_rule3 += 1
            continue

        # Rule 1: in-kidney constraint
        if not (cc & kidney_dilated).any():
            pred[cc] = 0
            removed_rule1 += 1
            continue

        kept += 1

    out_img = nib.Nifti1Image(pred, img.affine, img.header)
    nib.save(out_img, str(out_path))
    return {
        "removed_rule1": removed_rule1,
        "removed_rule3": removed_rule3,
        "kept": kept,
        "total_cc": n_cc,
    }


def compute_cyst_dice(pred: np.ndarray, gt: np.ndarray) -> float:
    p = pred == CYST_LABEL
    g = gt == CYST_LABEL
    inter = (p & g).sum()
    denom = p.sum() + g.sum()
    if denom == 0:
        return 1.0
    return 2.0 * inter / denom


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input prediction directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--gt", default=None, help="GT directory for Dice evaluation")
    parser.add_argument("--dilation", type=int, default=DILATION_VOXELS_DEFAULT,
                        help="Kidney mask dilation (voxels)")
    parser.add_argument("--min-vox", type=int, default=MIN_CYST_VOXELS_DEFAULT,
                        help="Min cyst CC size to keep (Rule 3)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print stats without saving files")
    args = parser.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    cases = sorted(in_dir.glob("*.nii.gz"))
    if not cases:
        print(f"No .nii.gz files found in {in_dir}", file=sys.stderr)
        sys.exit(1)

    total_removed_r1 = 0
    total_removed_r3 = 0
    total_kept = 0
    total_cc = 0
    dice_before_sum = 0.0
    dice_after_sum = 0.0
    n_eval = 0

    fp_alarm_before = 0
    fp_alarm_after = 0
    n_no_cyst_gt = 0

    print(f"Processing {len(cases)} cases  dilation={args.dilation}  min_vox={args.min_vox}")
    print(f"{'Case':<25} {'CC':>4} {'R3':>4} {'R1':>4} {'Kept':>5}", end="")
    if args.gt:
        print(f"  {'DiceBefore':>10}  {'DiceAfter':>10}", end="")
    print()

    for pred_path in cases:
        case_name = pred_path.name
        tmp_out = out_dir / case_name

        if args.dry_run:
            # Load, compute stats, but don't save
            img = nib.load(str(pred_path))
            pred_orig = np.asarray(img.dataobj).astype(np.uint8)
            import tempfile, shutil
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / case_name
                stats = process_one(pred_path, tmp, args.dilation, args.min_vox)
                pred_post = np.asarray(nib.load(str(tmp)).dataobj).astype(np.uint8)
        else:
            img = nib.load(str(pred_path))
            pred_orig = np.asarray(img.dataobj).astype(np.uint8)
            stats = process_one(pred_path, tmp_out, args.dilation, args.min_vox)
            pred_post = np.asarray(nib.load(str(tmp_out)).dataobj).astype(np.uint8)

        total_removed_r1 += stats["removed_rule1"]
        total_removed_r3 += stats["removed_rule3"]
        total_kept += stats["kept"]
        total_cc += stats["total_cc"]

        row = f"{case_name:<25} {stats['total_cc']:>4} {stats['removed_rule3']:>4} {stats['removed_rule1']:>4} {stats['kept']:>5}"

        if args.gt:
            gt_path = Path(args.gt) / case_name
            if gt_path.exists():
                gt = np.asarray(nib.load(str(gt_path)).dataobj).astype(np.uint8)
                d_before = compute_cyst_dice(pred_orig, gt)
                d_after = compute_cyst_dice(pred_post, gt)
                dice_before_sum += d_before
                dice_after_sum += d_after
                n_eval += 1

                gt_has_cyst = int((gt == CYST_LABEL).any())
                pred_before_has_cyst = int((pred_orig == CYST_LABEL).any())
                pred_after_has_cyst = int((pred_post == CYST_LABEL).any())
                if not gt_has_cyst:
                    n_no_cyst_gt += 1
                    if pred_before_has_cyst:
                        fp_alarm_before += 1
                    if pred_after_has_cyst:
                        fp_alarm_after += 1

                row += f"  {d_before:>10.4f}  {d_after:>10.4f}"
            else:
                row += f"  {'(no GT)':>10}  {'':>10}"

        if stats["removed_rule1"] > 0 or stats["removed_rule3"] > 0:
            row += "  <-- modified"
        print(row)

    print()
    print("=" * 60)
    print(f"Total CC:         {total_cc}")
    print(f"Removed Rule 3:   {total_removed_r3}  (size < {args.min_vox} vox)")
    print(f"Removed Rule 1:   {total_removed_r1}  (not in kidney)")
    print(f"Kept:             {total_kept}")
    if args.gt and n_eval > 0:
        print(f"Mean cyst Dice before: {dice_before_sum / n_eval:.4f}  (N={n_eval})")
        print(f"Mean cyst Dice after:  {dice_after_sum / n_eval:.4f}  (N={n_eval})")
        print(f"FP alarms before: {fp_alarm_before}/{n_no_cyst_gt} ({100*fp_alarm_before/max(1,n_no_cyst_gt):.1f}%)")
        print(f"FP alarms after:  {fp_alarm_after}/{n_no_cyst_gt} ({100*fp_alarm_after/max(1,n_no_cyst_gt):.1f}%)")


if __name__ == "__main__":
    main()
