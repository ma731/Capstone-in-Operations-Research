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

from src.analysis.plotstyle import apply_style, NAVY, GOLD, RUST, SAGE  # noqa: E402

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
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.0, 5.0),
                                   constrained_layout=True)

    # Panel A: transfer unlocks savings
    x = np.arange(len(GRIDS))
    axA.bar(x, SAVINGS, 0.55, color=[NAVY, RUST, SAGE])
    for i, v in enumerate(SAVINGS):
        axA.text(i, v + 0.15, f"{v:.1f}%", ha="center", fontsize=10, fontweight="bold")
    axA.set_xticks(x)
    axA.set_xticklabels(GRIDS, fontsize=9)
    axA.set_ylabel("out-of-sample $\\mathrm{CVaR}_{0.95}$ reduction\nvs.\\ no transfer  [%]",
                   fontsize=9)
    axA.set_ylim(0, 12)
    axA.set_title("A. Active transfer unlocks spatial value\n"
                  "(the value the passive null left on the table)", fontsize=10)
    axA.grid(axis="y", alpha=0.3, lw=0.5)

    # Panel B: the tail-risk crossover
    axB.axhline(0, color="0.35", lw=1.1)
    axB.axhspan(-0.5, 0, color="#fbeeec", alpha=0.7, zorder=0)
    axB.axhspan(0, 9, color="#eef4ef", alpha=0.6, zorder=0)
    for g, gain in GAIN.items():
        axB.plot(M, gain, "-o", color=COL[g], lw=2.2, ms=6, label=g)
    axB.axvline(3.0, color="0.5", ls="--", lw=1)
    axB.text(3.05, 7.2, "crossover\n($M^\\star\\approx3$)", fontsize=9, color="0.4")
    axB.axvline(1.4, color=RUST, ls=":", lw=1.2)
    axB.text(1.45, -0.9, "real grids reach\nonly $M\\approx1.4$", fontsize=9, color=RUST)
    axB.text(3.4, 5.0, "robustness\npays", fontsize=9, color=SAGE)
    axB.set_xlabel("grid-emergency severity $M$ (carbon spike multiplier)", fontsize=9)
    axB.set_ylabel("robust commitment gain over\nrisk-neutral  $\\mathrm{CVaR}_{0.95}$  [%]",
                   fontsize=9)
    axB.set_title("B. When does robustness pay? The tail-risk crossover\n"
                  "(crossover at $M^\\star\\approx3$; real grids reach only $M\\approx1.4$)",
                  fontsize=10)
    axB.legend(frameon=False, fontsize=9, loc="upper left")
    axB.grid(alpha=0.3, lw=0.5)

    fig.suptitle("Preliminary Phase 3: active transfer unlocks spatial value, and "
                 "robustness crosses over under grid-emergency tail risk", fontsize=12)
    for ext in ("pdf", "png"):
        p = FIG / f"part3_preliminary.{ext}"
        fig.savefig(p, dpi=300)
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
