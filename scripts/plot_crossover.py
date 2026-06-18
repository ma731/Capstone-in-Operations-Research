"""plot_crossover.py -- the money-shot figure for the redirected thesis.

The tail-severity crossover: robustness is worthless under normal carbon and earns
its keep only past an emergency-severity threshold M*. Synthetic severity sweep with
bootstrap CI bands; the honest bound (data-grounded emergencies stay below M*) is
annotated on the figure so the decision-rule reading is unmistakable.

Run: .venv\\Scripts\\python -m scripts.plot_crossover
"""
from __future__ import annotations

import pandas as pd
import matplotlib.pyplot as plt

from src.analysis.plotstyle import apply_style, NAVY, GOLD, SAGE, MUTED, RUST, save

apply_style()

df = pd.read_csv("docs/results_snapshots/part3_emergency_2026-06-15.csv")
COL = {"us_west": NAVY, "taskc": GOLD, "us_hetero": SAGE}
NAME = {"us_west": "Western US", "taskc": "Eastern US–Canada", "us_hetero": "Diversified"}

fig, ax = plt.subplots(figsize=(7.6, 4.8))

# "robustness pays" region (past the sharp crossover ~M=3)
ax.axvspan(3.0, 4.05, color="#eef4ef", zorder=0)
ax.text(3.5, ax.get_ylim()[1] if False else 7.6, "robustness\npays", ha="center",
        va="top", fontsize=10, color=SAGE, weight="bold")

for g in ("us_west", "taskc", "us_hetero"):
    d = df[df.grid == g]
    ax.fill_between(d.M, d.ci_lo, d.ci_hi, color=COL[g], alpha=0.13, zorder=1)
    ax.plot(d.M, d.gain_pct, "-o", color=COL[g], label=NAME[g], zorder=3)
    sig = d[d.significant]
    if len(sig):
        m = sig.M.iloc[0]
        ax.scatter([m], [sig.gain_pct.iloc[0]], s=130, facecolor="white",
                   edgecolor=COL[g], lw=2.2, zorder=4)

ax.axhline(0, color=MUTED, lw=1.1)
ax.set_xlabel("emergency severity $M$ (carbon-spike multiplier)")
ax.set_ylabel("robust advantage  [% CVaR$_{0.95}$ reduction]")
ax.set_title("Distributional robustness earns its keep only past a severity threshold")
ax.set_xlim(0.9, 4.1)
ax.legend(loc="upper left", title="grid")

# the honesty bound: real emergencies sit in the no-value zone
ax.annotate(
    "Real (data-grounded) emergencies\nstay here: robust gain $\\leq$ 0",
    xy=(1.05, -0.15), xytext=(1.5, -2.6), fontsize=10, color=RUST,
    ha="left", va="top",
    arrowprops=dict(arrowstyle="->", color=RUST, lw=1.3))
ax.scatter([1.0], [0.0], s=80, color=RUST, zorder=5, marker="X")

fig.tight_layout()
save(fig, "crossover")
print("wrote figures/crossover.png/.pdf")
