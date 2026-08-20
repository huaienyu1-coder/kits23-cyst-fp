"""
compute_hierarchical_dice.py

KiTS23-style hierarchical Dice evaluation.

Metrics (matching KiTS23 official leaderboard):
  Kidney = Dice(pred>=1, GT>=1)   -- all foreground (kidney + tumor + cyst)
  Masses = Dice(pred>=2, GT>=2)   -- tumor + cyst
  Tumor  = Dice(pred==2, GT==2)   -- tumor only
  Average = mean(Kidney, Masses, Tumor)

Cases where BOTH pred and GT are empty for a given metric level are excluded
from the average (same convention as KiTS23 official evaluation).

Usage:
  python compute_hierarchical_dice.py \\
      --pred /path/to/predictions \\
      --gt   ~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations \\
      [--output results.json] [--verbose]

  # Evaluate multiple folders at once (e.g. after ablation):
  python compute_hierarchical_dice.py \\
      --pred folder1 folder2 folder3 \\
      --gt   /path/to/gt
"""

import os
import json
import argparse
import numpy as np
import nibabel as nib
from datetime import datetime


REFERENCE = {
    'kidney': 0.948, 'masses': 0.776, 'tumor': 0.738, 'average': 0.820,
    'note': '2nd place test set (Uhm et al. 2024, Table 2)'
}


def dice_binary(pred_mask, gt_mask):
    """Dice for two binary masks. Returns NaN if both empty (excluded from avg)."""
    p = pred_mask.astype(bool)
    g = gt_mask.astype(bool)
    if p.sum() == 0 and g.sum() == 0:
        return float('nan')
    return 2.0 * float((p & g).sum()) / float(p.sum() + g.sum())


def hierarchical_dice_case(pred, gt):
    """KiTS23 hierarchical Dice for one case (integer label arrays)."""
    return {
        'kidney': dice_binary(pred >= 1, gt >= 1),
        'masses': dice_binary(pred >= 2, gt >= 2),
        'tumor':  dice_binary(pred == 2, gt == 2),
    }


def nanmean(values):
    vals = [v for v in values if not np.isnan(v)]
    return float(np.mean(vals)) if vals else float('nan')


def evaluate_folder(pred_folder, gt_folder, verbose=False):
    cases = sorted(f for f in os.listdir(pred_folder) if f.endswith('.nii.gz'))
    if not cases:
        raise ValueError(f'No .nii.gz files in {pred_folder}')

    per_case = {}
    lists = {'kidney': [], 'masses': [], 'tumor': []}

    for case in cases:
        gt_path = os.path.join(gt_folder, case)
        if not os.path.exists(gt_path):
            print(f'  [WARN] GT not found: {case}')
            continue

        pred = nib.load(os.path.join(pred_folder, case)).get_fdata().astype(np.int32)
        gt   = nib.load(gt_path).get_fdata().astype(np.int32)

        d = hierarchical_dice_case(pred, gt)
        per_case[case] = d
        for k in lists:
            lists[k].append(d[k])

        if verbose:
            def fmt(v): return f'{v:.4f}' if not np.isnan(v) else '  nan '
            print(f'  {case[:20]:<20}  kidney={fmt(d["kidney"])}  '
                  f'masses={fmt(d["masses"])}  tumor={fmt(d["tumor"])}')

    kidney  = nanmean(lists['kidney'])
    masses  = nanmean(lists['masses'])
    tumor   = nanmean(lists['tumor'])
    average = nanmean([kidney, masses, tumor])

    return {
        'pred_folder': pred_folder,
        'n_cases': len(per_case),
        'aggregate': {
            'kidney':  round(kidney,  4),
            'masses':  round(masses,  4),
            'tumor':   round(tumor,   4),
            'average': round(average, 4),
        },
        'per_case': {
            k: {m: (round(v, 4) if not np.isnan(v) else None) for m, v in vd.items()}
            for k, vd in per_case.items()
        },
    }


def print_result(r, label=None):
    a = r['aggregate']
    tag = f'  [{label}]' if label else ''
    print(f"  kidney={a['kidney']:.4f}  masses={a['masses']:.4f}  "
          f"tumor={a['tumor']:.4f}  average={a['average']:.4f}{tag}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pred', nargs='+', required=True,
                        help='Prediction folder(s)')
    parser.add_argument('--gt', required=True,
                        help='GT segmentation folder')
    parser.add_argument('--output', default=None,
                        help='Output JSON path')
    parser.add_argument('--verbose', action='store_true',
                        help='Print per-case Dice')
    args = parser.parse_args()

    all_results = {}

    seen_labels = {}
    for pred_folder in args.pred:
        parts = pred_folder.rstrip('/').split(os.sep)
        # use last 2 path components to disambiguate same-named folders
        label = '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        if label in seen_labels:
            seen_labels[label] += 1
            label = f'{label}_{seen_labels[label]}'
        else:
            seen_labels[label] = 0
        print(f'\nEvaluating: {label}')
        if args.verbose:
            print()
        r = evaluate_folder(pred_folder, args.gt, verbose=args.verbose)
        r['evaluated_at'] = datetime.now().isoformat()
        all_results[label] = r
        print_result(r)

    print(f'\n{"="*70}')
    print(f'{"Folder":<35} {"kidney":>8} {"masses":>8} {"tumor":>8} {"average":>8}')
    print(f'{"-"*70}')
    for label, r in all_results.items():
        a = r['aggregate']
        print(f'{label[:35]:<35} {a["kidney"]:>8.4f} {a["masses"]:>8.4f} '
              f'{a["tumor"]:>8.4f} {a["average"]:>8.4f}')
    print(f'{"-"*70}')
    print(f'{"2nd place (test set)":35} '
          f'{REFERENCE["kidney"]:>8.3f} {REFERENCE["masses"]:>8.3f} '
          f'{REFERENCE["tumor"]:>8.3f} {REFERENCE["average"]:>8.3f}  ← reference')
    print(f'{"="*70}')
    print(f'NOTE: our numbers = fold_all training-set; reference = unseen test set.')
    print(f'      Direct comparison is NOT valid until test server submission.')

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f'\nResults saved to: {args.output}')


if __name__ == '__main__':
    main()
