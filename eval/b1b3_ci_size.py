#!/usr/bin/env python3
"""B1: Wilson 95% CI for load-bearing rates. B3: size distribution of residual
cyst FP components on the headline pipeline (soft_majority_rule3_typex). READ-ONLY.
B3 gates the 'missed-malignancy' clinical framing: if the FP are sub-cm blobs the
framing must soften; if substantial, it holds."""
import os, json
from math import sqrt
import numpy as np
import SimpleITK as sitk
from scipy import ndimage as ndi

GT    = os.path.expanduser("~/KiTS23/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations")
FINAL = os.path.expanduser("~/KiTS23/holdout_pipeline/soft_majority_rule3_typex")
CYST = 3
CONN = np.ones((3, 3, 3), dtype=int)   # 26-conn (project convention)

def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return p, max(0, c-h), min(1, c+h)

def main():
    sizes_vox, sizes_mm3, diam_mm = [], [], []
    per_case = []
    gt_neg = fp_cases = 0
    gt_pos = fn_cases = 0
    for f in sorted(os.listdir(FINAL)):
        if not f.endswith(".nii.gz"):
            continue
        gimg = sitk.ReadImage(os.path.join(GT, f))
        pimg = sitk.ReadImage(os.path.join(FINAL, f))
        ga = sitk.GetArrayFromImage(gimg); pa = sitk.GetArrayFromImage(pimg)
        sx, sy, sz = gimg.GetSpacing()
        voxvol = sx*sy*sz   # mm^3 per voxel
        gt_has = bool((ga == CYST).any()); pr_has = bool((pa == CYST).any())
        if gt_has:
            gt_pos += 1
            if not pr_has: fn_cases += 1
            continue                       # B3 only on cyst-negative cases (unambiguous FP)
        gt_neg += 1
        if not pr_has:
            continue
        fp_cases += 1
        lab, n = ndi.label(pa == CYST, structure=CONN)
        comps = []
        for i in range(1, n+1):
            vox = int((lab == i).sum())
            mm3 = vox * voxvol
            d = 2 * (3*mm3/(4*np.pi))**(1/3)   # equiv-sphere diameter (mm)
            sizes_vox.append(vox); sizes_mm3.append(mm3); diam_mm.append(d)
            comps.append({"vox": vox, "mm3": round(mm3, 1), "diam_mm": round(d, 1)})
        per_case.append({"case": f.replace(".nii.gz",""), "n_comp": n,
                         "comps": sorted(comps, key=lambda c: -c["vox"])})

    dv = np.array(sizes_vox); dm = np.array(diam_mm); mm3 = np.array(sizes_mm3)
    def pct(a, q): return round(float(np.percentile(a, q)), 1)

    print("="*64)
    print("B1  Wilson 95% CI (load-bearing rates)")
    print("="*64)
    for name, k, n in [("cyst FP baseline (hard_intersection)", 19, 48),
                        ("cyst FP final (rule3+typeX)", 16, 48),
                        ("cyst FN (missed true cyst)", 2, 50)]:
        p, lo, hi = wilson(k, n)
        print(f"  {name:42s}: {k}/{n} = {p:.1%}  [95% CI {lo:.1%}, {hi:.1%}]")
    print("  NOTE: voxel taxonomy (Fullres 98.8% / ResEnc 23.4%) — point estimates on")
    print("        correlated voxels; report per-component, NOT a voxel-level CI.")

    print("\n" + "="*64)
    print(f"B3  Residual FP component SIZE distribution  (n={len(dv)} components, "
          f"{fp_cases} cases; verify {fp_cases}==16)")
    print("="*64)
    print(f"  voxels      : min {int(dv.min())}  p25 {pct(dv,25):.0f}  median {pct(dv,50):.0f}  "
          f"p75 {pct(dv,75):.0f}  max {int(dv.max())}")
    print(f"  volume mm^3 : min {mm3.min():.0f}  median {pct(mm3,50):.0f}  max {mm3.max():.0f}")
    print(f"  equiv-diam mm: min {dm.min():.1f}  p25 {pct(dm,25)}  median {pct(dm,50)}  "
          f"p75 {pct(dm,75)}  max {dm.max():.1f}")
    for thr in (3, 5, 10):
        print(f"    components < {thr} mm equiv-diam: {int((dm<thr).sum())}/{len(dm)} "
              f"({(dm<thr).mean():.0%})")
    print(f"  largest FP per case (diam mm): "
          f"{sorted([max(c['diam_mm'] for c in pc['comps']) for pc in per_case], reverse=True)}")

    json.dump({"per_case": per_case,
               "sizes_vox": sizes_vox, "diam_mm": [round(x,2) for x in diam_mm],
               "gt_neg": gt_neg, "fp_cases": fp_cases, "gt_pos": gt_pos, "fn_cases": fn_cases},
              open(os.path.expanduser("~/KiTS23/repro_check/b3_fp_sizes.json"), "w"), indent=2)
    print(f"\n  saved b3_fp_sizes.json  (gt_neg={gt_neg}, fp_cases={fp_cases}, fn={fn_cases}/{gt_pos})")

if __name__ == "__main__":
    main()
