"""run_part3_transfer_value.py -- Part 3, Finding 1: the value of active transfer.

Backs the headline "active transfer cuts out-of-sample CVaR_0.95 by 4.7-10.1%" with a
committed snapshot. For each grid we plan a deterministic schedule on the training-mean
carbon field with the transfer budget OFF (per-region marginal schedule) vs ON (free
inter-region flows), evaluate both on the 2025 test year, and report the reduction in
out-of-sample CVaR_0.95.

Outputs docs/results_snapshots/part3_transfer_value_<date>.csv
Run: .venv\\Scripts\\python -m scripts.run_part3_transfer_value
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.transfer_dro import solve_transfer_dro

CEIL, UTIL = 50.0, 0.80
GRIDS = ["us_west", "taskc", "us_hetero"]
OUT = Path("docs/results_snapshots")


def main():
    rows = []
    for grid in GRIDS:
        cfg = REGION_SETS[grid]; z = list(cfg["zones"])
        panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
        yrs = np.array([d.year for d in dates])
        tr, te = panel[yrs < 2025], panel[yrs == 2025]
        R, T = panel.shape[1], panel.shape[2]
        rho_bar = tr.mean(axis=0)
        wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
        L = np.zeros((R * T, R * T))                       # deterministic (epsilon=0)
        y0, _ = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0, transfer_budget=0.0)
        yT, used = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0,
                                      transfer_budget=2.0 * wl.sum())
        c0 = cvar_upper_tail(per_day_emissions(np.asarray(y0), te))
        cT = cvar_upper_tail(per_day_emissions(np.asarray(yT), te))
        red = 100.0 * (c0 - cT) / c0
        rows.append({"grid": grid, "cvar_no_transfer": c0, "cvar_transfer": cT,
                     "reduction_pct": red, "transfer_used": used})
        print(f"  {DISPLAY_NAME.get(grid, grid):16s}: CVaR {c0:.0f} -> {cT:.0f}  "
              f"reduction {red:.2f}%")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"part3_transfer_value_{dt.datetime(2026,6,15):%Y-%m-%d}.csv", index=False)
    print(f"\n  active-transfer CVaR reduction range: "
          f"{df.reduction_pct.min():.1f}--{df.reduction_pct.max():.1f}%")
    print(f"  Wrote {OUT}/part3_transfer_value_2026-06-15.csv")


if __name__ == "__main__":
    main()
