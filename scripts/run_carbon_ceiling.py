"""run_carbon_ceiling.py -- realized carbon-severity, reconciled with the M* axis.

The synthetic crossover experiment (run_part3_emergency.py) multiplies ONE region's
daily carbon by a severity M and finds robustness pays only past M* ~ 3. To compare M*
against reality we must measure realized severity on a matching axis, and there are TWO
distinct, easily-confused quantities:

  1. Per-region severity: for each zone, the largest single-day multiple of its daily
     carbon over its nominal (mean) level (max daily / mean). This is a *relative* swing;
     on very clean, low-carbon grids it can be large (e.g. BPAT ~ 5x) because the base is
     near zero, but a 5x swing on a tiny base is a small *absolute* emission.

  2. Joint (portfolio) severity: the worst realized day's portfolio-mean carbon over the
     portfolio mean (max daily / mean of the equal-weighted regional average). This is
     the *absolute-emissions* axis the M* crossover actually lives on: it is what a
     migration scheduler's tail emissions respond to, and it is dampened by
     diversification. This is the "M ~ 1.4" the thesis reports.

The rigorous RQ3 result is data-grounded separately in run_part3_real_emergency.py
(robust commitment evaluated on real top-5% emergency days; it does not pay). This
script archives the severity context for that result. Output is license-safe:
dimensionless ratios only, no raw carbon.

Outputs docs/results_snapshots/carbon_ceiling_<date>.csv
Run: .venv\\Scripts\\python -m scripts.run_carbon_ceiling
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel

NA = ["CA-AB", "CA-ON", "US-SW-SRP", "US-SW-AZPS", "US-SW-PNM",
      "US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-CAL-IID", "US-CAL-TIDC",
      "US-TEX-ERCO", "US-MIDW-MISO", "US-MIDW-AECI", "US-MIDA-PJM", "US-NY-NYIS",
      "US-NW-NEVP", "US-NW-BPAT"]
GRIDS = ["us_west", "taskc", "us_hetero"]
OUT = Path("docs/results_snapshots")


def main():
    rows = []

    # (1) per-region single-region severity (relative swing) over 17 NA zones
    daily = to_wide(load_all_zones(NA))[NA].resample("D").mean()
    for z in NA:
        s = daily[z].dropna()
        rows.append({"kind": "region", "key": z, "severity": float(s.max() / s.mean())})
    e = daily["US-TEX-ERCO"]
    uri = float(daily["US-TEX-ERCO"]["2021-02-12":"2021-02-21"].max()
                / e[e.index.year == 2021].mean())
    rows.append({"kind": "event", "key": "US-TEX-ERCO__Uri2021", "severity": uri})

    # (2) joint (portfolio) severity per scheduling grid: worst day / mean of the
    #     equal-weighted regional-average daily carbon (the absolute-emissions axis)
    joints = {}
    for grid in GRIDS:
        cfg = REGION_SETS[grid]; z = list(cfg["zones"])
        panel, _ = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
        port = panel.mean(axis=(1, 2))                       # portfolio-mean carbon per day
        sev = float(port.max() / port.mean())
        joints[grid] = sev
        rows.append({"kind": "joint", "key": grid, "severity": sev})

    df = pd.DataFrame(rows)
    stamp = dt.datetime(2026, 6, 24).strftime("%Y-%m-%d")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"carbon_ceiling_{stamp}.csv"
    df.to_csv(path, index=False)

    reg = df[df.kind == "region"]
    print("Per-region severity (max daily / mean), 17 NA zones:")
    for _, r in reg.sort_values("severity").iterrows():
        print(f"  {r['key']:24s} {r['severity']:.3f}x")
    print(f"\n  per-region range: {reg.severity.min():.2f}x .. {reg.severity.max():.2f}x"
          f"  (clean low-base grids swing widest; Uri {uri:.2f}x)")
    print("\nJoint (portfolio) severity per grid  [the M~1.4 axis, vs crossover M*~3]:")
    for grid in GRIDS:
        print(f"  {DISPLAY_NAME.get(grid, grid):18s} {joints[grid]:.3f}x")
    print(f"\n  worst joint severity = {max(joints.values()):.2f}x  <  M* ~ 3")
    print(f"  Wrote {path}")


if __name__ == "__main__":
    main()
