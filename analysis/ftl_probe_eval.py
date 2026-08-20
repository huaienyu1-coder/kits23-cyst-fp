"""
ftl_probe_eval.py

Compares cyst-specific metrics across FTL probe trainers vs baseline (ResEncL fold_0).
Reads validation/summary.json produced by nnUNet after each trainer completes 10 epochs.

Output:
  - N=98 cyst Dice (NaN → 1.0 for both-empty), matching paper convention
  - NaN-excluded cyst Dice (strict, matches KiTS23 hierarchical metric logic)
  - FP alarm rate (GT empty, pred cyst > 0)
  - FN miss rate (GT cyst > 0, pred cyst = 0)
  - Gross FP removals and gross FP additions vs baseline

Usage:
  python ftl_probe_eval.py [--show-cases]
"""

import argparse
import json
import os
import re
from pathlib import Path

RESULTS_ROOT = Path("/home/huaienyu/KiTS23/nnUNet_results/Dataset500_KiTS23")

TRAINERS = {
    "baseline_ResEncL": "nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres",
    "FTL_alpha03":      "nnUNetTrainerFTL_cyst_alpha03__nnUNetResEncUNetLPlans__3d_lowres",
    "FTL_alpha04":      "nnUNetTrainerFTL_cyst_alpha04__nnUNetResEncUNetLPlans__3d_lowres",
}
FOLD = "fold_0"
CYST_LABEL = "3"


def load_summary(trainer_dir: Path) -> list | None:
    summary_path = trainer_dir / FOLD / "validation" / "summary.json"
    if not summary_path.exists():
        return None
    with open(summary_path) as f:
        data = json.load(f)
    return data["metric_per_case"]


def case_id(entry: dict) -> str:
    return Path(entry["prediction_file"]).stem.replace(".nii", "")


def cyst_metrics(entry: dict) -> dict:
    m = entry["metrics"][CYST_LABEL]
    n_ref = m["n_ref"]
    n_pred = m["n_pred"]
    dice = m["Dice"]

    both_empty = (n_ref == 0 and n_pred == 0)
    fp_alarm   = (n_ref == 0 and n_pred > 0)
    fn_miss    = (n_ref > 0  and n_pred == 0)

    # N=98 convention: both-empty → 1.0
    dice_n98 = 1.0 if both_empty else (float("nan") if fp_alarm and dice != dice else dice)
    # For fp_alarm, nnUNet reports Dice=0.0 (n_ref=0, n_pred>0) → keep 0.0
    if not both_empty:
        dice_n98 = dice if dice == dice else 0.0  # NaN→0 if truly NaN
    else:
        dice_n98 = 1.0

    return {
        "dice":        dice,
        "dice_n98":    dice_n98,
        "n_ref":       n_ref,
        "n_pred":      n_pred,
        "both_empty":  both_empty,
        "fp_alarm":    fp_alarm,
        "fn_miss":     fn_miss,
    }


def summarize(name: str, entries: list, baseline_fp_cases: set | None = None,
              show_cases: bool = False):
    per_case = {}
    for e in entries:
        cid = case_id(e)
        per_case[cid] = cyst_metrics(e)

    n_total   = len(per_case)
    gt_pos    = sum(1 for v in per_case.values() if v["n_ref"] > 0)
    gt_neg    = n_total - gt_pos

    fp_cases  = {cid for cid, v in per_case.items() if v["fp_alarm"]}
    fn_cases  = {cid for cid, v in per_case.items() if v["fn_miss"]}

    # N=98 cyst Dice
    dice_n98_vals = [v["dice_n98"] for v in per_case.values()]
    mean_n98 = sum(dice_n98_vals) / len(dice_n98_vals)

    # NaN-excluded: only cases where at least one of GT/pred is non-empty
    nan_excl = [v["dice"] for v in per_case.values()
                if not v["both_empty"] and v["dice"] == v["dice"]]
    mean_nanexcl = sum(nan_excl) / len(nan_excl) if nan_excl else float("nan")

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  Cases total : {n_total}  (GT cyst+: {gt_pos}, GT cyst-: {gt_neg})")
    print(f"  CystDice N=98       : {mean_n98:.4f}")
    print(f"  CystDice NaN-excl   : {mean_nanexcl:.4f}  (N={len(nan_excl)})")
    print(f"  FP alarm rate       : {len(fp_cases)}/{gt_neg} = {len(fp_cases)/gt_neg:.1%}")
    print(f"  FN miss  rate       : {len(fn_cases)}/{gt_pos} = {len(fn_cases)/gt_pos:.1%}")

    if baseline_fp_cases is not None:
        gross_removed = baseline_fp_cases - fp_cases
        gross_added   = fp_cases - baseline_fp_cases
        print(f"  vs baseline FP: removed={len(gross_removed)}, added={len(gross_added)}, "
              f"net={len(gross_removed)-len(gross_added):+d}")
        if show_cases and gross_removed:
            print(f"    Removed: {sorted(gross_removed)}")
        if show_cases and gross_added:
            print(f"    Added:   {sorted(gross_added)}")

    if show_cases and fp_cases:
        print(f"  FP alarm cases: {sorted(fp_cases)}")

    return {
        "mean_n98": mean_n98,
        "mean_nanexcl": mean_nanexcl,
        "fp_cases": fp_cases,
        "fn_cases": fn_cases,
        "n_nanexcl": len(nan_excl),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-cases", action="store_true",
                        help="Print individual case IDs for FP alarms")
    args = parser.parse_args()

    results = {}
    missing = []

    for label, trainer_dir_name in TRAINERS.items():
        trainer_dir = RESULTS_ROOT / trainer_dir_name
        entries = load_summary(trainer_dir)
        if entries is None:
            print(f"\n[SKIP] {label}: validation/summary.json not found at {trainer_dir}")
            missing.append(label)
        else:
            results[label] = entries

    if not results:
        print("\nNo summary.json files found. Wait for training to complete.")
        return

    baseline_fp = None
    summary_results = {}
    for label, entries in results.items():
        is_baseline = (label == "baseline_ResEncL")
        r = summarize(label, entries,
                      baseline_fp_cases=(None if is_baseline else baseline_fp),
                      show_cases=args.show_cases)
        summary_results[label] = r
        if is_baseline:
            baseline_fp = r["fp_cases"]

    if len(summary_results) > 1:
        print(f"\n{'='*60}")
        print("  DELTA vs baseline (FTL probes — N=98 cyst Dice)")
        print(f"{'='*60}")
        base = summary_results.get("baseline_ResEncL")
        if base:
            for label, r in summary_results.items():
                if label == "baseline_ResEncL":
                    continue
                delta_n98  = r["mean_n98"] - base["mean_n98"]
                delta_nanx = r["mean_nanexcl"] - base["mean_nanexcl"]
                print(f"  {label:20s}  ΔN=98={delta_n98:+.4f}  ΔNAN-excl={delta_nanx:+.4f}")

    if missing:
        print(f"\n[Waiting for: {', '.join(missing)}]")
        print("  Re-run this script once training completes.")


if __name__ == "__main__":
    main()
