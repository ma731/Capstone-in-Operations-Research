"""PART 3 (the hard version) — two-stage robust transfer with costly recourse.

Why the one-shot tests showed robustness doesn't pay: if you can plan on a good
forecast, you just exploit it. Robustness only matters when you must COMMIT under
uncertainty and can only partially fix a bad commitment. That is the realistic
case for long-running jobs: assign them to regions day-ahead (here-and-now), then
migrating a *running* job costs money (per-unit cost lambda, budget Phi).

Two-stage structure, solved as one CVaR linear program over S scenarios:
  Stage 1 (here-and-now): commit base placement x[r,t]  (before carbon is known).
  Stage 2 (recourse):     for each scenario s, costly transfer f^s adapts to the
                          realized carbon rho^s; executed y^s = x + in^s - out^s.
  cost^s = <rho^s, y^s> + lambda * sum(f^s)
  objective = risk measure over scenarios of cost^s.

We compare two stage-1 commitment policies, both with the SAME recourse:
  * RISK-NEUTRAL  : commit x to minimize the *expected* cost  (the deterministic plan).
  * ROBUST (CVaR) : commit x to minimize CVaR_beta of cost     (hedged commitment).
Then we score both on held-out 2025 days (with optimal recourse per day) and sweep
the migration cost lambda. Hypothesis: as lambda rises (recourse gets expensive),
the robust commitment increasingly beats the risk-neutral one.

Run: .venv\\Scripts\\python -m scripts.prototype_twostage_transfer [grid]
"""
from __future__ import annotations

import sys

import cvxpy as cp
import numpy as np

from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel

CEIL, UTIL, BETA = 50.0, 0.80, 0.95
GRID = sys.argv[1] if len(sys.argv) > 1 else "us_west"
S = 60                       # day-ahead scenarios
SEED = 20260614


def transfer_expr(x, f):
    """Executed load y = x + inflow - outflow, from flow var f[r,s,t]."""
    return x + cp.sum(f, axis=0) - cp.sum(f, axis=1)


def commit(scenarios, wl, ceil, lam, Phi, risk):
    """Solve the two-stage program; return the stage-1 commitment x.
    risk='mean' -> expected cost; risk='cvar' -> CVaR_beta of cost."""
    Sn, R, T = scenarios.shape
    x = cp.Variable((R, T), nonneg=True)
    f = [cp.Variable((R, R, T), nonneg=True) for _ in range(Sn)]
    costs = []
    cons = [cp.sum(x, axis=1) == wl]
    for s in range(Sn):
        y = transfer_expr(x, f[s])
        cons += [y >= 0, y <= ceil, cp.sum(f[s]) <= Phi]
        for r in range(R):
            cons += [f[s][r, r, :] == 0]
        costs.append(cp.sum(cp.multiply(scenarios[s], y)) + lam * cp.sum(f[s]))
    if risk == "mean":
        obj = sum(costs) / Sn
    else:
        tau = cp.Variable(); z = cp.Variable(Sn, nonneg=True)
        cons += [z[s] >= costs[s] - tau for s in range(Sn)]
        obj = tau + cp.sum(z) / ((1 - BETA) * Sn)
    cp.Problem(cp.Minimize(obj), cons).solve(solver="HIGHS")
    return np.asarray(x.value)


def recourse_cost(x_fixed, rho, ceil, lam, Phi):
    """Given a fixed commitment x, best costly transfer for realized rho. Returns
    the realized cost (carbon + migration)."""
    R, T = rho.shape
    f = cp.Variable((R, R, T), nonneg=True)
    y = x_fixed + cp.sum(f, axis=0) - cp.sum(f, axis=1)
    cons = [y >= 0, y <= ceil, cp.sum(f) <= Phi]
    for r in range(R):
        cons += [f[r, r, :] == 0]
    cost = cp.sum(cp.multiply(rho, y)) + lam * cp.sum(f)
    cp.Problem(cp.Minimize(cost), cons).solve(solver="HIGHS")
    return float(cost.value)


def main():
    cfg = REGION_SETS[GRID]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                     region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr = panel[yrs < 2025]; te = panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    Phi = 0.5 * wl.sum()                 # bounded recourse (can't fully re-place)

    rng = np.random.default_rng(SEED)
    # day-ahead scenarios: resample training days, OVER-SAMPLING the dirtiest 20%
    # (tail/stress days) so the commitment must reckon with bad realizations.
    daily = tr.mean(axis=(1, 2)); thr = np.quantile(daily, 0.8)
    pool = np.where(daily >= thr)[0]; rest = np.where(daily < thr)[0]
    pick = np.concatenate([rng.choice(pool, S // 2), rng.choice(rest, S - S // 2)])
    scen = tr[pick]
    te_eval = te[::2]                    # subsample test for the recourse eval

    print(f"=== PART 3 (two-stage): {DISPLAY_NAME[GRID]} | {S} stress scenarios | "
          f"{len(te_eval)} test days ===")
    print(f"  {'lambda':>7} {'risk-neutral':>13} {'robust(CVaR)':>13} {'robust gain':>12}")
    for lam in [0.0, 5.0, 20.0, 60.0]:
        x_mean = commit(scen, wl, ceil, lam, Phi, "mean")
        x_cvar = commit(scen, wl, ceil, lam, Phi, "cvar")
        cm = cvar_upper_tail(np.array([recourse_cost(x_mean, te_eval[i], ceil, lam, Phi)
                                       for i in range(len(te_eval))]))
        cc = cvar_upper_tail(np.array([recourse_cost(x_cvar, te_eval[i], ceil, lam, Phi)
                                       for i in range(len(te_eval))]))
        print(f"  {lam:>7.1f} {cm:>13.0f} {cc:>13.0f} {100*(cm-cc)/cm:>11.2f}%")
    print("  (positive => the hedged commitment beats the deterministic one;")
    print("   expect it to grow as migration cost lambda rises)")


if __name__ == "__main__":
    main()
