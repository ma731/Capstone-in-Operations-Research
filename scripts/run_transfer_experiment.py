"""PART 3 — the proper test: does robustifying transfer against FORECAST ERROR
(not residual variability) finally pay?

Setup that fixes the prototype's mismatch:
  * Forecast model: PERSISTENCE -- plan day d on day (d-1)'s realized carbon. A
    realistic naive day-ahead forecast whose error is the day-over-day change.
  * Forecast-error ambiguity set: Sigma_fe = Cov over training of (rho_d - rho_{d-1}),
    so the robust penalty hedges the *forecast error*, which is what actually hurts.
  * Per-day rolling evaluation on real 2025: plan deterministic (eps=0) and robust
    (eps>0, L_fe) transfer schedules on the forecast, score on the realized day.

If the best robust eps beats deterministic by a margin -> robustness pays once the
decision is active and the ambiguity set matches the real uncertainty. If not, the
mean-dominance result extends even here.

Run: .venv\\Scripts\\python -m scripts.run_transfer_experiment [grid] [stride]
"""
from __future__ import annotations

import sys

import numpy as np

from scripts.prototype_transfer_dro import solve_transfer
from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import (
    build_daily_panel, cholesky_factor, daily_panel_to_matrix, regularize_covariance,
)

CEIL, UTIL = 50.0, 0.80
GRID = sys.argv[1] if len(sys.argv) > 1 else "us_west"
STRIDE = int(sys.argv[2]) if len(sys.argv) > 2 else 2   # subsample test days for speed
EPS_GRID = [0.0, 0.3, 1.0, 3.0, 10.0]                   # 0 = deterministic


def main():
    cfg = REGION_SETS[GRID]
    z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                     region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr = panel[yrs < 2025]
    te_idx = np.where(yrs == 2025)[0]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T)
    ceil = np.full((R, T), CEIL)
    Phi = 2.0 * wl.sum()                                # free transfer

    # forecast-error (persistence) covariance from training
    fe = daily_panel_to_matrix(tr[1:]) - daily_panel_to_matrix(tr[:-1])
    Sig_fe = np.cov(fe, rowvar=False)
    L_fe = cholesky_factor(regularize_covariance(Sig_fe, eta=1e-5))

    # rolling per-day eval (persistence forecast = previous day's real carbon)
    use = [i for i in te_idx if i - 1 >= 0][::STRIDE]
    print(f"=== PART 3: {DISPLAY_NAME[GRID]} | persistence forecast, "
          f"forecast-error ambiguity | {len(use)} test days (stride {STRIDE}) ===")
    em = {e: [] for e in EPS_GRID}
    for i in use:
        forecast = panel[i - 1]                         # day d-1 realized = day d forecast
        realized = panel[i]
        for e in EPS_GRID:
            y, _ = solve_transfer(forecast, L_fe, wl, ceil, epsilon=e, Phi=Phi)
            em[e].append(float(np.einsum("rt,rt->", y, realized)))

    det = cvar_upper_tail(np.array(em[0.0]))
    print(f"\n  {'eps':>6} {'CVaR_2025':>11} {'vs deterministic':>17}")
    best = (0.0, det)
    for e in EPS_GRID:
        cv = cvar_upper_tail(np.array(em[e]))
        gain = 100 * (det - cv) / det
        tag = " (deterministic)" if e == 0 else ""
        print(f"  {e:>6.1f} {cv:>11.0f} {gain:>15.2f}%{tag}")
        if e > 0 and cv < best[1]:
            best = (e, cv)
    print(f"\n  best robust eps={best[0]:.1f}: "
          f"{100*(det-best[1])/det:+.2f}% vs deterministic transfer")
    print("  (positive => robustness pays once the ambiguity set matches "
          "forecast error)")


if __name__ == "__main__":
    main()
