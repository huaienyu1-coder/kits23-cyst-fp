"""
post_process_typeX.py — Type X tumor-residual mislabel fix (independent step).

Background:
  post_process_tumor.py has a known bug (lines 445-459): all mass predictions
  (label >=2) from BOTH models are initialized as cyst (label 3), then only
  cross-scale-confirmed tumors are restored to label 2. Tumor CCs that fail
  the cross-scale check remain permanently labeled as cyst (label 3).
  These are "Type X" artifacts — not genuine cyst predictions.

Detection:
  For each cyst CC in the main prediction, check the raw predictions of BOTH
  models at those voxels. If >= typeX_thresh fraction were predicted as tumor
  (label 2) in either raw prediction → this is a tumor residual → remove.

Also applies size filter (min_vox < 3) as Rule 3.

Usage:
  python post_process_typeX.py \\
      --main     holdout_pipeline/step2_tumor_postprocess/pairB \\
      --raw-main holdout_pipeline/raw_predictions/fullres \\
      --raw-chk  holdout_pipeline/raw_predictions/resenc_l \\
      --output   holdout_pipeline/step4_typeX/pairB \\
      --gt       nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations \\
      [--typeX-thresh 0.5] [--min-vox 3] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import label as nd_label

CYST_LABEL   = 3
TUMOR_LABEL  = 2
KIDNEY_LABEL = 1


def dice_bin(a, b):
    p, g = a.astype(bool), b.astype(bool)
    if p.sum() == 0 and g.sum() == 0:
        return float('nan')
    denom = int(p.sum()) + int(g.sum())
    return 2.0 * float((p & g).sum()) / denom if denom else 1.0


def hec_case(pred, gt):
    return (dice_bin(pred >= 1, gt >= 1),
            dice_bin(pred >= 2, gt >= 2),
            dice_bin(pred == 2, gt == 2))


def process_one(pred_path, raw_main_path, raw_chk_path, out_path,
                typeX_thresh, min_vox, dry_run):
    img = nib.load(str(pred_path))
    pred     = np.asarray(img.dataobj, dtype=np.uint8)
    raw_main = np.asarray(nib.load(str(raw_main_path)).dataobj, dtype=np.uint8)
    raw_chk  = np.asarray(nib.load(str(raw_chk_path)).dataobj,  dtype=np.uint8)

    cyst_mask = pred == CYST_LABEL
    if not cyst_mask.any():
        if not dry_run and out_path:
            nib.save(img, str(out_path))
        return {'n_cc': 0, 'rm_size': 0, 'rm_typeX': 0, 'kept': 0,
                'rm_vox': 0, 'kept_vox': 0, 'typeX_cases': []}

    cc_map, n_cc = nd_label(cyst_mask)
    pred_out = pred.copy()
    rm_size = rm_typeX = kept = rm_vox = kept_vox = 0
    typeX_cases = []

    for cc_id in range(1, n_cc + 1):
        cc = cc_map == cc_id
        sz = int(cc.sum())

        # Rule 3: size filter
        if sz < min_vox:
            pred_out[cc] = KIDNEY_LABEL
            rm_size += 1
            rm_vox  += sz
            continue

        # Deterministic Type X: union=cyst, at least one model predicted tumor,
        # but neither model directly predicted cyst (so the cyst label is a pipeline artifact).
        # If either model predicted cyst, the union cyst label may be legitimate.
        typeX_vox = (cc
                     & ((raw_main == TUMOR_LABEL) | (raw_chk == TUMOR_LABEL))
                     & (raw_main != CYST_LABEL)
                     & (raw_chk  != CYST_LABEL))
        frac_typeX = float(typeX_vox.sum()) / sz

        if frac_typeX >= typeX_thresh:
            pred_out[cc] = KIDNEY_LABEL
            rm_typeX += 1
            rm_vox   += sz
            typeX_cases.append({
                'cc_id': cc_id, 'sz': sz,
                'frac_typeX': frac_typeX,
                'frac_main': float((raw_main[cc] == TUMOR_LABEL).mean()),
                'frac_chk':  float((raw_chk[cc]  == TUMOR_LABEL).mean()),
            })
        else:
            kept += 1
            kept_vox += sz

    if not dry_run and out_path:
        nib.save(nib.Nifti1Image(pred_out, img.affine, img.header), str(out_path))

    return {'pred_out': pred_out, 'n_cc': n_cc,
            'rm_size': rm_size, 'rm_typeX': rm_typeX, 'kept': kept,
            'rm_vox': rm_vox, 'kept_vox': kept_vox, 'typeX_cases': typeX_cases}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main',         required=True)
    ap.add_argument('--raw-main',     required=True, dest='raw_main')
    ap.add_argument('--raw-chk',      required=True, dest='raw_chk')
    ap.add_argument('--output',       default=None)
    ap.add_argument('--gt',           default=None)
    ap.add_argument('--typeX-thresh', type=float, default=0.5, dest='typeX_thresh',
                    help='Fraction of CC voxels predicted as tumor in raw to flag as Type X (default 0.5)')
    ap.add_argument('--min-vox',      type=int, default=3, dest='min_vox')
    ap.add_argument('--dry-run',      action='store_true', dest='dry_run')
    args = ap.parse_args()

    if not args.dry_run and not args.output:
        ap.error('Provide --output DIR or --dry-run')

    main_dir     = Path(args.main)
    raw_main_dir = Path(args.raw_main)
    raw_chk_dir  = Path(args.raw_chk)
    gt_dir       = Path(args.gt) if args.gt else None
    out_dir      = Path(args.output) if args.output else None

    if out_dir and not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    cases = sorted(main_dir.glob('*.nii.gz'))
    if not cases:
        print(f'No .nii.gz in {main_dir}', file=sys.stderr)
        sys.exit(1)

    print(f'Type X tumor-residual fix  typeX_thresh={args.typeX_thresh}  min_vox={args.min_vox}')
    print(f'  Main:     {main_dir}')
    print(f'  raw-main: {raw_main_dir}')
    print(f'  raw-chk:  {raw_chk_dir}')
    print(f'  Output:   {out_dir}  {"(dry-run)" if args.dry_run else ""}')
    print()

    # Aggregates
    fp_before = fp_after = 0
    no_cyst_gt = gt_cyst_cases = 0
    dice_before_sum = dice_after_sum = dice_n = 0.0           # N=98 (empty→1.0)
    nan_before_sum = nan_before_n = 0.0                      # NaN-excluded before
    nan_after_sum  = nan_after_n  = 0.0                      # NaN-excluded after
    hec_k = hec_m = hec_t = hec_n = 0.0
    total_gt_vox = 0

    hdr = f"{'Case':<28} {'CC':>4} {'R3':>4} {'TX':>4} {'Kp':>4} {'RmVox':>7}"
    if gt_dir:
        hdr += f"  {'DB':>7}  {'DA':>7}"
    print(hdr)
    print('-' * len(hdr))

    for pred_path in cases:
        fn = pred_path.name
        rmp = raw_main_dir / fn
        rcp = raw_chk_dir  / fn
        if not rmp.exists() or not rcp.exists():
            print(f'  {fn}: raw missing, skip')
            continue

        out_path = (out_dir / fn) if (out_dir and not args.dry_run) else None
        stats = process_one(pred_path, rmp, rcp, out_path,
                            args.typeX_thresh, args.min_vox, args.dry_run)

        pred_before = np.asarray(nib.load(str(pred_path)).dataobj, dtype=np.uint8)
        pred_after_arr = stats.get('pred_out', pred_before)

        gt = None
        if gt_dir:
            gp = gt_dir / fn
            if gp.exists():
                gt = np.asarray(nib.load(str(gp)).dataobj, dtype=np.uint8)
                gc = (gt == CYST_LABEL).any()
                total_gt_vox += int((gt == CYST_LABEL).sum())
                if not gc:
                    no_cyst_gt += 1
                    if (pred_before == CYST_LABEL).any(): fp_before += 1
                    if (pred_after_arr == CYST_LABEL).any(): fp_after += 1
                else:
                    gt_cyst_cases += 1

        row = (f"  {fn:<26} {stats['n_cc']:>4} {stats['rm_size']:>4} "
               f"{stats['rm_typeX']:>4} {stats['kept']:>4} {stats['rm_vox']:>7}")

        if gt is not None:
            db = dice_bin(pred_before == CYST_LABEL, gt == CYST_LABEL)
            da = dice_bin(pred_after_arr == CYST_LABEL, gt == CYST_LABEL)
            # N=98: both-empty → 1.0
            if not (np.isnan(db) and np.isnan(da)):
                dice_before_sum += db if not np.isnan(db) else 1.0
                dice_after_sum  += da if not np.isnan(da) else 1.0
                dice_n += 1
            # NaN-excluded: both-empty → skip; before and after counted separately
            if not np.isnan(db):
                nan_before_sum += db; nan_before_n += 1
            if not np.isnan(da):
                nan_after_sum  += da; nan_after_n  += 1
            row += f"  {(db if not np.isnan(db) else 1.0):>7.4f}  {(da if not np.isnan(da) else 1.0):>7.4f}"
            if stats['rm_typeX'] > 0:
                row += '  <TX'
            elif stats['rm_size'] > 0:
                row += '  <R3'

        print(row)

        if stats['typeX_cases']:
            for tc in stats['typeX_cases']:
                print(f"    [TypeX CC{tc['cc_id']}] {tc['sz']} vox  "
                      f"det={tc['frac_typeX']:.0%}  "
                      f"raw-main tumor={tc['frac_main']:.0%}  raw-chk tumor={tc['frac_chk']:.0%}")

        if gt is not None:
            k, m, t = hec_case(pred_after_arr, gt)
            if not np.isnan(k): hec_k += k; hec_n += 1
            if not np.isnan(m): hec_m += m
            if not np.isnan(t): hec_t += t

    print()
    print('=' * 70)
    if gt_dir:
        n = dice_n
        print(f'CystDice N=98 (empty→1.0)  '
              f'before: {dice_before_sum/n:.4f}  after: {dice_after_sum/n:.4f}'
              f'  (Δ={dice_after_sum/n - dice_before_sum/n:+.4f})')
        if nan_before_n > 0:
            nb, na = int(nan_before_n), int(nan_after_n)
            print(f'CystDice NaN-excluded      '
                  f'before(N={nb}): {nan_before_sum/nb:.4f}  '
                  f'after(N={na}): {nan_after_sum/max(1,na):.4f}'
                  f'  (Δ={nan_after_sum/max(1,na) - nan_before_sum/nb:+.4f})')
        print(f'FP alarm  before: {fp_before}/{no_cyst_gt} ({100*fp_before/max(1,no_cyst_gt):.1f}%)'
              f'  after: {fp_after}/{no_cyst_gt} ({100*fp_after/max(1,no_cyst_gt):.1f}%)')
        if hec_n > 0:
            nn = hec_n
            avg = (hec_k + hec_m + hec_t) / (3 * nn)
            print(f'HEC  K={hec_k/nn:.4f}  M={hec_m/nn:.4f}  T={hec_t/nn:.4f}  avg={avg:.4f}')


if __name__ == '__main__':
    main()
