"""Shuffled-marginals sensitivity experiment for the Mahalanobis-Wasserstein DRO.

DEPRECATED (kept as the locked Task A artifact): for new runs use
scripts/run_case_experiment.py --region-set {us_west,taskc,us_hetero}.

Tests the central Phase 1 empirical question of progress note v9 Section 4.3:
does the joint covariance Sigma_hat^joint produce a lower out-of-sample
CVaR_0.95 than the block-diagonal Sigma_hat^shuf when both are paired with
the Mahalanobis-Wasserstein scheduler (Algorithm 2b)?

Methodology
-----------
Three operational utilization levels are swept: {10%, 30%, 60%} of the per-
region per-hour ceiling.  For each utilization, the Wasserstein radius
epsilon is tuned separately for L_joint and L_shuf via blocked 5-fold time-
series cross-validation on the training set (2021-2024), with the
cross-validation criterion being mean validation CVaR_0.95 across folds.
The selected (epsilon*_joint, epsilon*_shuf) are then re-fit on the full
training set and evaluated once on the held-out 2025 test set.  Bootstrap
1000-resample 95% confidence intervals are reported on the
joint-minus-shuffled test CVaR gap, since with 362 test days the CVaR
average (over the worst ~18 days) has non-trivial sampling variability.

The pre-registration discipline this script supports is:
  1. Lock the script via git commit BEFORE running with `--dry-run` turned off.
  2. `--dry-run` reports CV-selected epsilon* values and CV curves without
     ever touching 2025; this is the methodological gate.
  3. Real run reads test data exactly once, at the end, and emits results.

Outputs
-------
  results/shuffled_marginals_<UTC-date>.csv  -- summary table
  results/shuffled_marginals_<UTC-date>.pkl  -- full schedules + per-day
                                                emissions for later analysis

Reference: progress_note_v9 sections 2 (Mahalanobis ground metric),
4.3 (experimental protocol), 5 (caveats).
"""
from __future__ import annotations

import argparse
import datetime as dt
import pickle
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    REGION_ORDER,
    block_diagonal_by_region,
    build_daily_panel,
    cholesky_factor,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
)

# ----------------------------------------------------------------------
# Configuration (locked at commit time; do not edit after committing
# before the test-set run -- that is the pre-registration discipline).
# ----------------------------------------------------------------------

UTILIZATION_LEVELS = (0.10, 0.30, 0.60, 0.80)
EPSILON_GRID = (0.0, 0.1, 1.0, 10.0, 100.0, 1000.0)
N_CV_FOLDS = 5
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 20260524  # date-based seed; reproducible
CVAR_ALPHA = 0.95          # mean of worst (1 - alpha) of test days
CEILING_PER_CELL_MW = 50.0
T_HOURS = 24
TRAIN_YEARS = (2021, 2022, 2023, 2024)
TEST_YEAR = 2025
RIDGE_ETA = 1e-5           # matches covariance.regularize_covariance default

RESULTS_DIR = Path("results")


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------

def cvar_upper_tail(values: np.ndarray, alpha: float = CVAR_ALPHA) -> float:
    """Mean of the worst (1 - alpha) fraction of values.

    Following the convention 'CVaR_0.95 = mean of worst 5%'.  Uses the
    upper-tail interpretation because realised emissions are a loss
    quantity (higher = worse).
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    n_tail = max(1, int(np.ceil(n * (1.0 - alpha))))
    sorted_desc = np.sort(values)[::-1]
    return float(sorted_desc[:n_tail].mean())


def per_day_emissions(schedule: np.ndarray, panel: np.ndarray) -> np.ndarray:
    """Return a length-N array of <rho_i, schedule> across the N daily samples
    in `panel`.  schedule is (R, T); panel is (N, R, T).
    """
    return np.einsum("rt,nrt->n", schedule, panel)


# ----------------------------------------------------------------------
# Blocked time-series cross-validation
# ----------------------------------------------------------------------

def blocked_fold_indices(n: int, k: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, val_idx) for k contiguous blocks of n indices.

    Each fold uses one contiguous block as validation; the other k-1
    blocks (also contiguous) as training.  This is the standard
    time-series CV pattern: no shuffling, no leakage across the temporal
    boundary.
    """
    boundaries = np.linspace(0, n, k + 1, dtype=int)
    folds = []
    all_idx = np.arange(n)
    for i in range(k):
        val_idx = all_idx[boundaries[i] : boundaries[i + 1]]
        train_idx = np.concatenate(
            [all_idx[: boundaries[i]], all_idx[boundaries[i + 1] :]]
        )
        folds.append((train_idx, val_idx))
    return folds


# ----------------------------------------------------------------------
# Core experiment
# ----------------------------------------------------------------------

@dataclass
class CVResult:
    """Outcome of cross-validating epsilon for one (utilization, Sigma) cell."""

    utilization: float
    sigma_label: str            # "joint" or "shuf"
    cv_curve: dict              # epsilon -> mean validation CVaR across folds
    cv_curve_std: dict          # epsilon -> stdev of validation CVaR across folds
    epsilon_star: float
    epsilon_star_at_boundary: bool


@dataclass
class TestResult:
    """Outcome of the final test-set evaluation for one (utilization, Sigma)."""

    utilization: float
    sigma_label: str
    epsilon_star: float
    test_cvar: float
    test_mean: float
    test_max: float
    schedule: np.ndarray
    per_day_emissions: np.ndarray


def fit_sigma_and_cholesky(
    panel: np.ndarray,
    shuffle_to_block_diagonal: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate Sigma_hat from a panel and return (Sigma_reg, L).

    If shuffle_to_block_diagonal is True, replaces the cross-region blocks
    of Sigma_hat with zeros before regularization+Cholesky, producing
    Sigma_hat^shuf.
    """
    samples = daily_panel_to_matrix(panel)              # (N, R*T)
    _, sigma_hat = estimate_mean_and_covariance(samples)
    R, T = panel.shape[1], panel.shape[2]
    if shuffle_to_block_diagonal:
        sigma_hat = block_diagonal_by_region(sigma_hat, R=R, T=T)
    sigma_reg = regularize_covariance(sigma_hat, eta=RIDGE_ETA)
    L = cholesky_factor(sigma_reg)
    return sigma_reg, L


def schedule_for(
    rho_bar: np.ndarray,
    L: np.ndarray,
    workloads: np.ndarray,
    ceiling: np.ndarray,
    epsilon: float,
) -> np.ndarray:
    """Wrapper around A2b returning just the (R, T) schedule."""
    result = solve_mahalanobis_dro(
        rho_bar=rho_bar,
        L=L,
        workloads=workloads,
        ceiling=ceiling,
        epsilon=epsilon,
    )
    return result.schedule


def cv_select_epsilon(
    train_panel: np.ndarray,
    workloads: np.ndarray,
    ceiling: np.ndarray,
    shuffle_to_block_diagonal: bool,
    utilization: float,
) -> CVResult:
    """Run blocked time-series CV across EPSILON_GRID; return CVResult.

    For each fold, fit Sigma_hat and rho_bar on the training portion,
    solve A2b at each epsilon, evaluate per-day emissions on the
    validation portion, compute the validation CVaR.  Across folds,
    average the validation CVaRs per epsilon.  Pick epsilon* = argmin.
    """
    folds = blocked_fold_indices(len(train_panel), N_CV_FOLDS)
    cvar_by_eps_by_fold: dict[float, list[float]] = {e: [] for e in EPSILON_GRID}

    for fold_idx, (fit_idx, val_idx) in enumerate(folds):
        fit_panel = train_panel[fit_idx]
        val_panel = train_panel[val_idx]
        rho_bar_fit = fit_panel.mean(axis=0)
        _, L_fit = fit_sigma_and_cholesky(fit_panel, shuffle_to_block_diagonal)

        for eps in EPSILON_GRID:
            x_star = schedule_for(rho_bar_fit, L_fit, workloads, ceiling, eps)
            val_em = per_day_emissions(x_star, val_panel)
            cvar_by_eps_by_fold[eps].append(cvar_upper_tail(val_em))

    cv_mean = {e: float(np.mean(v)) for e, v in cvar_by_eps_by_fold.items()}
    cv_std = {e: float(np.std(v, ddof=1)) for e, v in cvar_by_eps_by_fold.items()}
    eps_star = min(cv_mean, key=cv_mean.get)
    at_boundary = eps_star in (EPSILON_GRID[0], EPSILON_GRID[-1])

    return CVResult(
        utilization=utilization,
        sigma_label="shuf" if shuffle_to_block_diagonal else "joint",
        cv_curve=cv_mean,
        cv_curve_std=cv_std,
        epsilon_star=float(eps_star),
        epsilon_star_at_boundary=at_boundary,
    )


def evaluate_on_test(
    train_panel: np.ndarray,
    test_panel: np.ndarray,
    workloads: np.ndarray,
    ceiling: np.ndarray,
    shuffle_to_block_diagonal: bool,
    epsilon_star: float,
    utilization: float,
) -> TestResult:
    """Fit Sigma_hat on full training, solve A2b at epsilon*, evaluate on test."""
    rho_bar = train_panel.mean(axis=0)
    _, L = fit_sigma_and_cholesky(train_panel, shuffle_to_block_diagonal)
    schedule = schedule_for(rho_bar, L, workloads, ceiling, epsilon_star)
    test_em = per_day_emissions(schedule, test_panel)
    return TestResult(
        utilization=utilization,
        sigma_label="shuf" if shuffle_to_block_diagonal else "joint",
        epsilon_star=epsilon_star,
        test_cvar=cvar_upper_tail(test_em),
        test_mean=float(test_em.mean()),
        test_max=float(test_em.max()),
        schedule=schedule,
        per_day_emissions=test_em,
    )


def bootstrap_gap_ci(
    joint_per_day: np.ndarray,
    shuf_per_day: np.ndarray,
    n_resamples: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Bootstrap 95% CI for (shuf_cvar - joint_cvar).

    Positive gap = joint beats shuf (joint has lower tail emissions).
    Resamples test-day indices with replacement and recomputes both CVaRs
    on the resampled set; reports point estimate and (2.5, 97.5) percentiles.
    """
    rng = np.random.default_rng(seed)
    n = len(joint_per_day)
    assert len(shuf_per_day) == n
    gaps = np.empty(n_resamples)
    for b in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        j = joint_per_day[idx]
        s = shuf_per_day[idx]
        gaps[b] = cvar_upper_tail(s) - cvar_upper_tail(j)
    point = cvar_upper_tail(shuf_per_day) - cvar_upper_tail(joint_per_day)
    lo, hi = np.percentile(gaps, [2.5, 97.5])
    return float(point), float(lo), float(hi)


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------

def format_cv_table(cv_results: list[CVResult]) -> str:
    """Pretty-print CV curves grouped by utilization and Sigma."""
    lines = ["", "=" * 78, "Cross-validation curves (mean validation CVaR_0.95 across folds)", "=" * 78]
    by_util = {}
    for r in cv_results:
        by_util.setdefault(r.utilization, []).append(r)
    for util, group in sorted(by_util.items()):
        lines.append(f"\nUtilization {int(util*100):>3d}%")
        header = "  epsilon       " + "  ".join(f"{label:>16s}" for label in ["joint", "shuf"])
        lines.append(header)
        joint = next(r for r in group if r.sigma_label == "joint")
        shuf = next(r for r in group if r.sigma_label == "shuf")
        for eps in EPSILON_GRID:
            j = joint.cv_curve[eps]
            s = shuf.cv_curve[eps]
            marker_j = " *" if eps == joint.epsilon_star else "  "
            marker_s = " *" if eps == shuf.epsilon_star else "  "
            lines.append(
                f"  {eps:>10.4g}  "
                f"{j:>14.2f}{marker_j}  {s:>14.2f}{marker_s}"
            )
        lines.append(
            f"  epsilon*       {joint.epsilon_star:>14.4g}      {shuf.epsilon_star:>14.4g}"
        )
        for r in group:
            if r.epsilon_star_at_boundary:
                lines.append(
                    f"  WARNING: epsilon* for {r.sigma_label} is at the grid boundary "
                    f"({r.epsilon_star}); consider widening the grid before test."
                )
    lines.append("=" * 78)
    return "\n".join(lines)


def format_test_table(rows: list[dict]) -> str:
    """Pretty-print the final test-set comparison table."""
    df = pd.DataFrame(rows)
    return df.to_string(index=False, float_format=lambda x: f"{x:.4g}")


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run CV on training only; report epsilon* per (util, Sigma) "
        "without touching the 2025 test set. Intended for verifying the "
        "CV procedure is sane before committing to the test-set run.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=RESULTS_DIR,
        help=f"Output directory (default {RESULTS_DIR})",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # --- Data load ---------------------------------------------------------
    print("Loading 4-zone panel ...")
    df_long = load_all_zones(list(REGION_ORDER))
    wide = to_wide(df_long)
    panel, dates = build_daily_panel(wide)
    print(f"  panel shape  : {panel.shape}  (N={panel.shape[0]} daily samples)")
    print(f"  date range   : {dates.min().date()} -> {dates.max().date()}")

    is_train = np.array([d.year in TRAIN_YEARS for d in dates])
    is_test = np.array([d.year == TEST_YEAR for d in dates])
    train_panel = panel[is_train]
    test_panel = panel[is_test]
    train_dates = dates[is_train]
    test_dates = dates[is_test]
    print(f"  train (years {TRAIN_YEARS}): N={len(train_panel)} days")
    print(f"  test  (year  {TEST_YEAR})      : N={len(test_panel)} days")
    if args.dry_run:
        print("  --dry-run set: test panel will NOT be touched.")

    R, T = panel.shape[1], panel.shape[2]
    assert T == T_HOURS, f"Expected T={T_HOURS}, got {T}"

    # --- Cross-validation phase -------------------------------------------
    cv_results: list[CVResult] = []
    for util in UTILIZATION_LEVELS:
        workloads = np.full(R, util * CEILING_PER_CELL_MW * T)  # MWh per region
        ceiling = np.full((R, T), CEILING_PER_CELL_MW)
        print(f"\nCV for utilization {int(util*100)}% ...")
        for shuf in (False, True):
            label = "shuf" if shuf else "joint"
            print(f"  {label} ... ", end="", flush=True)
            cv = cv_select_epsilon(
                train_panel=train_panel,
                workloads=workloads,
                ceiling=ceiling,
                shuffle_to_block_diagonal=shuf,
                utilization=util,
            )
            cv_results.append(cv)
            print(
                f"epsilon* = {cv.epsilon_star:>8.4g}"
                + (" (BOUNDARY)" if cv.epsilon_star_at_boundary else "")
            )

    print(format_cv_table(cv_results))

    boundary_hits = [r for r in cv_results if r.epsilon_star_at_boundary]
    if boundary_hits:
        print(
            "\nNote: at least one epsilon* lies at the grid boundary. The grid "
            "may need widening before the test-set run."
        )

    if args.dry_run:
        print("\n--dry-run complete; not evaluating on test set. Exit.")
        return 0

    # --- Test-set evaluation phase (touched once) -------------------------
    print("\nEvaluating on test set ...")
    test_results: list[TestResult] = []
    for util in UTILIZATION_LEVELS:
        workloads = np.full(R, util * CEILING_PER_CELL_MW * T)
        ceiling = np.full((R, T), CEILING_PER_CELL_MW)
        cv_joint = next(r for r in cv_results if r.utilization == util and r.sigma_label == "joint")
        cv_shuf = next(r for r in cv_results if r.utilization == util and r.sigma_label == "shuf")
        for shuf, eps_star in ((False, cv_joint.epsilon_star), (True, cv_shuf.epsilon_star)):
            tr = evaluate_on_test(
                train_panel=train_panel,
                test_panel=test_panel,
                workloads=workloads,
                ceiling=ceiling,
                shuffle_to_block_diagonal=shuf,
                epsilon_star=eps_star,
                utilization=util,
            )
            test_results.append(tr)

    # --- Bootstrap CI on joint-vs-shuf gap, per utilization ---------------
    summary_rows = []
    for util in UTILIZATION_LEVELS:
        j = next(t for t in test_results if t.utilization == util and t.sigma_label == "joint")
        s = next(t for t in test_results if t.utilization == util and t.sigma_label == "shuf")
        point, lo, hi = bootstrap_gap_ci(j.per_day_emissions, s.per_day_emissions)
        ci_excludes_zero = (lo > 0) or (hi < 0)
        rel_gap = (s.test_cvar - j.test_cvar) / s.test_cvar * 100.0
        summary_rows.append({
            "utilization_pct": int(util * 100),
            "eps*_joint": j.epsilon_star,
            "eps*_shuf": s.epsilon_star,
            "joint_CVaR": j.test_cvar,
            "shuf_CVaR": s.test_cvar,
            "joint_mean": j.test_mean,
            "shuf_mean": s.test_mean,
            "gap_abs": point,
            "gap_pct": rel_gap,
            "gap_ci_lo": lo,
            "gap_ci_hi": hi,
            "detectable": ci_excludes_zero,
        })

    print("\n" + "=" * 78)
    print("Test-set results (CVaR_0.95 = mean of worst 5% of test days)")
    print("Positive gap = joint beats shuf (lower tail emissions)")
    print("=" * 78)
    print(format_test_table(summary_rows))
    print("=" * 78)

    # --- Persist ----------------------------------------------------------
    stamp = dt.datetime.utcnow().strftime("%Y-%m-%d")
    csv_path = args.out_dir / f"shuffled_marginals_{stamp}.csv"
    pkl_path = args.out_dir / f"shuffled_marginals_{stamp}.pkl"

    pd.DataFrame(summary_rows).to_csv(csv_path, index=False)
    with pkl_path.open("wb") as f:
        pickle.dump(
            {
                "cv_results": [asdict(r) for r in cv_results],
                "test_results": [
                    {
                        **{k: v for k, v in asdict(t).items() if k not in ("schedule", "per_day_emissions")},
                        "schedule": t.schedule,
                        "per_day_emissions": t.per_day_emissions,
                    }
                    for t in test_results
                ],
                "summary_rows": summary_rows,
                "config": {
                    "utilization_levels": UTILIZATION_LEVELS,
                    "epsilon_grid": EPSILON_GRID,
                    "n_cv_folds": N_CV_FOLDS,
                    "n_bootstrap": N_BOOTSTRAP,
                    "bootstrap_seed": BOOTSTRAP_SEED,
                    "cvar_alpha": CVAR_ALPHA,
                    "ceiling_per_cell_MW": CEILING_PER_CELL_MW,
                    "ridge_eta": RIDGE_ETA,
                    "train_years": TRAIN_YEARS,
                    "test_year": TEST_YEAR,
                },
                "panel_meta": {
                    "panel_shape": panel.shape,
                    "n_train": int(is_train.sum()),
                    "n_test": int(is_test.sum()),
                    "train_date_range": (str(train_dates.min().date()), str(train_dates.max().date())),
                    "test_date_range": (str(test_dates.min().date()), str(test_dates.max().date())),
                },
            },
            f,
        )

    print(f"\nWrote {csv_path}")
    print(f"Wrote {pkl_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
