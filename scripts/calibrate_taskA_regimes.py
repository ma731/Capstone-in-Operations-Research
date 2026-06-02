"""Calibration probe for the Task A constraint regimes (TRAINING DATA ONLY).

Pre-registration transparency: this script documents HOW the deadline window
fraction (gamma) and the thermal effective-power bound (bar_P) were chosen so
that constraints 3a/3b bind LOOSELY (active in some hours, not dominant) on the
real 4-zone training panel. It NEVER touches the 2025 test set.

It solves the coupled deterministic baseline (A2b at epsilon=0) at each alpha in
{0.30, 0.50, 0.75} for candidate (gamma, bar_P) settings and reports, per
regime, the binding margins (ramp tight transitions, deadline tight windows,
thermal tight cells, min thermal slack) so a loose-binding setting can be read
off directly.

Run: python -m scripts.calibrate_taskA_regimes
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
from src.models.covariance import REGION_ORDER, build_daily_panel

UTIL = 0.80
CEILING = 50.0
T = 24
RAMP = 15.0
ALPHAS = (0.30, 0.50, 0.75)
TRAIN_YEARS = (2021, 2022, 2023, 2024)
PUE0, KAPPA, T_SET = 1.10, 0.015, 20.0


def main() -> int:
    carbon_wide = to_wide(load_all_zones(list(REGION_ORDER)))
    panel, dates = build_daily_panel(carbon_wide)
    temp_panel, temp_dates = align_temperature_to_panel(
        load_temperature_wide(REGION_ORDER), carbon_wide
    )
    assert dates.equals(temp_dates)

    is_train = np.array([d.year in TRAIN_YEARS for d in dates])
    rho_bar = panel[is_train].mean(axis=0)            # (R,T)
    R = rho_bar.shape[0]
    temp_train = temperature_field(temp_panel, dates, TRAIN_YEARS)  # (R,T)
    workloads = np.full(R, UTIL * CEILING * T)
    ceiling = np.full((R, T), CEILING)

    pue = PUE0 + KAPPA * np.maximum(temp_train - T_SET, 0.0)
    print("Training thermal field (per-cell mean temp, deg C) -- max per region:")
    print("  ", np.round(temp_train.max(axis=1), 1), "C")
    print("Implied PUE range:", round(float(pue.min()), 3), "-", round(float(pue.max()), 3))
    print("Effective demand at ceiling (pue*50) range:",
          round(float(pue.min()*CEILING), 1), "-", round(float(pue.max()*CEILING), 1))
    # cool-hour effective load (floor pue * ceiling) sets the no-bite threshold:
    floor_eff = PUE0 * CEILING
    print(f"Floor effective load (cool hours) = {floor_eff:.1f}  "
          f"(bar_P below this would bite even cool hours -> too tight)")

    # carbon diurnal trough -> where flexible work wants to go (avg local hour)
    mean_by_hour = rho_bar.mean(axis=0)
    cheap_hours = np.argsort(mean_by_hour)[:8]
    print("\nCheapest 8 local hours (where flex piles): ", sorted(cheap_hours.tolist()))
    print("Mean carbon by hour:", np.round(mean_by_hour, 0).astype(int).tolist())

    # Candidate deadline windows: a morning block [0,7] OFF the cheap solar
    # trough forces some flex out of the cheapest hours -> active but small.
    candidate_windows = {
        "morning[0,7] g=0.20": [(0, 7, 0.20)],
        "morning[0,7] g=0.30": [(0, 7, 0.30)],
        "evening[18,23] g=0.20": [(18, 23, 0.20)],
    }
    candidate_barP = [57.0, 60.0, 63.0]   # all >= floor_eff(55) so cool hours free

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
                    tight_def = b.get("deferral_tight_windows", 0)
                    print(f"  alpha={a:.2f}: FEASIBLE  ramp_tight={b.get('ramp_tight_transitions')}/{R*(T-1)}"
                          f"  thermal_tight={b.get('thermal_tight_cells')}/{R*T}"
                          f"  thermal_min_slack={b.get('thermal_min_margin'):+.2f}"
                          f"  deadline_tight={tight_def}/{len(dm)}")
                except Exception as e:  # noqa: BLE001
                    print(f"  alpha={a:.2f}: INFEASIBLE/err -> {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
