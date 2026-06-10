"""Calibrate the 3c variable-capacity ceiling bounds (x_min, x_max) to a
loosely-binding 'Goldilocks' regime.

The 3c CFE-driven ceiling is x_bar_{r,t} = x_min + (x_max - x_min) * CFE_{r,t}/100.
We want it to BIND (the constraint is active -- it shapes the schedule away from
low-CFE hours) but not FREEZE (the schedule keeps real freedom; the problem stays
feasible with headroom). This script sweeps candidate (x_min, x_max) pairs and
reports, for the R2 regime schedule (eps=1, alpha=0.5, deadline+ramp+split):

  feasible      : did the SOCP solve
  bind_frac     : fraction of (region, hour) cells at the ceiling (x >= ceil - tol)
  mean_slack%   : mean (ceil - x)/ceil over all cells (headroom; 0 = frozen)
  cap_margin%   : (total ceiling capacity - total workload) / workload, min over regions

Goldilocks target (heuristic): feasible everywhere, bind_frac in ~[0.10, 0.45],
mean_slack% comfortably > 0, cap_margin% > 0 for every region. The recommended
pair is the feasible candidate whose bind_frac is closest to 0.25 with positive
margin.

Run:
    .venv\\Scripts\\python -m scripts.calibrate_capacity --region-set us_west
    .venv\\Scripts\\python -m scripts.calibrate_capacity --region-set all
"""
from __future__ import annotations

import argparse

import numpy as np

from src.analysis.stratified_correlations import REGION_SETS
from src.data.capacity import build_cfe_panel, capacity_from_cfe, cfe_field
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    build_daily_panel,
    cholesky_factor,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
)

# Must match the locked experiment config (run_case_experiment.py).
UTILIZATION_FIXED = 0.80
CEILING_PER_CELL_MW = 50.0
T_HOURS = 24
TRAIN_YEARS = (2021, 2022, 2023, 2024)
RIDGE_ETA = 1e-5
RAMP_PER_REGION = 15.0
DEADLINE_WINDOW = (0, 7)
DEADLINE_GAMMA = 0.20
EPS_CAL = 1.0          # the CV-selected radius across all cases
ALPHA_CAL = 0.50
BIND_TOL = 1e-3        # relative tolerance for 'at the ceiling'

# Candidate bounds: (x_min, x_max). Current provisional pair is (42, 65).
CANDIDATES = [
    (35.0, 60.0), (40.0, 60.0), (42.0, 65.0), (45.0, 65.0),
    (40.0, 70.0), (45.0, 70.0), (48.0, 72.0), (50.0, 75.0),
]
GOLDILOCKS_TARGET = 0.25


def _load(region_set: str):
    cfg = REGION_SETS[region_set]
    zones, tz = list(cfg["zones"]), cfg["tz"]
    panel, dates = build_daily_panel(to_wide(load_all_zones(zones))[zones],
                                     region_order=zones, tz=tz)
    cfe_panel, cfe_dates = build_cfe_panel(zones, tz=tz)
    is_train = np.array([d.year in TRAIN_YEARS for d in dates])
    train_panel = panel[is_train]
    field = cfe_field(cfe_panel, cfe_dates, TRAIN_YEARS)
    field = np.nan_to_num(field, nan=float(np.nanmean(field)))
    return zones, train_panel, field


def _schedule_R2(train_panel, ceiling, zones):
    rho_bar = train_panel.mean(axis=0)
    R, T = rho_bar.shape
    samples = daily_panel_to_matrix(train_panel)
    _, sigma = estimate_mean_and_covariance(samples)
    L = cholesky_factor(regularize_covariance(sigma, eta=RIDGE_ETA))
    workloads = np.full(R, UTILIZATION_FIXED * CEILING_PER_CELL_MW * T)
    res = solve_mahalanobis_dro(
        rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
        epsilon=EPS_CAL, alpha=np.full(R, ALPHA_CAL),
        ramp=np.full(R, RAMP_PER_REGION), region_order=tuple(zones),
        deferral_windows=[(DEADLINE_WINDOW[0], DEADLINE_WINDOW[1], DEADLINE_GAMMA)],
    )
    return res.schedule


def _diagnostics(x, ceiling, train_panel, zones):
    R, T = ceiling.shape
    workloads = UTILIZATION_FIXED * CEILING_PER_CELL_MW * T
    at_ceiling = x >= ceiling * (1.0 - BIND_TOL)
    bind_frac = float(at_ceiling.mean())
    mean_slack = float(np.mean((ceiling - x) / np.maximum(ceiling, 1e-9)))
    cap_per_region = ceiling.sum(axis=1)              # MWh available per region
    cap_margin = float(np.min((cap_per_region - workloads) / workloads))
    return bind_frac, mean_slack * 100.0, cap_margin * 100.0


def calibrate(region_set: str) -> dict:
    zones, train_panel, field = _load(region_set)
    print(f"\n=== {region_set}  ({', '.join(zones)}) ===")
    print(f"  {'x_min':>5} {'x_max':>5} | {'feasible':>8} {'bind_frac':>9} "
          f"{'mean_slack%':>11} {'cap_margin%':>11}")
    best = None
    for x_min, x_max in CANDIDATES:
        ceiling = capacity_from_cfe(field, x_min, x_max)
        try:
            x = _schedule_R2(train_panel, ceiling, zones)
            feasible = x is not None and np.all(np.isfinite(x))
        except Exception as e:  # noqa: BLE001
            feasible, x = False, None
            note = f"  ({type(e).__name__})"
        else:
            note = ""
        if feasible:
            bf, ms, cm = _diagnostics(x, ceiling, train_panel, zones)
            flag = ""
            if cm > 0 and 0.10 <= bf <= 0.45:
                score = abs(bf - GOLDILOCKS_TARGET)
                if best is None or score < best[0]:
                    best = (score, x_min, x_max, bf, ms, cm)
                    flag = "  <- candidate"
            print(f"  {x_min:>5.0f} {x_max:>5.0f} | {'yes':>8} {bf:>9.3f} "
                  f"{ms:>11.2f} {cm:>11.1f}{flag}")
        else:
            print(f"  {x_min:>5.0f} {x_max:>5.0f} | {'NO':>8}{note}")
    if best:
        _, xm, xx, bf, ms, cm = best
        print(f"  GOLDILOCKS -> x_min={xm:.0f}, x_max={xx:.0f} "
              f"(bind_frac={bf:.3f}, slack={ms:.1f}%, margin={cm:.1f}%)")
        return {"region_set": region_set, "x_min": xm, "x_max": xx,
                "bind_frac": bf, "mean_slack_pct": ms, "cap_margin_pct": cm}
    print("  GOLDILOCKS -> none of the candidates met the target band")
    return {"region_set": region_set, "x_min": None, "x_max": None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region-set", default="all",
                    choices=("us_west", "taskc", "us_hetero", "all"))
    args = ap.parse_args()
    sets = ("us_west", "taskc", "us_hetero") if args.region_set == "all" else (args.region_set,)
    results = [calibrate(rs) for rs in sets]
    print("\n" + "=" * 64)
    print("SUMMARY (recommended Goldilocks bounds per case)")
    print("=" * 64)
    for r in results:
        if r["x_min"] is not None:
            print(f"  {r['region_set']:10s} x_min={r['x_min']:.0f} x_max={r['x_max']:.0f} "
                  f"| bind={r['bind_frac']:.3f} slack={r['mean_slack_pct']:.1f}% "
                  f"margin={r['cap_margin_pct']:.1f}%")
        else:
            print(f"  {r['region_set']:10s} (no candidate in target band)")


if __name__ == "__main__":
    main()
