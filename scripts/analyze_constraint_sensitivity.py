"""analyze_constraint_sensitivity.py -- which constraints and modelling knobs
actually move the results? Ranked, from the committed snapshots alone.

Runs WITHOUT the licensed raw data: it reads only the archived, license-safe
snapshot CSVs in docs/results_snapshots/, so anyone can regenerate this table.

Two distinct notions of "impact" are measured for every swept knob:

  A. CONCLUSION impact  -- how much does the knob move the spatial-null gap
     (gap_pct, the RQ2 headline: joint vs shuffled covariance)?  Measured as the
     max and mean absolute change in gap_pct across matched regime x alpha cells
     between the variant snapshot and its base snapshot.

  B. MAGNITUDE impact   -- how much does the knob move the absolute problem,
     i.e. the joint schedule's CVaR level itself?  Measured as the mean percent
     change in joint_CVaR across matched cells.

The distinction matters: a knob can rescale the whole problem (huge B) while
leaving the scientific conclusion untouched (tiny A). The thesis's claims live
on axis A; deployment planning cares about axis B.

Also summarized: the DRO tail-level sensitivity file (CVaR_0.90/0.95/0.99) and
the kappa capacity sweep (part5), which quantify the same question for RQ3.

Run:  python -m scripts.analyze_constraint_sensitivity
Writes: docs/results_snapshots/constraint_sensitivity_<date>.csv (+ prints table)
Added post-defense (July 2026).
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import numpy as np
import pandas as pd

SNAP = Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"

# variant-suffix -> (knob family, human label)
KNOBS = {
    "seasonal": ("estimator", "covariance estimator: seasonal residualization"),
    "ar1": ("estimator", "covariance estimator: AR(1) residualization"),
    "lw": ("estimator", "covariance estimator: Ledoit-Wolf shrinkage"),
    "ramp5": ("feasibility", "ramp limit tightened (5%/step)"),
    "util0.5": ("feasibility", "utilization 0.50 (slack capacity)"),
    "util0.95": ("feasibility", "utilization 0.95 (tight capacity)"),
    "cvar0.9": ("metric", "risk tail CVaR_0.90"),
    "cvar0.99": ("metric", "risk tail CVaR_0.99"),
    "ty2022": ("test-year", "walk-forward test year 2022"),
    "ty2023": ("test-year", "walk-forward test year 2023"),
    "ty2024": ("test-year", "walk-forward test year 2024"),
}
KEY = ["regime", "alpha"]
BASE_RE = re.compile(r"^(?P<fam>[a-zA-Z_]+_regimes)_(?P<date>\d{4}-\d{2}-\d{2})$")


def _families() -> dict[str, dict]:
    """Map family (e.g. 'taskc_regimes') -> {'base': path, 'variants': {suffix: path}}."""
    fams: dict[str, dict] = {}
    for p in SNAP.glob("*_regimes_*.csv"):
        stem = p.stem
        for suffix in sorted(KNOBS, key=len, reverse=True):
            if stem.endswith("_" + suffix):
                core = stem[: -(len(suffix) + 1)]
                m = BASE_RE.match(core)
                if m:
                    fams.setdefault(m["fam"], {"base": None, "variants": {}})
                    fams[m["fam"]]["variants"][suffix] = p
                break
        else:
            m = BASE_RE.match(stem)
            if m and "ablate" not in stem:
                fams.setdefault(m["fam"], {"base": None, "variants": {}})
                # prefer the earliest-dated file as base if several exist
                cur = fams[m["fam"]]["base"]
                if cur is None or p.name < cur.name:
                    fams[m["fam"]]["base"] = p
    return {k: v for k, v in fams.items() if v["base"] is not None and v["variants"]}


def _impact(base: pd.DataFrame, var: pd.DataFrame) -> dict | None:
    need = set(KEY + ["gap_pct", "joint_CVaR"])
    if not need <= set(base.columns) or not need <= set(var.columns):
        return None
    m = base.merge(var, on=KEY, suffixes=("_b", "_v"))
    if m.empty:
        return None
    d_gap = (m["gap_pct_v"] - m["gap_pct_b"]).abs()
    d_mag = 100.0 * (m["joint_CVaR_v"] - m["joint_CVaR_b"]).abs() / m["joint_CVaR_b"]
    return dict(cells=len(m),
                gap_shift_max_pp=float(d_gap.max()),
                gap_shift_mean_pp=float(d_gap.mean()),
                cvar_magnitude_shift_mean_pct=float(d_mag.mean()))


def main() -> None:
    rows = []
    for fam, d in sorted(_families().items()):
        base = pd.read_csv(d["base"])
        for suffix, path in sorted(d["variants"].items()):
            r = _impact(base, pd.read_csv(path))
            if r is None:
                continue
            knob_family, label = KNOBS[suffix]
            rows.append(dict(grid_family=fam, knob=suffix, knob_family=knob_family,
                             label=label, base_file=d["base"].name,
                             variant_file=path.name, **r))
    df = pd.DataFrame(rows)

    print("CONSTRAINT / KNOB SENSITIVITY, from committed snapshots")
    print("A = conclusion impact: |shift| of the spatial-null gap (percentage points of CVaR)")
    print("B = magnitude impact: mean |shift| of the joint schedule's CVaR level (%)\n")
    agg = (df.groupby(["knob_family", "knob", "label"])
             .agg(max_gap_shift_pp=("gap_shift_max_pp", "max"),
                  mean_gap_shift_pp=("gap_shift_mean_pp", "mean"),
                  mean_cvar_shift_pct=("cvar_magnitude_shift_mean_pct", "mean"),
                  n_grid_families=("grid_family", "nunique"))
             .reset_index()
             .sort_values("max_gap_shift_pp", ascending=False))
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(agg.to_string(index=False,
                            float_format=lambda x: f"{x:8.4f}"))

    # RQ3 supplements
    tail = SNAP / "dro_tail_sensitivity_2026-06-25.csv"
    if tail.exists():
        t = pd.read_csv(tail)
        print("\nRQ3 supplement -- DRO gap by risk-tail level (dro_tail_sensitivity):")
        piv = t.pivot_table(index="grid", columns="metric", values="gap_pct")
        print(piv.to_string(float_format=lambda x: f"{x:7.3f}"))
    sweep = SNAP / "part5_sweep_2026-06-15.csv"
    if sweep.exists():
        s = pd.read_csv(sweep)
        print("\nRQ3 supplement -- capacity tightness kappa vs bound Delta (part5_sweep):")
        for g, sub in s.groupby("grid"):
            sub = sub.sort_values("kappa")
            ratio = (sub["Delta"] * sub["kappa"]).round(6).nunique() == 1
            print(f"  {g:10s} Delta spans {sub['Delta'].min():.2f} -> "
                  f"{sub['Delta'].max():.2f} as kappa {sub['kappa'].max():.2f} -> "
                  f"{sub['kappa'].min():.2f}  (Delta ~ 1/kappa: {ratio})")

    stamp = dt.date.today().strftime("%Y-%m-%d")
    out = SNAP / f"constraint_sensitivity_{stamp}.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
