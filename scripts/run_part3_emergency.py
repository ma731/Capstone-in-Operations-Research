"""run_part3_emergency.py  --  Part 3, hardened.

The tail-risk crossover with uncertainty quantification. Supersedes
prototype_emergency_crossover.py: uses the canonical, unit-tested transfer_dro
module, adds paired-bootstrap confidence intervals on the robust gain at each
severity, and reports the crossover threshold M* (the smallest severity at which the
robust commitment's advantage is bootstrap-significant).

Emergency model (stylised but interpretable): with probability P_EMG per day one
region's carbon is multiplied by a severity M. The M in [1,4] range spans realistic
renewable-drought / peaker-dispatch multipliers (grid carbon can rise 2-4x for a day).
M hits both the day-ahead scenarios (so the commitment can hedge) and the evaluation
world. Two-stage structure with costly, migration-limited recourse, so a bad
commitment cannot be fully undone.

Outputs docs/results_snapshots/part3_emergency_<date>.csv and prints a summary.
Run: .venv\\Scripts\\python -m scripts.run_part3_emergency
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

CEIL, UTIL = 50.0, 0.80
S = 60                      # day-ahead scenarios
LAM = 30.0                  # costly migration so the commitment matters
P_EMG = 0.10                # 10% of days carry an emergency
SEED = 20260614
N_BOOT = 500
M_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
GRIDS = ["us_west", "taskc", "us_hetero"]
OUT = Path("docs/results_snapshots")


def inject(panel, M, rng):
    """Each day, w.p. P_EMG, multiply one random region's carbon by severity M."""
    out = panel.copy()
    for i in range(len(out)):
        if rng.random() < P_EMG:
            out[i, rng.integers(out.shape[1]), :] *= M
    return out


def boot_gain(cost_mean, cost_cvar, rng, n=N_BOOT):
    """Paired bootstrap over evaluation days -> (gain%, lo, hi) on the robust gain
    in CVaR terms: 100*(CVaR(mean)-CVaR(cvar))/CVaR(mean)."""
    base = 100.0 * (cvar_upper_tail(cost_mean) - cvar_upper_tail(cost_cvar)) / cvar_upper_tail(cost_mean)
    n_days = len(cost_mean)
    g = np.empty(n)
    for b in range(n):
        idx = rng.integers(0, n_days, n_days)
        cm, cc = cvar_upper_tail(cost_mean[idx]), cvar_upper_tail(cost_cvar[idx])
        g[b] = 100.0 * (cm - cc) / cm
    lo, hi = np.percentile(g, [2.5, 97.5])
    return base, lo, hi


def run_grid(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    Phi = 0.4 * wl.sum()
    rows = []
    for M in M_GRID:
        rng = np.random.default_rng(SEED)
        scen = inject(tr, M, rng)[rng.choice(len(tr), S, replace=False)]
        te_eval = inject(te, M, np.random.default_rng(SEED + 1))[::2]
        x_mean = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=LAM, risk="mean")
        x_cvar = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=LAM, risk="cvar")
        cost_mean = np.array([recourse_cost(x_mean, d, ceil, transfer_budget=Phi, lam=LAM) for d in te_eval])
        cost_cvar = np.array([recourse_cost(x_cvar, d, ceil, transfer_budget=Phi, lam=LAM) for d in te_eval])
        gain, lo, hi = boot_gain(cost_mean, cost_cvar, np.random.default_rng(SEED + 7))
        rows.append({"grid": grid, "M": M, "gain_pct": gain, "ci_lo": lo, "ci_hi": hi,
                     "significant": lo > 0})
    return rows


def main():
    all_rows = []
    for g in GRIDS:
        rows = run_grid(g)
        all_rows += rows
        mstar = next((r["M"] for r in rows if r["significant"]), None)
        print(f"\n=== {DISPLAY_NAME.get(g, g)} ===  crossover M* = "
              f"{mstar if mstar else 'not reached in grid'}")
        print(f"  {'M':>5} {'robust gain%':>13} {'95% CI':>22} {'sig':>5}")
        for r in rows:
            print(f"  {r['M']:>5.1f} {r['gain_pct']:>12.2f}% "
                  f"[{r['ci_lo']:>7.2f},{r['ci_hi']:>7.2f}] {'YES' if r['significant'] else '':>5}")
    stamp = dt.datetime(2026, 6, 15).strftime("%Y-%m-%d")
    path = OUT / f"part3_emergency_{stamp}.csv"
    pd.DataFrame(all_rows).to_csv(path, index=False)
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
