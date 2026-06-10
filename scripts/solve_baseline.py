"""Solve the deterministic coupled baseline on real Electricity Maps data.

This is a demonstration / smoke script: it loads a region set's carbon-intensity
panel, computes the training-period mean carbon field (the same rho_bar that
Algorithm 2b uses at epsilon=0), and solves the coupled deterministic baseline
(schedule_deterministic_coupled) over the calibrated feasible set.

It solves TWICE -- once with cvxpy's free default solver, once with Gurobi -- and
prints total carbon, solver status, and wall-clock time for each, so the two can
be compared directly. If Gurobi is not licensed/available, that arm is skipped
with a clear message rather than crashing.

Run:
    .venv\\Scripts\\python -m scripts.solve_baseline                 # Task C (default)
    .venv\\Scripts\\python -m scripts.solve_baseline --region-set taskA
    .venv\\Scripts\\python -m scripts.solve_baseline --alpha 0.75

The feasible-set numbers mirror the locked Task A calibration
(see thesis/full_formulation.md): ceiling 50 MW, utilization 0.80, ramp 15 MW/h,
deadline window [0,7] gamma=0.20. Thermal (3b) is intentionally OFF here -- this
is the R1 "lean" regime baseline. Carbon is reported in tonnes CO2eq.
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from src.data.capacity import build_cfe_panel, capacity_from_cfe, cfe_field
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_1 import schedule_deterministic_coupled
from src.models.covariance import build_daily_panel

# Region sets. Each entry: (zone order, common reference clock).
# Task C is the Ontario-anchored Eastern-Interconnection hunt (this thesis step).
REGION_SETS = {
    "taskC": (
        ["CA-ON", "US-NY-NYIS", "US-MIDW-MISO", "US-MIDA-PJM"],
        "America/Toronto",   # Ontario anchor; NYIS/PJM are Eastern, MISO partly
                             # Central -> a stated common-reference-clock choice
                             # (mirrors Task A's single LA clock, Task B's Madrid).
    ),
    "taskA": (
        ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-NW-NEVP"],
        "America/Los_Angeles",
    ),
    "taskB": (["ES", "PT", "FR"], "Europe/Madrid"),
}

TRAIN_YEARS = [2021, 2022, 2023, 2024]   # 2025 held out as test (matches the studies)


def build_rho_bar(zones: list[str], tz: str) -> np.ndarray:
    """Training-mean carbon field (R, T) in gCO2eq/kWh from real EM data."""
    long_df = load_all_zones(zones, years=TRAIN_YEARS)
    wide = to_wide(long_df)                       # index=UTC, one col per zone
    panel, dates = build_daily_panel(wide, region_order=zones, tz=tz)  # (N, R, T)
    print(f"  panel: {panel.shape[0]} complete days x R={panel.shape[1]} x T={panel.shape[2]}"
          f"  ({dates.min().date()} -> {dates.max().date()})")
    return panel.mean(axis=0)                     # (R, T) training mean


def solve_with(solver_name, rho_bar, W, ceiling, alpha_vec, ramp_vec):
    """Solve the coupled baseline with the named solver; return (result, secs).

    solver_name=None uses cvxpy's default free solver. Returns (None, None) and
    prints a message if the solver is unavailable (e.g. Gurobi unlicensed).
    """
    label = solver_name or "default (free)"
    try:
        t0 = time.perf_counter()
        res = schedule_deterministic_coupled(
            carbon_intensity=rho_bar,
            workloads=W,
            ceiling=ceiling,
            alpha=alpha_vec,
            ramp=ramp_vec,
            deferral_windows=[(0, 7, 0.20)],   # 3a: morning deadline on flex work
            solver=solver_name,
        )
        secs = time.perf_counter() - t0
        tonnes = res.total_carbon / 1e6   # gCO2 -> tonnes
        print(f"  [{label:>16}] status={res.solver_status:18s} "
              f"carbon={tonnes:10.2f} t  time={secs*1000:7.1f} ms")
        return res, secs
    except Exception as exc:   # noqa: BLE001 -- want a friendly catch-all here
        msg = str(exc).splitlines()[0][:90]
        print(f"  [{label:>16}] UNAVAILABLE -> {msg}")
        return None, None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region-set", default="taskC", choices=sorted(REGION_SETS))
    ap.add_argument("--alpha", type=float, default=0.50,
                    help="inflexible fraction in [0,1] (default 0.50)")
    ap.add_argument("--variable-capacity", action="store_true",
                    help="Task C 3c: CFE-driven ceiling instead of a flat 50 MW")
    ap.add_argument("--cap-min", type=float, default=42.0,
                    help="ceiling floor (MW) at CFE=0  (--variable-capacity)")
    ap.add_argument("--cap-max", type=float, default=65.0,
                    help="ceiling cap (MW) at CFE=100 (--variable-capacity)")
    args = ap.parse_args()

    zones, tz = REGION_SETS[args.region_set]
    R = len(zones)
    print(f"\n=== Baseline solve: {args.region_set}  zones={zones}  tz={tz} ===")

    rho_bar = build_rho_bar(zones, tz)
    T = rho_bar.shape[1]

    # Feasible-set calibration (Task A numbers; see full_formulation.md).
    W = np.full(R, 0.80 * 50.0 * T)               # utilization 0.80 -> 960 MWh
    alpha_vec = np.full(R, args.alpha)
    ramp_vec = np.full(R, 15.0)                    # Delta = 15 MW/h

    if args.variable_capacity:
        # 3c: per-cell ceiling = capacity_from_cfe(training-mean CFE field).
        cfe_panel, cfe_dates = build_cfe_panel(zones, tz=tz)
        field = cfe_field(cfe_panel, cfe_dates, years=TRAIN_YEARS)   # (R, T) %
        ceiling = capacity_from_cfe(field, args.cap_min, args.cap_max)
        print(f"  ceiling: VARIABLE (CFE-driven, [{args.cap_min:.0f},{args.cap_max:.0f}] MW); "
              f"per-region mean ceiling = "
              f"{', '.join(f'{z}={ceiling[r].mean():.1f}' for r, z in enumerate(zones))}")
    else:
        ceiling = np.full((R, T), 50.0)           # flat x_bar = 50 MW per cell
        print("  ceiling: FLAT 50 MW")

    print(f"  feasible set: W={W[0]:.0f} MWh/region, "
          f"alpha={args.alpha}, ramp=15, deadline=[0,7] gamma=0.20\n")

    res_free, t_free = solve_with(None, rho_bar, W, ceiling, alpha_vec, ramp_vec)
    res_hi, t_hi = solve_with("HIGHS", rho_bar, W, ceiling, alpha_vec, ramp_vec)

    # Cross-check: both solvers should agree on the optimum (same LP). HiGHS is
    # the project solver (free, reliable, no license/IP restrictions -- Bissan's
    # recommendation); the default arm is whatever cvxpy picks.
    if res_free is not None and res_hi is not None:
        gap = abs(res_free.total_carbon - res_hi.total_carbon) / res_free.total_carbon
        verdict = "agree" if gap < 1e-6 else f"DIFFER ({gap:.2e})"
        print(f"\n  cross-check: default vs HiGHS {verdict}")
    elif res_hi is not None:
        print("\n  (solved on HiGHS.)")


if __name__ == "__main__":
    main()
