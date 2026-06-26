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
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), sharex=True,
                             constrained_layout=True)
    for ax, case in zip(axes, CASES):
        ax.axvspan(-0.1, 0.1, color="0.85", alpha=0.8, zorder=0)
        ax.axvline(0, color="0.35", lw=1.1, zorder=1)
        ys = np.arange(len(ARMS))[::-1]
        for y, (label, patt) in zip(ys, ARMS):
            df = pd.read_csv(SNAP / patt.format(c=case))
            g = df["gap_pct"].to_numpy()
            lo, hi, med = g.min(), g.max(), np.median(g)
            col = RUST if (hi > 0.1 or lo < -0.1) else NAVY
            ax.plot([lo, hi], [y, y], color=col, lw=3.2, alpha=0.55,
                    solid_capstyle="round", zorder=2)
            ax.scatter(g, np.full_like(g, y), s=14, color=col, zorder=3, alpha=0.9)
            ax.scatter([med], [y], s=70, marker="|", color="black", zorder=4)
        ax.set_yticks(ys)
        ax.set_yticklabels([a[0] for a in ARMS], fontsize=9)
        ax.set_title(TITLE[case], fontsize=10)
        ax.set_xlabel("spatial gap (shuf $-$ joint) $\\mathrm{CVaR}_{0.95}$  [%]",
                      fontsize=9)
        ax.set_xlim(-0.35, 0.35)
        ax.grid(axis="x", alpha=0.3, lw=0.5)
    axes[0].text(0.0, len(ARMS) - 0.35, "materiality band $\\pm0.1\\%$",
                 ha="center", fontsize=10, color="0.3")
    fig.suptitle("The null is robust: every estimator and stress test leaves the "
                 "spatial gap inside the no-value band", fontsize=12)
    FIG.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG / f"robustness.{ext}"
        fig.savefig(p, dpi=300)
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
