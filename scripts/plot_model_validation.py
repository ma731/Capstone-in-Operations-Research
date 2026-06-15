"""plot_model_validation.py

Model-validation figure: solve the FULL Phase-1 feasible set (capacity, work
conservation, ramp, deferral deadline -- all constraints active together) on a
small, human-checkable instance, then perturb the inputs and confirm the schedule
moves the way an analyst would anticipate. This is the supervisor-requested
"small instance, all constraints, print the solution, check it makes sense"
validation, rendered as one figure (figures/model_validation.pdf).

Three panels, region 1 (8 hours, capacity 10 MWh/cell, W = 35 MWh):
  A. Baseline. Load concentrates in the cheapest hours (3,4,5) subject to ramp
     and the deadline; work conserved (sum = 35).
  B. Carbon perturbation. Hours 3,4 are made dirty. Anticipated: the load leaves
     3,4 and migrates to the next-cleanest feasible hours. Observed: it does.
  C. Ramp tightening (Delta 6 -> 3). Anticipated: the schedule can no longer
     spike to capacity and must ramp gradually, smoothing into a plateau.
     Observed: it does.

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
T = 8
CMAX = 10.0                 # MWh per cell
W = 35.0                    # MWh region demand
GAMMA, T_DEAD = 0.5, 6      # >= 50% of work done by hour 6 (deferral deadline)

# Region-1 carbon field: clean dip at hours 3,4,5 (1-indexed), dirty at the edges.
RHO0 = np.array([400.0, 320.0, 150.0, 160.0, 180.0, 300.0, 360.0, 420.0])


def solve_region(rho: np.ndarray, ramp: float, cmax: float = CMAX,
                 w: float = W) -> np.ndarray:
    """Full single-region feasible set: capacity, work conservation, ramp,
    deferral deadline. Deterministic carbon objective. Returns the schedule."""
    x = cp.Variable(T, nonneg=True)
    cons = [
        x <= cmax,                                   # C0 capacity
        cp.sum(x) == w,                              # C2 work conservation
        cp.sum(x[:T_DEAD]) >= GAMMA * w,             # 3a deferral deadline
    ]
    cons += [cp.abs(x[t] - x[t - 1]) <= ramp for t in range(1, T)]   # C3 ramp
    prob = cp.Problem(cp.Minimize(rho @ x), cons)
    prob.solve(solver=cp.CLARABEL)
    return np.asarray(x.value)


# ----- three validation scenarios -----------------------------------------
x_base = solve_region(RHO0, ramp=6.0)

rho_pert = RHO0.copy()
rho_pert[2] = 380.0          # hour 3 now dirty
rho_pert[3] = 380.0          # hour 4 now dirty
x_pert = solve_region(rho_pert, ramp=6.0)

x_ramp = solve_region(RHO0, ramp=3.0)   # tighter ramp, same (clean) carbon field

for name, x in [("baseline", x_base), ("carbon-perturbed", x_pert),
                ("ramp-tightened", x_ramp)]:
    assert abs(x.sum() - W) < 1e-4, f"{name}: work not conserved"
    assert x.max() <= CMAX + 1e-4, f"{name}: capacity violated"
    print(f"  {name:>16}: x = [{', '.join(f'{v:4.1f}' for v in x)}]  "
          f"sum={x.sum():.1f}  by-deadline={x[:T_DEAD].sum():.1f}")

# ----- figure --------------------------------------------------------------
NAVY, GOLD, RUST, SAGE, CREAM = "#0c1e3e", "#b89535", "#8b3a0e", "#5d7a5a", "#faf7f0"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times", "DejaVu Serif"],
    "font.size": 10, "axes.edgecolor": NAVY, "axes.labelcolor": NAVY,
    "xtick.color": "#5a5a5a", "ytick.color": "#5a5a5a",
    "axes.facecolor": CREAM, "figure.facecolor": CREAM, "savefig.facecolor": CREAM,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#c9bfa6", "grid.linestyle": ":",
    "grid.linewidth": 0.5,
})
hours = np.arange(1, T + 1)

fig, axes = plt.subplots(1, 3, figsize=(13, 4.0), sharey=True)
panels = [
    ("A. Baseline", x_base, RHO0,
     "load fills the clean hours (3--5),\nramp and deadline satisfied"),
    ("B. Carbon perturbation", x_pert, rho_pert,
     "hours 3--4 made dirty:\nload migrates to the next-clean hours"),
    ("C. Ramp tightened ($\\Delta\\,6\\!\\to\\!3$)", x_ramp, RHO0,
     "schedule can no longer spike;\nit ramps gradually into a plateau"),
]

for ax, (title, x, rho, note) in zip(axes, panels):
    ax.bar(hours, x, color=NAVY, width=0.62, edgecolor="none", zorder=3,
           label="schedule $x^{\\star}$")
    ax.axhline(CMAX, color=RUST, ls="--", lw=1, alpha=0.7, zorder=2)
    ax.axvspan(0.5, T_DEAD + 0.5, color=SAGE, alpha=0.08, zorder=0)
    for h, v in zip(hours, x):
        if v > 0.05:
            ax.text(h, v + 0.3, f"{v:.0f}", ha="center", fontsize=8, color=NAVY)
    ax2 = ax.twinx()
    ax2.plot(hours, rho, color=GOLD, lw=1.8, marker="o", ms=3.5, zorder=4,
             label="carbon $\\rho$")
    ax2.set_ylim(100, 460)
    ax2.grid(False)
    ax2.tick_params(axis="y", colors=GOLD)
    if ax is axes[-1]:
        ax2.set_ylabel("carbon intensity (kg/MWh)", color=GOLD)
    ax.set_title(title, fontsize=11, color=NAVY, pad=8)
    ax.set_xlabel("hour of horizon")
    ax.set_xticks(hours)
    ax.set_ylim(0, CMAX * 1.28)
    ax.text(0.5, -0.34, note, transform=ax.transAxes, ha="center", va="top",
            fontsize=8.5, color="#444", style="italic")

axes[0].set_ylabel("energy allocated (MWh)")
axes[0].axhline(CMAX, color=RUST, ls="--", lw=1, alpha=0.7,
                label=f"capacity ({CMAX:.0f})")
axes[0].legend(loc="upper right", frameon=False, fontsize=8)
fig.suptitle("Full-model validation on a small instance: the schedule responds "
             "as anticipated to input perturbations",
             fontsize=12.5, color=NAVY, y=1.04)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "model_validation.pdf", bbox_inches="tight")
plt.savefig(OUTPUT_DIR / "model_validation.png", bbox_inches="tight", dpi=150)
plt.close()
print(f"\n  wrote {(OUTPUT_DIR / 'model_validation.pdf').resolve()}")
