"""The null is robust: spatial gap across every estimator and stress test.

For each case and each robustness arm (sample covariance, Ledoit-Wolf, seasonal
and AR(1) residuals, walk-forward to 2024, and a 3x tighter ramp), plot the spread
of the spatial gap across all nine (regime x alpha) cells against a materiality
band. Every arm sits inside the band: the null does not move.

Run: .venv\\Scripts\\python -m scripts.plot_robustness
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from src.analysis.plotstyle import NAVY, RUST, apply_style  # noqa: E402

FIG = Path("figures")
SNAP = Path("docs/results_snapshots")
CASES = ("us_west", "taskc", "us_hetero")
TITLE = {"us_west": "Western US  (CA/NV/AZ)", "taskc": "Eastern US–Canada  (Ontario belt)",
         "us_hetero": "Diversified  (solar/wind/hydro)"}
# arm label -> snapshot filename suffix
ARMS = [
    ("sample cov.",      "{c}_regimes_2026-06-10.csv"),
    ("Ledoit–Wolf", "{c}_regimes_2026-06-10_lw.csv"),
    ("seasonal resid.",  "{c}_regimes_2026-06-10_seasonal.csv"),
    ("AR(1) resid.",     "{c}_regimes_2026-06-10_ar1.csv"),
    ("walk-forward '24", "{c}_regimes_2026-06-10_ty2024.csv"),
    ("tighter ramp 5",   "{c}_regimes_2026-06-13_ramp5.csv"),
]


def main() -> None:
    apply_style()
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.2), sharex=True, sharey=True,
                             constrained_layout=True)
    ys = np.arange(len(ARMS))[::-1]
    band_grey = "0.86"
    for ax, case in zip(axes, CASES):
        ax.axvspan(-0.1, 0.1, color=band_grey, alpha=1.0, zorder=0)
        ax.axvline(0, color="0.45", lw=1.0, zorder=1)
        for y, (label, patt) in zip(ys, ARMS):
            df = pd.read_csv(SNAP / patt.format(c=case))
            g = df["gap_pct"].to_numpy()
            lo, hi, med = g.min(), g.max(), np.median(g)
            col = RUST if (hi > 0.1 or lo < -0.1) else NAVY
            ax.plot([lo, hi], [y, y], color=col, lw=3.4, alpha=0.45,
                    solid_capstyle="round", zorder=2)
            ax.scatter(g, np.full_like(g, y), s=16, color=col, zorder=3, alpha=0.9)
            ax.scatter([med], [y], s=130, marker="|", color="#16202E",
                       linewidths=1.8, zorder=4)
        ax.set_title(TITLE[case], fontsize=12.5, pad=10)
        ax.set_xlim(-0.35, 0.35)
        ax.set_xticks([-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3])
        ax.tick_params(axis="x", labelsize=11.5)
        ax.grid(axis="x", alpha=0.0)
        ax.grid(axis="y", alpha=0.0)
        for s in ("left",):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)

    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([a[0] for a in ARMS], fontsize=12)
    axes[0].set_ylim(-0.7, len(ARMS) - 0.3)

    axes[1].set_xlabel("spatial gap, shuffled $-$ joint $\\mathrm{CVaR}_{0.95}$  [%]",
                       fontsize=12.5, labelpad=8)

    # one shared legend, placed outside the panels in genuinely empty space
    handles = [
        Patch(facecolor=band_grey, edgecolor="none", label="no-value band  $\\pm0.1\\%$"),
        Line2D([0], [0], color=NAVY, lw=3.4, alpha=0.6, marker="o", markersize=5,
               markerfacecolor=NAVY, markeredgecolor=NAVY, label="within band"),
        Line2D([0], [0], color=RUST, lw=3.4, alpha=0.6, marker="o", markersize=5,
               markerfacecolor=RUST, markeredgecolor=RUST, label="exceeds band"),
        Line2D([0], [0], color="#16202E", lw=0, marker="|", markersize=13,
               markeredgewidth=1.8, label="median of 9 cells"),
    ]
    fig.legend(handles=handles, loc="outside lower center", ncol=4,
               frameon=False, fontsize=11.5, handletextpad=0.6,
               columnspacing=2.2, borderaxespad=0.0)

    fig.suptitle("The null is robust: every estimator and stress test leaves the\n"
                 "spatial gap inside the no-value band", fontsize=14,
                 fontweight="bold", color=NAVY)

    FIG.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG / f"robustness.{ext}"
        fig.savefig(p, dpi=300)
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
