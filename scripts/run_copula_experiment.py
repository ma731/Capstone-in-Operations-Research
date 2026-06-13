"""Phase 2 pre-registered experiment: does a non-elliptical copula recover the
spatial scheduling value the covariance ball could not?

For each (regime, alpha) cell we fit three nested dependence models on the
training panel and solve a CVaR-SAA schedule for each:

* ``independence`` -- regions decoupled (the Phase 1 shuffled arm);
* ``gaussian``     -- elliptical coupling (what a covariance ball can represent);
* ``clayton``      -- lower-tail coupling matched to the Phase 1 chi_L finding
  (the object the covariance ball cannot represent).

Each schedule is evaluated ONCE on the held-out 2025 panel by out-of-sample
CVaR_0.95 of daily emissions. The reported *copula gaps* are

    gap_gauss            = CVaR(indep)    - CVaR(gaussian)   (does elliptical help?)
    gap_clayton          = CVaR(indep)    - CVaR(clayton)    (does lower-tail help?)
    gap_clayton_vs_gauss = CVaR(gaussian) - CVaR(clayton)    (does asymmetry add?)

positive = the structured model reduces tail emissions. A paired day-bootstrap
gives a 95% CI per gap. Pre-registration: config commit-locked; scenarios use a
fixed seed; the test panel is read once (``--dry-run`` does train-only).

Usage:
    .venv\\Scripts\\python -m scripts.run_copula_experiment --region-set us_west
    add --dry-run to skip the test read; --regime {R3_reference,R1_lean,R2_varcap,all}
"""
from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.stratified_correlations import REGION_SETS
from src.data.capacity import build_cfe_panel, capacity_from_cfe, cfe_field
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.copula_scenarios import KINDS, fit_copula, generate_scenarios
from src.models.covariance import build_daily_panel
from src.models.cvar_saa import solve_cvar_saa

# ===================== LOCKED CONFIG (commit before any test read) ==========
UTILIZATION_FIXED = 0.80
ALPHA_LEVELS = (0.30, 0.50, 0.75)
CVAR_BETA = 0.95
CEILING_PER_CELL_MW = 50.0
T_HOURS = 24
TEST_YEAR = 2025
RAMP_PER_REGION = 15.0
DEADLINE_WINDOW = (0, 7)
DEADLINE_GAMMA = 0.20
CAP_MIN, CAP_MAX = 50.0, 75.0
N_SCENARIOS = 1000          # SAA scenario count (locked)
SCENARIO_SEED = 20260613    # locked
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 20260524   # same as Phase 1
ALLOWED_SETS = ("us_west", "taskc", "us_hetero")

REGIMES = {
    "R3_reference": dict(deadline=False, varcap=False),
    "R1_lean":      dict(deadline=True,  varcap=False),
    "R2_varcap":    dict(deadline=True,  varcap=True),
}
REGIME_ORDER = ("R3_reference", "R1_lean", "R2_varcap")

_VARCAP_CEILING: np.ndarray | None = None


# ===================== metrics (pure, self-contained) =======================
def cvar_upper_tail(values: np.ndarray, beta: float = CVAR_BETA) -> float:
    values = np.asarray(values, dtype=float)
    n = len(values)
    n_tail = max(1, int(np.ceil(n * (1.0 - beta))))
    return float(np.sort(values)[::-1][:n_tail].mean())


def per_day_emissions(schedule: np.ndarray, panel: np.ndarray) -> np.ndarray:
    return np.einsum("rt,nrt->n", schedule, panel)


def _ceiling_for(regime_key: str, R: int, T: int) -> np.ndarray:
    if REGIMES[regime_key]["varcap"]:
        assert _VARCAP_CEILING is not None
        return _VARCAP_CEILING
    return np.full((R, T), CEILING_PER_CELL_MW)


def _feasible_kwargs(regime_key: str, R: int, alpha_val: float) -> dict:
    kw = dict(alpha=np.full(R, alpha_val), ramp=np.full(R, RAMP_PER_REGION))
    if REGIMES[regime_key]["deadline"]:
        t1, t2 = DEADLINE_WINDOW
        kw["deferral_windows"] = [(t1, t2, DEADLINE_GAMMA)]
    return kw


def schedule_for_copula(kind, train_panel, regime_key, alpha_val, workloads):
    R, T = train_panel.shape[1], train_panel.shape[2]
    model = fit_copula(kind, train_panel)
    scen = generate_scenarios(model, N_SCENARIOS, seed=SCENARIO_SEED)
    ceiling = _ceiling_for(regime_key, R, T)
    res = solve_cvar_saa(scen, workloads, ceiling, beta=CVAR_BETA,
                         **_feasible_kwargs(regime_key, R, alpha_val))
    return res.schedule, model


def bootstrap_gap_ci(pd_better: np.ndarray, pd_base: np.ndarray,
                     n=N_BOOTSTRAP, seed=BOOTSTRAP_SEED):
    """CI for gap = CVaR(base) - CVaR(better); positive = 'better' arm wins."""
    rng = np.random.default_rng(seed)
    N = len(pd_base)
    point = cvar_upper_tail(pd_base) - cvar_upper_tail(pd_better)
    gaps = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, N, N)
        gaps[i] = cvar_upper_tail(pd_base[idx]) - cvar_upper_tail(pd_better[idx])
    lo, hi = np.percentile(gaps, [2.5, 97.5])
    return point, float(lo), float(hi)


@dataclass
class CopulaCell:
    regime: str
    alpha: float
    cvar_indep: float
    cvar_gauss: float
    cvar_clayton: float
    cvar_comonotone: float
    clayton_theta: float
    kendall_tau: float
    gap_gauss_pct: float
    gap_gauss_ci_lo: float
    gap_gauss_ci_hi: float
    gap_clayton_pct: float
    gap_clayton_ci_lo: float
    gap_clayton_ci_hi: float
    gap_comonotone_pct: float
    gap_comonotone_ci_lo: float
    gap_comonotone_ci_hi: float
    gap_clayton_vs_gauss_pct: float
    detectable_gauss: bool
    detectable_clayton: bool
    detectable_comonotone: bool


def main() -> int:
    global _VARCAP_CEILING
    ap = argparse.ArgumentParser()
    ap.add_argument("--region-set", required=True, choices=ALLOWED_SETS)
    ap.add_argument("--regime", default="all",
                    choices=list(REGIME_ORDER) + ["all"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()
    regimes = REGIME_ORDER if args.regime == "all" else (args.regime,)

    cfg = REGION_SETS[args.region_set]
    zones = list(cfg["zones"])
    tz = cfg["tz"]
    print(f"PHASE 2 COPULA [{args.region_set}]:", tuple(zones), "| clock", tz)
    print(f"  S={N_SCENARIOS} scenarios, seed={SCENARIO_SEED}, CVaR beta={CVAR_BETA}")

    carbon_wide = to_wide(load_all_zones(zones))
    panel, dates = build_daily_panel(carbon_wide, region_order=zones, tz=tz)
    cfe_panel, cfe_dates = build_cfe_panel(zones, tz=tz)
    assert dates.equals(cfe_dates), "CFE/carbon dates misaligned"
    train_years = tuple(range(2021, TEST_YEAR))
    is_train = np.array([d.year in train_years for d in dates])
    is_test = np.array([d.year == TEST_YEAR for d in dates])
    train_panel, test_panel = panel[is_train], panel[is_test]
    R, T = panel.shape[1], panel.shape[2]
    assert T == T_HOURS
    print(f"  train N={len(train_panel)}, test N={len(test_panel)}")

    field = cfe_field(cfe_panel, cfe_dates, train_years)
    field = np.nan_to_num(field, nan=float(np.nanmean(field)))
    _VARCAP_CEILING = capacity_from_cfe(field, CAP_MIN, CAP_MAX)
    workloads = np.full(R, UTILIZATION_FIXED * CEILING_PER_CELL_MW * T)

    rows: list[CopulaCell] = []
    for regime_key in regimes:
        for alpha_val in ALPHA_LEVELS:
            sched, models = {}, {}
            for kind in KINDS:
                sched[kind], models[kind] = schedule_for_copula(
                    kind, train_panel, regime_key, alpha_val, workloads)
            if args.dry_run:
                print(f"  [dry-run] {regime_key} a={alpha_val}: "
                      f"clayton theta={models['clayton'].clayton_theta:.3f} "
                      f"tau={models['clayton'].kendall_tau:.3f} (test NOT read)")
                continue

            em = {k: per_day_emissions(sched[k], test_panel) for k in KINDS}
            cv = {k: cvar_upper_tail(em[k]) for k in KINDS}
            g_gauss, gglo, gghi = bootstrap_gap_ci(em["gaussian"], em["independence"])
            g_clay, gclo, gchi = bootstrap_gap_ci(em["clayton"], em["independence"])
            g_como, gmlo, gmhi = bootstrap_gap_ci(em["comonotone"], em["independence"])
            g_cvg = cv["gaussian"] - cv["clayton"]
            base = cv["independence"]
            rows.append(CopulaCell(
                regime=regime_key, alpha=alpha_val,
                cvar_indep=cv["independence"], cvar_gauss=cv["gaussian"],
                cvar_clayton=cv["clayton"], cvar_comonotone=cv["comonotone"],
                clayton_theta=models["clayton"].clayton_theta,
                kendall_tau=models["clayton"].kendall_tau,
                gap_gauss_pct=100 * g_gauss / base,
                gap_gauss_ci_lo=100 * gglo / base, gap_gauss_ci_hi=100 * gghi / base,
                gap_clayton_pct=100 * g_clay / base,
                gap_clayton_ci_lo=100 * gclo / base, gap_clayton_ci_hi=100 * gchi / base,
                gap_comonotone_pct=100 * g_como / base,
                gap_comonotone_ci_lo=100 * gmlo / base, gap_comonotone_ci_hi=100 * gmhi / base,
                gap_clayton_vs_gauss_pct=100 * g_cvg / base,
                detectable_gauss=(gglo > 0 or gghi < 0),
                detectable_clayton=(gclo > 0 or gchi < 0),
                detectable_comonotone=(gmlo > 0 or gmhi < 0),
            ))
            print(f"  {regime_key} a={alpha_val}: tau={models['clayton'].kendall_tau:.2f} "
                  f"theta={models['clayton'].clayton_theta:.2f} | "
                  f"gap_gauss={100*g_gauss/base:+.3f}% gap_clayton={100*g_clay/base:+.3f}% "
                  f"gap_comono={100*g_como/base:+.3f}% clay-v-gauss={100*g_cvg/base:+.3f}%")

    if args.dry_run or not rows:
        print("Done (dry-run / no rows written).")
        return 0

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([asdict(r) for r in rows])
    path = out / f"{args.region_set}_copula_{stamp}.csv"
    df.to_csv(path, index=False)
    print(f"\nWrote {path}")
    print(df[["regime", "alpha", "gap_gauss_pct", "gap_clayton_pct",
              "gap_comonotone_pct", "detectable_comonotone"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
