"""
post_process_cyst.py — Step 4: Cyst cross-scale consistency filter (independent step).

Mirrors the tumor cross-scale check in post_process_tumor.py but applies it to cyst (label 3).
Does NOT modify any existing pipeline files.

For each cyst CC in the main prediction:
  1. Size filter  : CC voxels < --min-vox  → remove (noise)
  2. Cross-scale  : Dice(CC, checker_cyst_global) < CYST_OVERLAP_MIN_DICE → remove

Removed CCs are relabeled based on surrounding tissue (kidney=1 or background=0).

Modes:
  --ablation : sweep {0.1, 0.15, 0.2, 0.3, 0.5}, no files written, prints table
  --min-dice X --output DIR : single threshold, writes output

Usage:
  # Ablation sweep (no output written):
  python post_process_cyst.py \\
      --main   holdout_pipeline/step2_tumor_postprocess/pairB \\
      --checker holdout_pipeline/raw_predictions/resenc_l \\
      --gt      nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations \\
      --ablation

  # Single threshold run:
  python post_process_cyst.py \\
      --main   holdout_pipeline/step2_tumor_postprocess/pairB \\
      --checker holdout_pipeline/raw_predictions/resenc_l \\
      --output  holdout_pipeline/step4_cyst_postprocess/pairB_d010 \\
      --gt      nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations \\
      --min-dice 0.1
"""

import argparse
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import label as nd_label, binary_dilation

CYST_LABEL   = 3
KIDNEY_LABEL = 1
BG_LABEL     = 0

ABLATION_THRESHOLDS = [0.1, 0.15, 0.2, 0.3, 0.5]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def dice_bin(a, b):
    """Symmetric Dice for two boolean arrays. Returns NaN if both empty."""
    p, g = a.astype(bool), b.astype(bool)
    if p.sum() == 0 and g.sum() == 0:
        return float('nan')
    denom = int(p.sum()) + int(g.sum())
    if denom == 0:
        return 1.0
    return 2.0 * float((p & g).sum()) / denom


def cc_dice_checker(cc_mask: np.ndarray, checker_cyst_global: np.ndarray) -> float:
    """Dice between one CC and the global checker cyst mask."""
    inter = int((cc_mask & checker_cyst_global).sum())
    denom = int(cc_mask.sum()) + int(checker_cyst_global.sum())
    if denom == 0:
        return 1.0
    return 2.0 * inter / denom


def neighbor_label(cc_mask: np.ndarray, pred: np.ndarray, dilation: int = 2) -> int:
    """
    Majority non-cyst label in the dilated border of cc_mask.
    Used to decide replacement label: kidney(1) if inside kidney, background(0) if at border.
    """
    dilated = binary_dilation(cc_mask, iterations=dilation)
    border  = dilated & ~cc_mask
    neighbors = pred[border]
    non_cyst  = neighbors[neighbors != CYST_LABEL]
    if len(non_cyst) == 0:
        return KIDNEY_LABEL
    # most common label (0=bg, 1=kidney, 2=tumor)
    counts = np.bincount(non_cyst.astype(np.int32), minlength=4)
    return int(np.argmax(counts))


def hec_case(pred: np.ndarray, gt: np.ndarray) -> tuple:
    """KiTS23 hierarchical Dice for one case. Returns (kidney, masses, tumor)."""
    k = dice_bin(pred >= 1, gt >= 1)
    m = dice_bin(pred >= 2, gt >= 2)
    t = dice_bin(pred == 2, gt == 2)
    return k, m, t


# ---------------------------------------------------------------------------
# Per-case processing
# ---------------------------------------------------------------------------

def analyze_case(pred: np.ndarray,
                 checker: np.ndarray,
                 gt: np.ndarray | None,
                 min_vox: int,
                 thresholds: list[float]) -> dict:
    """
    Process one case for all thresholds in-memory.

    Returns dict: threshold -> {
        pred_after  : np.ndarray,
        removed_total : int,   # CCs removed (size + cross-scale)
        removed_tp    : int,   # removed CCs that overlapped GT cyst  (BAD)
        removed_vox   : int,
        kept_vox      : int,
    }
    """
    checker_cyst = checker == CYST_LABEL
    cyst_mask    = pred == CYST_LABEL

    if not cyst_mask.any():
        empty = {'removed_total': 0, 'removed_tp': 0,
                 'removed_vox': 0,   'kept_vox': 0}
        return {t: {**empty, 'pred_after': pred.copy()} for t in thresholds}

    cc_map, n_cc = nd_label(cyst_mask)

    # Precompute per-CC metadata (done once, shared across thresholds).
    # neighbor_label (binary_dilation) is skipped here for speed; ablation uses
    # kidney=1 as replacement. Single-threshold save mode applies smart labeling.
    gt_cyst_mask = (gt == CYST_LABEL) if gt is not None else None
    cc_info = []
    for cc_id in range(1, n_cc + 1):
        cc_mask_i = (cc_map == cc_id)
        sz        = int(cc_mask_i.sum())
        dice      = cc_dice_checker(cc_mask_i, checker_cyst)
        is_tp     = bool((cc_mask_i & gt_cyst_mask).any()) if gt_cyst_mask is not None else None
        cc_info.append({'mask': cc_mask_i, 'sz': sz, 'dice': dice, 'is_tp': is_tp})

    results = {}
    for t in thresholds:
        pred_t = pred.copy()
        removed_total = removed_tp = removed_vox = kept_vox = 0

        for cc in cc_info:
            if cc['sz'] < min_vox or cc['dice'] < t:
                pred_t[cc['mask']] = KIDNEY_LABEL  # fast default; save mode uses neighbor_label
                removed_total += 1
                removed_vox   += cc['sz']
                if cc['is_tp']:
                    removed_tp += 1
            else:
                kept_vox += cc['sz']

        results[t] = {
            'pred_after':    pred_t,
            'removed_total': removed_total,
            'removed_tp':    removed_tp,
            'removed_vox':   removed_vox,
            'kept_vox':      kept_vox,
        }

    return results


# ---------------------------------------------------------------------------
# Aggregate accumulators
# ---------------------------------------------------------------------------

class Agg:
    def __init__(self):
        self.fp_alarm_after   = 0  # FP cases remaining after filter
        self.false_del_cases  = 0  # GT-cyst-positive cases with TP CC removed
        self.false_del_ccs    = 0  # total TP CCs removed
        self.cyst_dice_sum    = 0.0
        self.cyst_dice_n      = 0
        self.total_pred_vox   = 0  # sum of pred cyst voxels (for voxel ratio)
        self.kidney_vals      = []
        self.masses_vals      = []
        self.tumor_vals       = []

    def update(self, pred_after, gt, gt_has_cyst, removed_tp):
        pred_has_cyst = bool((pred_after == CYST_LABEL).any())

        if not gt_has_cyst and pred_has_cyst:
            self.fp_alarm_after += 1

        if gt_has_cyst and removed_tp > 0:
            self.false_del_cases += 1
            self.false_del_ccs   += removed_tp

        cd = dice_bin(pred_after == CYST_LABEL, gt == CYST_LABEL)
        if not np.isnan(cd):
            self.cyst_dice_sum += cd
            self.cyst_dice_n   += 1

        self.total_pred_vox += int((pred_after == CYST_LABEL).sum())

        k, m, t = hec_case(pred_after, gt)
        if not np.isnan(k): self.kidney_vals.append(k)
        if not np.isnan(m): self.masses_vals.append(m)
        if not np.isnan(t): self.tumor_vals.append(t)

    def mean_cyst_dice(self):
        return self.cyst_dice_sum / self.cyst_dice_n if self.cyst_dice_n else float('nan')

    def hec(self):
        def nm(lst): return float(np.mean(lst)) if lst else float('nan')
        k, m, t = nm(self.kidney_vals), nm(self.masses_vals), nm(self.tumor_vals)
        avg = float(np.nanmean([k, m, t]))
        return k, m, t, avg


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main',    required=True, help='Main prediction dir (step2 output)')
    ap.add_argument('--checker', required=True, help='Checker prediction dir (raw model output)')
    ap.add_argument('--output',  default=None,  help='Output dir (required if not --ablation)')
    ap.add_argument('--gt',      default=None,  help='GT dir for evaluation')
    ap.add_argument('--min-dice', type=float, default=None,
                    help='Single threshold (required if not --ablation)')
    ap.add_argument('--min-vox',  type=int, default=3,
                    help='Min CC voxels; smaller always removed (default 3)')
    ap.add_argument('--ablation', action='store_true',
                    help='Sweep over multiple thresholds, no files written')
    args = ap.parse_args()

    # Validate
    if not args.ablation and args.min_dice is None:
        ap.error('Provide --min-dice X or --ablation')
    if not args.ablation and args.output is None:
        ap.error('Provide --output DIR when not using --ablation')

    main_dir    = Path(args.main)
    checker_dir = Path(args.checker)
    gt_dir      = Path(args.gt) if args.gt else None

    thresholds = ABLATION_THRESHOLDS if args.ablation else [args.min_dice]

    cases = sorted(main_dir.glob('*.nii.gz'))
    if not cases:
        print(f'No .nii.gz in {main_dir}', file=sys.stderr)
        sys.exit(1)

    print(f'Cyst cross-scale filter  min_vox={args.min_vox}')
    print(f'  Main:    {main_dir}')
    print(f'  Checker: {checker_dir}')
    if args.ablation:
        print(f'  Mode:    ABLATION sweep {thresholds}')
    else:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f'  Output:  {out_dir}  min-dice={args.min_dice}')
    print()

    # ---------------------------------------------------------------------------
    # Setup aggregators
    # ---------------------------------------------------------------------------
    aggs = {t: Agg() for t in thresholds}
    fp_alarm_before  = 0
    no_cyst_gt_cases = 0
    gt_cyst_cases    = 0
    total_gt_cyst_vox = 0
    n_total = 0

    # ---------------------------------------------------------------------------
    # Case loop
    # ---------------------------------------------------------------------------
    for pred_path in cases:
        fn = pred_path.name
        checker_path = checker_dir / fn
        if not checker_path.exists():
            print(f'  {fn}: checker missing, skip', file=sys.stderr)
            continue

        img_main = nib.load(str(pred_path))
        pred     = np.asarray(img_main.dataobj, dtype=np.uint8)
        checker  = np.asarray(nib.load(str(checker_path)).dataobj, dtype=np.uint8)

        gt = None
        gt_has_cyst = False
        if gt_dir is not None:
            gt_path = gt_dir / fn
            if gt_path.exists():
                gt = np.asarray(nib.load(str(gt_path)).dataobj, dtype=np.uint8)
                gt_has_cyst = bool((gt == CYST_LABEL).any())
                total_gt_cyst_vox += int((gt == CYST_LABEL).sum())

        pred_has_cyst_before = bool((pred == CYST_LABEL).any())
        if gt is not None:
            if not gt_has_cyst:
                no_cyst_gt_cases += 1
                if pred_has_cyst_before:
                    fp_alarm_before += 1
            else:
                gt_cyst_cases += 1
        n_total += 1

        # Run all thresholds in-memory
        per_t = analyze_case(pred, checker, gt, args.min_vox, thresholds)

        for t in thresholds:
            res = per_t[t]
            if gt is not None:
                aggs[t].update(res['pred_after'], gt, gt_has_cyst, res['removed_tp'])

        # Save output (single-threshold mode): recompute with smart neighbor label
        if not args.ablation:
            t = args.min_dice
            out_path  = Path(args.output) / fn
            pred_save = pred.copy()
            cc_map_s, n_cc_s = nd_label(pred == CYST_LABEL)
            for cc_id in range(1, n_cc_s + 1):
                cc_i = (cc_map_s == cc_id)
                sz_i = int(cc_i.sum())
                dice_i = cc_dice_checker(cc_i, checker == CYST_LABEL)
                if sz_i < args.min_vox or dice_i < t:
                    pred_save[cc_i] = neighbor_label(cc_i, pred)
            nib.save(nib.Nifti1Image(pred_save, img_main.affine, img_main.header),
                     str(out_path))

    # ---------------------------------------------------------------------------
    # Print results
    # ---------------------------------------------------------------------------
    if gt_dir is None:
        print('No GT provided; skipping evaluation.')
        return

    if args.ablation:
        print('=' * 95)
        hdr = (f"{'Thresh':>7} | {'FP-alarm':>8} {'Δ-FP':>6} | "
               f"{'FalseDel-case':>13} {'FalseDel-CC':>11} | "
               f"{'CystDice':>9} {'VoxRatio':>9} | "
               f"{'Kidney':>7} {'Masses':>7} {'Tumor':>7} {'HEC':>7}")
        print(hdr)
        print('-' * 95)

        for t in thresholds:
            agg = aggs[t]
            fp_after  = agg.fp_alarm_after
            delta_fp  = fp_alarm_before - fp_after
            cd        = agg.mean_cyst_dice()
            # voxel ratio
            vr = agg.total_pred_vox / max(1, total_gt_cyst_vox)
            k, m, tu, avg = agg.hec()
            print(
                f"  {t:5.2f}  | {fp_after:>3}/{no_cyst_gt_cases:<4} {delta_fp:>+4}  | "
                f"{agg.false_del_cases:>6}/{gt_cyst_cases:<5}  {agg.false_del_ccs:>8}  | "
                f"  {cd:7.4f}  {vr:8.4f}  | "
                f"{k:7.4f} {m:7.4f} {tu:7.4f} {avg:7.4f}"
            )

        print('=' * 95)
        print(f'\nBaseline (before filter):')
        print(f'  FP alarms:  {fp_alarm_before}/{no_cyst_gt_cases} '
              f'({100*fp_alarm_before/max(1,no_cyst_gt_cases):.1f}%)')
        # Baseline cyst dice and HEC are from first threshold at removed_total=0 effectively
        # (hard to reconstruct here; user should compare to step2 pairB HEC=0.9021)
        print(f'  GT cyst vox: {total_gt_cyst_vox}')
        print(f'\nColumn guide:')
        print(f'  FP-alarm    : after/total FP alarms remaining (lower=better)')
        print(f'  Δ-FP        : FP alarms removed (higher=better)')
        print(f'  FalseDel-case: GT-cyst cases with TP CC removed / total GT-cyst (lower=better)')
        print(f'  FalseDel-CC : total TP CCs removed (lower=better, 0 = no TP harm)')
        print(f'  CystDice    : mean per-case cyst Dice (higher=better)')
        print(f'  VoxRatio    : pred_cyst_vox / gt_cyst_vox (close to baseline=good; drop=over-removal)')
        print(f'  HEC         : hierarchical Dice kidney/masses/tumor/mean')

    else:
        t   = args.min_dice
        agg = aggs[t]
        fp_after  = agg.fp_alarm_after
        k, m, tu, avg = agg.hec()
        vr = agg.total_pred_vox / max(1, total_gt_cyst_vox)
        print(f'FP alarms    : {fp_alarm_before}/{no_cyst_gt_cases} → {fp_after}/{no_cyst_gt_cases}'
              f'  (Δ={fp_alarm_before-fp_after:+d})')
        print(f'False del    : {agg.false_del_ccs} TP CCs removed'
              f' in {agg.false_del_cases}/{gt_cyst_cases} GT-cyst cases')
        print(f'Cyst Dice    : {agg.mean_cyst_dice():.4f}  VoxRatio: {vr:.4f}')
        print(f'HEC          : kidney={k:.4f}  masses={m:.4f}  tumor={tu:.4f}  avg={avg:.4f}')
        print(f'Output       : {args.output}')


if __name__ == '__main__':
    main()
