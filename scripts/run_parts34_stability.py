"""run_parts34_stability.py -- prove Parts 3 & 4 are not seed/scenario artifacts.

The earlier comonotone "+0.18%" turned out to be scenario-seed noise, so single-seed
positive results are treated as unproven until shown stable. This script re-runs the
Part 3 crossover and the Part 4 online comparison across several independent seeds and
(for Part 4's surprising -10% loss on the Diversified grid) across scenario counts,
reporting mean +/- std and sign-stability. Stable sign across seeds = real effect.

Outputs docs/results_snapshots/parts34_stability_<date>.csv
Run: .venv\\Scripts\\python -m scripts.run_parts34_stability
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.online_transfer import rolling_eval
from src.models.transfer_dro import recourse_cost, two_stage_commit

CEIL, UTIL = 50.0, 0.80
SEEDS = [11, 23, 37, 51]              # 4 independent seeds
M_VALS = [1.0, 2.0, 4.0]             # null point, mid, strong crossover
S_COMMIT = 35                        # scenarios per commit
GRIDS = ["us_west", "taskc", "us_hetero"]
OUT = Path("docs/results_snapshots")


def load(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    R, T = panel.shape[1], panel.shape[2]
    return panel[yrs < 2025], panel[yrs == 2025], R, T


def inject(panel, M, rng, p=0.10):
    out = panel.copy()
    for i in range(len(out)):
        if rng.random() < p:
            out[i, rng.integers(out.shape[1]), :] *= M
    return out


def part3_stability():
    rows = []
    for grid in GRIDS:
        tr, te, R, T = load(grid)
        wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL); Phi = 0.4 * wl.sum()
        for M in M_VALS:
            gains = []
            for sd in SEEDS:
                rng = np.random.default_rng(sd)
                scen = inject(tr, M, rng)[rng.choice(len(tr), S_COMMIT, replace=False)]
                ev = inject(te, M, np.random.default_rng(sd + 1))[::4]
                xm = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=30.0, risk="mean")
                xc = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=30.0, risk="cvar")
                cm = cvar_upper_tail(np.array([recourse_cost(xm, d, ceil, transfer_budget=Phi, lam=30.0) for d in ev]))
                cc = cvar_upper_tail(np.array([recourse_cost(xc, d, ceil, transfer_budget=Phi, lam=30.0) for d in ev]))
                gains.append(100 * (cm - cc) / cm)
            g = np.array(gains)
            rows.append({"part": 3, "grid": grid, "setting": f"M={M}", "mean": g.mean(),
                         "std": g.std(ddof=1), "min": g.min(), "max": g.max(),
                         "frac_positive": float((g > 0).mean()), "n_seeds": len(g)})
            print(f"  [P3] {DISPLAY_NAME.get(grid,grid):16s} M={M}: "
                  f"{g.mean():+6.2f} +/- {g.std(ddof=1):4.2f}%  "
                  f"[{g.min():+.2f},{g.max():+.2f}]  {int((g>0).mean()*100)}% seeds positive")
    return rows


def part4_stability():
    rows = []
    for grid in GRIDS:
        tr, te, R, T = load(grid)
        wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL); Phi = 0.4 * wl.sum()
        Ss = [20, 40, 80] if grid == "us_hetero" else [35]    # sensitivity on the -10% grid
        for S in Ss:
            gaps = []
            for sd in SEEDS:
                kw = dict(ceiling=ceil, workloads=wl, transfer_budget=Phi, n_scenarios=S,
                          stride=7, seed=sd)
                det = rolling_eval(tr, te, robust=False, **kw)
                rob = rolling_eval(tr, te, robust=True, **kw)
                gaps.append(100 * (cvar_upper_tail(det) - cvar_upper_tail(rob)) / cvar_upper_tail(det))
            g = np.array(gaps)
            tag = f"S={S}" if grid == "us_hetero" else "online"
            rows.append({"part": 4, "grid": grid, "setting": tag, "mean": g.mean(),
                         "std": g.std(ddof=1), "min": g.min(), "max": g.max(),
                         "frac_positive": float((g > 0).mean()), "n_seeds": len(g)})
            print(f"  [P4] {DISPLAY_NAME.get(grid,grid):16s} {tag}: gap "
                  f"{g.mean():+6.2f} +/- {g.std(ddof=1):4.2f}%  "
                  f"[{g.min():+.2f},{g.max():+.2f}]  sign-stable={'yes' if (g>0).all() or (g<0).all() else 'NO'}")
    return rows


def main():
    print("=== Part 3 crossover: stability across", len(SEEDS), "seeds ===")
    r3 = part3_stability()
    print("\n=== Part 4 online: stability across seeds (+ S sensitivity on Diversified) ===")
    r4 = part4_stability()
    stamp = dt.datetime(2026, 6, 15).strftime("%Y-%m-%d")
    pd.DataFrame(r3 + r4).to_csv(OUT / f"parts34_stability_{stamp}.csv", index=False)
    print(f"\nWrote {OUT / f'parts34_stability_{stamp}.csv'}")


if __name__ == "__main__":
    main()
