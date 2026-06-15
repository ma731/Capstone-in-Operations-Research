"""run_part5_tight.py -- Part 5, the tightened bound.

The a-priori mean-dominance ratio Delta = B/M uses the worst-case feasible diameter
max_x||x|| (maximal concentration), which makes B loose and Delta ~ 1.5-3.4
(inconclusive). Substituting the *realized* optimal schedule norm ||x*|| gives a
tighter, data-dependent bound B* = eps*||x*||*sqrt(||Sigma_off||). If Delta* = B*/M
falls below 1, the spatial gap is provably immaterial *given the actual schedules* --
upgrading the screen from inconclusive to conclusive in hindsight.

Outputs docs/results_snapshots/part5_tight_<date>.csv
Run: .venv\\Scripts\\python -m scripts.run_part5_tight
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    block_diagonal_by_region, build_daily_panel, cholesky_factor,
    estimate_mean_and_covariance, regularize_covariance,
)

CEIL, UTIL, RIDGE, EPS, ALPHA = 50.0, 0.80, 1e-5, 1.0, 0.50
TRAIN = range(2021, 2025)
GRIDS = ["us_west", "taskc", "us_hetero"]
OUT = Path("docs/results_snapshots")


def mean_value_range(rho, cap, W):
    tot = 0.0
    for r in range(rho.shape[0]):
        c = np.sort(rho[r]); lo = hi = 0.0; rem = W
        for v in c:
            t = min(cap, rem); lo += v * t; rem -= t
            if rem <= 0: break
        rem = W
        for v in c[::-1]:
            t = min(cap, rem); hi += v * t; rem -= t
            if rem <= 0: break
        tot += hi - lo
    return tot


def main():
    rows = []
    hdr = f"  {'grid':18s} {'||x||_apri':>10} {'||x*||':>8} {'Delta_apri':>11} {'Delta*':>8} {'verdict':>14}"
    print(hdr)
    for grid in GRIDS:
        z = list(REGION_SETS[grid]["zones"])
        panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                         region_order=z, tz=REGION_SETS[grid]["tz"])
        tr = panel[np.array([d.year in TRAIN for d in dates])]
        R, T = tr.shape[1], tr.shape[2]
        rho = tr.mean(axis=0); W = UTIL * CEIL * T
        _, sig = estimate_mean_and_covariance(tr.reshape(tr.shape[0], R * T))
        off = regularize_covariance(sig, eta=RIDGE) - regularize_covariance(
            block_diagonal_by_region(sig, R=R, T=T), eta=RIDGE)
        off_norm = np.sqrt(float(np.abs(np.linalg.eigvalsh(off)).max()))
        L = cholesky_factor(regularize_covariance(sig, eta=RIDGE))
        res = solve_mahalanobis_dro(rho_bar=rho, L=L, workloads=np.full(R, W),
                                    ceiling=np.full((R, T), CEIL), epsilon=EPS,
                                    region_order=z, alpha=np.full(R, ALPHA),
                                    ramp=np.full(R, 15.0))
        x_norm = float(np.linalg.norm(np.asarray(res.schedule)))
        x_apri = CEIL * np.sqrt(R * T * UTIL)
        M = mean_value_range(rho, CEIL, W)
        d_apri = EPS * x_apri * off_norm / M
        d_star = EPS * x_norm * off_norm / M
        verdict = "CONCLUSIVE" if d_star < 1 else "inconclusive"
        rows.append({"grid": grid, "x_apriori": x_apri, "x_star": x_norm,
                     "Delta_apriori": d_apri, "Delta_star": d_star, "verdict": verdict})
        print(f"  {DISPLAY_NAME.get(grid, grid):18s} {x_apri:>10.1f} {x_norm:>8.1f} "
              f"{d_apri:>11.3f} {d_star:>8.3f} {verdict:>14}")
    pd.DataFrame(rows).to_csv(OUT / f"part5_tight_{dt.datetime(2026,6,15):%Y-%m-%d}.csv", index=False)
    print("\n  Delta* uses the realized schedule norm; where Delta* < 1 the a-priori")
    print("  inconclusive screen becomes a provable certificate of immateriality.")


if __name__ == "__main__":
    main()
