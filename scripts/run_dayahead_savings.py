"""run_dayahead_savings.py -- the "useful result" headline for the redirected thesis.

Quantifies what the day-ahead, carbon-aware scheduler actually SAVES, rolling daily
across the 2025 test year, against a carbon-blind baseline. Three controllers, same
feasible set, same realised carbon, paired on the same test days:

  * blind        : carbon-agnostic. Each region serves its own workload spread
                   uniformly across the day, no inter-region transfer. (What you do
                   if you ignore carbon entirely.)
  * carbon-aware : day-ahead forecast -> minimise <forecast, y> with transfer
                   (deterministic, point-forecast controller).
  * robust       : same, but the commit hedges forecast error (CVaR over residual
                   scenarios) -- the Wasserstein/CVaR DRO over the day-ahead error.

Reports, per grid: realised mean carbon for each; the carbon-aware saving vs blind
(the headline), and the robust saving vs carbon-aware on both mean and CVaR_0.95
(does robustness pay under real forecast error?).

Run: .venv\\Scripts\\python -m scripts.run_dayahead_savings
"""
from __future__ import annotations

import numpy as np

from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.online_transfer import rolling_eval

CEIL, UTIL = 50.0, 0.80
STRIDE, S, SEED = 3, 40, 20260615
GRIDS = ["us_west", "taskc", "us_hetero"]
FORECAST = "seasonal"


def blind_uniform(test_panel, ceiling, workloads, stride):
    """Carbon-agnostic: serve each region's workload uniformly over the day, no
    transfer. Realised carbon on the same strided test days as rolling_eval."""
    R, T = test_panel.shape[1], test_panel.shape[2]
    y = np.minimum((workloads / T)[:, None] * np.ones((R, T)), ceiling)
    days = range(0, len(test_panel), stride)
    return np.array([float((test_panel[t] * y).sum()) for t in days])


def run_grid(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    Phi = 0.4 * wl.sum()
    kw = dict(ceiling=ceil, workloads=wl, transfer_budget=Phi, n_scenarios=S,
              stride=STRIDE, seed=SEED, forecast_kind=FORECAST)
    blind = blind_uniform(te, ceil, wl, STRIDE)
    det = rolling_eval(tr, te, robust=False, **kw)
    rob = rolling_eval(tr, te, robust=True, **kw)
    save_aware = 100.0 * (blind.mean() - det.mean()) / blind.mean()
    save_rob_mean = 100.0 * (det.mean() - rob.mean()) / det.mean()
    save_rob_cvar = 100.0 * (cvar_upper_tail(det) - cvar_upper_tail(rob)) / cvar_upper_tail(det)
    return dict(grid=grid, n=len(det), blind=blind.mean(), det=det.mean(), rob=rob.mean(),
                save_aware=save_aware, save_rob_mean=save_rob_mean,
                det_cvar=cvar_upper_tail(det), rob_cvar=cvar_upper_tail(rob),
                save_rob_cvar=save_rob_cvar)


def main():
    print(f"Day-ahead carbon-aware scheduling savings ({FORECAST} forecast, 2025 test year)\n")
    for g in GRIDS:
        r = run_grid(g)
        print(f"=== {DISPLAY_NAME.get(g, g)} ===  ({r['n']} test days)")
        print(f"  realised mean carbon:  blind {r['blind']:.0f}   carbon-aware {r['det']:.0f}   robust {r['rob']:.0f}")
        print(f"  HEADLINE  carbon-aware vs blind : {r['save_aware']:.1f}% lower emissions")
        print(f"  robust vs carbon-aware (mean)   : {r['save_rob_mean']:+.2f}%")
        print(f"  robust vs carbon-aware (CVaR95) : {r['save_rob_cvar']:+.2f}%   "
              f"(det {r['det_cvar']:.0f} -> robust {r['rob_cvar']:.0f})\n")


if __name__ == "__main__":
    main()
