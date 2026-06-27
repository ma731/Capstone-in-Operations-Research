"""Poster figure: the mean-leveling positive control (replaces certificate_canyon).

For each grid, the spatial gap (value of modelling cross-region covariance) in two
worlds: the REAL world (gaps near zero, masked) and a MEAN-FLATTENED world where each
region's average carbon is levelled so only the co-movement remains. Flattening the
mean reveals a real signal (Diversified +1.46%, Eastern +0.42%) that is invisible in
reality. This is the test's positive control: it fires when value exists, so the
real-world null is a genuine absence of value, not a blind test. Numbers trace to the
committed *_ablate-flat snapshots.

Run:  python -m scripts.plot_positive_control
Writes: poster/figs/positive_control.png
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NAVY, GOLD, GOLDD, RUST = "#1F3B63", "#C98A2B", "#8A5C16", "#B3402F"
SNAP = Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"
OUT = Path(__file__).resolve().parents[1] / "poster" / "figs" / "positive_control.png"
GRIDS = [("us_west", "Western US"), ("taskc", "Eastern US–Canada"),
         ("us_hetero", "Diversified")]
MARGIN = 0.4


def maxgap(stem):
    rows = list(csv.DictReader(open(SNAP / stem)))
    return max(float(r["gap_pct"]) for r in rows)


def main():
    real, flat = [], []
    for key, _ in GRIDS:
        real.append(maxgap(f"{key}_regimes_2026-06-10.csv"))
        flat.append(maxgap(f"{key}_regimes_2026-06-10_ablate-flat.csv"))
    y = np.arange(len(GRIDS))[::-1]   # Diversified at top

    plt.rcParams.update({"font.family": "serif"})
    fig, ax = plt.subplots(figsize=(6.3, 3.9), dpi=300)

    ax.axvspan(-0.15, MARGIN, color="0.92", zorder=0)
    ax.axvline(MARGIN, color=RUST, lw=1.6, ls="--", zorder=1)
    ax.text(MARGIN + 0.03, len(GRIDS) - 0.5, "0.4% materiality", color=RUST,
            fontsize=9.5, style="italic", va="center")

    for yi, r, f in zip(y, real, flat):
        ax.annotate("", xy=(f, yi), xytext=(r, yi),
                    arrowprops=dict(arrowstyle="-|>", color="0.55", lw=2.0,
                                    shrinkA=6, shrinkB=6))
        ax.scatter(r, yi, s=150, color=NAVY, zorder=4, edgecolor="white", lw=1.2)
        ax.scatter(f, yi, s=170, color=GOLD, zorder=4, edgecolor="white", lw=1.2)
        ax.text(f + 0.04, yi + 0.12, f"+{f:.2f}%", color=GOLDD, fontsize=10.5,
                fontweight="bold", va="bottom")

    ax.scatter([], [], s=150, color=NAVY, label="real mean field (masked)")
    ax.scatter([], [], s=170, color=GOLD, label="mean removed (positive control)")

    ax.set_yticks(y)
    ax.set_yticklabels([g[1] for g in GRIDS], fontsize=11)
    ax.set_ylim(-0.6, len(GRIDS) - 0.3)
    ax.set_xlim(-0.15, 1.62)
    ax.set_xlabel("value of modelling cross-region covariance  (% of $\\mathrm{CVaR}_{0.95}$)")
    ax.set_title("The signal is real but masked: covariance pays only when the\n"
                 "mean field is flattened (the test's positive control)",
                 fontsize=12, fontweight="bold", color=NAVY, pad=8)
    ax.legend(loc="lower right", fontsize=9.5, frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="0.88", lw=0.6)
    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    print(f"wrote {OUT}  real={[round(x,3) for x in real]}  flat={[round(x,3) for x in flat]}")


if __name__ == "__main__":
    main()
