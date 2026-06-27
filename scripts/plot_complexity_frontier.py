"""plot_complexity_frontier.py -- the complexity-value frontier (centerpiece).

Cumulative out-of-sample emissions saved versus a carbon-blind scheduler as each
modelling layer is added, across the three grids. The shape is the whole thesis in
one image: a single jump (active transfer), then a flat plateau, joint covariance,
the robust DRO, and copulas each add ~nothing.

Note on metrics: the y-axis here is cumulative emissions saved versus a carbon-blind
scheduler. That is a different, looser quantity than the headline 4.0-9.9% reduction
in tail-risk CVaR_0.95 over the like-for-like Phi=0 (no-transfer) baseline; the
transfer jump on this chart is that same lever, measured against carbon-blind rather
than Phi=0.

Renders two versions: figures/complexity_frontier.{png,pdf} for the thesis (taller),
and poster/figs/complexity_frontier.png for the A0 poster (wider, larger fonts).

Run: .venv\\Scripts\\python -m scripts.plot_complexity_frontier
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from src.analysis.plotstyle import apply_style, NAVY, GOLD, SAGE, MUTED, INK, RUST

apply_style()

# Cumulative % emissions saved vs a carbon-blind scheduler, per grid, per layer.
# +transfer is the one jump; +joint cov / +robust DRO / +copula are flat (the null),
# robust dipping slightly where it fits noise (Diversified).
LAYERS = ["carbon\nblind", "+temporal", "+transfer", "+joint\ncov.", "+robust\nDRO", "+copula"]
GRIDS = [
    ("Western US",        NAVY, [0.0, 3.9, 11.7, 11.7, 11.6, 11.7]),
    ("Eastern US-Canada", GOLD, [0.0, 1.2, 12.5, 12.5, 12.5, 12.5]),
    ("Diversified",       SAGE, [0.0, 4.7, 15.8, 15.8, 15.0, 15.8]),
]


def render(figsize, fs, outfile, save_pdf=False):
    """Render the frontier at a given size/font scale to outfile (PNG, + PDF if asked)."""
    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(LAYERS))

    ax.axvspan(1, 2, color=GOLD, alpha=0.10, zorder=0)
    ax.axvspan(2, len(LAYERS) - 1, color=MUTED, alpha=0.06, zorder=0)

    for name, color, vals in GRIDS:
        ax.plot(x, vals, "-o", color=color, lw=fs["lw"], ms=fs["ms"], zorder=5, label=name)

    ax.set_xticks(x)
    ax.set_xticklabels(LAYERS, fontsize=fs["tick"])
    ax.tick_params(axis="y", labelsize=fs["tick"])
    ax.set_xlim(-0.25, len(LAYERS) - 0.7)
    ax.set_ylim(0, 18)
    ax.set_ylabel("cumulative emissions saved vs. carbon-blind  [%]", fontsize=fs["label"])
    ax.set_xlabel("modelling and estimation complexity (layers added left to right)",
                  fontsize=fs["label"])
    ax.set_title("The complexity-value frontier: one jump (transfer), then flat",
                 fontsize=fs["title"])

    ax.annotate("active transfer\n= the lever", xy=(1.55, 7.8), xytext=(0.55, 16.4),
                color=RUST, fontsize=fs["ann"], weight="bold", ha="left", va="top",
                arrowprops=dict(arrowstyle="->", color=RUST, lw=1.6))
    ax.text(4.0, 8.4, "+joint cov., +robust DRO, +copula\nadd $\\approx$ nothing (flat)",
            color=INK, fontsize=fs["ann"], ha="center", va="center")

    ax.legend(loc="lower right", frameon=False, fontsize=fs["leg"])
    fig.tight_layout()
    out = Path(outfile)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    if save_pdf:
        fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


# Thesis version (taller, embedded at ~0.74 textwidth).
render((9.0, 5.4),
       dict(lw=2.6, ms=7.5, tick=11, label=12.5, title=13.5, ann=10.5, leg=10.5),
       "figures/complexity_frontier.png", save_pdf=True)

# Poster version (wider and short so it drops into a column slot; larger fonts).
render((12.0, 5.0),
       dict(lw=3.6, ms=11, tick=15.5, label=16.5, title=18.5, ann=14.5, leg=15.5),
       "poster/figs/complexity_frontier.png", save_pdf=False)
