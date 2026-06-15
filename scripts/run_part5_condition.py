"""run_part5_condition.py  --  Part 5, the problem-class condition.

Generalises the mean-dominance bound into a dimensionless predictor of *when*
cross-coordinate dependence can improve a robust allocation. Define

    B = epsilon * max_x||x|| * sqrt(||Sigma_off||)     (Prop. 1 spatial-gap bound)
    M = max_x <rho_bar, x> - min_x <rho_bar, x>          (mean-exploitable value over X)
    Delta = B / M                                        (mean-dominance ratio)

The spatial (dependence) gap is at most B, so as a fraction of the value the mean
field already delivers it is at most Delta = B/M. Delta is a cheap, a-priori,
data-only quantity (no DRO solve). Delta << 1 would CERTIFY dependence-immateriality;
on the studied grids Delta ~ 1.5-3.4 (B is a loose bound), so the a-priori screen is
inconclusive -- which is precisely why the empirical falsification of Parts 1-2 was
needed. Delta's role is therefore (i) a negative filter and (ii) a monotone regime
indicator: a mean-flattening sweep (kappa: 1=real -> 0=flat) shrinks M and raises
Delta in lockstep with the empirical dependence value, which rises from ~0 (real) to
+1.46% (mean-ablated). This script computes Delta on the three grids and along the
sweep.

Run: .venv\\Scripts\\python -m scripts.run_part5_condition
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import (
    block_diagonal_by_region, build_daily_panel,
    estimate_mean_and_covariance, regularize_covariance,
)

CEIL, UTIL, RIDGE, EPS = 50.0, 0.80, 1e-5, 1.0
TRAIN = range(2021, 2025)
GRIDS = ["us_west", "taskc", "us_hetero"]
OUT = Path("docs/results_snapshots")


def mean_value_range(rho_bar, cap, W):
    """M = max_x<rho_bar,x> - min_x<rho_bar,x> over {0<=x<=cap, sum_t x_r = W_r}.
    Separable per region: greedy fill of cheapest (min) / dirtiest (max) hours."""
    R, T = rho_bar.shape
    total = 0.0
    for r in range(R):
        c = np.sort(rho_bar[r])           # ascending carbon
        need = W
        lo = hi = 0.0
        # cheapest fill (min) and dirtiest fill (max)
        rem = need
        for v in c:                        # min: cheapest hours first
            take = min(cap, rem); lo += v * take; rem -= take
            if rem <= 0: break
        rem = need
        for v in c[::-1]:                  # max: dirtiest hours first
            take = min(cap, rem); hi += v * take; rem -= take
            if rem <= 0: break
        total += (hi - lo)
    return total


def flatten_mean(rho_bar, kappa):
    """Shrink the mean's deviation from its grand average by factor kappa (1=real,
    0=flat)."""
    g = rho_bar.mean()
    return g + kappa * (rho_bar - g)


def main():
    rows, sweep = [], []
    for grid in GRIDS:
        z = list(REGION_SETS[grid]["zones"])
        panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                         region_order=z, tz=REGION_SETS[grid]["tz"])
        tr = panel[np.array([d.year in TRAIN for d in dates])]
        R, T = tr.shape[1], tr.shape[2]
        rho_bar = tr.mean(axis=0)
        W = UTIL * CEIL * T
        _, sigma = estimate_mean_and_covariance(tr.reshape(tr.shape[0], R * T))
        off = regularize_covariance(sigma, eta=RIDGE) - regularize_covariance(
            block_diagonal_by_region(sigma, R=R, T=T), eta=RIDGE)
        B = EPS * (CEIL * np.sqrt(R * T * UTIL)) * np.sqrt(float(np.abs(np.linalg.eigvalsh(off)).max()))
        M = mean_value_range(rho_bar, CEIL, W)
        rows.append({"grid": grid, "B": B, "M": M, "Delta": B / M})
        for k in [1.0, 0.5, 0.25, 0.1, 0.05]:
            Mk = mean_value_range(flatten_mean(rho_bar, k), CEIL, W)
            sweep.append({"grid": grid, "kappa": k, "M": Mk,
                          "Delta": B / Mk if Mk > 1e-9 else np.inf})

    print("=== Part 5: mean-dominance ratio Delta = B / M  (Delta << 1 => dependence immaterial) ===")
    print(f"  {'grid':18s} {'B (gap bound)':>14} {'M (mean value)':>15} {'Delta':>9}")
    for r in rows:
        print(f"  {DISPLAY_NAME.get(r['grid'], r['grid']):18s} {r['B']:>14.0f} {r['M']:>15.0f} {r['Delta']:>9.4f}")
    print("\n  Mean-flattening sweep (kappa: 1=real -> 0=flat); Delta grows as the mean is removed:")
    sw = pd.DataFrame(sweep)
    for grid in GRIDS:
        g = sw[sw.grid == grid]
        ds = "  ".join(f"k={k:.2f}:{d:.3f}" for k, d in zip(g.kappa, g.Delta))
        print(f"    {DISPLAY_NAME.get(grid, grid):18s} {ds}")
    print("\n  Honest reading: B is a loose a-priori bound, so Delta ~ 1-3 on these grids:")
    print("  the cheap a-priori screen is INCONCLUSIVE here (Delta not << 1), which is exactly")
    print("  why the empirical falsification (Parts 1-2) was necessary. Delta's value is (i) a")
    print("  NEGATIVE filter -- Delta << 1 would certify immateriality without any solve -- and")
    print("  (ii) a monotone REGIME INDICATOR: as the mean flattens (kappa->0) Delta rises in")
    print("  lockstep with the empirical dependence value (0 at kappa=1 -> +1.46% at kappa->0).")
    stamp = dt.datetime(2026, 6, 15).strftime("%Y-%m-%d")
    pd.DataFrame(rows).to_csv(OUT / f"part5_condition_{stamp}.csv", index=False)
    sw.to_csv(OUT / f"part5_sweep_{stamp}.csv", index=False)
    print(f"\nWrote {OUT / f'part5_condition_{stamp}.csv'} and the kappa sweep.")


if __name__ == "__main__":
    main()
