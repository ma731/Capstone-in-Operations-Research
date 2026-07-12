"""Is the spatial null an artifact of the hand-calibrated capacity geometry?

The headline study pre-registers alpha and the ambiguity radius epsilon, but the
capacity bounds (x_min, x_max) = (50, 75) were "Goldilocks-calibrated" on training
data to a loosely-binding regime (bind fraction 0.28-0.37). A sharp reviewer objects
that the one tuned knob is the geometric one, and geometry is exactly what decides
whether dependence can bind. This script removes that objection by re-running the
shuffled-marginals falsification across a grid of capacity settings, from loose to
tight binding, and showing the null holds throughout.

For each grid and each (utilization, ceiling) setting we solve the Mahalanobis-
Wasserstein DRO under the joint Sigma and the shuffled (block-diagonal) Sigma, then
difference the OUT-OF-SAMPLE CVaR_0.95 of 2025 emissions. We also report the bind
fraction (share of cells at the capacity ceiling) so the reader can see the binding
genuinely varies. If the spatial gap stays within the materiality margin across the
whole grid -- including settings far tighter and far looser than the calibrated point
-- the null does not depend on the tuned geometry, and the Goldilocks point is shown
to bias toward (not against) dependence mattering: looser binding = a more responsive
schedule = the regime most able to exploit covariance.

Run:  python -m scripts.run_capacity_sensitivity
Writes: docs/results_snapshots/capacity_sensitivity_2026-06-27.csv
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
    block_diagonal_by_region,
    build_daily_panel,
    cholesky_factor,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
)

TRAIN_YEARS = (2021, 2022, 2023, 2024)
TEST_YEAR = 2025
T_HOURS = 24
RIDGE_ETA = 1e-5
CVAR_ALPHA = 0.95
EPS_ACTIVE = 100.0          # ambiguity radius large enough that the ball is active
GRIDS = ("us_hetero", "us_west", "taskc")
# capacity grid: utilization (workload / (ceiling*T)) spans loose -> tight binding;
# the calibrated headline point sits at util ~ 0.80, ceiling 50.
UTIL_GRID = (0.60, 0.70, 0.80, 0.90)
CEILING_GRID = (50.0, 75.0)
MATERIALITY_PCT = 0.4

SNAPSHOT = (Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"
            / "capacity_sensitivity_2026-06-27.csv")


def load_split(region_set: str):
    cfg = REGION_SETS[region_set]
    zones = list(cfg["zones"])
    wide = to_wide(load_all_zones(zones), value_col="ci_lifecycle")
    panel, dates = build_daily_panel(wide, region_order=zones, tz=cfg["tz"], expected_T=T_HOURS)
    is_tr = np.array([d.year in TRAIN_YEARS for d in dates])
    is_te = np.array([d.year == TEST_YEAR for d in dates])
    return panel[is_tr], panel[is_te], zones


def fit_sigmas(train_panel):
    _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train_panel))
    R, T = train_panel.shape[1], train_panel.shape[2]
    sig_j = regularize_covariance(sig, RIDGE_ETA)
    sig_s = regularize_covariance(block_diagonal_by_region(sig, R=R, T=T), RIDGE_ETA)
    return sig_j, sig_s


def bind_fraction(x, ceiling) -> float:
    return float((np.asarray(x) >= 0.99 * ceiling).mean())


def run_grid(region_set, rows):
    tr, te, zones = load_split(region_set)
    R, T = tr.shape[1], tr.shape[2]
    rho_bar = tr.mean(axis=0)
    sig_j, sig_s = fit_sigmas(tr)
    L_j, L_s = cholesky_factor(sig_j), cholesky_factor(sig_s)
    print(f"\n{region_set}: R={R} zones={zones}")

    for ceil_mw in CEILING_GRID:
        ceiling = np.full((R, T), ceil_mw)
        for util in UTIL_GRID:
            workloads = np.full(R, util * ceil_mw * T)
            try:
                rj = solve_mahalanobis_dro(rho_bar, L_j, workloads, ceiling,
                                           epsilon=EPS_ACTIVE, region_order=tuple(zones))
                rs = solve_mahalanobis_dro(rho_bar, L_s, workloads, ceiling,
                                           epsilon=EPS_ACTIVE, region_order=tuple(zones))
            except Exception as exc:  # infeasible at extreme util
                print(f"  ceil={ceil_mw:g} util={util:.2f}  SKIP ({exc})")
                continue
            cj = cvar_upper_tail(per_day_emissions(rj.schedule, te), CVAR_ALPHA)
            cs = cvar_upper_tail(per_day_emissions(rs.schedule, te), CVAR_ALPHA)
            gap = 100 * (cs - cj) / cj
            bf = bind_fraction(rj.schedule, ceiling)
            verdict = "helps" if gap > MATERIALITY_PCT else ("hurts" if gap < -MATERIALITY_PCT else "null")
            print(f"  ceil={ceil_mw:g} util={util:.2f}  bind={bf:.2f}  spatial_gap={gap:+.3f}%  [{verdict}]")
            rows.append(dict(grid=region_set, ceiling_mw=ceil_mw, utilization=util,
                             bind_fraction=round(bf, 3), spatial_gap_pct=round(gap, 4),
                             verdict=verdict))


def main():
    rows = []
    for g in GRIDS:
        run_grid(g, rows)
    fields = ["grid", "ceiling_mw", "utilization", "bind_fraction", "spatial_gap_pct", "verdict"]
    with open(SNAPSHOT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    gaps = [r["spatial_gap_pct"] for r in rows]
    print(f"\nWrote {SNAPSHOT.relative_to(Path(__file__).resolve().parents[1])} ({len(rows)} rows)")
    print(f"spatial gap range over all capacity settings: "
          f"[{min(gaps):+.3f}%, {max(gaps):+.3f}%]; "
          f"materially helps in {sum(1 for g in gaps if g > MATERIALITY_PCT)}/{len(gaps)}")


if __name__ == "__main__":
    main()
