"""Poster custom figures: the lever bar and the transfer schematic.

Headline carbon savings are reported as a CVaR (tail) reduction, so the labels
say "tail carbon", not "worst-case carbon". Writes into poster/figs/.

Run: python -m scripts.plot_poster_figs
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

NAVY, GOLD, GOLDD, SAGE = "#00338D", "#E8A33D", "#8A5C16", "#4A7C59"
INK, MUTED, LINE, RUST, GREEN = "#16202E", "#4A5568", "#C9D2E0", "#C0504D", "#4A7C59"
plt.rcParams.update({"font.family": "serif", "text.color": INK})
O = "poster/figs/"

# 1) LEVER BAR
fig, ax = plt.subplots(figsize=(7.2, 5.0))
g = ["Western\nUS", "Eastern\nUS-Canada", "Diversified"]
v = [4.0, 9.9, 9.0]
c = [NAVY, GOLD, SAGE]
ax.bar(range(3), v, width=0.62, color=c, edgecolor="white", linewidth=1.6, zorder=3)
for i, val in enumerate(v):
    ax.text(i, val + 0.22, f"{val:.1f}%", ha="center", va="bottom",
            fontsize=26, weight="bold", color=c[i])
ax.set_xticks(range(3))
ax.set_xticklabels(g, fontsize=17)
ax.set_ylim(0, 11.6)
ax.set_ylabel("Tail Carbon Cut\nvs No Transfer  [%]", fontsize=17)
ax.set_title("Active transfer pays on every grid", fontsize=20, weight="bold",
             color=NAVY, pad=12)
for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
ax.spines["left"].set_color("#33414f")
ax.spines["bottom"].set_color("#33414f")
ax.tick_params(axis="y", labelsize=15, colors=MUTED)
ax.tick_params(axis="x", length=0, labelsize=17)
ax.grid(axis="y", color=LINE, alpha=0.6, zorder=0)
fig.tight_layout()
fig.savefig(O + "lever_bar.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# 2) TRANSFER SCHEMATIC
fig, ax = plt.subplots(figsize=(8.0, 3.0))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")
ax.text(0.5, 0.93, "move the work", ha="center", va="center", fontsize=19,
        weight="bold", color=GOLDD)
for x, col, name, sub in [(0.20, RUST, "GRID A", "dirty now"),
                          (0.80, GREEN, "GRID B", "clean now")]:
    ax.scatter([x], [0.60], s=5200, c=col, edgecolors="white", linewidths=2.8, zorder=3)
    ax.text(x, 0.60, name, ha="center", va="center", fontsize=17, weight="bold",
            color="white", zorder=4)
    ax.text(x, 0.31, sub, ha="center", va="center", fontsize=15, style="italic", color=INK)
ax.add_patch(FancyArrowPatch((0.34, 0.60), (0.66, 0.60), arrowstyle="-|>",
             mutation_scale=40, lw=11, color=GOLD, alpha=0.92, zorder=2,
             shrinkA=4, shrinkB=4))
ax.text(0.5, 0.07, "cuts 4 to 10% of tail carbon, every single day", ha="center",
        va="center", fontsize=17, weight="bold", color=NAVY)
fig.savefig(O + "schematic_transfer_v3.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# 3) SEVERITY NUMBER LINE
fig, ax = plt.subplots(figsize=(7.8, 3.8))
ax.set_xlim(0.9, 4.15)
ax.set_ylim(0, 1)
ax.axis("off")
ax.axvspan(3.0, 4.15, color="#e6efe6", zorder=0)
ax.annotate("", xy=(4.12, 0.42), xytext=(0.92, 0.42),
            arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=2.6))
for m in [1, 1.5, 2, 2.5, 3, 3.5, 4]:
    ax.plot([m, m], [0.40, 0.46], color=MUTED, lw=1.8)
    ax.text(m, 0.29, f"{m:g}", ha="center", fontsize=15, color=MUTED)
ax.text(4.07, 0.23, "Severity M", ha="center", fontsize=15, style="italic", color=INK)
rng = np.random.default_rng(3)
xr = rng.uniform(1.0, 1.4, 17)
yr = rng.uniform(0.50, 0.66, 17)
ax.scatter(xr, yr, s=190, color=NAVY, edgecolor="white", linewidth=1.6, zorder=4, alpha=0.92)
ax.annotate("17 real grids\n(worst was 1.4x)", xy=(1.23, 0.64), xytext=(0.97, 0.97),
            fontsize=16, weight="bold", color=NAVY, ha="left", va="top",
            arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.8))
ax.plot([3, 3], [0.40, 0.80], color=SAGE, lw=4.5, ls=(0, (5, 3)))
ax.text(3.07, 0.90, "M* = 3\nrobustness starts to pay", ha="left", va="top",
        fontsize=16, weight="bold", color=SAGE)
ax.text(0.95, 0.08, "none of them ever reach the point where robustness helps",
        ha="left", va="center", fontsize=15.5, weight="bold", color=RUST)
ax.set_title("Real grids never reach the danger zone", fontsize=20, weight="bold",
             color=NAVY, y=1.03)
fig.savefig(O + "severity_line.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# 4) LAYER-GAIN BAR
fig, ax = plt.subplots(figsize=(7.4, 5.0))
lay = ["+ temporal\nshifting", "+ active\ntransfer", "+ joint\ncovariance",
       "+ robust\nDRO", "+ richer\ncopula"]
gn = [3.3, 10.1, 0.0, 0.0, 0.1]
cb = [MUTED, GOLD, LINE, LINE, LINE]
y = np.arange(len(lay))[::-1]
ax.barh(y, gn, height=0.62, color=cb, edgecolor="white", linewidth=1.5, zorder=3)
for yi, gg in zip(y, gn):
    ax.text(gg + 0.25, yi, ("~0" if gg < 0.4 else f"+{gg:.1f}%"), va="center",
            ha="left", fontsize=17, weight="bold", color=(MUTED if gg < 0.4 else GOLDD))
ax.set_yticks(y)
ax.set_yticklabels(lay, fontsize=15.5)
ax.set_xlim(0, 12.5)
ax.set_xlabel("Extra Carbon Saved by This Layer  [%]", fontsize=17)
ax.set_title("Only moving the work adds value", fontsize=20, weight="bold", color=NAVY, pad=12)
for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
ax.spines["left"].set_color("#33414f")
ax.spines["bottom"].set_color("#33414f")
ax.tick_params(labelsize=15, colors=MUTED)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color=LINE, alpha=0.6, zorder=0)
fig.tight_layout()
fig.savefig(O + "layer_gain_bar.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("wrote lever_bar, schematic_transfer_v3, severity_line, layer_gain_bar")
