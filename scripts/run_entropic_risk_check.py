"""Does the spatial null survive a metric whose risk term is variance-sensitive?

The risk-measure swap (scripts/run_risk_measure_swap.py) optimised a covariance-amplifying
mean-variance objective but still SCORED out of sample on CVaR. CVaR is linear in the
emission standard deviation s = sqrt(x^T Sigma x), so a sceptic can argue covariance had
little CURVATURE to bite on in the score. This script scores on the metric that objective
targets: the ENTROPIC (exponential-utility) risk

    rho_theta(E) = (1/theta) log E[ exp(theta E) ],

whose risk term, for a Gaussian residual, is (theta/2) s^2 -- QUADRATIC in the same s, so
covariance gets its strongest curvature-based purchase. Note (this matters): entropic risk
is itself translation-invariant, rho_theta(E+c) = rho_theta(E)+c, so this is NOT an escape
from the mean/residual decomposition the swap was accused of leaning on; what changes versus
CVaR is the curvature of the risk term, not the separability of the mean.

For a Gaussian field the entropic-optimal schedule is exactly the mean-variance schedule
with lam = theta/2, so we reuse that schedule and score it on OUT-OF-SAMPLE entropic risk of
2025 emissions, sweeping risk aversion theta = C / std(in-sample emissions) from mild to
severe.

INTERPRETIVE CAVEAT (read before quoting any single row). As theta grows, rho_theta
concentrates on the worst held-out days; we report the participation ratio EFF_DAYS (the
effective number of days carrying the statistic) so the reader can see this. At severe theta
EFF_DAYS collapses to a handful of 2025 days: there the statistic is NO LONGER variance-like
but near-worst-case, and the percentile bootstrap is unreliable for such a max-dominated
functional. The DEFENSIBLE regime is MODERATE theta (C ~ 2), where the schedule already
relocates 7-13% of compute yet EFF_DAYS still spans ~50-70 of the ~360 held-out days. There,
modelling the joint covariance changes OOS entropic risk by under 0.1% on all three grids:
the variance-curvature metric the swap was accused of dodging shows no covariance benefit.
At severe theta the outcome is grid-specific and we do NOT rely on it -- on the strongly
correlated Eastern belt a small covariance benefit appears, on the other two a few-day
adverse gap -- because the metric has degenerated to a near-worst-case statistic.

Run:  python -m scripts.run_entropic_risk_check
Writes: docs/results_snapshots/entropic_risk_check_2026-06-27.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

import cvxpy as cp
import numpy as np

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.stratified_correlations import REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import (
    block_diagonal_by_region,
    build_daily_panel,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
)
from src.models.feasible_set import build_feasible_constraints

# ----- locked config (mirrors scripts/run_risk_measure_swap.py) -----
TRAIN_YEARS = (2021, 2022, 2023, 2024)
TEST_YEAR = 2025
UTILIZATION_FIXED = 0.80
CEILING_PER_CELL_MW = 50.0
T_HOURS = 24
RIDGE_ETA = 1e-5
CVAR_ALPHA = 0.95
BOOTSTRAP_SEED = 20260524
N_BOOTSTRAP = 1000
GRIDS = ("us_hetero", "us_west", "taskc")
# dimensionless risk aversion: theta = C / std(in-sample emissions of the mean-optimal
# schedule). C=2 is the headline "moderate" regime (non-degenerate); C=4,8 are reported
# only to show the metric degenerates to near-worst-case (see EFF_DAYS).
C_GRID = (0.5, 1.0, 2.0, 4.0, 8.0)
C_HEADLINE = 2.0
MATERIALITY_PCT = 0.4

SNAPSHOT = (Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"
            / "entropic_risk_check_2026-06-27.csv")


def load_split(region_set: str):
    cfg = REGION_SETS[region_set]
    zones = list(cfg["zones"])
    wide = to_wide(load_all_zones(zones), value_col="ci_lifecycle")
    panel, dates = build_daily_panel(wide, region_order=zones, tz=cfg["tz"], expected_T=T_HOURS)
    is_tr = np.array([d.year in TRAIN_YEARS for d in dates])
    is_te = np.array([d.year == TEST_YEAR for d in dates])
    return panel[is_tr], panel[is_te], zones


def fit_sigmas(train_panel: np.ndarray):
    _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train_panel))
    R, T = train_panel.shape[1], train_panel.shape[2]
    sig_j = regularize_covariance(sig, RIDGE_ETA)
    sig_s = regularize_covariance(block_diagonal_by_region(sig, R=R, T=T), RIDGE_ETA)
    return sig_j, sig_s


def solve_meanvar(rho_bar, sigma, workloads, ceiling, lam):
    """Mean-variance == Gaussian entropic-optimal schedule at lam = theta/2."""
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
    return np.asarray(x.value)


def entropic_risk(e: np.ndarray, theta: float) -> float:
    """rho_theta(E) = (1/theta) log mean exp(theta E), max-stabilised (any theta)."""
    a = theta * np.asarray(e, dtype=float)
    M = a.max()
    return float((M + np.log(np.mean(np.exp(a - M)))) / theta)


def effective_days(e: np.ndarray, theta: float) -> float:
    """Participation ratio of the entropic weights: ~ how many days carry the statistic.

    Equals N when theta->0 (mean, all days equal) and ->1 when one worst day dominates.
    A small value flags that rho_theta has degenerated into a near-worst-case statistic.
    """
    a = theta * np.asarray(e, dtype=float)
    a -= a.max()
    w = np.exp(a)
    w /= w.sum()
    return float(1.0 / np.sum(w ** 2))


def rel_diff(xa, xb) -> float:
    xa, xb = np.asarray(xa), np.asarray(xb)
    return float(np.abs(xa - xb).sum() / np.abs(xa).sum())


def boot_entropic_gap_ci(ej, es, theta, n=N_BOOTSTRAP, seed=BOOTSTRAP_SEED):
    rng = np.random.default_rng(seed)
    N = len(ej)
    gaps = np.empty(n)
    for k in range(n):
        idx = rng.integers(0, N, size=N)
        gaps[k] = entropic_risk(es[idx], theta) - entropic_risk(ej[idx], theta)
    base = entropic_risk(ej, theta)
    return (100 * np.percentile(gaps, 2.5) / base,
            100 * np.percentile(gaps, 97.5) / base)


def run_grid(region_set: str, rows: list):
    tr, te, zones = load_split(region_set)
    R, T = tr.shape[1], tr.shape[2]
    rho_bar = tr.mean(axis=0)
    sig_j, sig_s = fit_sigmas(tr)
    workloads = np.full(R, UTILIZATION_FIXED * CEILING_PER_CELL_MW * T)
    ceiling = np.full((R, T), CEILING_PER_CELL_MW)

    x0 = solve_meanvar(rho_bar, sig_j, workloads, ceiling, lam=0.0)
    std0 = float(per_day_emissions(x0, tr).std())
    n_test = te.shape[0]
    print(f"\n{region_set}: R={R} zones={zones} train={len(tr)}d test={n_test}d  std0={std0:.4g}")

    for c in C_GRID:
        theta = c / std0
        lam = theta / 2.0
        xj = solve_meanvar(rho_bar, sig_j, workloads, ceiling, lam)
        xs = solve_meanvar(rho_bar, sig_s, workloads, ceiling, lam)
        ej, es = per_day_emissions(xj, te), per_day_emissions(xs, te)

        ent_gap = 100 * (entropic_risk(es, theta) - entropic_risk(ej, theta)) / entropic_risk(ej, theta)
        cvar_gap = 100 * (cvar_upper_tail(es, CVAR_ALPHA) - cvar_upper_tail(ej, CVAR_ALPHA)) / cvar_upper_tail(ej, CVAR_ALPHA)
        mean_gap = 100 * (es.mean() - ej.mean()) / ej.mean()
        sched = 100 * rel_diff(xj, xs)
        lo, hi = boot_entropic_gap_ci(ej, es, theta)
        eff = effective_days(ej, theta)          # effective days on the joint schedule
        # symmetric, point-estimate verdict at the materiality margin
        verdict = "helps" if ent_gap > MATERIALITY_PCT else ("hurts" if ent_gap < -MATERIALITY_PCT else "null")
        degenerate = eff < 0.1 * n_test          # flag near-worst-case collapse
        print(f"  C={c:<4g} sched={sched:5.1f}%  eff_days={eff:5.1f}/{n_test}  "
              f"entropic_gap={ent_gap:+.3f}% CI=[{lo:+.3f},{hi:+.3f}]  "
              f"cvar={cvar_gap:+.3f}% mean={mean_gap:+.3f}%  [{verdict}{' DEGENERATE' if degenerate else ''}]")
        rows.append(dict(grid=region_set, c_riskaversion=c, theta=f"{theta:.6g}",
                         sched_diff_pct=round(sched, 3), eff_days=round(eff, 1), n_test=n_test,
                         entropic_gap_pct=round(ent_gap, 4),
                         entropic_ci_lo=round(lo, 4), entropic_ci_hi=round(hi, 4),
                         cvar_gap_pct=round(cvar_gap, 4), mean_gap_pct=round(mean_gap, 4),
                         verdict=verdict, degenerate=int(degenerate)))


def main():
    rows: list = []
    for g in GRIDS:
        run_grid(g, rows)
    fields = ["grid", "c_riskaversion", "theta", "sched_diff_pct", "eff_days", "n_test",
              "entropic_gap_pct", "entropic_ci_lo", "entropic_ci_hi",
              "cvar_gap_pct", "mean_gap_pct", "verdict", "degenerate"]
    with open(SNAPSHOT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {SNAPSHOT.relative_to(Path(__file__).resolve().parents[1])} ({len(rows)} rows)")

    head = [r for r in rows if r["c_riskaversion"] == C_HEADLINE]
    worst = max(abs(r["entropic_gap_pct"]) for r in head)
    eff_lo = min(r["eff_days"] for r in head)
    sched_lo = min(r["sched_diff_pct"] for r in head)
    print(f"\nHEADLINE (moderate risk aversion C={C_HEADLINE}, non-degenerate):")
    print(f"  schedule moves >= {sched_lo:.1f}% of compute, statistic spans >= {eff_lo:.0f} effective days,")
    print(f"  yet |OOS entropic gap| <= {worst:.3f}% on every grid (materiality {MATERIALITY_PCT}%).")
    deg = [r for r in rows if r["degenerate"]]
    print(f"Degenerate (near-worst-case) rows at severe theta, reported but NOT relied upon: "
          f"{len(deg)}/{len(rows)} -> {sorted(set(r['grid'] for r in deg))}")


if __name__ == "__main__":
    main()
