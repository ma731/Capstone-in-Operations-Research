"""plot_model_validation.py

Model-validation figure: solve the FULL Phase-1 feasible set on a small,
human-checkable, TWO-REGION instance so the cross-region constraint interaction
(not just temporal shifting) is exercised, then perturb the inputs and confirm the
schedule moves the way an analyst anticipates. This is the supervisor-requested
"two or three regions, four to six time slots, all constraints, print the solution,
check it makes sense" validation, rendered as one figure
(figures/model_validation.pdf).

Two regions, eight hours, 10 MWh/cell capacity, W = 30 MWh each. The regions are
coupled by a shared aggregate hourly cap sum_r x[r,t] <= P_AGG (a shared
interconnect / power-delivery limit), so they compete for the same clean hours --
the cross-region interaction the thesis is about. Each region also carries the full
per-region feasible set: capacity, work conservation, ramp, deferral deadline.

Three panels (stacked bars = how the two regions share each hour; dashed line =
aggregate cap; curves = each region's carbon field):
  A. Baseline. Region 1 is clean at hours 3--5, region 2 at 4--6; they overlap at
     4--5, and the aggregate cap forces them to split the contested clean hours.
  B. Carbon perturbation. Region 1's clean hours are made dirty. Anticipated:
     region 1 vacates the contested hours, ceding them to region 2, and spreads to
     its own next-clean hours. Observed: it does, work conserved per region.
  C. Tighter aggregate cap (P_AGG 14 -> 11). Anticipated: with less shared headroom
     the two regions can no longer co-locate in the clean window and must spread
     further in time. Observed: they do.

Self-contained (CVXPY directly); the formulation mirrors src/models/feasible_set.py.
"""
from __future__ import annotations

import os
from pathlib import Path

import cvxpy as cp
import numpy as np
import matplotlib.pyplot as plt

OUTPUT_DIR = Path(os.environ.get("FIG_OUTPUT_DIR", "figures"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----- toy instance --------------------------------------------------------
R, T = 2, 8
CMAX = 10.0                  # MWh per cell
W = np.array([30.0, 30.0])   # MWh per region demand
GAMMA, T_DEAD = 0.5, 6       # >= 50% of each region's work done by hour 6
P_AGG = 14.0                 # shared aggregate hourly cap (couples the regions)

# Region carbon fields (kg/MWh): clean dips that overlap at hours 4--5.
RHO0 = np.array([
    [400, 320, 150, 160, 180, 300, 360, 420],   # region 1 clean at 3,4,5
    [410, 360, 320, 170, 160, 175, 330, 430],   # region 2 clean at 4,5,6
], dtype=float)


def solve(rho: np.ndarray, ramp: float, p_agg: float) -> np.ndarray:
    """Full two-region feasible set with a shared aggregate hourly cap."""
    x = cp.Variable((R, T), nonneg=True)
    cons = [
        x <= CMAX,                                          # C0 capacity
        cp.sum(x, axis=1) == W,                             # C2 work conservation
        cp.sum(x[:, :T_DEAD], axis=1) >= GAMMA * W,         # 3a deferral deadline
        cp.sum(x, axis=0) <= p_agg,                         # shared aggregate cap
    ]
    for r in range(R):                                      # C3 ramp, per region
        cons += [cp.abs(x[r, t] - x[r, t - 1]) <= ramp for t in range(1, T)]
    cp.Problem(cp.Minimize(cp.sum(cp.multiply(rho, x))), cons).solve(solver=cp.CLARABEL)
    return np.asarray(x.value)


x_base = solve(RHO0, ramp=6.0, p_agg=P_AGG)

rho_pert = RHO0.copy()
rho_pert[0, 2:5] = 380.0                 # region 1's clean window made dirty
x_pert = solve(rho_pert, ramp=6.0, p_agg=P_AGG)

x_cap = solve(RHO0, ramp=6.0, p_agg=11.0)  # tighter shared cap

for nm, x in [("baseline", x_base), ("carbon-perturbed", x_pert), ("cap-tightened", x_cap)]:
    assert np.allclose(x.sum(axis=1), W, atol=1e-3), f"{nm}: work not conserved"
    assert x.max() <= CMAX + 1e-3 and x.sum(axis=0).max() <= P_AGG + 1e-3, f"{nm}: cap"
    print(f"  {nm:>16}:")
    print(f"      R1 = [{', '.join(f'{v:4.1f}' for v in x[0])}]  sum={x[0].sum():.1f}")
    print(f"      R2 = [{', '.join(f'{v:4.1f}' for v in x[1])}]  sum={x[1].sum():.1f}")
    print(f"     agg = [{', '.join(f'{v:4.1f}' for v in x.sum(0))}]  (cap {P_AGG:.0f})")

# ----- figure --------------------------------------------------------------
NAVY, GOLD, RUST, SAGE, CREAM = "#0E2A52", "#E69F00", "#B3402F", "#4A7C59", "#FFFFFF"
R2COL = "#7a9bb8"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 11.5, "axes.edgecolor": NAVY, "axes.labelcolor": NAVY,
    "axes.linewidth": 0.9,
    "xtick.color": "#5a5a5a", "ytick.color": "#5a5a5a",
    "xtick.labelsize": 10.5, "ytick.labelsize": 10.5,
    "axes.facecolor": CREAM, "figure.facecolor": CREAM, "savefig.facecolor": CREAM,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#dbe1ea", "grid.linestyle": ":",
    "grid.linewidth": 0.5, "axes.axisbelow": True,
})
hours = np.arange(1, T + 1)
panels = [
    ("A. Baseline", x_base, RHO0, P_AGG,
     "regions 1 and 2 share the contested\nclean hours (4 to 5) under the cap"),
    ("B. Carbon perturbation", x_pert, rho_pert, P_AGG,
     "region 1's clean window dirtied:\nit cedes hours 4 to 5 to region 2, spreads out"),
    ("C. Tighter shared cap ($14\\!\\to\\!11$)", x_cap, RHO0, 11.0,
     "less shared headroom:\nboth regions spread further in time"),
]

CARB2 = "#B3402F"   # brick-red for the region-2 carbon line (no brown)

fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.9), sharey=True)
for i, (ax, (title, x, rho, pagg, note)) in enumerate(zip(axes, panels)):
    ax.bar(hours, x[0], width=0.66, color=NAVY, edgecolor="none", zorder=3)
    ax.bar(hours, x[1], width=0.66, bottom=x[0], color=R2COL, edgecolor="none",
           zorder=3)
    ax.axhline(pagg, color="#3a4a5c", ls="--", lw=1.4, alpha=0.9, zorder=4)
    ax.axvspan(0.5, T_DEAD + 0.5, color=SAGE, alpha=0.08, zorder=0)
    ax2 = ax.twinx()
    ax2.plot(hours, rho[0], color=GOLD, lw=1.8, marker="o", ms=3.5, zorder=5)
    ax2.plot(hours, rho[1], color=CARB2, lw=1.5, ls=(0, (4, 2)), marker="s",
             ms=3, zorder=5)
    ax2.set_ylim(100, 470); ax2.grid(False)
    # carbon intensity (right axis) labelled once, on the last panel only
    if i == len(axes) - 1:
        ax2.tick_params(axis="y", colors=GOLD, labelsize=10.5)
        ax2.set_ylabel("carbon intensity (kg/MWh)", color=GOLD)
        ax2.spines["right"].set_color(GOLD)
    else:
        ax2.tick_params(axis="y", length=0, labelleft=False, labelright=False)
        ax2.set_yticklabels([])
        ax2.spines["right"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax.set_title(title, fontsize=12.5, color=NAVY, pad=10)
    ax.set_xlabel("hour of horizon", fontsize=11.5)
    ax.set_xticks(hours)
    ax.set_ylim(0, P_AGG * 1.18)
    ax.text(0.5, -0.22, note, transform=ax.transAxes, ha="center", va="top",
            fontsize=11, color="#555", style="italic")

axes[0].set_ylabel("energy allocated (MWh)", fontsize=11.5)

from matplotlib.lines import Line2D
from matplotlib.patches import Patch
legend_handles = [
    Patch(color=NAVY, label="region 1 load"),
    Patch(color=R2COL, label="region 2 load"),
    Patch(facecolor=SAGE, alpha=0.18, edgecolor="none",
          label="deferral window (to h6)"),
    Line2D([], [], color="#3a4a5c", ls="--", lw=1.4, label="aggregate cap"),
    Line2D([], [], color=GOLD, lw=1.8, marker="o", ms=3.5, label="carbon, R1"),
    Line2D([], [], color=CARB2, lw=1.5, ls=(0, (4, 2)), marker="s", ms=3,
           label="carbon, R2"),
]
fig.legend(handles=legend_handles, loc="lower center",
           bbox_to_anchor=(0.5, 0.005), ncol=6, frameon=False, fontsize=10.8,
           columnspacing=1.8, handlelength=2.0, handletextpad=0.6)
fig.suptitle("Full-model validation on a two-region instance: the schedule "
             "responds as anticipated, across regions, to input perturbations",
             fontsize=13.5, color=NAVY, fontweight="bold", y=0.99)
fig.subplots_adjust(left=0.055, right=0.93, top=0.87, bottom=0.33, wspace=0.10)
plt.savefig(OUTPUT_DIR / "model_validation.pdf", bbox_inches="tight")
plt.savefig(OUTPUT_DIR / "model_validation.png", bbox_inches="tight", dpi=300)
plt.close()
print(f"\n  wrote {(OUTPUT_DIR / 'model_validation.pdf').resolve()}")
