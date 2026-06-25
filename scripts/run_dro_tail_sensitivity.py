"""run_dro_tail_sensitivity.py -- does day-ahead robustness pay deeper in the tail?

The body reports the robust-vs-deterministic online gap at CVaR_0.95 (~null). A robust
(CVaR-hedged) controller is a tail insurance, so its value should, if anywhere, grow
with the operator's tail-aversion. This re-evaluates the SAME online controllers as
run_part4_online (no injected emergencies) at deeper tail levels -- CVaR_0.90 / 0.95 /
0.99 and the worst single day -- to locate the smallest tail-aversion at which day-ahead
robustness earns its keep, OR to confirm with data that the mean-dominance ceiling holds
even in the deep tail. No new modelling: same controllers, same data, different metric.

Outputs docs/results_snapshots/dro_tail_sensitivity_<date>.csv
Run: .venv\\Scripts\\python -m scripts.run_dro_tail_sensitivity
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
STRIDE, S, SEED, N_BOOT = 3, 40, 20260615, 500
GRIDS = ["us_west", "taskc", "us_hetero"]
ALPHAS = [0.90, 0.95, 0.99]
OUT = Path("docs/results_snapshots")


def gap(det, rob, fn, rng, n=N_BOOT):
    """Robust-minus-deterministic gap in metric fn (positive = robust lower = wins),
    with a paired day-bootstrap 95% CI."""
    base = 100.0 * (fn(det) - fn(rob)) / fn(det)
    g = np.empty(n)
    for b in range(n):
        i = rng.integers(0, len(det), len(det))
        g[b] = 100.0 * (fn(det[i]) - fn(rob[i])) / fn(det[i])
    lo, hi = np.percentile(g, [2.5, 97.5])
    return base, lo, hi


def verdict(lo, hi):
    return "robust wins" if lo > 0 else "robust loses" if hi < 0 else "null"


def run_grid(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL); Phi = 0.4 * wl.sum()
    kw = dict(ceiling=ceil, workloads=wl, transfer_budget=Phi, n_scenarios=S,
              stride=STRIDE, seed=SEED)
    det = rolling_eval(tr, te, robust=False, **kw)
    rob = rolling_eval(tr, te, robust=True, **kw)
    rows = []
    for a in ALPHAS:
        rng = np.random.default_rng(SEED + 3)
        base, lo, hi = gap(det, rob, lambda v, a=a: cvar_upper_tail(v, alpha=a), rng)
        rows.append({"grid": grid, "metric": f"CVaR_{a:.2f}", "gap_pct": base,
                     "ci_lo": lo, "ci_hi": hi, "verdict": verdict(lo, hi)})
    rng = np.random.default_rng(SEED + 3)
    base, lo, hi = gap(det, rob, lambda v: float(np.max(v)), rng)
    rows.append({"grid": grid, "metric": "worst_day", "gap_pct": base,
                 "ci_lo": lo, "ci_hi": hi, "verdict": verdict(lo, hi)})
    return rows, len(det)


def main():
    all_rows = []
    for g in GRIDS:
        rows, nd = run_grid(g); all_rows += rows
        print(f"\n=== {DISPLAY_NAME.get(g, g)} ===  ({nd} eval days)")
        for r in rows:
            print(f"  {r['metric']:>10} : robust gap {r['gap_pct']:>7.2f}%  "
                  f"95% CI [{r['ci_lo']:>7.2f},{r['ci_hi']:>7.2f}]  -> {r['verdict']}")
    stamp = dt.datetime(2026, 6, 25).strftime("%Y-%m-%d")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"dro_tail_sensitivity_{stamp}.csv"
    pd.DataFrame(all_rows).to_csv(path, index=False)
    wins = [r for r in all_rows if r["verdict"] == "robust wins"]
    print(f"\n  positive AND significant cells: {len(wins)} / {len(all_rows)}")
    for r in wins:
        print(f"    {r['grid']} {r['metric']}: +{r['gap_pct']:.2f}% "
              f"[{r['ci_lo']:.2f},{r['ci_hi']:.2f}]")
    if not wins:
        print("    none -> mean-dominance ceiling holds even in the deep tail "
              "(CVaR_0.99 / worst day): day-ahead robustness does not pay.")
    print(f"  Wrote {path}")


if __name__ == "__main__":
    main()
