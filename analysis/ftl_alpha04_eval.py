"""
ftl_alpha04_eval.py

Evaluates FTL-alpha04 ResEnc-L probe in the 2/3 majority voting pipeline.

Two comparisons:
A) Soft voting baseline (existing soft_voting/hard_intersection/, 0.9022)
   → FP alarm set for context / §7f cross-path comparison
B) Hard label 2/3 majority baseline vs FTL hard label 2/3 majority
   → Self-consistent comparison: same mechanism, ResEnc-L vs alpha04

Note: soft voting uses raw probability .npz (unavailable from probe training).
Alpha04 validation only writes .nii.gz (save_probabilities=False by default).
Therefore the gated evaluation uses hard label majority for both sides.

Usage:
  python ftl_alpha04_eval.py [--alpha04-dir PATH]
"""

import argparse
import os
import numpy as np
import SimpleITK as sitk
from pathlib import Path

# Local KiTS23 working root (raw data / weights obtained separately, not in this repo).
# Override with:  export KITS23_ROOT=/path/to/your/KiTS23
KITS23_ROOT = Path(os.environ.get("KITS23_ROOT", os.path.expanduser("~/KiTS23")))
HOLDOUT = KITS23_ROOT / "holdout_pipeline"
RAW_LOWRES  = HOLDOUT / "raw_predictions/lowres_plain"
RAW_FULLRES = HOLDOUT / "raw_predictions/fullres"
RAW_RESENC  = HOLDOUT / "raw_predictions/resenc_l"
SOFT_MAJORITY = HOLDOUT / "soft_voting/hard_intersection"  # 0.9022 baseline

ALPHA04_DIR_DEFAULT = (
    KITS23_ROOT / "nnUNet_results/Dataset500_KiTS23"
    / "nnUNetTrainerFTL_cyst_alpha04__nnUNetResEncUNetLPlans__3d_lowres"
    / "fold_0/validation"
)
GT_DIR = KITS23_ROOT / "nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations"

CYST = 3


def arr(path):
    return sitk.GetArrayFromImage(sitk.ReadImage(str(path)))


def has_cyst(a):
    return bool((a == CYST).any())


def hard_majority(a, b, c):
    """Voxel-wise 2-of-3 majority. Ties → 0."""
    n = int(max(a.max(), b.max(), c.max())) + 1
    out = np.zeros_like(a)
    for lbl in range(1, n):
        votes = (a == lbl).astype(np.int8) + (b == lbl).astype(np.int8) + (c == lbl).astype(np.int8)
        out = np.where((votes >= 2) & (out == 0), lbl, out)
    return out


def fp_source(pred, gt, raw_l, raw_f, raw_r):
    """Classify cyst FP voxels by which raw models contribute."""
    fp_mask = (pred == CYST) & (gt != CYST)
    if not fp_mask.any():
        return "no_fp"
    fl = (raw_l == CYST)[fp_mask].mean()
    ff = (raw_f == CYST)[fp_mask].mean()
    fr = (raw_r == CYST)[fp_mask].mean()
    fa = ((raw_l == CYST) & (raw_f == CYST) & (raw_r == CYST))[fp_mask].mean()
    if fa >= 0.5:  return "ALL_3"
    if ff >= 0.5 and fr >= 0.5: return "Full+ResEnc"
    if fl >= 0.5 and fr >= 0.5: return "Low+ResEnc"
    if fl >= 0.5 and ff >= 0.5: return "Low+Full"
    if fr >= 0.5: return "ResEnc_only"
    if ff >= 0.5: return "Fullres_only"
    if fl >= 0.5: return "Lowres_only"
    return "mixed"


def analyze_fp_set(pred_dir, gt_dir, raw_l_dir, raw_f_dir, raw_r_dir, label=""):
    cases = sorted([f.name for f in Path(pred_dir).glob("*.nii.gz")])
    fp_map = {}  # case → source
    fn_set = set()
    gt_neg = 0
    for fname in cases:
        case = fname.replace(".nii.gz", "")
        gt   = arr(gt_dir   / fname)
        pred = arr(pred_dir / fname)
        rl   = arr(raw_l_dir / fname)
        rf   = arr(raw_f_dir / fname)
        rr   = arr(raw_r_dir / fname)
        gt_cyst = has_cyst(gt)
        pred_cyst = has_cyst(pred)
        if gt_cyst:
            if not pred_cyst:
                fn_set.add(case)
        else:
            gt_neg += 1
            if pred_cyst:
                fp_map[case] = fp_source(pred, gt, rl, rf, rr)
    return fp_map, fn_set, gt_neg, len(cases)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha04-dir", default=str(ALPHA04_DIR_DEFAULT))
    args = parser.parse_args()
    alpha04_dir = Path(args.alpha04_dir)

    cases = sorted([f.name for f in SOFT_MAJORITY.glob("*.nii.gz")])
    n_total = len(cases)
    alpha04_files = list(alpha04_dir.glob("*.nii.gz"))

    # ── A: Soft voting baseline (0.9022 path) ─────────────────────────
    print("═" * 65)
    print("  A. Soft voting baseline (soft_voting/hard_intersection/, 0.9022)")
    print("═" * 65)
    soft_fp, soft_fn, gt_neg, _ = analyze_fp_set(
        SOFT_MAJORITY, GT_DIR, RAW_LOWRES, RAW_FULLRES, RAW_RESENC)
    print(f"  FP alarm: {len(soft_fp)}/{gt_neg} = {len(soft_fp)/gt_neg:.1%}")
    print(f"  FN miss : {len(soft_fn)}")
    src_counts = {}
    for s in soft_fp.values():
        src_counts[s] = src_counts.get(s, 0) + 1
    for s, n in sorted(src_counts.items(), key=lambda x: -x[1]):
        print(f"    {s:20s}: {n}")

    # ── B: Hard label 2/3 majority — baseline ─────────────────────────
    print()
    print("═" * 65)
    print("  B. Hard label 2/3 majority — BASELINE (lowres + fullres + resenc_l)")
    print("═" * 65)

    hard_baseline_fp = {}
    hard_baseline_fn = set()
    hard_baseline_dir = HOLDOUT / "_tmp_hard_majority_baseline"
    hard_baseline_dir.mkdir(exist_ok=True)

    for fname in cases:
        case = fname.replace(".nii.gz", "")
        gt   = arr(GT_DIR / fname)
        rl   = arr(RAW_LOWRES  / fname)
        rf   = arr(RAW_FULLRES  / fname)
        rr   = arr(RAW_RESENC   / fname)
        maj  = hard_majority(rl, rf, rr)
        # save for later HEC if needed
        ref  = sitk.ReadImage(str(RAW_LOWRES / fname))
        out  = sitk.GetImageFromArray(maj.astype(np.uint8))
        out.CopyInformation(ref)
        sitk.WriteImage(out, str(hard_baseline_dir / fname))

        if has_cyst(gt):
            if not has_cyst(maj):
                hard_baseline_fn.add(case)
        else:
            if has_cyst(maj):
                hard_baseline_fp[case] = fp_source(maj, gt, rl, rf, rr)

    print(f"  FP alarm: {len(hard_baseline_fp)}/{gt_neg} = {len(hard_baseline_fp)/gt_neg:.1%}")
    print(f"  FN miss : {len(hard_baseline_fn)}")
    src_counts2 = {}
    for s in hard_baseline_fp.values():
        src_counts2[s] = src_counts2.get(s, 0) + 1
    for s, n in sorted(src_counts2.items(), key=lambda x: -x[1]):
        print(f"    {s:20s}: {n}")

    # ── Wait check ────────────────────────────────────────────────────
    if len(alpha04_files) < n_total:
        print()
        print(f"[WAIT] alpha04 validation: {len(alpha04_files)}/{n_total} cases done.")
        print(f"       Re-run when complete.\n")
        print(f"  → Key finding already available:")
        print(f"     Soft voting path: ALL_3 = {src_counts.get('ALL_3',0)}/19 FP cases")
        print(f"     Hard majority path: ALL_3 = {src_counts2.get('ALL_3',0)}/{len(hard_baseline_fp)} FP cases")
        print(f"     (§7f ALL_3=10 was on union+TypeX path — DIFFERENT pipeline)")
        return

    # ── C: Hard label 2/3 majority — FTL alpha04 ──────────────────────
    print()
    print("═" * 65)
    print("  C. Hard label 2/3 majority — FTL alpha04")
    print("═" * 65)

    ftl_fp = {}
    ftl_fn = set()
    for fname in cases:
        case = fname.replace(".nii.gz", "")
        gt   = arr(GT_DIR / fname)
        rl   = arr(RAW_LOWRES  / fname)
        rf   = arr(RAW_FULLRES  / fname)
        ra4  = arr(alpha04_dir  / fname)  # FTL alpha04 replaces resenc_l
        maj  = hard_majority(rl, rf, ra4)

        if has_cyst(gt):
            if not has_cyst(maj):
                ftl_fn.add(case)
        else:
            if has_cyst(maj):
                ftl_fp[case] = fp_source(maj, gt, rl, rf, ra4)

    print(f"  FP alarm: {len(ftl_fp)}/{gt_neg} = {len(ftl_fp)/gt_neg:.1%}")
    print(f"  FN miss : {len(ftl_fn)}")
    src_counts3 = {}
    for s in ftl_fp.values():
        src_counts3[s] = src_counts3.get(s, 0) + 1
    for s, n in sorted(src_counts3.items(), key=lambda x: -x[1]):
        print(f"    {s:20s}: {n}")

    # ── D: Comparison (B vs C) ─────────────────────────────────────────
    print()
    print("═" * 65)
    print("  D. Comparison: FTL alpha04 vs Hard Baseline")
    print("═" * 65)
    removed = set(hard_baseline_fp) - set(ftl_fp)
    added   = set(ftl_fp) - set(hard_baseline_fp)
    print(f"  FP removed (gross): {len(removed)}")
    for c in sorted(removed):
        print(f"    {c}  (was: {hard_baseline_fp[c]})")
    print(f"  FP added   (gross): {len(added)}")
    for c in sorted(added):
        print(f"    {c}  (new: {ftl_fp[c]})")
    print(f"  Net FP change: {len(ftl_fp)-len(hard_baseline_fp):+d}")

    # ALL_3 gate
    all3_base  = {c for c, s in hard_baseline_fp.items() if s == "ALL_3"}
    all3_fixed = all3_base - set(ftl_fp)
    print()
    print(f"  ALL_3 gate check (from hard majority path):")
    print(f"    Baseline ALL_3 FP: {len(all3_base)}")
    print(f"    ALL_3 fixed: {len(all3_fixed)}")
    gate = len(all3_fixed) >= 5
    print(f"    Gate (≥5 ALL_3 fixed): {'PASS' if gate else 'FAIL'}")
    if not gate:
        print()
        print("  NEGATIVE RESULT:")
        print("  FTL-alpha04 probe failed the gate.")
        print("  Structural reason: in 2/3 majority, ALL_3 cases require ≥2 models")
        print("  to disagree. Fine-tuning only ResEnc-L cannot break ALL_3 consensus.")
        print("  Majority path ALL_3 (hard): ONLY from the hard majority baseline above.")
        print("  (§7f's '10 ALL_3' was measured on union+TypeX path = different pipeline.)")

    # Cyst diff per case for top changed cases
    print()
    print("  Per-case ResEnc-L changes (cases where baseline≠FTL hard label):")
    n_changed = 0
    for fname in cases:
        case = fname.replace(".nii.gz", "")
        rr = arr(RAW_RESENC  / fname)
        ra4 = arr(alpha04_dir / fname)
        diff = int((rr != ra4).sum())
        if diff > 0:
            n_changed += 1
    print(f"    {n_changed}/{n_total} cases have at least 1 voxel difference in ResEnc-L prediction")


if __name__ == "__main__":
    main()
