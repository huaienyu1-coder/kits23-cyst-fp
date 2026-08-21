#!/usr/bin/env python3
"""Regenerate the pooled five-fold feature-overlap figure (supplement S9).

Reads the released per-component feature table and plots the two Fig. 2 axes
(mean attenuation vs heterogeneity) for the pooled 215 residual false positives
vs 724 annotated-cyst components. Grayscale-safe.

Usage:  python analysis/make_pooled_scatter.py [out.png]
"""
import csv
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "classifier_features_pooled.csv")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, os.pardir, "figures", "fig_pooled215_scatter.png")

xs_tp, ys_tp, xs_fp, ys_fp = [], [], [], []
with open(CSV) as f:
    for r in csv.DictReader(f):
        x, y = float(r["mean_hu"]), float(r["std_hu"])
        (xs_tp, ys_tp) if r["group"] == "B_tp" else (xs_fp, ys_fp)
        if r["group"] == "B_tp":
            xs_tp.append(x); ys_tp.append(y)
        else:
            xs_fp.append(x); ys_fp.append(y)

fig, ax = plt.subplots(figsize=(6.4, 4.6))
ax.scatter(xs_tp, ys_tp, s=16, marker="o", facecolors="none",
           edgecolors="0.62", linewidths=0.6, label=f"annotated cyst, pooled ($N={len(xs_tp)}$)")
ax.scatter(xs_fp, ys_fp, s=34, marker="^", facecolors="0.15", edgecolors="black",
           linewidths=0.5, label=f"residual false positive ($n={len(xs_fp)}$)", zorder=3)
ax.set_xlabel("mean attenuation (HU)")
ax.set_ylabel("heterogeneity (HU std.)")
ax.set_title("Pooled five-fold: residual false positives vs annotated cyst")
ax.legend(loc="upper right", frameon=True, fontsize=9)
ax.grid(True, color="0.9", linewidth=0.5)
fig.tight_layout()
fig.savefig(OUT, dpi=300)
print("SAVED", OUT, " TP", len(xs_tp), " FP", len(xs_fp))
