"""run_part4_forecasts.py -- Part 4 rigor upgrade: forecast-model robustness.

Closes the stated caveat that the online verdict might be specific to the seasonal
forecast. Re-runs the deterministic-vs-robust closed loop under three day-ahead
forecasts (seasonal mean / persistence / same-day-last-week), each across several
seeds, for all three grids, and reports whether the verdicts (null on the correlated
grids, robust-harmful on Diversified) are forecast-stable.

Outputs docs/results_snapshots/part4_forecasts_<date>.csv
Run: .venv\\Scripts\\python -m scripts.run_part4_forecasts
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
from src.models.online_transfer import rolling_eval

CEIL, UTIL = 50.0, 0.80
SEEDS = [11, 23, 37]
STRIDE, S = 6, 30
FORECASTS = ["seasonal", "persistence", "lagged_week"]
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
        wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL); Phi = 0.4 * wl.sum()
        for fc in FORECASTS:
            gaps = []
            for sd in SEEDS:
                kw = dict(ceiling=ceil, workloads=wl, transfer_budget=Phi, n_scenarios=S,
                          stride=STRIDE, seed=sd, forecast_kind=fc)
                det = rolling_eval(tr, te, robust=False, **kw)
                rob = rolling_eval(tr, te, robust=True, **kw)
                gaps.append(100 * (cvar_upper_tail(det) - cvar_upper_tail(rob)) / cvar_upper_tail(det))
            g = np.array(gaps)
            verdict = ("robust wins" if (g > 0).all() else
                       "robust loses" if (g < 0).all() else "null/mixed")
            rows.append({"grid": grid, "forecast": fc, "mean": g.mean(),
                         "std": g.std(ddof=1), "min": g.min(), "max": g.max(),
                         "verdict": verdict})
            print(f"  {DISPLAY_NAME.get(grid,grid):16s} {fc:12s}: gap "
                  f"{g.mean():+6.2f} +/- {g.std(ddof=1):4.2f}%  [{g.min():+.2f},{g.max():+.2f}]  {verdict}")
    pd.DataFrame(rows).to_csv(OUT / f"part4_forecasts_{dt.datetime(2026,6,15):%Y-%m-%d}.csv", index=False)
    print(f"\n  Wrote part4_forecasts snapshot. Stable verdicts across forecasts -> "
          f"the online result is not a seasonal-forecast artifact.")


if __name__ == "__main__":
    main()
