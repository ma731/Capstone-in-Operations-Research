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


# Where to drop the direct end-of-line labels (nudged off the exact endpoints so the
# near-tied Western/Eastern curves get a clear gap; colour does the matching).
LABEL_Y = {"Western US": 10.7, "Eastern US-Canada": 13.0, "Diversified": 15.8}


def render(figsize, fs, outfile, save_pdf=False):
    """Render the frontier at a given size/font scale to outfile (PNG, + PDF if asked)."""
    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)
    x = np.arange(len(LAYERS))

    # Shade the one segment that matters (the transfer jump) and the flat tail.
    ax.axvspan(1, 2, color=GOLD, alpha=0.12, zorder=0)
    ax.axvspan(2, len(LAYERS) - 1, color=MUTED, alpha=0.06, zorder=0)

    for name, color, vals in GRIDS:
        ax.plot(x, vals, "-o", color=color, lw=fs["lw"], ms=fs["ms"],
                mec="white", mew=fs["mew"], zorder=5)
        # Direct labels in the empty margin to the right; no legend over the data.
        ax.text(len(LAYERS) - 0.92, LABEL_Y[name], name, color=color,
                fontsize=fs["leg"], va="center", ha="left", clip_on=False)

    ax.set_xticks(x)
    ax.set_xticklabels(LAYERS, fontsize=fs["tick"])
    ax.tick_params(axis="y", labelsize=fs["tick"])
    ax.set_xlim(-0.3, len(LAYERS) - 0.55)
    ax.set_ylim(0, 18)
    ax.set_ylabel("cumulative emissions saved vs. carbon-blind  [%]", fontsize=fs["label"])
    ax.set_xlabel("modelling and estimation complexity (layers added left to right)",
                  fontsize=fs["label"])
    ax.set_title("The complexity-value frontier: one jump (transfer), then flat",
                 fontsize=fs["title"])

    # The single takeaway: the one bold annotation, with a short arrow onto the jump.
    ax.annotate("active transfer:\nthe lever", xy=(1.62, 8.6), xytext=(0.18, 15.2),
                color=RUST, fontsize=fs["ann"], weight="bold", ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", color=RUST, lw=fs["lw"] * 0.6,
                                connectionstyle="arc3,rad=0.18", shrinkB=4))
    # Secondary note, regular weight, in the empty space under the flat tail.
    ax.text(3.55, 6.4, "+joint cov., +robust DRO, +copula\nadd $\\approx$ nothing (flat)",
            color=MUTED, fontsize=fs["ann"], ha="center", va="center")

    out = Path(outfile)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    if save_pdf:
        fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


# Thesis version (compact so fonts stay legible when embedded at ~0.75 textwidth).
render((7.4, 4.7),
       dict(lw=2.6, ms=7.5, mew=1.0, tick=12.5, label=13.5, title=14.5, ann=12.0, leg=12.0),
       "figures/complexity_frontier.png", save_pdf=True)

# Poster version (wider and short so it drops into a column slot; larger fonts).
render((12.0, 5.4),
       dict(lw=3.6, ms=11, mew=1.4, tick=15.5, label=16.5, title=18.5, ann=14.5, leg=15.5),
       "poster/figs/complexity_frontier.png", save_pdf=False)
