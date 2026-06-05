"""Calibration probe for the IBERIAN (ES-PT-FR) constraint regimes.

Task B counterpart of scripts/calibrate_taskA_regimes.py. The constraint LOGIC
is locked (Task A); only the binding PARAMETERS are re-calibrated to Iberian
TRAINING data, with the same loose-binding discipline (active in some hours,
not dominant). NEVER touches the 2025 test set.

Iberian climate/grid differs from California/Nevada: ES (Madrid) hot continental
summers, PT (Lisbon) milder Atlantic, FR (Paris) cool and nuclear-dominated
(carbon ~50 vs ES/PT ~160). So thermal will bite mainly in ES summer; the
California bar_P=57 is NOT reused.

Run: python -m scripts.calibrate_iberia_regimes
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
    DEFAULT_TZ_IBERIA,
    REGION_ORDER_IBERIA,
    build_daily_panel,
    cholesky_factor,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
)

UTIL = 0.80
CEILING = 50.0           # same abstract capacity unit as Task A (comparability)
T = 24
RAMP = 15.0              # same as Task A (30% of ceiling) -- kept for comparability
ALPHAS = (0.30, 0.50, 0.75)
TRAIN_YEARS = (2021, 2022, 2023, 2024)
PUE0, KAPPA, T_SET = 1.10, 0.015, 20.0   # same PUE shape; bar_P re-calibrated


def main() -> int:
    zones = list(REGION_ORDER_IBERIA)
    carbon_wide = to_wide(load_all_zones(zones))
    panel, dates = build_daily_panel(carbon_wide, region_order=zones, tz=DEFAULT_TZ_IBERIA)
    temp_panel, temp_dates = align_temperature_to_panel(
        load_temperature_wide(zones), carbon_wide,
        region_order=zones, tz=DEFAULT_TZ_IBERIA,
    )
    assert dates.equals(temp_dates)

    is_train = np.array([d.year in TRAIN_YEARS for d in dates])
    rho_bar = panel[is_train].mean(axis=0)
    R = rho_bar.shape[0]
    temp_train = temperature_field(temp_panel, dates, TRAIN_YEARS)
    workloads = np.full(R, UTIL * CEILING * T)
    ceiling = np.full((R, T), CEILING)

    pue = PUE0 + KAPPA * np.maximum(temp_train - T_SET, 0.0)
    print("Iberian training thermal field (per-cell mean temp) -- max per zone:")
    for r, z in enumerate(zones):
        print(f"  {z}: max {temp_train[r].max():.1f} C  PUE max {pue[r].max():.3f}")
    print("PUE range:", round(float(pue.min()), 3), "-", round(float(pue.max()), 3))
    floor_eff = PUE0 * CEILING
    print(f"Floor effective load (cool cells) = {floor_eff:.1f}  "
          f"(bar_P below this bites even cool cells -> too tight)")
    print(f"Effective demand at ceiling (pue*{CEILING:.0f}) max = "
          f"{(pue*CEILING).max():.1f}")

    mean_by_hour = rho_bar.mean(axis=0)
    print("\nMean carbon by local hour:", np.round(mean_by_hour, 0).astype(int).tolist())
    print("Cheapest 8 local hours:", sorted(np.argsort(mean_by_hour)[:8].tolist()))

    # Candidate deadline windows (off the cheap hours) and thermal bounds.
    candidate_windows = {
        "morning[0,7] g=0.20": [(0, 7, 0.20)],
        "morning[0,7] g=0.30": [(0, 7, 0.30)],
        "evening[17,23] g=0.20": [(17, 23, 0.20)],
    }
    candidate_barP = [56.0, 58.0, 60.0]

    for win_label, win in candidate_windows.items():
        for bar_P in candidate_barP:
            print(f"\n=== deadline {win_label} | bar_P={bar_P} ===")
            for a in ALPHAS:
                alpha = np.full(R, a)
                try:
                    res = schedule_deterministic_coupled(
                        rho_bar, workloads, ceiling, p_max=None, alpha=alpha,
                        ramp=np.full(R, RAMP), deferral_windows=win,
                        temperature=temp_train, bar_P=bar_P,
                        pue0=PUE0, kappa=KAPPA, t_set=T_SET,
                    )
                    b = res.binding
                    dm = b.get("deferral_margins", [])
                    print(f"  alpha={a:.2f}: FEAS  ramp={b.get('ramp_tight_transitions')}/{R*(T-1)}"
                          f"  thermal={b.get('thermal_tight_cells')}/{R*T}"
                          f"  th_slack={b.get('thermal_min_margin'):+.2f}"
                          f"  deadline={b.get('deferral_tight_windows')}/{len(dm)}")
                except Exception as e:  # noqa: BLE001
                    print(f"  alpha={a:.2f}: INFEASIBLE/err -> {type(e).__name__}: {e}")

    # Goldilocks probe on the FULL regime (R2) for a chosen candidate.
    print("\n--- Goldilocks: does the DRO move on R2 (full)? (joint L) ---")
    _, S = estimate_mean_and_covariance(daily_panel_to_matrix(panel[is_train]))
    L = cholesky_factor(regularize_covariance(S))
    win = [(0, 7, 0.20)]
    bar_P = 58.0
    for a in ALPHAS:
        alpha = np.full(R, a)
        kw = dict(p_max=None, alpha=alpha, ramp=np.full(R, RAMP),
                  deferral_windows=win, temperature=temp_train, bar_P=bar_P,
                  pue0=PUE0, kappa=KAPPA, t_set=T_SET)
        x0 = solve_mahalanobis_dro(rho_bar, L, workloads, ceiling, 0.0, region_order=zones, **kw).schedule
        mv = max(float(np.abs(solve_mahalanobis_dro(rho_bar, L, workloads, ceiling, e, region_order=zones, **kw).schedule - x0).sum())
                 for e in (1.0, 10.0, 100.0, 1000.0))
        print(f"  R2 alpha={a:.2f}: max reallocation {mv:8.1f} MWh = {100*mv/workloads.sum():5.1f}% of work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
