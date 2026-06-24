"""run_robust_transfer_value.py -- does the STOCHASTIC transfer earn its keep?

The deterministic transfer is established background (radovanovic2022/wiesner2021);
this script isolates the robust (DRO/CVaR) layer. The mean savings come from the
deterministic transfer; the honest question for
the stochastic layer is whether it buys better TAIL / RELIABILITY behaviour at a
small mean premium -- the thing a deterministic LP cannot target.

Robust vs deterministic day-ahead transfer, rolling over 2025 (seasonal forecast),
multi-seed for the robust scenario draw. We report, per grid:
  * mean        -- the premium (robust expected to be slightly higher = worse).
  * std         -- day-to-day variability (lower = more predictable).
  * VaR_0.95    -- the 95th-percentile day.
  * worst day   -- the single dirtiest realised day (max).
  * CVaR_0.95   -- mean of the worst 5% (already ~neutral in the fair-shot).
  * budget viol -- fraction of days over a cap B set at the deterministic 90th pct
                   (deterministic violates 10% by construction; does robust violate less?).
  * stress days -- mean carbon on the inherently dirtiest decile of days.

If robust beats deterministic on the tail/reliability metrics, that is Marco's
positive, uniquely-owned contribution. If not, the stochastic layer is a null.

Run: .venv\\Scripts\\python -m scripts.run_robust_transfer_value
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
FORECAST = "seasonal"


def blind_days(test_panel, ceiling, workloads, stride):
    R, T = test_panel.shape[1], test_panel.shape[2]
    y = np.minimum((workloads / T)[:, None] * np.ones((R, T)), ceiling)
    return np.array([float((test_panel[t] * y).sum())
                     for t in range(0, len(test_panel), stride)])


def metrics(costs, B, stress_mask):
    return dict(
        mean=costs.mean(), std=costs.std(), var95=np.percentile(costs, 95),
        worst=costs.max(), cvar=cvar_upper_tail(costs),
        viol=float((costs > B).mean()), stress=costs[stress_mask].mean(),
    )


def run_grid(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    kw = dict(ceiling=ceil, workloads=wl, transfer_budget=0.4 * wl.sum(),
              n_scenarios=S, stride=STRIDE, forecast_kind=FORECAST)
    blind = blind_days(te, ceil, wl, STRIDE)
    stress_mask = blind >= np.percentile(blind, 90)            # dirtiest decile of days

    det = rolling_eval(tr, te, robust=False, seed=0, **kw)
    B = float(np.percentile(det, 90))                          # carbon cap
    md = metrics(det, B, stress_mask)

    rob_metrics = []
    for sd in SEEDS:
        rob = rolling_eval(tr, te, robust=True, seed=sd, **kw)
        rob_metrics.append(metrics(rob, B, stress_mask))
    mr = {k: np.mean([m[k] for m in rob_metrics]) for k in md}
    return md, mr


def main():
    print(f"Stochastic vs deterministic transfer: tail & reliability "
          f"({FORECAST} forecast, 2025, mean of {len(SEEDS)} robust seeds)\n"
          f"(positive % = robust BETTER = stochastic layer earns its keep)\n")
    KEYS = [("mean", "mean (premium)"), ("std", "day-to-day std"),
            ("var95", "VaR_0.95 day"), ("worst", "worst single day"),
            ("cvar", "CVaR_0.95 tail"), ("viol", "over-budget freq"),
            ("stress", "dirtiest-decile mean")]
    for g in GRIDS:
        md, mr = run_grid(g)
        print(f"=== {DISPLAY_NAME.get(g, g)} ===")
        for k, label in KEYS:
            if k == "viol":
                print(f"  {label:<22}: det {md[k]*100:5.1f}%   robust {mr[k]*100:5.1f}%   "
                      f"({'robust better' if mr[k] < md[k] else 'robust worse/equal'})")
            else:
                imp = 100.0 * (md[k] - mr[k]) / md[k]
                print(f"  {label:<22}: {imp:+6.2f}%   ({'robust better' if imp > 0 else 'robust worse'})")
        print()


if __name__ == "__main__":
    main()
