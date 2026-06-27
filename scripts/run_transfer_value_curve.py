"""run_transfer_value_curve.py -- the value of the spatial transfer lever, on the
headline metric.

This sweeps the inter-region transfer budget Phi and reports, at each budget, the
out-of-sample CVaR_0.95 reduction of daily emissions RELATIVE TO THE Phi=0 baseline
(carbon-aware day-ahead scheduling with no inter-region transfer, on the same feasible
set). It uses the same one-shot deterministic transfer machinery (solve_transfer_dro,
epsilon=0) and the same CVaR evaluation as run_part3_transfer_value.py, so the curve's
saturation equals the reported headline (4.0--9.9%). By construction Phi=0 reads 0%
(it is the baseline); the curve traces how the tail reduction grows with transfer
capacity and where it saturates (the diminishing-returns "knee").

Outputs the CVaR-reduction-vs-budget curve (CSV) and figure.
Run: .venv\\Scripts\\python -m scripts.run_transfer_value_curve
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.plotstyle import GOLD, MUTED, NAVY, SAGE, apply_style
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.transfer_dro import solve_transfer_dro

CEIL, UTIL = 50.0, 0.80
GRIDS = ["us_west", "taskc", "us_hetero"]
# transfer budget as a fraction of total daily workload that may migrate across regions
PHI_FRACS = [0.0, 0.025, 0.05, 0.10, 0.20, 0.40, 0.80]


def run_grid(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    rho_bar = tr.mean(axis=0)
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    L = np.zeros((R * T, R * T))                       # deterministic (epsilon=0)
    total_wl = float(wl.sum())
    # Phi = 0 baseline: carbon-aware schedule, no inter-region transfer.
    y0, _ = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0, transfer_budget=0.0)
    c0 = cvar_upper_tail(per_day_emissions(np.asarray(y0), te))
    curve = []
    for frac in PHI_FRACS:
        yP, used = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0,
                                      transfer_budget=frac * total_wl)
        cP = cvar_upper_tail(per_day_emissions(np.asarray(yP), te))
        red = 100.0 * (c0 - cP) / c0
        curve.append((frac, red, float(used)))
    return curve


COLORS = {"us_west": NAVY, "taskc": GOLD, "us_hetero": SAGE}


def main():
    apply_style()
    print("Transfer-value curve: out-of-sample CVaR_0.95 reduction vs the Phi=0 "
          "carbon-aware baseline, by transfer budget (fraction of daily workload).\n")
    rows, curves = [], {}
    for g in GRIDS:
        curve = run_grid(g); curves[g] = curve
        print(f"=== {DISPLAY_NAME.get(g, g)} ===")
        for frac, red, used in curve:
            print(f"  budget {frac*100:5.1f}% of workload : CVaR -{red:5.2f}%  "
                  f"(transfer used {used:.0f})  {'#'*int(round(max(red,0)*4))}")
            rows.append(dict(grid=g, display=DISPLAY_NAME.get(g, g),
                             budget_frac=frac, cvar_reduction_pct=red, transfer_used=used))
        print(f"  -> saturates at {curve[-1][1]:.2f}% CVaR reduction over the Phi=0 "
              f"baseline\n")

    stamp = dt.datetime(2026, 6, 24).strftime("%Y-%m-%d")
    Path("docs/results_snapshots").mkdir(parents=True, exist_ok=True)
    csv = Path("docs/results_snapshots") / f"transfer_value_curve_{stamp}.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)

    # centerpiece figure: CVaR reduction over Phi=0 vs transfer budget
    Path("figures").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.6, 4.8), constrained_layout=True)

    # subtle "knee" marker: a faint vertical guide where the curves flatten.
    knee = 20.0
    ax.axvline(knee, color=MUTED, lw=1.0, ls=(0, (4, 4)), alpha=0.45, zorder=0)

    sat = {}  # saturation level per grid, for the right-edge direct labels
    for g in GRIDS:
        fr = [c[0] * 100 for c in curves[g]]
        sv = [c[1] for c in curves[g]]
        sat[g] = sv[-1]
        ax.plot(fr, sv, "-o", lw=2.6, ms=6.5, color=COLORS[g], zorder=3,
                solid_capstyle="round")
        ax.scatter([fr[0]], [sv[0]], s=80, facecolor="white",
                   edgecolor=COLORS[g], zorder=5, lw=2.2)

    # direct labels at the plateau, in genuinely empty space past the last point.
    xmax = max(c[0] * 100 for c in curves[GRIDS[0]])
    ax.set_xlim(-3, xmax + 24)
    ax.set_ylim(-0.6, max(sat.values()) + 1.4)
    # nudge near-coincident labels apart so no two overlap
    label_y = {"taskc": sat["taskc"] + 0.18, "us_hetero": sat["us_hetero"] - 0.30,
               "us_west": sat["us_west"]}
    for g in GRIDS:
        ax.annotate(f"{DISPLAY_NAME.get(g, g)}",
                    xy=(xmax, sat[g]), xytext=(xmax + 2.0, label_y[g]),
                    va="center", ha="left", fontsize=11.5, color=COLORS[g],
                    annotation_clip=False)
        ax.annotate(f"{sat[g]:.1f}%", xy=(xmax + 2.0, label_y[g] - 0.62),
                    va="center", ha="left", fontsize=10, color=COLORS[g],
                    annotation_clip=False)

    # baseline note: explain the open marker at the origin.
    ax.annotate(r"$\Phi=0$ baseline", xy=(0, 0), xytext=(3.5, -0.32),
                va="center", ha="left", fontsize=10, color=MUTED)

    # one bold takeaway, placed in the open lower band under the curves.
    ax.annotate("Gains saturate by a 20% budget:\ndiminishing returns beyond the knee",
                xy=(knee, 3.0), xytext=(34, 1.7), fontsize=11.5, fontweight="bold",
                color=NAVY, va="center", ha="left",
                arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.4,
                                connectionstyle="arc3,rad=-0.18"))

    ax.set_xlabel("transfer budget (% of daily workload that may migrate)",
                  fontsize=12.5)
    ax.set_ylabel(r"out-of-sample CVaR$_{0.95}$ reduction vs $\Phi=0$ [%]",
                  fontsize=12.5)
    ax.set_title("Spatial transfer cuts tail emissions, then saturates early",
                 fontsize=14, fontweight="bold", color=NAVY, pad=12)
    ax.tick_params(labelsize=11)
    ax.grid(True, axis="y", alpha=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    for ext in ("png", "pdf"):
        fig.savefig(f"figures/transfer_value_curve.{ext}", dpi=300)
    plt.close(fig)
    print(f"Wrote {csv} and figures/transfer_value_curve.png")


if __name__ == "__main__":
    main()
