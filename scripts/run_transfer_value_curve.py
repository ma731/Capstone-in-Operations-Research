"""run_transfer_value_curve.py -- the "interesting" OR result for the redirected thesis.

Carbon-aware compute migration saves emissions through two levers: shifting work in
TIME (within a region, to clean hours) and in SPACE (transferring work to a cleaner
region). This experiment characterises the value of the SPATIAL lever by sweeping the
transfer budget Phi, the cap on how much work may be moved across regions per day.

For each grid, rolling daily over 2025 with the deterministic day-ahead controller:
  * Phi = 0          -> temporal-only carbon-aware scheduling (no migration).
  * Phi increasing   -> migration allowed; realised savings vs a carbon-blind
                        baseline trace the marginal value of transfer capacity.

Outputs the savings-vs-budget curve (diminishing returns / the "knee") and the
temporal-vs-spatial decomposition: how much of the headline saving is when vs where.

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

from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.online_transfer import rolling_eval

CEIL, UTIL = 50.0, 0.80
STRIDE, FORECAST, SEED = 3, "seasonal", 20260615
GRIDS = ["us_west", "taskc", "us_hetero"]
# transfer budget as a fraction of total daily workload moved
PHI_FRACS = [0.0, 0.025, 0.05, 0.10, 0.20, 0.40, 0.80]


def blind_mean(test_panel, ceiling, workloads, stride):
    R, T = test_panel.shape[1], test_panel.shape[2]
    y = np.minimum((workloads / T)[:, None] * np.ones((R, T)), ceiling)
    days = range(0, len(test_panel), stride)
    return np.mean([float((test_panel[t] * y).sum()) for t in days])


def run_grid(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    total_wl = float(wl.sum())
    blind = blind_mean(te, ceil, wl, STRIDE)
    curve = []
    for frac in PHI_FRACS:
        det = rolling_eval(tr, te, robust=False, ceiling=ceil, workloads=wl,
                           transfer_budget=frac * total_wl, n_scenarios=1,
                           stride=STRIDE, seed=SEED, forecast_kind=FORECAST)
        save = 100.0 * (blind - det.mean()) / blind
        curve.append((frac, save))
    return curve


COLORS = {"us_west": "#0E2A52", "taskc": "#E69F00", "us_hetero": "#4A7C59"}


def main():
    print(f"Transfer-value curve ({FORECAST} forecast, 2025 rolling). "
          f"Savings vs carbon-blind, by transfer budget (fraction of daily workload).\n")
    rows, curves = [], {}
    for g in GRIDS:
        curve = run_grid(g); curves[g] = curve
        temporal, total = curve[0][1], curve[-1][1]
        print(f"=== {DISPLAY_NAME.get(g, g)} ===")
        for frac, save in curve:
            print(f"  budget {frac*100:5.1f}% of workload : {save:5.1f}%  {'#'*int(round(save*2))}")
            rows.append(dict(grid=g, display=DISPLAY_NAME.get(g, g),
                             budget_frac=frac, savings_pct=save))
        print(f"  -> temporal-only (no transfer): {temporal:.1f}%   |   "
              f"with full migration: {total:.1f}%   |   "
              f"spatial transfer adds: {total - temporal:.1f} pts\n")

    stamp = dt.datetime(2026, 6, 18).strftime("%Y-%m-%d")
    Path("docs/results_snapshots").mkdir(parents=True, exist_ok=True)
    csv = Path("docs/results_snapshots") / f"transfer_value_curve_{stamp}.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)

    # centerpiece figure: savings vs transfer budget
    Path("figures").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for g in GRIDS:
        fr = [c[0] * 100 for c in curves[g]]
        sv = [c[1] for c in curves[g]]
        ax.plot(fr, sv, "-o", lw=2.4, ms=6, color=COLORS[g], label=DISPLAY_NAME.get(g, g))
        ax.scatter([fr[0]], [sv[0]], s=70, facecolor="white",
                   edgecolor=COLORS[g], zorder=5, lw=2)
    ax.axvspan(0, 0.6, color="#f3f6fb", zorder=0)
    ax.text(0.3, ax.get_ylim()[1] * 0.06, "temporal\nonly", ha="center",
            fontsize=8.5, color="#5b6675")
    ax.set_xlabel("transfer budget (% of daily workload that may migrate)", fontsize=11)
    ax.set_ylabel("emissions saved vs carbon-blind [%]", fontsize=11)
    ax.set_title("Spatial migration is the dominant lever, and it saturates early",
                 fontsize=12, color="#0E2A52")
    ax.legend(frameon=False, fontsize=10, loc="lower right")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"figures/transfer_value_curve.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {csv} and figures/transfer_value_curve.png")


if __name__ == "__main__":
    main()
