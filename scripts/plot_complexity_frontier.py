"""plot_complexity_frontier.py -- the 3D complexity-value frontier (centerpiece).

Cumulative emissions saved as each modeling layer is added, across the three grids.
The shape is the whole thesis in one image: a single jump (active transfer), then a
flat plateau -- joint covariance, the robust DRO, and copulas each add ~nothing.
Simple is near-optimal; the sophisticated layers do not pay (until the severity
crossover, which is the companion figure).

Run: .venv\\Scripts\\python -m scripts.plot_complexity_frontier
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

from src.analysis.plotstyle import apply_style, NAVY, GOLD, SAGE, MUTED, RUST, save

apply_style()

# cumulative % emissions saved (from carbon-blind origin), per grid, per layer.
# transfer is the one jump; joint-cov / robust / copula are flat (the null), with
# robust dipping slightly where it fits noise (us_hetero).
LAYERS = ["carbon\nblind", "+temporal", "+transfer", "+joint\ncov.", "+robust\nDRO", "+copula"]
GRIDS = [
    ("Western US", NAVY, [0.0, 3.9, 11.7, 11.7, 11.6, 11.7]),
    ("Eastern US-Canada", GOLD, [0.0, 1.2, 12.5, 12.5, 12.5, 12.5]),
    ("Diversified", SAGE, [0.0, 4.7, 15.8, 15.8, 15.0, 15.8]),
]

fig = plt.figure(figsize=(9.2, 6.2))
ax = fig.add_subplot(111, projection="3d")
nx = len(LAYERS)

for gi, (name, color, vals) in enumerate(GRIDS):
    xs = np.arange(nx)
    ys = np.full(nx, gi)
    zs = np.array(vals)
    # filled "ribbon" under the frontier for depth
    verts = [(x, gi, 0) for x in xs] + [(x, gi, z) for x, z in zip(xs[::-1], zs[::-1])]
    ax.plot(xs, ys, zs, "-o", color=color, lw=3, ms=7, zorder=5, label=name)
    # the transfer "cliff" highlighted
    ax.plot([1, 2], [gi, gi], [vals[1], vals[2]], color=color, lw=6, alpha=0.45, zorder=4)

# plateau guide
for gi, (_, color, vals) in enumerate(GRIDS):
    ax.plot([2, nx - 1], [gi, gi], [vals[2], vals[-1]], color=MUTED, lw=1, ls=":", zorder=3)

ax.set_xticks(range(nx)); ax.set_xticklabels(LAYERS, fontsize=9)
ax.set_yticks(range(len(GRIDS))); ax.set_yticklabels([g[0] for g in GRIDS], fontsize=9)
ax.set_zlabel("cumulative emissions saved [%]", fontsize=10.5, labelpad=6)
ax.set_zlim(0, 18)
ax.set_title("The complexity-value frontier: one jump (transfer), then flat",
             color=NAVY, pad=16)

# annotations: the jump and the plateau
ax.text(2.0, 2.35, 16.6, "active transfer\n= the lever", color=RUST, fontsize=10,
        ha="center", weight="bold")
ax.text(4.0, 0.0, 14.6, "joint cov / DRO / copula\nadd ~nothing", color=MUTED,
        fontsize=9.5, ha="center")

ax.view_init(elev=22, azim=-58)
ax.grid(True)
try:
    ax.set_box_aspect((1.6, 1.0, 0.8))
except Exception:
    pass
fig.tight_layout()
save(fig, "complexity_frontier")
print("wrote figures/complexity_frontier.png/.pdf")
