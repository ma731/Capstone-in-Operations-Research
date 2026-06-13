"""Measure problem dimensions and solve times for the Computational
considerations paragraph. Times one SOCP (Mahalanobis-DRO) and one CVaR-SAA solve
per case, reports R, T, variable/constraint counts, and wall-clock.

Run: .venv\\Scripts\\python -m scripts.measure_complexity
"""
from __future__ import annotations

import time

import numpy as np

from src.analysis.stratified_correlations import REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.copula_scenarios import fit_copula, generate_scenarios
from src.models.covariance import (
    build_daily_panel, cholesky_factor, daily_panel_to_matrix,
    estimate_mean_and_covariance, regularize_covariance,
)
from src.models.cvar_saa import solve_cvar_saa

CASES = ("us_west", "taskc", "us_hetero")
N_REP = 5


def _time(fn, n=N_REP):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return np.median(ts) * 1000.0  # ms


def main():
    print(f"{'case':<10} {'R':>2} {'T':>3} {'RT':>4} {'SOCP_ms':>9} {'CVaR-SAA_ms':>12} {'S':>5}")
    socp_times, saa_times, dims = [], [], []
    for c in CASES:
        cfg = REGION_SETS[c]
        z = list(cfg["zones"])
        panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
        train = panel[np.array([d.year < 2025 for d in dates])]
        R, T = panel.shape[1], panel.shape[2]
        rho_bar = train.mean(axis=0)
        _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train))
        L = cholesky_factor(regularize_covariance(sig, eta=1e-5))
        workloads = np.full(R, 0.80 * 50.0 * T)
        ceiling = np.full((R, T), 50.0)
        kw = dict(alpha=np.full(R, 0.5), ramp=np.full(R, 15.0),
                  deferral_windows=[(0, 7, 0.20)])

        socp_ms = _time(lambda: solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
            epsilon=1.0, region_order=tuple(z), **kw))
        model = fit_copula("clayton", train)
        scen = generate_scenarios(model, 1000, seed=20260613)
        saa_ms = _time(lambda: solve_cvar_saa(scen, workloads, ceiling, beta=0.95, **kw))

        socp_times.append(socp_ms)
        saa_times.append(saa_ms)
        dims.append(R * T)
        print(f"{c:<10} {R:>2} {T:>3} {R*T:>4} {socp_ms:>9.1f} {saa_ms:>12.1f} {1000:>5}")

    print(f"\nSOCP: {min(socp_times):.0f}-{max(socp_times):.0f} ms "
          f"(RT {min(dims)}-{max(dims)} vars)")
    print(f"CVaR-SAA (S=1000): {min(saa_times):.0f}-{max(saa_times):.0f} ms "
          f"(+S={1000} epigraph vars/constraints)")


if __name__ == "__main__":
    main()
