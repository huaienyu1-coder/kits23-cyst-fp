"""
Cyst cross-scale consistency filter (independent step, after post_process_tumor.py).

Mirrors the tumor cross-scale check in post_process_tumor.py but applies it to cyst (label 3).

Rationale (hold-out analysis 2026-07-08):
  15/17 cyst FP alarms are Type Y (genuine model cyst predictions, not pipeline artifacts).
  Of those 15, 8 have ResEnc-L predicting kidney/background at the same voxels — meaning
  the cross-scale evidence for cyst is absent. Removing those CCs mimics what Step 2 already
  does for tumor, extended to cyst.

Logic:
  For each connected component of cyst (label 3) in the MAIN prediction:
    dice = 2 * |CC ∩ checker_cyst| / (|CC| + |checker_cyst_overlap|)
    if dice < MIN_DICE  →  remove CC (relabel as kidney=1)

Usage:
  python cyst_cross_scale_postprocess.py \\
      --main   holdout_pipeline/step2_tumor_postprocess/pairB \\
      --checker nnUNet_results/Dataset500_KiTS23/nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/fold_0/validation \\
      --output  holdout_pipeline/step4_cyst_xscale/pairB \\
      [--gt     nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations] \\
      [--min-dice 0.1] \\
      [--dry-run]
"""

import argparse
import os
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import label as nd_label


CYST_LABEL = 3
KIDNEY_LABEL = 1


def cyst_dice_with_checker(cc_mask: np.ndarray, checker_cyst: np.ndarray) -> float:
    """Dice between this cyst CC and all checker cyst predictions (global image space)."""
    inter = int((cc_mask & checker_cyst).sum())
    denom = int(cc_mask.sum()) + int(checker_cyst.sum())
    if denom == 0:
        return 1.0
    return 2.0 * inter / denom


def process_one(pred_path: Path, checker_path: Path, out_path: Path,
                min_dice: float, min_vox: int) -> dict:
    img_main = nib.load(str(pred_path))
    pred = np.asarray(img_main.dataobj).astype(np.uint8)

    img_chk = nib.load(str(checker_path))
    checker = np.asarray(img_chk.dataobj).astype(np.uint8)
    checker_cyst = checker == CYST_LABEL

    cyst_mask = pred == CYST_LABEL
    if not cyst_mask.any():
        nib.save(img_main, str(out_path))
        return {"n_cc": 0, "removed": 0, "kept": 0,
                "removed_vox": 0, "kept_vox": 0}

    cc_map, n_cc = nd_label(cyst_mask)

    removed = kept = removed_vox = kept_vox = 0

    for cc_id in range(1, n_cc + 1):
        cc = cc_map == cc_id
        sz = int(cc.sum())

        # Tiny CC filter (noise before cross-scale check)
        if sz < min_vox:
            pred[cc] = KIDNEY_LABEL
            removed += 1
            removed_vox += sz
            continue

        dice = cyst_dice_with_checker(cc, checker_cyst)
        if dice < min_dice:
            pred[cc] = KIDNEY_LABEL
            removed += 1
            removed_vox += sz
        else:
            kept += 1
            kept_vox += sz

    nib.save(nib.Nifti1Image(pred, img_main.affine, img_main.header), str(out_path))
    return {"n_cc": n_cc, "removed": removed, "kept": kept,
            "removed_vox": removed_vox, "kept_vox": kept_vox}


def cyst_dice_gt(pred: np.ndarray, gt: np.ndarray) -> float:
    p = pred == CYST_LABEL
    g = gt == CYST_LABEL
    denom = p.sum() + g.sum()
    return float(2 * (p & g).sum() / denom) if denom > 0 else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main",    required=True, help="Main prediction dir (Fullres step2 output)")
    ap.add_argument("--checker", required=True, help="Checker prediction dir (ResEnc-L raw or step1)")
    ap.add_argument("--output",  required=True, help="Output directory")
    ap.add_argument("--gt",      default=None,  help="GT dir for evaluation")
    ap.add_argument("--min-dice", type=float, default=0.1,
                    help="Min Dice between cyst CC and checker cyst to KEEP the CC (default 0.1)")
    ap.add_argument("--min-vox", type=int, default=3,
                    help="Min CC voxels; smaller are always removed (default 3)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    main_dir    = Path(args.main)
    checker_dir = Path(args.checker)
    out_dir     = Path(args.output)

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    cases = sorted(main_dir.glob("*.nii.gz"))
    if not cases:
        print(f"No .nii.gz in {main_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Cyst cross-scale filter  min_dice={args.min_dice}  min_vox={args.min_vox}")
    print(f"  Main:    {main_dir}")
    print(f"  Checker: {checker_dir}")
    print(f"  Output:  {out_dir}")
    print()

    hdr = f"{'Case':<25} {'CC':>4} {'Rm':>4} {'Kp':>4} {'RmVox':>7} {'KpVox':>7}"
    if args.gt:
        hdr += f"  {'DiceBef':>8}  {'DiceAft':>8}"
    print(hdr)
    print("-" * len(hdr))

    dice_before = dice_after = 0.0
    fp_before = fp_after = n_no_cyst_gt = 0
    n_eval = 0
    total_removed = total_removed_vox = 0

    for pred_path in cases:
        fn = pred_path.name
        checker_path = checker_dir / fn
        if not checker_path.exists():
            print(f"  {fn}: checker missing, skip")
            continue

        import tempfile
        if args.dry_run:
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / fn
                pred_orig = np.asarray(nib.load(str(pred_path)).dataobj).astype(np.uint8)
                stats = process_one(pred_path, checker_path, tmp, args.min_dice, args.min_vox)
                pred_post = np.asarray(nib.load(str(tmp)).dataobj).astype(np.uint8)
        else:
            pred_orig = np.asarray(nib.load(str(pred_path)).dataobj).astype(np.uint8)
            out_path  = out_dir / fn
            stats = process_one(pred_path, checker_path, out_path, args.min_dice, args.min_vox)
            pred_post = np.asarray(nib.load(str(out_path)).dataobj).astype(np.uint8)

        total_removed     += stats["removed"]
        total_removed_vox += stats["removed_vox"]

        row = (f"  {fn:<25} {stats['n_cc']:>4} {stats['removed']:>4} {stats['kept']:>4}"
               f" {stats['removed_vox']:>7} {stats['kept_vox']:>7}")

        if args.gt:
            gt_path = Path(args.gt) / fn
            if gt_path.exists():
                gt = np.asarray(nib.load(str(gt_path)).dataobj).astype(np.uint8)
                db = cyst_dice_gt(pred_orig, gt)
                da = cyst_dice_gt(pred_post, gt)
                dice_before += db; dice_after += da; n_eval += 1
                gt_nc = not (gt == CYST_LABEL).any()
                if gt_nc:
                    n_no_cyst_gt += 1
                    if (pred_orig == CYST_LABEL).any(): fp_before += 1
                    if (pred_post == CYST_LABEL).any(): fp_after  += 1
                row += f"  {db:>8.4f}  {da:>8.4f}"
                if stats["removed"] > 0:
                    row += "  <--"

        print(row)

    print()
    print("=" * 65)
    print(f"CCs removed:  {total_removed}  ({total_removed_vox} voxels)")
    if args.gt and n_eval > 0:
        print(f"Mean cyst Dice  before: {dice_before/n_eval:.4f}")
        print(f"Mean cyst Dice  after:  {dice_after/n_eval:.4f}   (Δ={dice_after/n_eval - dice_before/n_eval:+.4f})")
        print(f"FP alarms  before: {fp_before}/{n_no_cyst_gt} ({100*fp_before/max(1,n_no_cyst_gt):.1f}%)")
        print(f"FP alarms  after:  {fp_after}/{n_no_cyst_gt} ({100*fp_after/max(1,n_no_cyst_gt):.1f}%)")


if __name__ == "__main__":
    main()
