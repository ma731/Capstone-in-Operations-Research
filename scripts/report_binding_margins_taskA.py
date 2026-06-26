"""Binding-margin report per regime (Gate 3 support).

Reconstructs, for each regime x alpha, the deterministic (epsilon=0) schedule
on the FULL training data and reports which constraints bind and by how much,
plus a Goldilocks 'can the DRO still move' probe (||x_eps - x_0||_1 vs total
work). This is the binding-margin half of the planning hand-back.

Reads only training data + the locked config; does not touch the test set and
does not re-score emissions, so it is safe to run any number of times.

Run: python -m scripts.report_binding_margins_taskA
"""
from __future__ import annotations

import numpy as np

from src.data.electricitymaps import load_all_zones, to_wide
from src.data.temperature import (
    align_temperature_to_panel,
    load_temperature_wide,
    temperature_field,
)
from src.models.algorithm_1 import schedule_deterministic_coupled
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    REGION_ORDER,
    build_daily_panel,
    cholesky_factor,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
)
from scripts.run_shuffled_marginals_taskA_experiment import (
    ALPHA_LEVELS,
    BAR_P,
    CEILING_PER_CELL_MW,
    DEADLINE_GAMMA,
    DEADLINE_WINDOW,
    KAPPA,
    PUE0,
    RAMP_PER_REGION,
    REGIME_ORDER,
    REGIMES,
    T_SET,
    TRAIN_YEARS,
    UTILIZATION_FIXED,
)


def main() -> int:
    carbon_wide = to_wide(load_all_zones(list(REGION_ORDER)))
    panel, dates = build_daily_panel(carbon_wide)
    temp_panel, _ = align_temperature_to_panel(load_temperature_wide(REGION_ORDER), carbon_wide)
    is_train = np.array([d.year in TRAIN_YEARS for d in dates])
    rho_bar = panel[is_train].mean(axis=0)
    R, T = rho_bar.shape
    thermal = temperature_field(temp_panel, dates, TRAIN_YEARS)
    W = np.full(R, UTILIZATION_FIXED * CEILING_PER_CELL_MW * T)
    ceiling = np.full((R, T), CEILING_PER_CELL_MW)
    _, S = estimate_mean_and_covariance(daily_panel_to_matrix(panel[is_train]))
    L = cholesky_factor(regularize_covariance(S))

    print("=" * 92)
    print("BINDING-MARGIN REPORT (epsilon=0 deterministic schedule on full training data)")
    print("Cap is DROPPED in every regime. ramp tights / (R*(T-1)=92), thermal tights / (R*T=96)")
    print("=" * 92)
    header = (f"{'regime':14s} {'alpha':>5s} {'ramp_tight':>10s} {'therm_tight':>11s} "
              f"{'therm_slack':>11s} {'dead_tight':>10s} {'DRO_move_%work':>14s} {'verdict':>20s}")
    print(header)
    for regime_key in REGIME_ORDER:
        spec = REGIMES[regime_key]
        for a in ALPHA_LEVELS:
            alpha = np.full(R, a)
            kw = dict(p_max=None, alpha=alpha, ramp=np.full(R, RAMP_PER_REGION))
            if spec["deadline"]:
                kw["deferral_windows"] = [(DEADLINE_WINDOW[0], DEADLINE_WINDOW[1], DEADLINE_GAMMA)]
            if spec["thermal"]:
                kw.update(temperature=thermal, bar_P=BAR_P, pue0=PUE0, kappa=KAPPA, t_set=T_SET)
            res = schedule_deterministic_coupled(rho_bar, W, ceiling, **kw)
            b = res.binding
            ramp_t = b.get("ramp_tight_transitions", 0)
            therm_t = b.get("thermal_tight_cells", "-")
            therm_s = b.get("thermal_min_margin", float("nan"))
            dm = b.get("deferral_margins", [])
            dead_t = b.get("deferral_tight_windows", "-")
            dead_str = f"{dead_t}/{len(dm)}" if dm else "-"

            # Goldilocks probe: max reallocation as epsilon grows (same constraints).
            x0 = solve_mahalanobis_dro(rho_bar, L, W, ceiling, 0.0, **kw).schedule
            mv = max(
                float(np.abs(solve_mahalanobis_dro(rho_bar, L, W, ceiling, e, **kw).schedule - x0).sum())
                for e in (1.0, 10.0, 100.0, 1000.0)
            )
            frac = 100.0 * mv / float(W.sum())
            verdict = ("FROZEN" if frac < 0.5 else
                       "loose-OK" if frac <= 35 else "very-loose")
            ts = f"{therm_s:+.2f}" if isinstance(therm_s, float) and np.isfinite(therm_s) else "-"
            print(f"{regime_key:14s} {a:>5.2f} {ramp_t:>10} {str(therm_t):>11} {ts:>11} "
                  f"{dead_str:>10} {frac:>13.1f}% {verdict:>20s}")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
