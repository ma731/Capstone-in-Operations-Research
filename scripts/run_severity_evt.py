"""run_severity_evt.py -- roadmap D3: EVT-calibrated emergency severity.

Fits a generalized Pareto upper tail (peaks-over-threshold, runs-declustered)
to the realized daily severity ratios and converts the M* crossover axis into
return periods: how many years between days with joint severity >= M? The
crossover experiment says robustness starts to pay near M ~ 3; this script
prices how rare such a day is under the fitted tail, with a threshold sweep
(q = 85/90/95) and a block-bootstrap CI, plus the top severity dates so the
tail is anchored on named events (e.g. the 2022 French nuclear outage).

Runs on the two locally-cached panels: the California-Nevada case (taskA
zones) and ES-PT-FR. The us_west / taskc / us_hetero grids require their raw
CSVs re-fetched before a paper-grade run (see docs/roadmap_papers.md).

Output is licence-safe: dimensionless ratios, fitted parameters, and dates
only, no raw carbon values.

Outputs docs/results_snapshots/severity_evt_<date>.csv and prints a summary.
Run: .venv\\Scripts\\python -m scripts.run_severity_evt
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.severity_evt import (
    bootstrap_return_period,
    daily_joint_severity,
    daily_zone_severity,
    fit_gpd_tail,
    return_period_years,
)
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import (
    DEFAULT_TZ,
    DEFAULT_TZ_ES_PT_FR,
    REGION_ORDER,
    REGION_ORDER_ES_PT_FR,
    build_daily_panel,
)

GRIDS = {
    "taskA": {"zones": list(REGION_ORDER), "tz": DEFAULT_TZ,
              "display": "California-Nevada"},
    "es_pt_fr": {"zones": list(REGION_ORDER_ES_PT_FR), "tz": DEFAULT_TZ_ES_PT_FR,
                 "display": "Iberia+France"},
}
Q_SWEEP = [85.0, 90.0, 95.0]
M_GRID = [1.5, 2.0, 2.5, 3.0]
BOOT_M = [2.0, 3.0]
Q_BOOT = 90.0
N_BOOT = 500
SEED = 20260719
OUT = Path("docs/results_snapshots")


def severity_rows(name: str, display: str, label: str,
                  sev: np.ndarray, dates: pd.DatetimeIndex) -> list[dict]:
    """All snapshot rows for one severity series: fits, return periods, top days."""
    rows: list[dict] = []
    for q in Q_SWEEP:
        fit = fit_gpd_tail(sev, threshold_q=q)
        base = dict(grid=name, display=display, series=label, threshold_q=q,
                    threshold=round(fit.threshold, 4), xi=round(fit.shape, 4),
                    sigma=round(fit.scale, 4), n_exceed=fit.n_exceed,
                    n_days=fit.n_total,
                    upper_endpoint=(round(fit.upper_endpoint, 4)
                                    if np.isfinite(fit.upper_endpoint) else np.inf))
        for M in M_GRID:
            if M < fit.threshold:
                continue
            rp = return_period_years(M, fit)
            rows.append(base | dict(kind="return_period", M=M,
                                    value=(round(rp, 2) if np.isfinite(rp) else np.inf),
                                    lo=np.nan, hi=np.nan))
    rng = np.random.default_rng(SEED)
    for M in BOOT_M:
        point, lo, hi = bootstrap_return_period(
            sev, M, rng, threshold_q=Q_BOOT, n_boot=N_BOOT)
        rows.append(dict(grid=name, display=display, series=label,
                         threshold_q=Q_BOOT, kind="return_period_boot", M=M,
                         value=(round(point, 2) if np.isfinite(point) else np.inf),
                         lo=(round(lo, 2) if np.isfinite(lo) else np.inf),
                         hi=(round(hi, 2) if np.isfinite(hi) else np.inf)))
    top = np.argsort(sev)[::-1][:5]
    for rank, i in enumerate(top, start=1):
        rows.append(dict(grid=name, display=display, series=label,
                         kind="top_day", M=round(float(sev[i]), 4),
                         value=rank, date=str(dates[i].date())))
    return rows


def main() -> None:
    all_rows: list[dict] = []
    for name, cfg in GRIDS.items():
        wide = to_wide(load_all_zones(cfg["zones"]))
        panel, dates = build_daily_panel(
            wide, region_order=cfg["zones"], tz=cfg["tz"])
        joint = daily_joint_severity(panel)
        print(f"\n=== {cfg['display']} ({name}): {panel.shape[0]} days, "
              f"R={panel.shape[1]} ===")
        print(f"joint severity: max={joint.max():.3f} "
              f"p99={np.percentile(joint, 99):.3f}")
        all_rows += severity_rows(name, cfg["display"], "joint", joint, dates)
        for r, zone in enumerate(cfg["zones"]):
            zsev = daily_zone_severity(panel, r)
            all_rows += severity_rows(name, cfg["display"], f"zone:{zone}",
                                      zsev, dates)

    df = pd.DataFrame(all_rows)
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"severity_evt_{dt.date.today().isoformat()}.csv"
    df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path} ({len(df)} rows)")

    # Console summary: joint return periods at q=90 + bootstrap, top days.
    for name, cfg in GRIDS.items():
        sub = df[(df.grid == name) & (df.series == "joint")]
        print(f"\n--- {cfg['display']}: joint tail (q=90) ---")
        fitrow = sub[(sub.threshold_q == 90.0) & (sub.kind == "return_period")]
        if not fitrow.empty:
            f0 = fitrow.iloc[0]
            print(f"  u={f0.threshold}  xi={f0.xi}  sigma={f0.sigma}  "
                  f"endpoint={f0.upper_endpoint}")
            for _, row in fitrow.iterrows():
                print(f"  M>={row.M}: return period {row.value} years")
        for _, row in sub[sub.kind == "return_period_boot"].iterrows():
            print(f"  M>={row.M} (boot, q={Q_BOOT}): {row.value}y "
                  f"[{row.lo}, {row.hi}]")
        tops = sub[sub.kind == "top_day"].sort_values("value")
        days = ", ".join(f"{r.date} (M={r.M})" for _, r in tops.iterrows())
        print(f"  top days: {days}")


if __name__ == "__main__":
    main()
