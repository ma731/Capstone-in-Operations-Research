"""plot_certificate_canyon.py -- theorem bound vs realized gap (poster figure, 2D).

Replaces the old 3D bar chart with a clean 2D grouped bar on a log axis. Per grid:
the a-priori Proposition-1 bound on the spatial gap (right-hand side, % of
CVaR_0.95) vs the realized gap. The measured gap sits more than an order of
magnitude below the bound on every grid. Writes poster/figs/certificate_canyon.png
(the poster reads its figures from poster/figs/).

Run: .venv\\Scripts\\python -m scripts.plot_certificate_canyon
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from src.analysis.plotstyle import apply_style, NAVY, GOLD

apply_style()

GRIDS = ["Western US", "Eastern\nUS-Canada", "Diversified"]
BOUND = [12.7, 7.4, 9.6]        # Proposition-1 a-priori bound, % of CVaR_0.95
REALIZED = [0.04, 0.02, 0.23]   # realized spatial gap, % of CVaR_0.95

fig, ax = plt.subplots(figsize=(6.5, 4.0))
x = np.arange(len(GRIDS))
w = 0.38

b1 = ax.bar(x - w / 2, BOUND, w, color=NAVY, zorder=3, label="theorem bound (a-priori)")
b2 = ax.bar(x + w / 2, REALIZED, w, color=GOLD, zorder=3, label="realized gap (measured)")

ax.set_yscale("log")
ax.set_ylim(0.01, 40)
ax.set_ylabel("spatial gap, % of $\\mathrm{CVaR}_{0.95}$ (log)")
ax.set_xticks(x)
ax.set_xticklabels(GRIDS)
ax.set_title("The theorem bounds the gap: the data beats it\nby over an order of magnitude",
             fontsize=13)

for rect, v in zip(b1, BOUND):
    ax.text(rect.get_x() + rect.get_width() / 2, v * 1.15, f"{v:.1f}%",
            ha="center", va="bottom", color=NAVY, fontsize=9.5, weight="bold")
for rect, v in zip(b2, REALIZED):
    ax.text(rect.get_x() + rect.get_width() / 2, v * 1.15, f"{v:.2f}%",
            ha="center", va="bottom", color=GOLD, fontsize=9.5, weight="bold")

ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=10)
ax.grid(True, axis="y", which="both", alpha=0.3)
fig.tight_layout()

out = Path("poster/figs/certificate_canyon.png")
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"wrote {out}")
