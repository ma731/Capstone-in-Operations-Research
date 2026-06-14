"""PROTOTYPE (Part 3) — spatially-coupled transfer DRO.

Extends the scheduler with inter-region load flows f[r,s,t] >= 0. Executed load
    y[r,t] = x[r,t] + inflow - outflow,   sum_t x[r,t] = W_r,   0 <= y <= ceiling,
emissions are evaluated on y, and a transfer budget Phi caps total relocation.
The program stays an SOCP. This is a *prototype* with a minimal feasible set
(capacity + work conservation + transfer budget) to see the shape of the result;
it does not touch the frozen algorithm_2b. Two questions:

  (a) Does raising the transfer budget Phi unlock carbon savings? (Phi=0 == the null.)
  (b) Does robustifying (eps>0) beat deterministic (eps=0) transfer under FORECAST
      ERROR -- the hypothesis that transfer amplifies forecast risk, so robustness
      finally pays.

Run: .venv\\Scripts\\python -m scripts.prototype_transfer_dro
"""
from __future__ import annotations

import cvxpy as cp
import numpy as np

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import (
    build_daily_panel, cholesky_factor, daily_panel_to_matrix,
    estimate_mean_and_covariance, regularize_covariance,
)

import sys
CASE = sys.argv[1] if len(sys.argv) > 1 else "taskc"
CEIL = 50.0
UTIL = 0.80


def solve_transfer(rho_bar, L, workloads, ceiling, epsilon, Phi, lam=0.0):
    """Min <rho_bar,y> + eps||L^T y|| + lam*sum f, over transfer flows. SOCP."""
    R, T = rho_bar.shape
    x = cp.Variable((R, T), nonneg=True)
    f = cp.Variable((R, R, T), nonneg=True)            # f[r,s,t]: r -> s in hour t
    # executed load y[r,t] = x[r,t] + inflow(into r) - outflow(out of r)
    inflow = cp.sum(f, axis=0)                          # sum_s f[s, r, t] -> (R,T)
    outflow = cp.sum(f, axis=1)                         # sum_s f[r, s, t] -> (R,T)
    y = x + inflow - outflow
    y_vec = cp.hstack([y[r, :] for r in range(R)])
    obj = cp.sum(cp.multiply(rho_bar, y)) + epsilon * cp.norm(L.T @ y_vec, 2)
    if lam:
        obj = obj + lam * cp.sum(f)
    cons = [
        cp.sum(x, axis=1) == workloads,                # each region's work is scheduled
        y >= 0, y <= ceiling,                          # executed-load capacity
        cp.sum(cp.reshape(f, (R * R, T), order="C"), axis=0) >= 0,
        cp.sum(f) <= Phi,                              # transfer budget
    ]
    # no self-loops
    for r in range(R):
        cons.append(f[r, r, :] == 0)
    prob = cp.Problem(cp.Minimize(obj), cons)
    prob.solve(solver="CLARABEL")
    return np.asarray(y.value), float(cp.sum(f).value)


def main():
    cfg = REGION_SETS[CASE]
    z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                     region_order=z, tz=cfg["tz"])
    tr = panel[np.array([d.year < 2025 for d in dates])]
    te = panel[np.array([d.year == 2025 for d in dates])]
    R, T = panel.shape[1], panel.shape[2]
    rho_bar = tr.mean(axis=0)
    _, S = estimate_mean_and_covariance(daily_panel_to_matrix(tr))
    L = cholesky_factor(regularize_covariance(S, eta=1e-5))
    wl = np.full(R, UTIL * CEIL * T)
    ceil = np.full((R, T), CEIL)

    print(f"=== {DISPLAY_NAME[CASE]} ({', '.join(zz.split('-')[-1] for zz in z)}) ===")
    print("regional MEAN carbon (gCO2/kWh), day-average:")
    for r, zz in enumerate(z):
        print(f"    {zz.split('-')[-1]:>5}: {rho_bar[r].mean():6.0f}")
    Wtot = wl.sum()

    # ---- (a) transfer-budget sweep: does transfer unlock savings? ----
    print("\n(a) Transfer-budget sweep (epsilon* = 1, evaluated on real 2025):")
    print(f"    {'Phi/Wtot':>9} {'used':>6} {'CVaR_2025':>11} {'savings_vs_Phi0':>16}")
    base = None
    for frac in [0.0, 0.25, 0.5, 1.0, 2.0]:
        Phi = frac * Wtot
        y, used = solve_transfer(rho_bar, L, wl, ceil, epsilon=1.0, Phi=Phi)
        cv = cvar_upper_tail(per_day_emissions(y, te))
        if base is None:
            base = cv
        sav = 100 * (base - cv) / base
        print(f"    {frac:>9.2f} {used/Wtot:>6.2f} {cv:>11.0f} {sav:>15.2f}%")

    # ---- (b) robust vs deterministic transfer under forecast error ----
    print("\n(b) Robust (eps*=1) vs deterministic (eps=0) transfer, free transfer,")
    print("    planned on a NOISY forecast, evaluated on real 2025:")
    print(f"    {'fcst_noise':>10} {'det_CVaR':>9} {'rob_CVaR':>9} {'robust_gain':>12}")
    rng = np.random.default_rng(0)
    sigma_rho = rho_bar.std()
    for noise in [0.0, 0.15, 0.30, 0.50]:
        # degrade the planning forecast; evaluate on the true field
        rho_fc = rho_bar + noise * sigma_rho * rng.standard_normal(rho_bar.shape)
        rho_fc = np.clip(rho_fc, 1.0, None)
        yd, _ = solve_transfer(rho_fc, L, wl, ceil, epsilon=0.0, Phi=2.0 * Wtot)
        yr, _ = solve_transfer(rho_fc, L, wl, ceil, epsilon=1.0, Phi=2.0 * Wtot)
        cd = cvar_upper_tail(per_day_emissions(yd, te))
        cr = cvar_upper_tail(per_day_emissions(yr, te))
        print(f"    {noise:>10.2f} {cd:>9.0f} {cr:>9.0f} {100*(cd-cr)/cd:>11.2f}%")


if __name__ == "__main__":
    main()
