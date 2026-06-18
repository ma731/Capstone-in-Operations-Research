"""run_crossover_sensitivity.py -- how the robustness threshold M* moves (#3).

The crossover (robust beats deterministic) sits at emergency severity M*. This sweep
asks how M* responds to the two decision-relevant knobs: the transfer budget Phi (how
much load may migrate) and the migration cost lam. It characterizes the DRO's domain
of value -- "under what operating conditions would robustness pay sooner?" -- on the
Western US grid. M* is the smallest severity at which the robust CVaR gain turns
materially positive (> 0.5%).

Run: .venv\\Scripts\\python -m scripts.run_crossover_sensitivity
"""
from __future__ import annotations

import numpy as np

from scripts.run_part3_emergency import inject          # P_EMG = 0.10 per day
from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.transfer_dro import two_stage_commit, recourse_cost

CEIL, UTIL, S, SEED = 50.0, 0.80, 40, 20260614
M_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
GRID = "us_west"


def setup():
    cfg = REGION_SETS[GRID]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    return tr, te, np.full(R, UTIL * CEIL * T), np.full((R, T), CEIL)


def mstar(tr, te, wl, ceil, Phi, lam):
    gains = []
    for M in M_GRID:
        rng = np.random.default_rng(SEED)
        scen = inject(tr, M, rng)[rng.choice(len(tr), S, replace=False)]
        ev = inject(te, M, np.random.default_rng(SEED + 1))[::2]
        xm = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=lam, risk="mean")
        xc = two_stage_commit(scen, wl, ceil, transfer_budget=Phi, lam=lam, risk="cvar")
        cm = cvar_upper_tail(np.array([recourse_cost(xm, d, ceil, transfer_budget=Phi, lam=lam) for d in ev]))
        cc = cvar_upper_tail(np.array([recourse_cost(xc, d, ceil, transfer_budget=Phi, lam=lam) for d in ev]))
        gains.append(100.0 * (cm - cc) / cm)
    ms = next((M for M, g in zip(M_GRID, gains) if g > 0.5), None)
    return ms, gains


def main():
    tr, te, wl, ceil = setup()
    W = float(wl.sum())
    print("M* sensitivity on Western US (M* = smallest severity with robust gain > 0.5%)\n")
    print("transfer-budget sweep (lam=30):")
    for frac in (0.2, 0.4, 0.8):
        ms, g = mstar(tr, te, wl, ceil, frac * W, 30.0)
        print(f"  Phi={frac*100:.0f}% of workload  M*={ms}  gains%={[round(x,2) for x in g]}")
    print("\nmigration-cost sweep (Phi=0.4):")
    for lam in (10.0, 30.0, 60.0):
        ms, g = mstar(tr, te, wl, ceil, 0.4 * W, lam)
        print(f"  lam={lam:.0f}  M*={ms}  gains%={[round(x,2) for x in g]}")
    print("\nReading: M* stays high (~3) across budgets and costs -> robustness's"
          "\nactivation threshold is not sensitive to operating knobs; it is set by the"
          "\nmean-dominance structure, and real severities (<1.5x) never reach it.")


if __name__ == "__main__":
    main()
