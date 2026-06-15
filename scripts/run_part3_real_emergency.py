"""run_part3_real_emergency.py -- Part 3 rigor upgrade: data-grounded emergencies.

The crossover experiment used a synthetic Bernoulli severity multiplier M. Here the
emergency magnitude is taken from the data itself: an "emergency" replaces a region's
day with a draw from that region's empirical upper tail (its top-q% highest-carbon
days, i.e. real renewable-drought / peak-dispatch realizations), so the severity is
grounded, not chosen. The swept parameter is the emergency *frequency* p. We compare a
risk-neutral and a CVaR-hedged two-stage commitment, across seeds, and ask whether the
Western US crossover survives a real-data emergency definition.

Outputs docs/results_snapshots/part3_real_emergency_<date>.csv
Run: .venv\\Scripts\\python -m scripts.run_part3_real_emergency
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.transfer_dro import recourse_cost, two_stage_commit

CEIL, UTIL, LAM = 50.0, 0.80, 30.0
SEEDS = [11, 23, 37]
P_GRID = [0.0, 0.1, 0.2, 0.3]          # emergency frequency
TAIL_Q = 95                            # draw emergencies from each region's top 5%
S = 40
GRIDS = ["us_west", "taskc", "us_hetero"]
OUT = Path("docs/results_snapshots")


def tail_pools(panel):
    """For each region, the set of full daily profiles among its top (100-TAIL_Q)%
    highest-carbon days (real upper-tail realizations)."""
    R = panel.shape[1]
    pools = []
    for r in range(R):
        daily = panel[:, r, :].mean(axis=1)
        thr = np.percentile(daily, TAIL_Q)
        pools.append(panel[daily >= thr, r, :])
    return pools


def inject_real(panel, p, pools, rng):
    """Each day, w.p. p, replace one region's profile with a draw from its tail pool."""
    out = panel.copy()
    for i in range(len(out)):
        if rng.random() < p:
            r = rng.integers(out.shape[1])
            out[i, r, :] = pools[r][rng.integers(len(pools[r]))]
    return out


def main():
    rows = []
    for grid in GRIDS:
        cfg = REGION_SETS[grid]; z = list(cfg["zones"])
        panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
        yrs = np.array([d.year for d in dates])
        tr, te = panel[yrs < 2025], panel[yrs == 2025]
        R, T = panel.shape[1], panel.shape[2]
        wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL); Phi = 0.4 * wl.sum()
        pools_tr, pools_te = tail_pools(tr), tail_pools(te)
        for p in P_GRID:
            gains = []
            for sd in SEEDS:
                rng = np.random.default_rng(sd)
                scen = inject_real(tr, p, pools_tr, rng)[rng.choice(len(tr), S, replace=False)]
                ev = inject_real(te, p, pools_te, np.random.default_rng(sd + 1))[::4]
                xm = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=LAM, risk="mean")
                xc = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=LAM, risk="cvar")
                cm = cvar_upper_tail(np.array([recourse_cost(xm, d, ceil, transfer_budget=Phi, lam=LAM) for d in ev]))
                cc = cvar_upper_tail(np.array([recourse_cost(xc, d, ceil, transfer_budget=Phi, lam=LAM) for d in ev]))
                gains.append(100 * (cm - cc) / cm)
            g = np.array(gains)
            rows.append({"grid": grid, "p": p, "mean": g.mean(), "std": g.std(ddof=1),
                         "min": g.min(), "max": g.max(), "frac_positive": float((g > 0).mean())})
            print(f"  {DISPLAY_NAME.get(grid,grid):16s} p={p:.2f}: robust gain "
                  f"{g.mean():+6.2f} +/- {g.std(ddof=1):4.2f}%  [{g.min():+.2f},{g.max():+.2f}]  "
                  f"{int((g>0).mean()*100)}% seeds +")
    pd.DataFrame(rows).to_csv(OUT / f"part3_real_emergency_{dt.datetime(2026,6,15):%Y-%m-%d}.csv", index=False)
    print("\n  Emergencies are real upper-tail days; p is their frequency. A crossover")
    print("  surviving here is grounded in data, not a synthetic severity multiplier.")


if __name__ == "__main__":
    main()
