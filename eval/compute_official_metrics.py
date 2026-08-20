"""
compute_official_metrics.py

KiTS23 official metrics: Hierarchical Dice + Surface Dice.
Matches the official evaluation exactly (same HEC definitions, same SD tolerances).

HEC definitions (from kits23/configuration/labels.py):
  kidney_and_mass : labels (1, 2, 3)  — kidney + tumor + cyst
  mass            : labels (2, 3)      — tumor + cyst
  tumor           : label  (2,)        — tumor only

SD tolerances (pre-computed by KiTS organizers, unit: mm):
  kidney_and_mass : 1.0331 mm
  mass            : 1.1329 mm
  tumor           : 1.1498 mm

Usage:
  python compute_official_metrics.py \
      --pred /path/to/pred_folder [folder2 ...] \
      --gt   ~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations \
      [--output results.json] [--workers 4] [--verbose]
"""

import os
import json
import argparse
import numpy as np
import SimpleITK as sitk
from datetime import datetime
from multiprocessing import Pool
from functools import partial

from surface_distance import compute_surface_distances, compute_surface_dice_at_tolerance

# KiTS23 label mapping (verified 2026-06-22 via np.unique on GT + kits23.configuration.labels):
#   0 = background
#   1 = kidney  (parenchyma only, excluding tumor/cyst voxels)
#   2 = tumor
#   3 = cyst
# Source: kits23/configuration/labels.py KITS_LABEL_NAMES = {1:'kidney', 2:'tumor', 3:'cyst'}
HEC_LABELS = {
    'kidney': (1, 2, 3),  # kidney_and_mass: all foreground
    'masses': (2, 3),     # mass: tumor + cyst
    'tumor':  (2,),       # tumor only
}
SD_TOLERANCES = {
    'kidney': 1.0330772532390826,
    'masses': 1.1328796488598762,
    'tumor':  1.1498198361434828,
}
REFERENCE = {
    'kidney_dice': 0.948, 'masses_dice': 0.776, 'tumor_dice': 0.738,
    'kidney_sd':   0.895, 'masses_sd':   0.810, 'tumor_sd':   0.712,
    'note': '2nd place test set (Uhm et al. 2024, Table 2)'
}


def make_mask(arr, labels):
    mask = np.zeros(arr.shape, dtype=bool)
    for l in labels:
        mask |= (arr == l)
    return mask


def dice_binary(pred, gt):
    p, g = pred.astype(bool), gt.astype(bool)
    if p.sum() == 0 and g.sum() == 0:
        return float('nan')
    return 2.0 * float((p & g).sum()) / float(p.sum() + g.sum())


def compute_case(pred_path, gt_path):
    img_pred = sitk.ReadImage(pred_path)
    img_gt   = sitk.ReadImage(gt_path)

    spacing = tuple(reversed(img_pred.GetSpacing()))  # SimpleITK: (x,y,z) → numpy: (z,y,x)

    pred_arr = sitk.GetArrayFromImage(img_pred).astype(np.int32)
    gt_arr   = sitk.GetArrayFromImage(img_gt).astype(np.int32)

    result = {}
    for hec, labels in HEC_LABELS.items():
        pmask = make_mask(pred_arr, labels)
        gmask = make_mask(gt_arr,   labels)

        gt_empty   = gmask.sum() == 0
        pred_empty = pmask.sum() == 0

        if gt_empty and pred_empty:
            dc, sd = float('nan'), float('nan')  # excluded from average (official convention)
        elif gt_empty or pred_empty:
            dc, sd = 0.0, 0.0
        else:
            dc = dice_binary(pmask, gmask)
            dist = compute_surface_distances(gmask, pmask, spacing)
            sd = float(compute_surface_dice_at_tolerance(dist, SD_TOLERANCES[hec]))

        result[hec] = {'dice': dc, 'sd': sd}

    return result


def _worker(args):
    pred_path, gt_path = args
    case = os.path.basename(pred_path)
    try:
        metrics = compute_case(pred_path, gt_path)
        return case, metrics, None
    except Exception as e:
        return case, None, str(e)


def nanmean(values):
    vals = [v for v in values if not (v is None or (isinstance(v, float) and np.isnan(v)))]
    return float(np.mean(vals)) if vals else float('nan')


def evaluate_folder(pred_folder, gt_folder, workers=4, verbose=False):
    cases = sorted(f for f in os.listdir(pred_folder) if f.endswith('.nii.gz'))
    if not cases:
        raise ValueError(f'No .nii.gz files in {pred_folder}')

    args = []
    for case in cases:
        gt_path = os.path.join(gt_folder, case)
        if not os.path.exists(gt_path):
            print(f'  [WARN] GT not found: {case}')
            continue
        args.append((os.path.join(pred_folder, case), gt_path))

    with Pool(workers) as pool:
        raw = pool.map(_worker, args)

    per_case = {}
    lists = {hec: {'dice': [], 'sd': []} for hec in HEC_LABELS}

    for case, metrics, err in raw:
        if err:
            print(f'  [ERROR] {case}: {err}')
            continue
        per_case[case] = metrics
        for hec in HEC_LABELS:
            lists[hec]['dice'].append(metrics[hec]['dice'])
            lists[hec]['sd'].append(metrics[hec]['sd'])

    if verbose:
        header = f'  {"case":<25} {"kid_dc":>7} {"kid_sd":>7} {"mas_dc":>7} {"mas_sd":>7} {"tum_dc":>7} {"tum_sd":>7}'
        print(header)
        for case in sorted(per_case):
            m = per_case[case]
            def f(v): return f'{v:7.4f}' if not (v is None or np.isnan(v)) else '    nan'
            print(f'  {case[:25]:<25} {f(m["kidney"]["dice"])} {f(m["kidney"]["sd"])} '
                  f'{f(m["masses"]["dice"])} {f(m["masses"]["sd"])} '
                  f'{f(m["tumor"]["dice"])} {f(m["tumor"]["sd"])}')

    agg = {}
    for hec in HEC_LABELS:
        agg[hec] = {
            'dice': round(nanmean(lists[hec]['dice']), 4),
            'sd':   round(nanmean(lists[hec]['sd']),   4),
        }
    mean_dice = nanmean([agg[h]['dice'] for h in HEC_LABELS])
    mean_sd   = nanmean([agg[h]['sd']   for h in HEC_LABELS])
    agg['mean'] = {'dice': round(mean_dice, 4), 'sd': round(mean_sd, 4)}

    return {
        'pred_folder': pred_folder,
        'n_cases': len(per_case),
        'aggregate': agg,
        'per_case': {
            c: {hec: {k: (round(v, 4) if v is not None and not np.isnan(v) else None)
                      for k, v in vals.items()}
                for hec, vals in m.items()}
            for c, m in per_case.items()
        },
    }


def print_result(r, label=''):
    a = r['aggregate']
    tag = f'  [{label}]' if label else ''
    print(f"  kidney  dice={a['kidney']['dice']:.4f}  sd={a['kidney']['sd']:.4f}")
    print(f"  masses  dice={a['masses']['dice']:.4f}  sd={a['masses']['sd']:.4f}")
    print(f"  tumor   dice={a['tumor']['dice']:.4f}  sd={a['tumor']['sd']:.4f}")
    print(f"  mean    dice={a['mean']['dice']:.4f}  sd={a['mean']['sd']:.4f}{tag}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pred', nargs='+', required=True)
    parser.add_argument('--gt', required=True)
    parser.add_argument('--output', default=None)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    all_results = {}
    seen = {}
    for pred_folder in args.pred:
        parts = pred_folder.rstrip('/').split(os.sep)
        label = '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        if label in seen:
            seen[label] += 1
            label = f'{label}_{seen[label]}'
        else:
            seen[label] = 0

        print(f'\nEvaluating: {label}  (workers={args.workers})')
        if args.verbose:
            print()
        r = evaluate_folder(pred_folder, args.gt, workers=args.workers, verbose=args.verbose)
        r['evaluated_at'] = datetime.now().isoformat()
        all_results[label] = r
        print_result(r, label)

    # summary table
    hecs = ['kidney', 'masses', 'tumor', 'mean']
    W = 36
    print(f'\n{"="*(W+64)}')
    print(f'{"Folder":<{W}} {"kid_dc":>7} {"kid_sd":>7} {"mas_dc":>7} {"mas_sd":>7} {"tum_dc":>7} {"tum_sd":>7} {"mean_dc":>8} {"mean_sd":>8}')
    print(f'{"-"*(W+64)}')
    for label, r in all_results.items():
        a = r['aggregate']
        print(f'{label[:W]:<{W}} '
              f'{a["kidney"]["dice"]:>7.4f} {a["kidney"]["sd"]:>7.4f} '
              f'{a["masses"]["dice"]:>7.4f} {a["masses"]["sd"]:>7.4f} '
              f'{a["tumor"]["dice"]:>7.4f} {a["tumor"]["sd"]:>7.4f} '
              f'{a["mean"]["dice"]:>8.4f} {a["mean"]["sd"]:>8.4f}')
    print(f'{"-"*(W+64)}')
    ref = REFERENCE
    ref_mean_dice = (ref["kidney_dice"] + ref["masses_dice"] + ref["tumor_dice"]) / 3
    ref_mean_sd   = (ref["kidney_sd"]   + ref["masses_sd"]   + ref["tumor_sd"])   / 3
    print(f'{"2nd place (test set)":<{W}} '
          f'{ref["kidney_dice"]:>7.3f} {ref["kidney_sd"]:>7.3f} '
          f'{ref["masses_dice"]:>7.3f} {ref["masses_sd"]:>7.3f} '
          f'{ref["tumor_dice"]:>7.3f} {ref["tumor_sd"]:>7.3f} '
          f'{ref_mean_dice:>8.3f} {ref_mean_sd:>8.3f}  <- reference')
    print(f'{"="*(W+64)}')
    print('NOTE: our numbers = fold_all training-set (inflated). Direct comparison invalid until hold-out retraining.')

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f'\nSaved to: {args.output}')


if __name__ == '__main__':
    main()
