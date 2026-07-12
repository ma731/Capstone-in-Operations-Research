"""Poster figure: the emergency-severity crossover (poster variant).

Same data as scripts.plot_crossover, but the poster layout: a top-left legend,
the "robustness pays" band, and the honesty marker (real emergencies sit at
M near 1, where the robust gain is zero). Writes poster/figs/crossover.png.

Run: python -m scripts.plot_crossover_poster
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

NAVY, GOLD, SAGE = "#00338D", "#E8A33D", "#4A7C59"
MUTED, RUST, INK = "#586173", "#C0504D", "#16202E"
plt.rcParams.update({"font.family": "serif", "text.color": INK})

df = pd.read_csv("docs/results_snapshots/part3_emergency_2026-06-15.csv")
COL = {"us_west": NAVY, "taskc": GOLD, "us_hetero": SAGE}
NAME = {"us_west": "Western US", "taskc": "Eastern US-Canada", "us_hetero": "Diversified"}

fig, ax = plt.subplots(figsize=(8.0, 5.0), constrained_layout=True)
ax.set_xlim(0.92, 4.08)
ax.set_ylim(-2.6, 14.5)                       # lower floor -> red note clears the x-axis
ax.axvspan(3.0, 4.08, color="#e6efe6", zorder=0)
ax.text(3.52, 13.9, "robustness pays", ha="center", va="top",
        fontsize=16, weight="bold", color=SAGE)
for g in ("us_west", "taskc", "us_hetero"):
    d = df[df.grid == g].sort_values("M")
    ax.fill_between(d.M, d.ci_lo, d.ci_hi, color=COL[g], alpha=0.16, zorder=1)
    ax.plot(d.M, d.gain_pct, "-o", color=COL[g], lw=3.4, ms=8, zorder=3)
    sig = d[d.significant]
    if len(sig):
        ax.scatter([sig.M.iloc[0]], [sig.gain_pct.iloc[0]], s=150,
                   facecolor="white", edgecolor=COL[g], lw=2.4, zorder=4)
ax.axhline(0, color=MUTED, lw=1.2, zorder=2)
ax.set_xlabel("Emergency Severity M (Carbon-Spike Multiplier)", fontsize=17)
ax.set_ylabel("Robust Advantage  [% CVaR Cut]", fontsize=17)
ax.set_title("Robustness earns its keep only past a severity threshold",
             fontsize=20, weight="bold", color=NAVY)
ax.tick_params(labelsize=15)
leg = [Line2D([0], [0], color=COL[g], lw=3.4, marker="o", mec=COL[g], label=NAME[g])
       for g in ("us_west", "taskc", "us_hetero")]
ax.legend(handles=leg, loc="upper left", bbox_to_anchor=(0.02, 0.98), fontsize=15,
          frameon=True, framealpha=0.95, edgecolor="#d9dee6")
ax.scatter([1.0], [0.0], s=150, color=RUST, zorder=5, marker="X")
ax.annotate("real emergencies sit here\n(M near 1, gain is zero)",
            xy=(1.04, 0.12), xytext=(1.55, -1.05),     # lifted off the x-axis
            fontsize=15, color=RUST, weight="bold", ha="left", va="center",
            arrowprops=dict(arrowstyle="->", color=RUST, lw=1.8,
                            connectionstyle="arc3,rad=-0.15"))
fig.savefig("poster/figs/crossover.png", dpi=300, bbox_inches="tight")
print("wrote poster/figs/crossover.png  aspect",
      round(fig.get_size_inches()[0] / fig.get_size_inches()[1], 3))
