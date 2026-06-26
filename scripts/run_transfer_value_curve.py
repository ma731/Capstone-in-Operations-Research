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
from src.analysis.plotstyle import GOLD, NAVY, SAGE, apply_style
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
    fig, ax = plt.subplots(figsize=(7.2, 4.6), constrained_layout=True)
    for g in GRIDS:
        fr = [c[0] * 100 for c in curves[g]]
        sv = [c[1] for c in curves[g]]
        ax.plot(fr, sv, "-o", lw=2.4, ms=6, color=COLORS[g], label=DISPLAY_NAME.get(g, g))
        ax.scatter([fr[0]], [sv[0]], s=70, facecolor="white",
                   edgecolor=COLORS[g], zorder=5, lw=2)
    ax.set_xlabel("transfer budget (% of daily workload that may migrate)")
    ax.set_ylabel(r"out-of-sample CVaR$_{0.95}$ reduction vs $\Phi=0$ [%]")
    ax.set_title(r"Active transfer cuts tail emissions over the $\Phi=0$ baseline, "
                 "and saturates early")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    for ext in ("png", "pdf"):
        fig.savefig(f"figures/transfer_value_curve.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {csv} and figures/transfer_value_curve.png")


if __name__ == "__main__":
    main()
