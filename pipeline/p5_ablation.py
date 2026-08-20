"""
P5 Ablation: majority voting threshold experiment
Run AFTER Phase A (2 models) + Phase B P1 (3rd model, ResEnc) are complete.

With N=2 models: num_majority=1 == ceil(2/2)=1, no difference. Run with N=3.
With N=3 models: tests union (1), majority (2), intersection (3).

Usage:
    python p5_ablation.py \
        --inputs /path/to/pp_model1 /path/to/pp_model2 /path/to/pp_model3 \
        --gt /path/to/gt_segmentations \
        --output_dir ~/KiTS23/p5_ablation_results
"""

import os
import math
import argparse
import json
import shutil
import nibabel as nib
import numpy as np
from datetime import datetime
from time import time


def dice_binary(pred_mask, gt_mask):
    """Dice for two binary masks. NaN if both empty (excluded from average)."""
    p = pred_mask.astype(bool)
    g = gt_mask.astype(bool)
    if p.sum() == 0 and g.sum() == 0:
        return float('nan')
    return 2.0 * float((p & g).sum()) / float(p.sum() + g.sum())


def majority_vote(list_of_input_folders, output_folder, num_majority):
    """Run majority voting with given threshold. Adapted from KiTS23-2nd-place."""
    os.makedirs(output_folder, exist_ok=True)
    cases = sorted(f for f in os.listdir(list_of_input_folders[0]) if f.endswith('.nii.gz'))

    for case in cases:
        list_seg_nib = [nib.load(os.path.join(d, case)) for d in list_of_input_folders]
        list_seg = [s.get_fdata() for s in list_seg_nib]

        seg_out = np.zeros_like(list_seg[0])

        # kidney (foreground)
        vote = sum((seg > 0).astype(np.int16) for seg in list_seg)
        seg_out[vote >= num_majority] = 1

        # cyst (class > 1)
        vote = sum((seg > 1).astype(np.int16) for seg in list_seg)
        seg_out[vote >= num_majority] = 3

        # tumor (class == 2)
        vote = sum((seg == 2).astype(np.int16) for seg in list_seg)
        seg_out[vote >= num_majority] = 2

        nib.save(
            nib.Nifti1Image(seg_out.astype(np.uint8), list_seg_nib[0].affine),
            os.path.join(output_folder, case)
        )


def compute_dice(pred_folder, gt_folder):
    """KiTS23 hierarchical Dice over all cases in folder.
    kidney = Dice(pred>=1, gt>=1)  -- all foreground
    masses = Dice(pred>=2, gt>=2)  -- tumor + cyst
    tumor  = Dice(pred==2, gt==2)  -- tumor only
    Cases where both pred and GT are empty for a level are excluded from average.
    """
    cases = sorted(f for f in os.listdir(pred_folder) if f.endswith('.nii.gz'))
    lists = {'kidney': [], 'masses': [], 'tumor': []}

    for case in cases:
        gt_path = os.path.join(gt_folder, case)
        if not os.path.exists(gt_path):
            continue
        pred = nib.load(os.path.join(pred_folder, case)).get_fdata().astype(np.int32)
        gt   = nib.load(gt_path).get_fdata().astype(np.int32)

        lists['kidney'].append(dice_binary(pred >= 1, gt >= 1))
        lists['masses'].append(dice_binary(pred >= 2, gt >= 2))
        lists['tumor'].append( dice_binary(pred == 2, gt == 2))

    def nanmean(vals):
        v = [x for x in vals if not np.isnan(x)]
        return float(np.mean(v)) if v else float('nan')

    return {k: nanmean(v) for k, v in lists.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', nargs='+', required=True,
                        help='Post-processed prediction folders (one per model)')
    parser.add_argument('--gt', required=True,
                        help='Ground truth segmentation folder')
    parser.add_argument('--output_dir', required=True,
                        help='Where to save ablation results')
    args = parser.parse_args()

    n = len(args.inputs)
    assert n >= 3, f"P5 ablation needs N>=3 models to be meaningful (got {n}). With N=2, num_majority=1 == ceil(N/2)."

    os.makedirs(args.output_dir, exist_ok=True)
    results = {}

    print(f"\n{'='*60}")
    print(f"P5 Ablation: N={n} models")
    print(f"Testing num_majority = 1 to {n}")
    print(f"{'='*60}\n")

    for num_majority in range(1, n + 1):
        tag = f"majority_{num_majority}"
        if num_majority == 1:
            label = f"union (original, num_majority=1)"
        elif num_majority == math.ceil(n / 2):
            label = f"majority ceil({n}/2)={num_majority} [P5 fix]"
        else:
            label = f"num_majority={num_majority}"

        out_folder = os.path.join(args.output_dir, tag)
        print(f"Running {label} → {out_folder}")

        t0 = time()
        majority_vote(args.inputs, out_folder, num_majority)
        t1 = time()

        dice = compute_dice(out_folder, args.gt)
        mean_dice = np.mean([v for v in dice.values() if not np.isnan(v)])

        results[tag] = {
            "num_majority": num_majority,
            "label": label,
            "dice_kidney": round(dice['kidney'], 4),
            "dice_masses": round(dice['masses'], 4),
            "dice_tumor":  round(dice['tumor'],  4),
            "mean_dice":   round(mean_dice, 4),
            "time_s": round(t1 - t0, 1),
        }

        print(f"  kidney={dice['kidney']:.4f} masses={dice['masses']:.4f} "
              f"tumor={dice['tumor']:.4f} mean={mean_dice:.4f} ({t1-t0:.0f}s)\n")

    # Save results
    result_path = os.path.join(args.output_dir, "p5_ablation_results.json")
    with open(result_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Print comparison table
    print(f"\n{'='*70}")
    print(f"{'num_majority':<15} {'kidney':>8} {'masses':>8} {'tumor':>8} {'mean':>8}")
    print(f"{'(all fg)':>37} {'(t+cyst)':>8} {'(tumor)':>8}")
    print(f"{'-'*60}")
    baseline = results.get("majority_1", {}).get("mean_dice", float('nan'))
    for tag, r in results.items():
        delta = r["mean_dice"] - baseline if tag != "majority_1" else 0.0
        marker = " ← baseline" if tag == "majority_1" else f" ({delta:+.4f})"
        print(f"{r['num_majority']:<15} {r['dice_kidney']:>8.4f} {r['dice_masses']:>8.4f} "
              f"{r['dice_tumor']:>8.4f} {r['mean_dice']:>8.4f}{marker}")
    print(f"{'-'*60}")
    print(f"{'2nd place (test set)':<15} {'0.948':>8} {'0.776':>8} {'0.738':>8} {'0.820':>8}  ← reference")
    print(f"\nNOTE: above numbers = fold_all training-set. Not comparable to reference until test server submission.")
    print(f"\nResults saved to: {result_path}")


if __name__ == '__main__':
    main()
