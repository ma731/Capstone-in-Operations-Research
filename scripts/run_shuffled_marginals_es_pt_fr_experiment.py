"""Task B: shuffled-marginals DRO experiment for ES_PT_FR (ES-PT-FR).

Second region case. The constraint set, the DRO method (Algorithm 2b
Mahalanobis-Wasserstein SOCP), the three-regime design, the metric
(CVaR_0.95), the blocked 5-fold CV, the 1000-bootstrap CI, the alpha sweep, and
the table format are ALL LOCKED from Task A
(scripts/run_shuffled_marginals_taskA_experiment.py) and reproduced here
verbatim so the two cases sit side by side. Only what MUST differ differs:

  * REGION_ORDER = (ES, PT, FR), R=3 (D = R*T = 72, not 96).
  * common clock = Europe/Madrid (PT is WET, one hour behind -> its panel hours
    are shifted +1h under this common reference clock; stated, not silenced).
  * constraint PARAMETERS re-calibrated to Iberian TRAINING data (Phase 3):
      - thermal economizer set-point t_set = 14 C (was 20 C in CA): the Iberian
        annual-mean thermal field is milder, so a lower set-point keeps 3b
        loosely active (binds ~22-26% of cells, matching the CA discipline).
        PUE shape, slope kappa, floor pue0, and bar_P are UNCHANGED.
      - deadline window [0,7], gamma 0.20, ramp 15, alpha sweep, util 0.80,
        ceiling 50: IDENTICAL to Task A (the diurnal carbon structure is
        similar -- a midday solar trough -- so these transfer directly).

Comparability guardrail: nothing structural diverges. If a future change forces
a different metric / CV / bootstrap, STOP -- the side-by-side comparison is the
point of this second case.

Pre-commitment (same as Task A): lock via git commit before the test run;
--dry-run reports CV epsilon* without touching 2025; real run reads 2025 once.

Outputs: results/es_pt_fr_regimes_<UTC-date>.csv / .pkl
Reference: progress note v14; Task B brief.
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

from src.data.electricitymaps import load_all_zones, to_wide
from src.data.temperature import (
    align_temperature_to_panel,
    load_temperature_wide,
    temperature_field,
)
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    DEFAULT_TZ_ES_PT_FR,
    REGION_ORDER_ES_PT_FR,
    block_diagonal_by_region,
    build_daily_panel,
    cholesky_factor,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    regularize_covariance,
    shrink_covariance_ledoit_wolf,
)

# ======================================================================
# LOCKED CONFIGURATION (do not edit after committing, before the test run)
# ======================================================================
REGION_ORDER = REGION_ORDER_ES_PT_FR          # (ES, PT, FR) -- R=3
TZ = DEFAULT_TZ_ES_PT_FR                       # Europe/Madrid common clock
UTILIZATION_FIXED = 0.80
ALPHA_LEVELS = (0.30, 0.50, 0.75)
EPSILON_GRID = (0.0, 0.1, 1.0, 10.0, 100.0, 1000.0)
N_CV_FOLDS = 5
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 20260524                    # same seed as Task A
CVAR_ALPHA = 0.95
CEILING_PER_CELL_MW = 50.0
T_HOURS = 24
TRAIN_YEARS = (2021, 2022, 2023, 2024)
TEST_YEAR = 2025
RIDGE_ETA = 1e-5

P_MAX = None                                 # cap dropped (as in Task A)
RAMP_PER_REGION = 15.0                       # identical to Task A
DEADLINE_WINDOW = (0, 7)                     # identical to Task A
DEADLINE_GAMMA = 0.20                        # identical to Task A
# Thermal: PUE shape identical; t_set recalibrated 20 -> 14 for the milder
# Iberian annual-mean field (Phase 3). bar_P identical to Task A.
PUE0 = 1.10
KAPPA = 0.015
T_SET = 14.0
BAR_P = 57.0

REGIMES = {
    "R3_reference": dict(deadline=False, thermal=False),
    "R1_lean":      dict(deadline=True,  thermal=False),
    "R2_full":      dict(deadline=True,  thermal=True),
}
REGIME_ORDER = ("R3_reference", "R1_lean", "R2_full")

RESULTS_DIR = Path("results")

USE_SHRINKAGE = False
_LW_INTENSITIES: list[float] = []
RESIDUALIZE = "none"
_THERMAL_FIELD: np.ndarray | None = None


# ----------------------------------------------------------------------
# Metrics / CV  (verbatim from Task A for comparability)
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


def fit_sigma_and_cholesky(panel: np.ndarray, shuffle: bool) -> tuple[np.ndarray, np.ndarray]:
    samples = daily_panel_to_matrix(panel)
    R, T = panel.shape[1], panel.shape[2]
    if USE_SHRINKAGE:
        sigma_hat, rho = shrink_covariance_ledoit_wolf(samples)
        _LW_INTENSITIES.append(rho)
        if shuffle:
            sigma_hat = block_diagonal_by_region(sigma_hat, R=R, T=T)
        sigma_reg = regularize_covariance(sigma_hat, eta=RIDGE_ETA)
    else:
        _, sigma_hat = estimate_mean_and_covariance(samples)
        if shuffle:
            sigma_hat = block_diagonal_by_region(sigma_hat, R=R, T=T)
        sigma_reg = regularize_covariance(sigma_hat, eta=RIDGE_ETA)
    return sigma_reg, cholesky_factor(sigma_reg)


def schedule_for(rho_bar, L, workloads, ceiling, epsilon, alpha, regime_key) -> np.ndarray:
    R = rho_bar.shape[0]
    spec = REGIMES[regime_key]
    kw = dict(p_max=P_MAX, alpha=alpha, ramp=np.full(R, RAMP_PER_REGION))
    if spec["deadline"]:
        t1, t2 = DEADLINE_WINDOW
        kw["deferral_windows"] = [(t1, t2, DEADLINE_GAMMA)]
    if spec["thermal"]:
        kw["temperature"] = _THERMAL_FIELD
        kw["bar_P"] = BAR_P
        kw["pue0"] = PUE0
        kw["kappa"] = KAPPA
        kw["t_set"] = T_SET
    return solve_mahalanobis_dro(
        rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
        epsilon=epsilon, region_order=REGION_ORDER, **kw,
    ).schedule


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


def cv_select_epsilon(train_panel, workloads, ceiling, shuffle, alpha_val, regime_key, cov_panel):
    folds = blocked_fold_indices(len(train_panel), N_CV_FOLDS)
    by_eps = {e: [] for e in EPSILON_GRID}
    alpha_vec = np.full(train_panel.shape[1], alpha_val)
    for fit_idx, val_idx in folds:
        rho_bar_fit = train_panel[fit_idx].mean(axis=0)
        _, L_fit = fit_sigma_and_cholesky(cov_panel[fit_idx], shuffle)
        for eps in EPSILON_GRID:
            x = schedule_for(rho_bar_fit, L_fit, workloads, ceiling, eps, alpha_vec, regime_key)
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


def evaluate_on_test(train_panel, test_panel, workloads, ceiling, shuffle,
                     eps_star, alpha_val, regime_key, train_cov_panel):
    rho_bar = train_panel.mean(axis=0)
    _, L = fit_sigma_and_cholesky(train_cov_panel, shuffle)
    alpha_vec = np.full(train_panel.shape[1], alpha_val)
    x = schedule_for(rho_bar, L, workloads, ceiling, eps_star, alpha_vec, regime_key)
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="CV only; do not touch the 2025 test set.")
    ap.add_argument("--regime", choices=REGIME_ORDER + ("all",), default="all")
    ap.add_argument("--shrinkage", action="store_true")
    ap.add_argument("--residualize", choices=("none", "seasonal", "ar1"), default="none")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    global USE_SHRINKAGE, RESIDUALIZE, _THERMAL_FIELD
    USE_SHRINKAGE = args.shrinkage
    RESIDUALIZE = args.residualize
    regimes = REGIME_ORDER if args.regime == "all" else (args.regime,)

    print("ES_PT_FR (ES-PT-FR) | ESTIMATION:",
          "Ledoit-Wolf shrinkage" if USE_SHRINKAGE else "sample covariance + ridge",
          "| residualize:", RESIDUALIZE)
    print(f"CAP: DROPPED. Common clock: {TZ} (PT is WET, +1h shifted). Regimes:", regimes)

    zones = list(REGION_ORDER)
    carbon_wide = to_wide(load_all_zones(zones))
    panel, dates = build_daily_panel(carbon_wide, region_order=zones, tz=TZ)
    temp_panel, temp_dates = align_temperature_to_panel(
        load_temperature_wide(zones), carbon_wide, region_order=zones, tz=TZ
    )
    assert dates.equals(temp_dates), "temperature/carbon dates misaligned"
    print(f"  panel {panel.shape}, dates {dates.min().date()} -> {dates.max().date()}")

    is_train = np.array([d.year in TRAIN_YEARS for d in dates])
    is_test = np.array([d.year == TEST_YEAR for d in dates])
    train_panel, test_panel = panel[is_train], panel[is_test]
    train_dates, test_dates = dates[is_train], dates[is_test]
    print(f"  train N={len(train_panel)}, test N={len(test_panel)}")
    if args.dry_run:
        print("  --dry-run: test panel will NOT be touched.")

    R, T = panel.shape[1], panel.shape[2]
    assert T == T_HOURS and R == 3
    _THERMAL_FIELD = temperature_field(temp_panel, dates, TRAIN_YEARS)
    print(f"  thermal field (train mean temp) max/zone: "
          f"{np.round(_THERMAL_FIELD.max(axis=1), 1)} C  (t_set={T_SET})")

    if RESIDUALIZE != "none":
        stats = fit_residual_baseline(train_panel, train_dates, RESIDUALIZE)
        train_cov_panel = apply_residual_baseline(train_panel, train_dates, stats)
        print(f"  COVARIANCE INPUT: {RESIDUALIZE} residuals (rho_bar/emissions stay RAW)")
    else:
        train_cov_panel = train_panel

    workloads = np.full(R, UTILIZATION_FIXED * CEILING_PER_CELL_MW * T)
    ceiling = np.full((R, T), CEILING_PER_CELL_MW)

    cv_results: list[CVResult] = []
    for regime_key in regimes:
        for a in ALPHA_LEVELS:
            for shuf in (False, True):
                cv = cv_select_epsilon(train_panel, workloads, ceiling, shuf,
                                       a, regime_key, train_cov_panel)
                cv_results.append(cv)
                tag = "shuf" if shuf else "joint"
                print(f"  CV {regime_key:13s} alpha={a:.2f} {tag:5s}: "
                      f"eps*={cv.epsilon_star:>7.4g}"
                      + (" (BOUNDARY)" if cv.epsilon_star_at_boundary else ""))

    if args.dry_run:
        if USE_SHRINKAGE and _LW_INTENSITIES:
            import statistics
            print(f"\nLedoit-Wolf rho: mean={statistics.mean(_LW_INTENSITIES):.4f}, "
                  f"min={min(_LW_INTENSITIES):.4f}, max={max(_LW_INTENSITIES):.4f}")
        print("\n--dry-run complete; test set untouched. Exit.")
        return 0

    print("\nEvaluating on 2025 test set ...")
    test_results: list[TestResult] = []
    for regime_key in regimes:
        for a in ALPHA_LEVELS:
            cvj = next(r for r in cv_results if r.regime == regime_key and r.alpha == a and r.sigma_label == "joint")
            cvs = next(r for r in cv_results if r.regime == regime_key and r.alpha == a and r.sigma_label == "shuf")
            for shuf, eps_star in ((False, cvj.epsilon_star), (True, cvs.epsilon_star)):
                test_results.append(evaluate_on_test(
                    train_panel, test_panel, workloads, ceiling, shuf,
                    eps_star, a, regime_key, train_cov_panel,
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
    print("ES_PT_FR SENSITIVITY TABLE -- spatial gap (shuf - joint) CVaR_0.95, by regime x alpha")
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
    if args.regime != "all":
        suffix += f"_{args.regime}"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    csv_path = args.out_dir / f"es_pt_fr_regimes_{stamp}{suffix}.csv"
    pkl_path = args.out_dir / f"es_pt_fr_regimes_{stamp}{suffix}.pkl"
    df.to_csv(csv_path, index=False)
    with pkl_path.open("wb") as f:
        pickle.dump({
            "cv_results": [asdict(r) for r in cv_results],
            "test_results": [
                {**{k: v for k, v in asdict(t).items()
                    if k not in ("schedule", "per_day_emissions")},
                 "schedule": t.schedule, "per_day_emissions": t.per_day_emissions}
                for t in test_results
            ],
            "summary_rows": rows,
            "config": {
                "region_order": list(REGION_ORDER), "tz": TZ,
                "regimes": regimes, "alpha_levels": ALPHA_LEVELS,
                "utilization_fixed": UTILIZATION_FIXED, "p_max": P_MAX,
                "ramp_per_region": RAMP_PER_REGION,
                "deadline_window": DEADLINE_WINDOW, "deadline_gamma": DEADLINE_GAMMA,
                "pue0": PUE0, "kappa": KAPPA, "t_set": T_SET, "bar_P": BAR_P,
                "epsilon_grid": EPSILON_GRID, "n_cv_folds": N_CV_FOLDS,
                "n_bootstrap": N_BOOTSTRAP, "bootstrap_seed": BOOTSTRAP_SEED,
                "cvar_alpha": CVAR_ALPHA, "ceiling_per_cell_MW": CEILING_PER_CELL_MW,
                "ridge_eta": RIDGE_ETA, "train_years": TRAIN_YEARS, "test_year": TEST_YEAR,
                "use_shrinkage": USE_SHRINKAGE, "residualize": RESIDUALIZE,
            },
            "thermal_field": _THERMAL_FIELD,
        }, f)
    print(f"\nWrote {csv_path}\nWrote {pkl_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
