"""Generalized shuffled-marginals DRO experiment (any registered region set).

Runs ANY thesis case from src.analysis.stratified_correlations.REGION_SETS through
the SAME locked machinery as Task C (Algorithm 2b Mahalanobis-Wasserstein SOCP,
blocked 5-fold CV to select epsilon, 1000-bootstrap CI on the spatial gap,
CVaR_0.95 metric, nested regimes R3/R1/R2 with the 3c CFE-driven ceiling in R2).
The shuffled-marginals device (joint covariance vs block-diagonal-by-region)
isolates the spatial contribution.

This is the single parameterized runner for the three thesis cases, so they are
guaranteed to use identical machinery:

  --region-set us_west    CA + NV + Phoenix (Western Interconnection; strong,
                          residual-surviving solar/weather correlation)
  --region-set taskc      Ontario + Eastern-Interconnection belt (strong,
                          residual-surviving weather-front correlation)
  --region-set us_hetero  CISO(solar) + ERCO(wind) + BPAT(hydro): deliberately
                          HETEROGENEOUS / near-uncorrelated -- the adversarial
                          best-case test for spatial DRO value. If diversification
                          value appears anywhere, it should appear here.

(Task C's run_shuffled_marginals_taskc_experiment.py remains as the locked,
pre-registered Task C artifact; this runner reproduces its taskc numbers and
extends the identical protocol to the other two cases.)

Regimes (nested):
    R3 (reference): ceiling + split + ramp
    R1 (lean)     : R3 + deadline (3a)
    R2 (varcap)   : R1 + variable capacity (3c, CFE-driven ceiling)

The DRO SOCP is solved by CLARABEL (conic). HiGHS cannot do second-order cones;
it is only for the deterministic LP baseline (scripts/solve_baseline.py).

NOTE: the 3c ceiling bounds (x_min, x_max) are PROVISIONAL (not yet Goldilocks-
calibrated -- see docs/decisions.md Decision 8). Treat R2 as exploratory.

Pre-registration discipline: --dry-run reports CV-selected epsilon* per
(regime, alpha, Sigma) WITHOUT touching the 2025 test set; commit before the
real run; the test year is read exactly once, at the end.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pickle
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.stratified_correlations import REGION_SETS
from src.data.capacity import build_cfe_panel, capacity_from_cfe, cfe_field
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    block_diagonal_by_region,
    build_daily_panel,
    cholesky_factor,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
    shrink_covariance_ledoit_wolf,
)

# ======================================================================
# LOCKED CONFIGURATION (identical to Task C; do not edit after committing)
# ======================================================================
UTILIZATION_FIXED = 0.80
ALPHA_LEVELS = (0.30, 0.50, 0.75)
EPSILON_GRID = (0.0, 0.1, 1.0, 10.0, 100.0, 1000.0)
N_CV_FOLDS = 5
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 20260524
CVAR_ALPHA = 0.95
CEILING_PER_CELL_MW = 50.0
T_HOURS = 24
TRAIN_YEARS = (2021, 2022, 2023, 2024)  # overridden by --test-year (walk-forward)
TEST_YEAR = 2025

EPSILON_GRID_FINE = (0.0, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)
RIDGE_ETA = 1e-5

P_MAX = None
RAMP_PER_REGION = 15.0
DEADLINE_WINDOW = (0, 7)
DEADLINE_GAMMA = 0.20
# 3c variable capacity (R2): Goldilocks-calibrated on TRAINING data via
# scripts/calibrate_capacity.py (loosely binding: bind_frac ~0.28-0.37, positive
# slack + capacity margin across all three cases). Supersedes the provisional
# (42, 65). See docs/decisions.md Decision 8.
CAP_MIN = 50.0
CAP_MAX = 75.0

REGIMES = {
    "R3_reference": dict(deadline=False, varcap=False),
    "R1_lean":      dict(deadline=True,  varcap=False),
    "R2_varcap":    dict(deadline=True,  varcap=True),
}
REGIME_ORDER = ("R3_reference", "R1_lean", "R2_varcap")

RESULTS_DIR = Path("results")
ALLOWED_SETS = ("us_west", "taskc", "us_hetero")

# --- Mutable globals set per-run from the chosen region set ------------------
REGION_ORDER: tuple[str, ...] = ()
TZ: str = "UTC"
USE_SHRINKAGE = False
_LW_INTENSITIES: list[float] = []
RESIDUALIZE = "none"
ABLATE_MEAN = "none"  # none | level | flat (mean-ablation experiment)
_VARCAP_CEILING: np.ndarray | None = None


def ablate_mean(rho_bar: np.ndarray) -> np.ndarray:
    """Transform the mean field used for SCHEDULING (not evaluation).

    Mean-ablation experiment: the Phase 1 null claims the mean field dominates and
    the covariance is 2nd-order. Remove the mean's separable cross-region dominance
    and check whether the joint-vs-shuffled covariance effect then appears.

      none  : return rho_bar unchanged (locked Phase 1 behavior).
      level : equalize each region's time-average to the global mean, keeping each
              region's hour-of-day shape -> regions are equally clean ON AVERAGE,
              differing only in timing + co-movement.
      flat  : constant global mean everywhere -> the mean term <rho_bar, x> is
              constant (demand is fixed), so the schedule is driven PURELY by the
              eps*||L^T x|| penalty == a covariance-only world.

    Evaluation always uses the REAL carbon panel, so CVaR reflects real emissions.
    """
    if ABLATE_MEAN == "none":
        return rho_bar
    global_mean = float(rho_bar.mean())
    if ABLATE_MEAN == "flat":
        return np.full_like(rho_bar, global_mean)
    if ABLATE_MEAN == "level":
        region_mean = rho_bar.mean(axis=1, keepdims=True)  # (R, 1)
        return rho_bar - region_mean + global_mean
    raise ValueError(f"unknown ablate-mean mode: {ABLATE_MEAN}")


# ----------------------------------------------------------------------
# Metrics / CV (identical to Task C)
# ----------------------------------------------------------------------

def cvar_upper_tail(values: np.ndarray, alpha: float = CVAR_ALPHA) -> float:
    values = np.asarray(values, dtype=float)
    n = len(values)
    n_tail = max(1, int(np.ceil(n * (1.0 - alpha))))
    return float(np.sort(values)[::-1][:n_tail].mean())


def per_day_emissions(schedule: np.ndarray, panel: np.ndarray) -> np.ndarray:
    return np.einsum("rt,nrt->n", schedule, panel)


def blocked_fold_indices(n: int, k: int) -> list[tuple[np.ndarray, np.ndarray]]:
    boundaries = np.linspace(0, n, k + 1, dtype=int)
    all_idx = np.arange(n)
    folds = []
    for i in range(k):
        val_idx = all_idx[boundaries[i]:boundaries[i + 1]]
        train_idx = np.concatenate([all_idx[:boundaries[i]], all_idx[boundaries[i + 1]:]])
        folds.append((train_idx, val_idx))
    return folds


# ----------------------------------------------------------------------
# Residual baselines (identical to Task C)
# ----------------------------------------------------------------------

def fit_residual_baseline(panel: np.ndarray, dates, method: str) -> dict:
    N, R, T = panel.shape
    if method == "seasonal":
        months = np.array([d.month for d in dates])
        means = {m: panel[months == m].mean(axis=0) for m in range(1, 13) if (months == m).any()}
        return {"method": "seasonal", "means": means, "global_mean": panel.mean(axis=0)}
    if method == "ar1":
        c = np.zeros((R, T)); phi = np.zeros((R, T)); cell_mean = panel.mean(axis=0)
        for r in range(R):
            for t in range(T):
                y = panel[1:, r, t]; x = panel[:-1, r, t]
                A = np.vstack([np.ones_like(x), x]).T
                coef, *_ = np.linalg.lstsq(A, y, rcond=None)
                c[r, t], phi[r, t] = float(coef[0]), float(coef[1])
        return {"method": "ar1", "c": c, "phi": phi, "cell_mean": cell_mean}
    raise ValueError(f"unknown residualization method: {method}")


def apply_residual_baseline(panel: np.ndarray, dates, stats: dict) -> np.ndarray:
    N, R, T = panel.shape
    resid = np.empty_like(panel)
    if stats["method"] == "seasonal":
        months = np.array([d.month for d in dates])
        for i in range(N):
            resid[i] = panel[i] - stats["means"].get(months[i], stats["global_mean"])
    else:
        c, phi, cell_mean = stats["c"], stats["phi"], stats["cell_mean"]
        resid[0] = panel[0] - cell_mean
        resid[1:] = panel[1:] - (c[None] + phi[None] * panel[:-1])
    return resid


# ----------------------------------------------------------------------
# Estimation + scheduling
# ----------------------------------------------------------------------

def fit_sigma_and_cholesky(panel: np.ndarray, shuffle: bool) -> tuple[np.ndarray, np.ndarray]:
    samples = daily_panel_to_matrix(panel)
    R, T = panel.shape[1], panel.shape[2]
    if USE_SHRINKAGE:
        sigma_hat, rho = shrink_covariance_ledoit_wolf(samples)
        _LW_INTENSITIES.append(rho)
    else:
        _, sigma_hat = estimate_mean_and_covariance(samples)
    if shuffle:
        sigma_hat = block_diagonal_by_region(sigma_hat, R=R, T=T)
    sigma_reg = regularize_covariance(sigma_hat, eta=RIDGE_ETA)
    return sigma_reg, cholesky_factor(sigma_reg)


def _ceiling_for(regime_key: str, R: int, T: int) -> np.ndarray:
    """Flat ceiling for R3/R1; CFE-driven (3c) ceiling for R2."""
    if REGIMES[regime_key]["varcap"]:
        assert _VARCAP_CEILING is not None
        return _VARCAP_CEILING
    return np.full((R, T), CEILING_PER_CELL_MW)


def schedule_for(rho_bar, L, workloads, epsilon, alpha, regime_key) -> np.ndarray:
    R, T = rho_bar.shape
    spec = REGIMES[regime_key]
    ceiling = _ceiling_for(regime_key, R, T)
    kw = dict(p_max=P_MAX, alpha=alpha, ramp=np.full(R, RAMP_PER_REGION),
              region_order=REGION_ORDER)
    if spec["deadline"]:
        t1, t2 = DEADLINE_WINDOW
        kw["deferral_windows"] = [(t1, t2, DEADLINE_GAMMA)]
    return solve_mahalanobis_dro(
        rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
        epsilon=epsilon, **kw,
    ).schedule


# ----------------------------------------------------------------------
# Result records (identical to Task C)
# ----------------------------------------------------------------------

@dataclass
class CVResult:
    regime: str
    alpha: float
    sigma_label: str
    cv_curve: dict
    cv_curve_std: dict
    epsilon_star: float
    epsilon_star_at_boundary: bool


@dataclass
class TestResult:
    regime: str
    alpha: float
    sigma_label: str
    epsilon_star: float
    test_cvar: float
    test_mean: float
    test_max: float
    schedule: np.ndarray
    per_day_emissions: np.ndarray


def cv_select_epsilon(train_panel, workloads, shuffle, alpha_val, regime_key, cov_panel):
    folds = blocked_fold_indices(len(train_panel), N_CV_FOLDS)
    by_eps = {e: [] for e in EPSILON_GRID}
    alpha_vec = np.full(train_panel.shape[1], alpha_val)
    for fit_idx, val_idx in folds:
        rho_bar_fit = ablate_mean(train_panel[fit_idx].mean(axis=0))
        _, L_fit = fit_sigma_and_cholesky(cov_panel[fit_idx], shuffle)
        for eps in EPSILON_GRID:
            x = schedule_for(rho_bar_fit, L_fit, workloads, eps, alpha_vec, regime_key)
            by_eps[eps].append(cvar_upper_tail(per_day_emissions(x, train_panel[val_idx])))
    cv_mean = {e: float(np.mean(v)) for e, v in by_eps.items()}
    cv_std = {e: float(np.std(v, ddof=1)) for e, v in by_eps.items()}
    eps_star = min(cv_mean, key=cv_mean.get)
    return CVResult(
        regime=regime_key, alpha=alpha_val,
        sigma_label="shuf" if shuffle else "joint",
        cv_curve=cv_mean, cv_curve_std=cv_std,
        epsilon_star=float(eps_star),
        epsilon_star_at_boundary=eps_star in (EPSILON_GRID[0], EPSILON_GRID[-1]),
    )


def evaluate_on_test(train_panel, test_panel, workloads, shuffle,
                     eps_star, alpha_val, regime_key, train_cov_panel):
    rho_bar = ablate_mean(train_panel.mean(axis=0))
    _, L = fit_sigma_and_cholesky(train_cov_panel, shuffle)
    alpha_vec = np.full(train_panel.shape[1], alpha_val)
    x = schedule_for(rho_bar, L, workloads, eps_star, alpha_vec, regime_key)
    em = per_day_emissions(x, test_panel)
    return TestResult(
        regime=regime_key, alpha=alpha_val,
        sigma_label="shuf" if shuffle else "joint",
        epsilon_star=eps_star, test_cvar=cvar_upper_tail(em),
        test_mean=float(em.mean()), test_max=float(em.max()),
        schedule=x, per_day_emissions=em,
    )


def bootstrap_gap_ci(joint_pd, shuf_pd, n_resamples=N_BOOTSTRAP, seed=BOOTSTRAP_SEED):
    rng = np.random.default_rng(seed)
    n = len(joint_pd)
    gaps = np.empty(n_resamples)
    for b in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        gaps[b] = cvar_upper_tail(shuf_pd[idx]) - cvar_upper_tail(joint_pd[idx])
    point = cvar_upper_tail(shuf_pd) - cvar_upper_tail(joint_pd)
    lo, hi = np.percentile(gaps, [2.5, 97.5])
    return float(point), float(lo), float(hi)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region-set", required=True, choices=ALLOWED_SETS,
                    help="Which thesis case to run.")
    ap.add_argument("--dry-run", action="store_true",
                    help="CV only; do not touch the 2025 test set.")
    ap.add_argument("--regime", choices=REGIME_ORDER + ("all",), default="all")
    ap.add_argument("--shrinkage", action="store_true")
    ap.add_argument("--residualize", choices=("none", "seasonal", "ar1"), default="none")
    ap.add_argument("--ablate-mean", choices=("none", "level", "flat"), default="none",
                    help="Mean-ablation experiment: equalize regional means used for "
                         "scheduling (eval stays on real emissions). 'level' = equal "
                         "time-average per region; 'flat' = constant mean (covariance-"
                         "only world).")
    ap.add_argument("--test-year", type=int, default=2025,
                    help="Walk-forward: train on 2021..(year-1), test on this year.")
    ap.add_argument("--eps-grid", choices=("standard", "fine"), default="standard",
                    help="'fine' = log-denser epsilon grid (for ablation runs where "
                         "eps* is unstable on the standard grid).")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    global USE_SHRINKAGE, RESIDUALIZE, ABLATE_MEAN, _VARCAP_CEILING, REGION_ORDER, TZ
    global TRAIN_YEARS, TEST_YEAR, EPSILON_GRID
    USE_SHRINKAGE = args.shrinkage
    RESIDUALIZE = args.residualize
    ABLATE_MEAN = args.ablate_mean
    TEST_YEAR = args.test_year
    TRAIN_YEARS = tuple(range(2021, TEST_YEAR))
    if args.eps_grid == "fine":
        EPSILON_GRID = EPSILON_GRID_FINE
    regimes = REGIME_ORDER if args.regime == "all" else (args.regime,)

    cfg = REGION_SETS[args.region_set]
    REGION_ORDER = tuple(cfg["zones"])
    TZ = cfg["tz"]
    zones = list(REGION_ORDER)

    print(f"REGION SET [{args.region_set}]:", REGION_ORDER, "| clock", TZ)
    print("ESTIMATION:", "Ledoit-Wolf shrinkage" if USE_SHRINKAGE
          else "sample covariance + ridge", "| residualize:", RESIDUALIZE,
          "| ablate-mean:", ABLATE_MEAN)
    print("Regimes:", regimes, "| R2 uses 3c variable capacity (CFE-driven)")

    # --- Data: carbon panel + CFE panel (for the 3c ceiling) --------------
    print("Loading carbon panel + CFE field ...")
    carbon_wide = to_wide(load_all_zones(zones))
    panel, dates = build_daily_panel(carbon_wide, region_order=zones, tz=TZ)
    cfe_panel, cfe_dates = build_cfe_panel(zones, tz=TZ)
    assert dates.equals(cfe_dates), "CFE/carbon dates misaligned"
    print(f"  panel {panel.shape}, dates {dates.min().date()} -> {dates.max().date()}")

    is_train = np.array([d.year in TRAIN_YEARS for d in dates])
    is_test = np.array([d.year == TEST_YEAR for d in dates])
    train_panel, test_panel = panel[is_train], panel[is_test]
    train_dates, test_dates = dates[is_train], dates[is_test]
    print(f"  train N={len(train_panel)}, test N={len(test_panel)}")
    if args.dry_run:
        print("  --dry-run: test panel will NOT be touched.")

    R, T = panel.shape[1], panel.shape[2]
    assert T == T_HOURS

    # 3c CFE-driven ceiling: fixed from TRAINING CFE (feasible-set parameter).
    field = cfe_field(cfe_panel, cfe_dates, TRAIN_YEARS)        # (R, T) %
    field = np.nan_to_num(field, nan=float(np.nanmean(field)))  # guard stray NaNs
    _VARCAP_CEILING = capacity_from_cfe(field, CAP_MIN, CAP_MAX)
    print("  3c ceiling (per-region mean MW): "
          + ", ".join(f"{z}={_VARCAP_CEILING[r].mean():.1f}" for r, z in enumerate(zones)))

    if RESIDUALIZE != "none":
        stats = fit_residual_baseline(train_panel, train_dates, RESIDUALIZE)
        train_cov_panel = apply_residual_baseline(train_panel, train_dates, stats)
        print(f"  COVARIANCE INPUT: {RESIDUALIZE} residuals (rho_bar/emissions stay RAW)")
    else:
        train_cov_panel = train_panel

    workloads = np.full(R, UTILIZATION_FIXED * CEILING_PER_CELL_MW * T)

    # --- CV phase ---------------------------------------------------------
    cv_results: list[CVResult] = []
    for regime_key in regimes:
        for a in ALPHA_LEVELS:
            for shuf in (False, True):
                cv = cv_select_epsilon(train_panel, workloads, shuf, a, regime_key, train_cov_panel)
                cv_results.append(cv)
                tag = "shuf" if shuf else "joint"
                print(f"  CV {regime_key:13s} alpha={a:.2f} {tag:5s}: "
                      f"eps*={cv.epsilon_star:>7.4g}"
                      + (" (BOUNDARY)" if cv.epsilon_star_at_boundary else ""))

    if args.dry_run:
        print("\n--dry-run complete; test set untouched. Exit.")
        return 0

    # --- Test-set evaluation (touched once) -------------------------------
    print("\nEvaluating on 2025 test set ...")
    test_results: list[TestResult] = []
    for regime_key in regimes:
        for a in ALPHA_LEVELS:
            cvj = next(r for r in cv_results if r.regime == regime_key and r.alpha == a and r.sigma_label == "joint")
            cvs = next(r for r in cv_results if r.regime == regime_key and r.alpha == a and r.sigma_label == "shuf")
            for shuf, eps_star in ((False, cvj.epsilon_star), (True, cvs.epsilon_star)):
                test_results.append(evaluate_on_test(
                    train_panel, test_panel, workloads, shuf, eps_star, a, regime_key, train_cov_panel,
                ))

    rows = []
    for regime_key in regimes:
        for a in ALPHA_LEVELS:
            j = next(t for t in test_results if t.regime == regime_key and t.alpha == a and t.sigma_label == "joint")
            s = next(t for t in test_results if t.regime == regime_key and t.alpha == a and t.sigma_label == "shuf")
            point, lo, hi = bootstrap_gap_ci(j.per_day_emissions, s.per_day_emissions)
            rows.append({
                "regime": regime_key, "alpha": a,
                "eps*_joint": j.epsilon_star, "eps*_shuf": s.epsilon_star,
                "joint_CVaR": j.test_cvar, "shuf_CVaR": s.test_cvar,
                "joint_mean": j.test_mean, "shuf_mean": s.test_mean,
                "gap_abs": point,
                "gap_pct": (s.test_cvar - j.test_cvar) / s.test_cvar * 100.0,
                "gap_ci_lo": lo, "gap_ci_hi": hi,
                "detectable": (lo > 0) or (hi < 0),
            })

    print("\n" + "=" * 96)
    print(f"[{args.region_set}] SPATIAL GAP (shuf - joint) CVaR_0.95, by regime x alpha")
    print("Positive gap = joint beats shuf. 'detectable' = bootstrap CI excludes 0.")
    print("=" * 96)
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda x: f"{x:.4g}"))
    print("=" * 96)

    suffix = ""
    if USE_SHRINKAGE:
        suffix += "_lw"
    if RESIDUALIZE != "none":
        suffix += f"_{RESIDUALIZE}"
    if ABLATE_MEAN != "none":
        suffix += f"_ablate-{ABLATE_MEAN}"
    if args.eps_grid == "fine":
        suffix += "_finegrid"
    if TEST_YEAR != 2025:
        suffix += f"_ty{TEST_YEAR}"
    if args.regime != "all":
        suffix += f"_{args.regime}"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    base = f"{args.region_set}_regimes_{stamp}{suffix}"
    csv_path = args.out_dir / f"{base}.csv"
    pkl_path = args.out_dir / f"{base}.pkl"
    df.to_csv(csv_path, index=False)
    with pkl_path.open("wb") as f:
        pickle.dump({
            "region_set": args.region_set,
            "cv_results": [asdict(r) for r in cv_results],
            "test_results": [
                {**{k: v for k, v in asdict(t).items()
                    if k not in ("schedule", "per_day_emissions")},
                 "schedule": t.schedule, "per_day_emissions": t.per_day_emissions}
                for t in test_results
            ],
            "summary_rows": rows,
            "config": {
                "region_order": REGION_ORDER, "tz": TZ,
                "regimes": regimes, "alpha_levels": ALPHA_LEVELS,
                "utilization_fixed": UTILIZATION_FIXED, "p_max": P_MAX,
                "ramp_per_region": RAMP_PER_REGION,
                "deadline_window": DEADLINE_WINDOW, "deadline_gamma": DEADLINE_GAMMA,
                "cap_min": CAP_MIN, "cap_max": CAP_MAX,
                "epsilon_grid": EPSILON_GRID, "n_cv_folds": N_CV_FOLDS,
                "n_bootstrap": N_BOOTSTRAP, "bootstrap_seed": BOOTSTRAP_SEED,
                "cvar_alpha": CVAR_ALPHA, "ceiling_per_cell_MW": CEILING_PER_CELL_MW,
                "ridge_eta": RIDGE_ETA, "train_years": TRAIN_YEARS, "test_year": TEST_YEAR,
                "use_shrinkage": USE_SHRINKAGE, "residualize": RESIDUALIZE,
            },
            "varcap_ceiling": _VARCAP_CEILING,
        }, f)
    print(f"\nWrote {csv_path}\nWrote {pkl_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
