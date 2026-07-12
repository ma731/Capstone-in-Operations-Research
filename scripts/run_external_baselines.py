"""run_external_baselines.py -- how does the scheduler compare to PUBLISHED
approaches, not just to its own ablations?

The thesis's internal arms (deterministic vs robust vs joint vs shuffled) answer
"which layer of sophistication pays." A journal reviewer will additionally ask
"and how does any of it compare to what the literature already does?" This script
evaluates three literature-style policies on the SAME feasible set (workload,
per-cell ceiling) and the SAME out-of-sample panel as the headline experiments:

  B0  carbon-agnostic  -- workload spread uniformly across each region's hours,
      no carbon signal at all: the do-nothing status quo.
  B1  greedy time-shift -- within each region, pack work into the hours with the
      lowest mean train carbon intensity, up to the ceiling. The heuristic family
      of Google's carbon-intelligent computing platform (Radovanovic et al., 2023,
      IEEE Trans. Power Systems: temporal shifting of flexible load using
      day-ahead carbon forecasts, no inter-cluster moves).
  B2  threshold suspend/resume -- run only in hours whose train-mean intensity is
      below the region's q-quantile, subject to feasibility (the pause/resume
      family, e.g. Wiesner et al., Middleware 2021, "Let's wait awhile").

Against these it reports the thesis's LP time-shift (Phi=0) and transfer (Phi>0)
schedules. Expected qualitative outcome (to verify on real data): B1 approaches
the Phi=0 LP within a small gap (the LP's marginal value over greedy is modest);
the transfer lever is what none of the published temporal-only policies can reach.

Run:  python -m scripts.run_external_baselines
Writes: docs/results_snapshots/external_baselines_<date>.csv
Added post-defense (July 2026) for the journal submission's benchmarking section.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.transfer_dro import solve_transfer_dro

CEIL, UTIL = 50.0, 0.80
GRIDS = ["us_west", "taskc", "us_hetero"]
PHI_FRAC = 0.20
THRESH_Q = 0.5  # B2: run in the cleanest half of hours (feasibility permitting)


# --------------------------- pure policy builders ---------------------------
# Each returns an executed schedule x (R,T) satisfying: x >= 0, x <= ceiling,
# and per-region sum x[r,:] == workloads[r]. Pure numpy: unit-testable without
# any data or solver.

def carbon_agnostic(workloads: np.ndarray, ceiling: np.ndarray) -> np.ndarray:
    """B0: spread each region's workload uniformly over its hours (water-fill
    against the ceiling so the result is always feasible)."""
    R, T = ceiling.shape
    x = np.zeros((R, T))
    for r in range(R):
        x[r] = _water_fill_uniform(workloads[r], ceiling[r])
    return x


def greedy_time_shift(rho_bar: np.ndarray, workloads: np.ndarray,
                      ceiling: np.ndarray) -> np.ndarray:
    """B1: per region, fill the cleanest hours (lowest mean intensity) first,
    each to its ceiling, until the workload is placed."""
    R, T = rho_bar.shape
    x = np.zeros((R, T))
    for r in range(R):
        remaining = float(workloads[r])
        for t in np.argsort(rho_bar[r], kind="stable"):
            take = min(remaining, float(ceiling[r, t]))
            x[r, t] = take
            remaining -= take
            if remaining <= 1e-12:
                break
        if remaining > 1e-9:
            raise ValueError(f"infeasible: region {r} workload exceeds capacity")
    return x


def threshold_policy(rho_bar: np.ndarray, workloads: np.ndarray,
                     ceiling: np.ndarray, q: float = THRESH_Q) -> np.ndarray:
    """B2: run uniformly in hours below the region's q-quantile of mean
    intensity; if those hours cannot carry the workload, relax by admitting the
    next-cleanest hours (so the policy is always feasible, as a real pause/
    resume system must be)."""
    R, T = rho_bar.shape
    x = np.zeros((R, T))
    for r in range(R):
        order = np.argsort(rho_bar[r], kind="stable")
        k = max(1, int(np.ceil(q * T)))
        while True:
            hours = order[:k]
            cap = float(ceiling[r, hours].sum())
            if cap + 1e-9 >= workloads[r] or k == T:
                break
            k += 1  # relax: admit the next-cleanest hour
        sub_ceiling = np.zeros(T)
        sub_ceiling[hours] = ceiling[r, hours]
        x[r] = _water_fill_uniform(workloads[r], sub_ceiling)
    return x


def _water_fill_uniform(total: float, cap: np.ndarray) -> np.ndarray:
    """Distribute ``total`` across cells proportionally-uniformly without
    exceeding per-cell caps (iterative water-filling on the open cells)."""
    x = np.zeros_like(cap, dtype=float)
    open_ = cap > 0
    remaining = float(total)
    for _ in range(len(cap)):
        n = int(open_.sum())
        if remaining <= 1e-12 or n == 0:
            break
        share = remaining / n
        add = np.minimum(np.where(open_, share, 0.0), cap - x)
        x += add
        remaining -= float(add.sum())
        open_ = (cap - x) > 1e-12
    if remaining > 1e-9:
        raise ValueError("infeasible: workload exceeds total capacity")
    return x


# ------------------------------- experiment --------------------------------

def evaluate(schedule: np.ndarray, test_panel: np.ndarray) -> tuple[float, float]:
    em = per_day_emissions(np.asarray(schedule), test_panel)
    return float(cvar_upper_tail(em)), float(em.mean())


def run_grid(grid: str) -> list[dict]:
    cfg = REGION_SETS[grid]
    z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    rho_bar = tr.mean(axis=0)
    wl = np.full(R, UTIL * CEIL * T)
    ceil = np.full((R, T), CEIL)
    L = np.zeros((R * T, R * T))

    y_lp0, _ = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0, transfer_budget=0.0)
    y_lpT, _ = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0,
                                  transfer_budget=PHI_FRAC * float(wl.sum()))
    policies = {
        "B0_carbon_agnostic": carbon_agnostic(wl, ceil),
        "B1_greedy_time_shift": greedy_time_shift(rho_bar, wl, ceil),
        "B2_threshold": threshold_policy(rho_bar, wl, ceil),
        "LP_time_shift_phi0": np.asarray(y_lp0),
        "LP_transfer": np.asarray(y_lpT),
    }
    c_ref, _ = evaluate(policies["B0_carbon_agnostic"], te)
    rows = []
    for name, x in policies.items():
        cv, mean = evaluate(x, te)
        rows.append(dict(grid=grid, display=DISPLAY_NAME.get(grid, grid), policy=name,
                         cvar95=cv, mean=mean,
                         cvar_reduction_vs_agnostic_pct=100.0 * (c_ref - cv) / c_ref))
    return rows


def main() -> None:
    print("External baselines vs the thesis scheduler (out-of-sample, same feasible set).\n")
    all_rows = []
    for g in GRIDS:
        rows = run_grid(g)
        all_rows += rows
        print(f"=== {DISPLAY_NAME.get(g, g)} ===")
        for r in rows:
            print(f"  {r['policy']:22s} CVaR95 {r['cvar95']:12.1f}   "
                  f"vs agnostic -{r['cvar_reduction_vs_agnostic_pct']:5.2f}%")
        print()
    stamp = dt.date.today().strftime("%Y-%m-%d")
    out = Path("docs/results_snapshots") / f"external_baselines_{stamp}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_rows).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
