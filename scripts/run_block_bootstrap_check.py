"""Serial-dependence robustness check for the spatial-null bootstrap.

The headline inference uses a paired bootstrap that resamples individual days
independently. A reviewer can object that $\\CVaR_{0.95}$ is an average over the
~12 worst days of the year, and those days cluster (weather fronts, renewable
droughts span several days), so an iid-day bootstrap can understate the standard
error and overstate significance.

This script re-bootstraps the joint-vs-shuffled spatial gap with a MOVING-BLOCK
bootstrap that resamples contiguous runs of days (block length L), preserving the
serial dependence the iid scheme destroys. It reports, for each grid, the gap and
its 95% CI under L=1 (= iid baseline), L=7 (synoptic-weather week), and L=14, plus
the block/iid standard-error ratio. The question it answers: do the null
conclusions (every gap within the 0.4% materiality margin) survive a bootstrap
that respects serial dependence?

Run:  python -m scripts.run_block_bootstrap_check
Writes: docs/results_snapshots/block_bootstrap_2026-06-27.csv (license-safe summary).
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.stratified_correlations import REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    block_diagonal_by_region, build_daily_panel, cholesky_factor,
    daily_panel_to_matrix, estimate_mean_and_covariance, regularize_covariance,
)

TRAIN_YEARS = (2021, 2022, 2023, 2024)
TEST_YEAR = 2025
UTIL, CELL, T, ETA = 0.80, 50.0, 24, 1e-5
CVAR_A = 0.95
EPS = 1.0                 # the CV-selected radius the null reports
BLOCK_LENGTHS = (1, 7, 14)  # L=1 reproduces the iid bootstrap
N_BOOT = 2000
SEED = 20260524
MARGIN = 0.4             # materiality margin, percent of CVaR
GRIDS = ("us_west", "taskc", "us_hetero")
SNAPSHOT = Path(__file__).resolve().parents[1] / "docs" / "results_snapshots" / "block_bootstrap_2026-06-27.csv"


def load_split(region_set):
    cfg = REGION_SETS[region_set]
    zones = list(cfg["zones"])
    wide = to_wide(load_all_zones(zones), value_col="ci_lifecycle")
    panel, dates = build_daily_panel(wide, region_order=zones, tz=cfg["tz"], expected_T=T)
    is_tr = np.array([d.year in TRAIN_YEARS for d in dates])
    is_te = np.array([d.year == TEST_YEAR for d in dates])
    return panel[is_tr], panel[is_te], zones


def schedules(train_panel, zones):
    _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train_panel))
    R, T_ = train_panel.shape[1], train_panel.shape[2]
    L_j = cholesky_factor(regularize_covariance(sig, ETA))
    L_s = cholesky_factor(regularize_covariance(block_diagonal_by_region(sig, R=R, T=T_), ETA))
    rho_bar = train_panel.mean(axis=0)
    workloads = np.full(R, UTIL * CELL * T_)
    ceiling = np.full((R, T_), CELL)
    kw = dict(workloads=workloads, ceiling=ceiling, epsilon=EPS, region_order=tuple(zones))
    xj = solve_mahalanobis_dro(rho_bar, L_j, **kw).schedule
    xs = solve_mahalanobis_dro(rho_bar, L_s, **kw).schedule
    return xj, xs


def block_boot(ej, es, L, n=N_BOOT, seed=SEED):
    """Moving-block paired bootstrap of the CVaR gap (CVaR_shuf - CVaR_joint)."""
    rng = np.random.default_rng(seed)
    N = len(ej)
    nblocks = -(-N // L)  # ceil
    gaps = np.empty(n)
    for b in range(n):
        starts = rng.integers(0, N, size=nblocks)
        idx = np.concatenate([(np.arange(s, s + L) % N) for s in starts])[:N]
        gaps[b] = cvar_upper_tail(es[idx], CVAR_A) - cvar_upper_tail(ej[idx], CVAR_A)
    lo, hi = np.percentile(gaps, [2.5, 97.5])
    return float(lo), float(hi), float(gaps.std(ddof=1))


def main():
    rows = []
    print(f"{'grid':10s} {'L':>3s} {'gap%':>8s} {'CI%':>20s} {'SE/SE(iid)':>11s} {'within margin?':>14s}")
    for g in GRIDS:
        tr, te, zones = load_split(g)
        xj, xs = schedules(tr, zones)
        ej, es = per_day_emissions(xj, te), per_day_emissions(xs, te)
        base = cvar_upper_tail(ej, CVAR_A)
        gap_pct = 100.0 * (cvar_upper_tail(es, CVAR_A) - base) / base
        se_iid = None
        for L in BLOCK_LENGTHS:
            lo, hi, se = block_boot(ej, es, L)
            if L == 1:
                se_iid = se
            lo_pct, hi_pct = 100.0 * lo / base, 100.0 * hi / base
            within = abs(lo_pct) < MARGIN and abs(hi_pct) < MARGIN
            ratio = se / se_iid if se_iid else 1.0
            print(f"{g:10s} {L:>3d} {gap_pct:>7.3f}% [{lo_pct:>+6.3f},{hi_pct:>+6.3f}]% "
                  f"{ratio:>10.2f}x {'yes' if within else 'NO':>14s}")
            rows.append(dict(grid=g, block_length=L, gap_pct=round(gap_pct, 4),
                             ci_lo_pct=round(lo_pct, 4), ci_hi_pct=round(hi_pct, 4),
                             se_ratio_vs_iid=round(ratio, 3), within_margin=within))
    with open(SNAPSHOT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["grid", "block_length", "gap_pct", "ci_lo_pct",
                                          "ci_hi_pct", "se_ratio_vs_iid", "within_margin"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {SNAPSHOT.name}")


if __name__ == "__main__":
    main()
