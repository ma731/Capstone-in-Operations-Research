"""Preliminary Phase 3 figures: active transfer unlocks value, and robustness
crosses over under tail risk. Numbers are from the prototype scripts
(prototype_transfer_dro.py, prototype_emergency_crossover.py); this draws them.

Run: .venv\\Scripts\\python -m scripts.plot_part3
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.analysis.plotstyle import (  # noqa: E402
    apply_style, NAVY, GOLD, RUST, SAGE, INK, LINE,
)

FIG = Path("figures")

# (a) transfer-budget savings (out-of-sample CVaR reduction vs no transfer)
GRIDS = ["Western US", "Eastern US–Canada", "Diversified"]
SAVINGS = [4.0, 9.9, 9.0]

# (b) emergency-severity crossover: robust(CVaR)-commitment gain over risk-neutral
M = [1.0, 1.5, 2.0, 3.0, 4.0]
GAIN = {
    "Western US": [-0.03, 0.02, 0.17, 3.67, 8.39],
    "Diversified": [-0.12, 0.07, 0.34, 1.32, 1.47],
}
COL = {"Western US": NAVY, "Diversified": SAGE}


def main():
    apply_style()
    FIG.mkdir(exist_ok=True)
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.0, 5.6),
                                   constrained_layout=True)

    # ---- Panel A: transfer unlocks savings ----
    x = np.arange(len(GRIDS))
    axA.bar(x, SAVINGS, 0.62, color=[NAVY, RUST, SAGE], zorder=3)
    for i, v in enumerate(SAVINGS):
        axA.text(i, v + 0.25, f"{v:.1f}%", ha="center", va="bottom",
                 fontsize=13, color=INK)
    axA.set_xticks(x)
    axA.set_xticklabels(GRIDS, fontsize=12)
    axA.set_ylabel("Out-of-sample $\\mathrm{CVaR}_{0.95}$ reduction"
                   " vs. no transfer  [%]")
    axA.set_ylim(0, 12)
    axA.set_title("A.  Active transfer unlocks spatial value")
    axA.grid(axis="y", color=LINE, alpha=0.7, lw=0.8)
    axA.margins(x=0.08)

    # ---- Panel B: the tail-risk crossover ----
    axB.set_xlim(0.78, 4.62)
    axB.set_ylim(-1.4, 9.6)
    axB.axhspan(-1.4, 0, color="#fbeeec", alpha=0.7, zorder=0)
    axB.axhspan(0, 9.6, color="#eef4ef", alpha=0.6, zorder=0)
    axB.axhline(0, color="0.45", lw=1.0, zorder=1)

    for g, gain in GAIN.items():
        axB.plot(M, gain, "-o", color=COL[g], lw=2.4, ms=6.5, zorder=4)
    # direct labels at the right ends, no legend needed
    axB.text(4.08, GAIN["Western US"][-1], " Western US", va="center",
             ha="left", fontsize=12, color=NAVY)
    axB.text(4.08, GAIN["Diversified"][-1], " Diversified", va="center",
             ha="left", fontsize=12, color=SAGE)

    # crossover marker
    axB.axvline(3.0, color="0.5", ls="--", lw=1.0, zorder=1)
    axB.text(3.0, 9.25, "crossover  $M^{\\star}\\!\\approx\\!3$", ha="center",
             va="top", fontsize=11, color="0.35")
    # operating range of real grids
    axB.axvline(1.4, color=RUST, ls=":", lw=1.4, zorder=1)
    axB.text(1.46, -1.05, "real grids reach\nonly $M\\approx1.4$", ha="left",
             va="bottom", fontsize=11, color=RUST)
    # single bold takeaway, in the empty upper-left band
    axB.text(1.0, 6.6, "Robustness pays\nonly in the deep tail", ha="left",
             va="center", fontsize=12.5, fontweight="bold", color=NAVY)

    axB.set_xlabel("Grid-emergency severity $M$  (carbon-spike multiplier)")
    axB.set_ylabel("Robust commitment gain over"
                   " risk-neutral, $\\mathrm{CVaR}_{0.95}$  [%]")
    axB.set_title("B.  When does robustness pay?")
    axB.set_xticks(M)
    axB.grid(axis="y", color=LINE, alpha=0.7, lw=0.8)

    for ext in ("pdf", "png"):
        p = FIG / f"part3_preliminary.{ext}"
        fig.savefig(p, dpi=300)
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
