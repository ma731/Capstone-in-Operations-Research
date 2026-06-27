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
NAME = {"us_west": "Western US", "taskc": "Eastern US, Canada", "us_hetero": "Diversified"}
# nudge the right-edge direct labels so they never collide vertically
LABEL_DY = {"us_west": 0.0, "taskc": -0.35, "us_hetero": 0.35}

fig, ax = plt.subplots(figsize=(8.0, 5.0), constrained_layout=True)

XMAX_DATA = 4.0
ax.set_xlim(0.92, 5.05)
ax.set_ylim(-1.7, 14.2)

# "robustness pays" region (past the sharp crossover near M = 3)
ax.axvspan(3.0, XMAX_DATA, color="#eef4ef", zorder=0)
ax.text(3.5, 13.7, "robustness pays", ha="center", va="top",
        fontsize=11.5, color=SAGE)

for g in ("us_west", "taskc", "us_hetero"):
    d = df[df.grid == g].sort_values("M")
    ax.fill_between(d.M, d.ci_lo, d.ci_hi, color=COL[g], alpha=0.12, zorder=1)
    ax.plot(d.M, d.gain_pct, "-o", color=COL[g], zorder=3)
    sig = d[d.significant]
    if len(sig):
        m = sig.M.iloc[0]
        ax.scatter([m], [sig.gain_pct.iloc[0]], s=130, facecolor="white",
                   edgecolor=COL[g], lw=2.2, zorder=4)
    # direct label at the right endpoint, in the clear white margin
    last = d.iloc[-1]
    ax.annotate(NAME[g], xy=(last.M, last.gain_pct),
                xytext=(XMAX_DATA + 0.12, last.gain_pct + LABEL_DY[g]),
                va="center", ha="left", fontsize=11.5, color=COL[g])

ax.axhline(0, color=MUTED, lw=1.1, zorder=2)
ax.set_xlabel("emergency severity $M$ (carbon-spike multiplier)")
ax.set_ylabel(r"robust advantage  [% CVaR$_{0.95}$ reduction]")
ax.set_title("Distributional robustness earns its keep only past a severity threshold")
ax.tick_params(labelsize=11.5)

# explain the open ring markers, in clear empty space (regular weight, muted)
ax.text(1.45, 6.4,
        "open marker: first statistically\nsignificant gain (95% CI clears 0)",
        ha="left", va="top", fontsize=10.2, color=MUTED)

# the honesty bound: the single bold takeaway. Real emergencies sit at M near 1,
# where the robust gain is statistically zero.
ax.annotate(
    "Real, data-grounded emergencies\nsit here: robust gain $\\leq 0$",
    xy=(1.02, 0.45), xytext=(1.45, 11.6), fontsize=11.5, color=RUST,
    weight="bold", ha="left", va="top",
    arrowprops=dict(arrowstyle="->", color=RUST, lw=1.4,
                    connectionstyle="arc3,rad=-0.12"))
ax.scatter([1.0], [0.0], s=90, color=RUST, zorder=5, marker="X")

save(fig, "crossover")
print("wrote figures/crossover.png/.pdf")
