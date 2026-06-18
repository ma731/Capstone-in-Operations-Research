"""run_dro_fairshot.py -- does the day-ahead DRO earn its keep under realistic error?

The seasonal forecast is hour-of-day climatology: unusually accurate for carbon, so
hedging its error buys little. This gives the DRO its fairest shot: realistic,
noisier day-ahead forecasts (persistence = yesterday; lagged_week = same weekday last
week) with real, fat-tailed errors, judged where insurance pays -- the TAIL
(CVaR_0.95 of realised daily carbon) -- and MULTI-SEED so a single lucky/unlucky
scenario draw can't decide it.

Verdict per (grid, forecast): the robust controller "earns its keep" only if it
lowers the realised worst-day carbon (positive CVaR gap) consistently across seeds.

Run: .venv\\Scripts\\python -m scripts.run_dro_fairshot
"""
from __future__ import annotations

import numpy as np

from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.online_transfer import rolling_eval

CEIL, UTIL = 50.0, 0.80
STRIDE, S = 3, 40
SEEDS = list(range(5))
GRIDS = ["us_west", "taskc", "us_hetero"]
FORECASTS = ["seasonal", "persistence", "lagged_week"]


def run_grid(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    Phi = 0.4 * wl.sum()
    base = dict(ceiling=ceil, workloads=wl, transfer_budget=Phi, n_scenarios=S, stride=STRIDE)
    rows = []
    for fk in FORECASTS:
        det = rolling_eval(tr, te, robust=False, forecast_kind=fk, seed=0, **base)
        det_cvar = cvar_upper_tail(det)
        gaps = []
        for sd in SEEDS:
            rob = rolling_eval(tr, te, robust=True, forecast_kind=fk, seed=sd, **base)
            gaps.append(100.0 * (det_cvar - cvar_upper_tail(rob)) / det_cvar)
        gaps = np.array(gaps)
        rows.append((fk, gaps.mean(), gaps.min(), gaps.max(),
                     "EARNS IT" if (gaps > 0).all() else
                     "loses" if (gaps < 0).all() else "inconsistent (sign flips)"))
    return rows


def main():
    print("DRO fair-shot: robust vs deterministic, CVaR_0.95 tail, multi-seed\n"
          "(positive % = robust lowers worst-day carbon = robustness pays)\n")
    for g in GRIDS:
        print(f"=== {DISPLAY_NAME.get(g, g)} ===")
        for fk, mean, lo, hi, verdict in run_grid(g):
            print(f"  {fk:<12} CVaR gap: mean {mean:+.2f}%  [seed range {lo:+.2f}, {hi:+.2f}]  -> {verdict}")
        print()


if __name__ == "__main__":
    main()
