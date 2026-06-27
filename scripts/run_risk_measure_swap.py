"""Generality probe: is the spatial null an artifact of the coherent objective?

A natural objection to the spatial null (Proposition 1's mean-dominance argument)
is that it leans on two structural facts: emissions are LINEAR in the uncertain
carbon vector, and CVaR is TRANSLATION-INVARIANT (cash-additive). Together these
make the mean field additively separable from the dependence-bearing residual, so a
sceptic can ask how much of the null is a property of the chosen risk measure rather
than of carbon scheduling.

This script answers that empirically. It holds the data, the feasible set, and the
out-of-sample CVaR_0.95 metric fixed, and swaps ONLY the risk functional:

  Coherent mean-std DRO  : min <rho_bar,x> + eps * sqrt(x^T Sigma x)   (the thesis)
  Non-coherent mean-var  : min <rho_bar,x> + lam * (x^T Sigma x)        (the swap)

The mean-variance objective is NOT cash-additive and gives the cross-region
covariance an explicit quadratic term to bite on (a "portfolio-variance" objective).
For each grid it re-measures the joint-vs-shuffled gap (the same shuffled-marginals
falsification as the headline null) under both objectives, sweeping the covariance
weight over several orders of magnitude, and bootstraps a 95% CI on the gap at the
weighting where the variance term balances the mean.

Result (see the archived snapshot): swapping to mean-variance moves the schedule by
up to ~30%, but does NOT make modelling covariance pay out of sample. At the balanced
weighting the joint covariance significantly WORSENS OOS CVaR on two of three grids
and helps only trivially on the third; even OOS standard deviation (the metric
mean-variance optimises) shows no robust covariance benefit, and in-sample beats
out-of-sample, the signature of overfitting. The null is therefore not an artifact of
the coherent risk measure.

Run:  python -m scripts.run_risk_measure_swap
Writes: docs/results_snapshots/risk_measure_swap_2026-06-27.csv (license-safe summary).
"""
from __future__ import annotations

import csv
from pathlib import Path

import cvxpy as cp
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
from src.models.feasible_set import build_feasible_constraints

# ----- locked config (mirrors scripts/run_case_experiment.py) -----
TRAIN_YEARS = (2021, 2022, 2023, 2024)
TEST_YEAR = 2025
UTILIZATION_FIXED = 0.80
CEILING_PER_CELL_MW = 50.0
T_HOURS = 24
RIDGE_ETA = 1e-5
CVAR_ALPHA = 0.95
BOOTSTRAP_SEED = 20260524
N_BOOTSTRAP = 1000
EPS_GRID = (0.0, 1.0, 10.0, 100.0)
LAM_MULTS = (0.1, 1.0, 10.0, 100.0, 1000.0)
GRIDS = ("us_hetero", "us_west", "taskc")

SNAPSHOT = Path(__file__).resolve().parents[1] / "docs" / "results_snapshots" / "risk_measure_swap_2026-06-27.csv"


def load_split(region_set: str):
    cfg = REGION_SETS[region_set]
    zones = list(cfg["zones"])
    tz = cfg["tz"]
    wide = to_wide(load_all_zones(zones), value_col="ci_lifecycle")
    panel, dates = build_daily_panel(wide, region_order=zones, tz=tz, expected_T=T_HOURS)
    is_tr = np.array([d.year in TRAIN_YEARS for d in dates])
    is_te = np.array([d.year == TEST_YEAR for d in dates])
    return panel[is_tr], panel[is_te], zones


def fit_sigmas(train_panel: np.ndarray):
    _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train_panel))
    R, T = train_panel.shape[1], train_panel.shape[2]
    sig_j = regularize_covariance(sig, RIDGE_ETA)
    sig_s = regularize_covariance(block_diagonal_by_region(sig, R=R, T=T), RIDGE_ETA)
    return sig_j, sig_s


def emis_stats(x: np.ndarray, panel: np.ndarray):
    e = per_day_emissions(np.asarray(x), panel)
    return cvar_upper_tail(e, CVAR_ALPHA), float(e.std())


def rel_diff(xa: np.ndarray, xb: np.ndarray) -> float:
    xa, xb = np.asarray(xa), np.asarray(xb)
    return float(np.abs(xa - xb).sum() / np.abs(xa).sum())


def solve_meanvar(rho_bar, sigma, workloads, ceiling, lam):
    R, T = rho_bar.shape
    x = cp.Variable((R, T), nonneg=True)
    cons, _ = build_feasible_constraints(x, workloads, ceiling)
    xvec = cp.hstack([x[r, :] for r in range(R)])
    mean_term = cp.sum(cp.multiply(rho_bar, x))
    var_term = cp.quad_form(xvec, cp.psd_wrap(sigma))
    prob = cp.Problem(cp.Minimize(mean_term + lam * var_term), cons)
    prob.solve(solver="CLARABEL")
    if x.value is None:
        raise RuntimeError(f"mean-variance solve failed: {prob.status}")
    return np.asarray(x.value), float(mean_term.value), float(var_term.value)


def bootstrap_gap_ci(x_joint, x_shuf, test_panel, n=N_BOOTSTRAP, seed=BOOTSTRAP_SEED):
    ej = per_day_emissions(np.asarray(x_joint), test_panel)
    es = per_day_emissions(np.asarray(x_shuf), test_panel)
    rng = np.random.default_rng(seed)
    N = len(ej)
    gaps = np.array(
        [cvar_upper_tail(es[i], CVAR_ALPHA) - cvar_upper_tail(ej[i], CVAR_ALPHA)
         for i in (rng.integers(0, N, size=N) for _ in range(n))]
    )
    point = cvar_upper_tail(es, CVAR_ALPHA) - cvar_upper_tail(ej, CVAR_ALPHA)
    return point, float(np.percentile(gaps, 2.5)), float(np.percentile(gaps, 97.5))


def run_grid(region_set: str, rows: list):
    tr, te, zones = load_split(region_set)
    R, T = tr.shape[1], tr.shape[2]
    rho_bar = tr.mean(axis=0)
    sig_j, sig_s = fit_sigmas(tr)
    L_j, L_s = cholesky_factor(sig_j), cholesky_factor(sig_s)
    workloads = np.full(R, UTILIZATION_FIXED * CEILING_PER_CELL_MW * T)
    ceiling = np.full((R, T), CEILING_PER_CELL_MW)
    print(f"\n{region_set}: R={R} zones={zones} train={len(tr)}d test={len(te)}d")

    # [A] coherent mean-std DRO (reference: reproduces the published null)
    for eps in EPS_GRID:
        rj = solve_mahalanobis_dro(rho_bar, L_j, workloads, ceiling, epsilon=eps, region_order=tuple(zones))
        rs = solve_mahalanobis_dro(rho_bar, L_s, workloads, ceiling, epsilon=eps, region_order=tuple(zones))
        cj, _ = emis_stats(rj.schedule, te)
        cs, _ = emis_stats(rs.schedule, te)
        gap_pct = 100 * (cs - cj) / cj
        rows.append(dict(grid=region_set, objective="mean_std_dro", param="epsilon", param_value=eps,
                         sched_diff_pct=round(100 * rel_diff(rj.schedule, rs.schedule), 3),
                         cvar_gap_pct=round(gap_pct, 4), oos_std_gap_pct="", is_std_gap_pct="",
                         var_over_mean="", boot_gap_pct="", boot_lo_pct="", boot_hi_pct=""))
        print(f"  DRO   eps={eps:<7g} cvar_gap={gap_pct:+.3f}%  sched_diff={100*rel_diff(rj.schedule, rs.schedule):.1f}%")

    # auto-scale lam so the variance term balances the mean term at lam=0 optimum
    _, m0, v0 = solve_meanvar(rho_bar, sig_j, workloads, ceiling, lam=0.0)
    lam_ref = m0 / v0

    # [B] non-coherent mean-variance sweep
    for mult in LAM_MULTS:
        lam = mult * lam_ref
        xj, mj, vj = solve_meanvar(rho_bar, sig_j, workloads, ceiling, lam)
        xs, _, _ = solve_meanvar(rho_bar, sig_s, workloads, ceiling, lam)
        cj, oos_sj = emis_stats(xj, te)
        cs, oos_ss = emis_stats(xs, te)
        _, is_sj = emis_stats(xj, tr)
        _, is_ss = emis_stats(xs, tr)
        boot = dict(boot_gap_pct="", boot_lo_pct="", boot_hi_pct="")
        if mult == 1.0:
            pt, lo, hi = bootstrap_gap_ci(xj, xs, te)
            boot = dict(boot_gap_pct=round(100 * pt / cj, 4),
                        boot_lo_pct=round(100 * lo / cj, 4),
                        boot_hi_pct=round(100 * hi / cj, 4))
            print(f"  MV    lam={mult}xref  cvar_gap={100*(cs-cj)/cj:+.3f}%  "
                  f"CI=[{100*lo/cj:+.3f}%, {100*hi/cj:+.3f}%]  sched_diff={100*rel_diff(xj, xs):.1f}%")
        rows.append(dict(grid=region_set, objective="mean_variance", param="lam_over_ref", param_value=mult,
                         sched_diff_pct=round(100 * rel_diff(xj, xs), 3),
                         cvar_gap_pct=round(100 * (cs - cj) / cj, 4),
                         oos_std_gap_pct=round(100 * (oos_ss - oos_sj) / oos_sj, 4),
                         is_std_gap_pct=round(100 * (is_ss - is_sj) / is_sj, 4),
                         var_over_mean=round((lam * vj) / mj, 4), **boot))


def main():
    rows: list = []
    for g in GRIDS:
        run_grid(g, rows)
    fields = ["grid", "objective", "param", "param_value", "sched_diff_pct", "cvar_gap_pct",
              "oos_std_gap_pct", "is_std_gap_pct", "var_over_mean",
              "boot_gap_pct", "boot_lo_pct", "boot_hi_pct"]
    with open(SNAPSHOT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {SNAPSHOT.relative_to(Path(__file__).resolve().parents[1])} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
