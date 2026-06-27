"""run_part5_kappa.py -- Part 5, the intermediate validation.

The Delta = B/M condition predicts dependence value should rise monotonically as the
mean field is flattened. The pre-committed ablation gives only the two endpoints
(kappa=1 real ~0%, kappa=0 flat +1.46% on the Diversified grid). Here we re-solve the
shuffled-marginals DRO at *intermediate* flattenings kappa in {1,.75,.5,.25,0} and show
the realised spatial gap climbs in lockstep with Delta -- a real interior datapoint,
not an interpolation. Schedule uses the R3 reference feasible set (capacity + flex
split + ramp); evaluation is on real 2025 emissions.

Run: .venv\\Scripts\\python -m scripts.run_part5_kappa
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    block_diagonal_by_region, build_daily_panel, cholesky_factor,
    estimate_mean_and_covariance, regularize_covariance,
)

CEIL, UTIL, RIDGE, EPS, ALPHA = 50.0, 0.80, 1e-5, 1.0, 0.50
KAPPAS = [1.0, 0.75, 0.5, 0.25, 0.0]
GRIDS = ["us_hetero", "taskc"]          # grids whose flat-ablation shows a signal
OUT = Path("docs/results_snapshots")


def flatten(rho_bar, k):
    g = rho_bar.mean()
    return g + k * (rho_bar - g)


def chol(sigma, R, T, shuffle):
    s = block_diagonal_by_region(sigma, R=R, T=T) if shuffle else sigma
    return cholesky_factor(regularize_covariance(s, eta=RIDGE))


def mean_value_range(rho_bar, cap, W):
    total = 0.0
    for r in range(rho_bar.shape[0]):
        c = np.sort(rho_bar[r]); lo = hi = 0.0; rem = W
        for v in c:
            t = min(cap, rem); lo += v * t; rem -= t
            if rem <= 0: break
        rem = W
        for v in c[::-1]:
            t = min(cap, rem); hi += v * t; rem -= t
            if rem <= 0: break
        total += hi - lo
    return total


def main():
    rows = []
    for grid in GRIDS:
        z = list(REGION_SETS[grid]["zones"])
        panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                         region_order=z, tz=REGION_SETS[grid]["tz"])
        yrs = np.array([d.year for d in dates])
        tr, te = panel[yrs < 2025], panel[yrs == 2025]
        R, T = panel.shape[1], panel.shape[2]
        rho_bar = tr.mean(axis=0)
        wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
        alpha = np.full(R, ALPHA); ramp = np.full(R, 15.0)
        _, sigma = estimate_mean_and_covariance(tr.reshape(tr.shape[0], R * T))
        Lj, Ls = chol(sigma, R, T, False), chol(sigma, R, T, True)
        off = regularize_covariance(sigma, eta=RIDGE) - regularize_covariance(
            block_diagonal_by_region(sigma, R=R, T=T), eta=RIDGE)
        B = EPS * (CEIL * np.sqrt(R * T * UTIL)) * np.sqrt(float(np.abs(np.linalg.eigvalsh(off)).max()))
        print(f"\n=== {DISPLAY_NAME.get(grid, grid)} ===  (B={B:.0f})")
        print(f"  {'kappa':>6} {'gap %':>8} {'Delta=B/M':>10}")
        for k in KAPPAS:
            rb = flatten(rho_bar, k)
            common = dict(workloads=wl, ceiling=ceil, epsilon=EPS, region_order=z,
                          alpha=alpha, ramp=ramp)
            rj = solve_mahalanobis_dro(rho_bar=rb, L=Lj, **common)
            rs = solve_mahalanobis_dro(rho_bar=rb, L=Ls, **common)
            xj = np.asarray(rj.schedule); xs = np.asarray(rs.schedule)
            cj = cvar_upper_tail(per_day_emissions(xj, te))
            cs = cvar_upper_tail(per_day_emissions(xs, te))
            gap = 100 * (cs - cj) / cs
            M = mean_value_range(rb, CEIL, UTIL * CEIL * T)
            delta = B / M if M > 1e-6 else np.inf
            rows.append({"grid": grid, "kappa": k, "gap_pct": gap, "Delta": delta, "M": M})
            print(f"  {k:>6.2f} {gap:>+7.3f}% {delta:>10.3f}")
    pd.DataFrame(rows).to_csv(OUT / f"part5_kappa_{dt.datetime(2026,6,15):%Y-%m-%d}.csv", index=False)
    print("\nIf gap rises monotonically as kappa->0 (Delta rises), the condition is validated")
    print("with real interior points, not just the two ablation endpoints.")


if __name__ == "__main__":
    main()
