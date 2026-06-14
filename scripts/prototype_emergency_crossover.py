"""PART 3 — the crossover: WHEN does robust transfer start to beat deterministic?

Every 'normal' experiment said robustness is worthless: carbon is predictable, so
exploiting the mean wins. DRO is designed for the opposite case -- rare, surprising
tail events a historical mean cannot foresee. Real grids have these: renewable
droughts, heat-wave peaker dispatch, transmission faults spike a region's carbon
2-3x for a day. A 4-year sample under-represents them.

We model them explicitly as a stress parameter and find the crossover. With
probability p per day, one random region's carbon is multiplied by a severity M.
This stress hits BOTH the day-ahead scenarios (so the commitment can hedge) and the
evaluation world. Two-stage structure with costly/limited recourse (migration
cost lambda, budget Phi), so a bad commitment cannot be fully undone:

  risk-neutral commitment  vs  CVaR-hedged commitment, both with recourse.

Sweeping the severity M traces the crossover: at M=1 (no emergencies) robustness is
worthless (our main result); as M grows the hedged commitment starts to win.

Run: .venv\\Scripts\\python -m scripts.prototype_emergency_crossover [grid]
"""
from __future__ import annotations

import sys

import numpy as np

from scripts.prototype_twostage_transfer import commit, recourse_cost
from src.analysis.metrics import cvar_upper_tail
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel

CEIL, UTIL = 50.0, 0.80
GRID = sys.argv[1] if len(sys.argv) > 1 else "us_west"
S = 60
LAM = 30.0          # costly migration -> the commitment matters
P_EMG = 0.10        # 10% of days have an emergency somewhere
SEED = 20260614


def inject(panel, M, rng):
    """Return a stressed copy: each day, w.p. P_EMG multiply one random region by M."""
    out = panel.copy()
    for i in range(len(out)):
        if rng.random() < P_EMG:
            r = rng.integers(out.shape[1])
            out[i, r, :] *= M
    return out


def main():
    cfg = REGION_SETS[GRID]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                     region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr = panel[yrs < 2025]; te = panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    Phi = 0.4 * wl.sum()                          # limited recourse

    print(f"=== PART 3 crossover: {DISPLAY_NAME[GRID]} | migration cost lambda={LAM}, "
          f"emergency prob={P_EMG:.0%} ===")
    print(f"  {'severity M':>10} {'risk-neutral':>13} {'robust(CVaR)':>13} {'robust gain':>12}")
    for M in [1.0, 1.5, 2.0, 3.0, 4.0]:
        rng = np.random.default_rng(SEED)
        # day-ahead scenarios from stressed training days
        scen_src = inject(tr, M, rng)
        pick = rng.choice(len(scen_src), S, replace=False)
        scen = scen_src[pick]
        # stressed evaluation world (independent draws)
        te_eval = inject(te, M, np.random.default_rng(SEED + 1))[::2]
        x_mean = commit(scen, wl, ceil, LAM, Phi, "mean")
        x_cvar = commit(scen, wl, ceil, LAM, Phi, "cvar")
        cm = cvar_upper_tail(np.array([recourse_cost(x_mean, d, ceil, LAM, Phi) for d in te_eval]))
        cc = cvar_upper_tail(np.array([recourse_cost(x_cvar, d, ceil, LAM, Phi) for d in te_eval]))
        flag = "  <-- robust wins" if cc < cm else ""
        print(f"  {M:>10.1f} {cm:>13.0f} {cc:>13.0f} {100*(cm-cc)/cm:>11.2f}%{flag}")
    print("  (M=1: no emergencies -> our main result; larger M -> robustness should pay)")


if __name__ == "__main__":
    main()
